"""Collection / Penagihan Tunggakan (P1.1 Operational Completion).

Manusia tetap memutuskan siapa/kapan/ditagih bagaimana. Sistem hanya mencatat
aktivitas, mengirim via dispatcher WhatsApp E1 yang sudah ada, dan memberi
reminder follow-up. Tidak menyentuh formula payment/arrears/ledger/balance.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from core import (db, require_roles, new_id, now_iso, today_str, clean, log_audit,
                  payment_summary_map, fee_total)
from routers.whatsapp import (queue_message, attempt_send, wa_config, get_template,
                              render_template, mask_phone, TEMPLATE_VARS)

router = APIRouter()

COL_READ = require_roles("owner", "admin", "finance")
COL_WRITE = require_roles("owner", "finance")
NOTIF_COLLECTION = ["owner", "finance"]

CHANNELS = ["whatsapp", "phone", "in_person", "other"]
OUTCOMES = ["contacted", "promised_payment", "paid_after_contact", "no_response",
            "wrong_number", "requested_extension", "refused", "other"]
CLOSED_OUTCOMES = ["paid_after_contact"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ActivityIn(BaseModel):
    student_id: str
    channel: str
    outcome: str
    note: str
    next_follow_up_at: Optional[str] = None
    next_follow_up_note: Optional[str] = ""
    idem_key: Optional[str] = None


class SendWaIn(BaseModel):
    student_id: str
    recipient: str = "siswa"
    template_key: str = "payment_due"
    outcome: str = "contacted"
    note: str = ""
    next_follow_up_at: Optional[str] = None
    next_follow_up_note: Optional[str] = ""
    idem_key: str


class ActivityUpdateIn(BaseModel):
    outcome: Optional[str] = None
    note: Optional[str] = None
    next_follow_up_at: Optional[str] = None
    next_follow_up_note: Optional[str] = None
    alasan: str = ""


async def _student_or_404(sid: str) -> dict:
    s = await db.students.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    return s


def _check_enums(channel: str, outcome: str):
    if channel not in CHANNELS:
        raise HTTPException(status_code=400, detail=f"Channel tidak valid: {channel}")
    if outcome not in OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Outcome tidak valid: {outcome}")


def _check_fu_date(v: Optional[str]):
    if v is not None and not DATE_RE.match(v):
        raise HTTPException(status_code=400, detail="next_follow_up_at harus format YYYY-MM-DD")


async def _sisa_snapshot(s: dict) -> dict:
    pay = await payment_summary_map([s["id"]])
    total = fee_total(s)
    bayar = pay.get(s["id"], {}).get("bayar", 0)
    return {"total": total, "bayar": bayar, "sisa": max(total - bayar, 0)}


async def _arrears_rows():
    students = await db.students.find({"status": {"$nin": ["calon_siswa", "gagal", "alumni"]}}, {"_id": 0}).to_list(5000)
    pay = await payment_summary_map()
    t = today_str()
    out = []
    for s in students:
        total = fee_total(s)
        bayar = pay.get(s["id"], {}).get("bayar", 0)
        sisa = total - bayar
        if sisa <= 0:
            continue
        jt = s.get("jatuh_tempo")
        kondisi = "belum_jatuh_tempo"
        if jt:
            kondisi = "terlambat" if jt < t else ("hari_ini" if jt == t else "akan_jatuh_tempo")
        out.append({"id": s["id"], "nama_lengkap": s["nama_lengkap"], "sisa": sisa,
                    "jatuh_tempo": jt, "kondisi": kondisi})
    return out


@router.get("/collections/overview")
async def collections_overview(user: dict = Depends(COL_READ)):
    arrears = await _arrears_rows()
    acts = await db.collection_activities.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    contacted = {a["student_id"] for a in acts}
    latest = {}
    for a in acts:
        latest.setdefault(a["student_id"], a)
    t = today_str()
    due, overdue, never = [], [], []
    for r in arrears:
        a = latest.get(r["id"])
        if not a:
            never.append(r)
        elif a.get("next_follow_up_at") and a.get("outcome") not in CLOSED_OUTCOMES:
            fu = a["next_follow_up_at"]
            item = {**r, "next_follow_up_at": fu, "next_follow_up_note": a.get("next_follow_up_note", ""),
                     "last_outcome": a.get("outcome"), "last_at": a.get("created_at")}
            if fu < t:
                overdue.append(item)
            elif fu == t:
                due.append(item)
    return {"arrears_count": len(arrears), "arrears_total": sum(r["sisa"] for r in arrears),
            "contacted_count": len(contacted & {r["id"] for r in arrears}),
            "recent": [{k: a.get(k) for k in ("id", "student_id", "student_nama", "channel", "outcome",
                                              "created_at", "actor_name", "wa_status")} for a in acts[:20]],
            "due_today": due, "overdue": overdue, "never_contacted": never}


@router.get("/collections/summary-map")
async def collections_summary_map(user: dict = Depends(COL_READ)):
    acts = await db.collection_activities.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    out = {}
    for a in acts:
        out.setdefault(a["student_id"], {"last_at": a["created_at"], "last_outcome": a["outcome"],
                                         "last_channel": a["channel"],
                                         "next_follow_up_at": a.get("next_follow_up_at"),
                                         "next_follow_up_note": a.get("next_follow_up_note", ""),
                                         "count": 0})
        out[a["student_id"]]["count"] += 1
    return out


@router.get("/collections/students/{sid}/activities")
async def student_activities(sid: str, user: dict = Depends(COL_READ)):
    await _student_or_404(sid)
    rows = await db.collection_activities.find({"student_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [clean(r) for r in rows]


@router.get("/collections/preview")
async def collections_preview(student_id: str, recipient: str = "siswa",
                              template_key: str = "payment_due", user: dict = Depends(COL_READ)):
    from routers.whatsapp import _manual_variables
    s = await _student_or_404(student_id)
    if recipient not in ("siswa", "wali"):
        raise HTTPException(status_code=400, detail="Recipient tidak valid")
    tpl = await get_template(template_key)
    if not tpl:
        raise HTTPException(status_code=400, detail="Template tidak aktif")
    variables = await _manual_variables(template_key, student_id, None, {})
    body = render_template(tpl["body"], tpl.get("variables") or TEMPLATE_VARS.get(template_key, []), variables)
    phone = s.get("wa_student_phone") or s.get("no_hp") or ""
    if recipient == "wali":
        phone = s.get("wa_guardian_phone") or s.get("no_hp_orang_tua") or ""
    cfg = wa_config()
    return {"template_key": template_key, "template_version": tpl["version"], "body": body,
            "recipient": recipient,
            "recipient_name": s.get("nama_lengkap") if recipient == "siswa" else s.get("nama_orang_tua"),
            "phone_masked": mask_phone(phone or ""),
            "wa_enabled": cfg["enabled"], "dry_run": cfg["dry_run"]}


@router.post("/collections/activities")
async def create_activity(body: ActivityIn, user: dict = Depends(COL_WRITE)):
    _check_enums(body.channel, body.outcome)
    if not (body.note or "").strip():
        raise HTTPException(status_code=400, detail="Catatan wajib diisi")
    _check_fu_date(body.next_follow_up_at)
    s = await _student_or_404(body.student_id)
    snap = await _sisa_snapshot(s)
    doc = {"id": new_id(), "student_id": s["id"], "student_nama": s.get("nama_lengkap", ""),
            "actor_id": user["id"], "actor_name": user.get("name", ""), "actor_role": user.get("role", ""),
            "created_at": now_iso(), "channel": body.channel, "outcome": body.outcome,
            "note": body.note.strip(), "next_follow_up_at": body.next_follow_up_at,
            "next_follow_up_note": (body.next_follow_up_note or "").strip(),
            "sisa_snapshot": snap, "template_key": None, "wa_message_id": None, "wa_status": None}
    if body.idem_key:
        doc["idem_key"] = body.idem_key
    try:
        await db.collection_activities.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.collection_activities.find_one({"idem_key": body.idem_key}, {"_id": 0}) if body.idem_key else None
        if existing:
            return {**clean(existing), "duplicate": True}
        raise
    await log_audit("collection", doc["id"], "create", user, None,
                    {"student_id": s["id"], "channel": body.channel, "outcome": body.outcome})
    return clean(doc)


@router.post("/collections/activities/send-wa")
async def send_wa_activity(body: SendWaIn, user: dict = Depends(COL_WRITE)):
    from routers.whatsapp import _manual_variables
    if body.outcome not in OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Outcome tidak valid: {body.outcome}")
    if body.recipient not in ("siswa", "wali"):
        raise HTTPException(status_code=400, detail="Recipient tidak valid")
    _check_fu_date(body.next_follow_up_at)
    s = await _student_or_404(body.student_id)
    dup = await db.collection_activities.find_one({"idem_key": body.idem_key}, {"_id": 0})
    if dup:
        return {**clean(dup), "duplicate": True, "wa_sent": bool((dup.get("wa_status") or "") == "sent")}
    cfg = wa_config()
    if not cfg["enabled"]:
        raise HTTPException(status_code=400, detail="WhatsApp belum diaktifkan — catat sebagai penagihan manual")
    tpl = await get_template(body.template_key)
    if not tpl:
        raise HTTPException(status_code=400, detail="Template tidak aktif")
    variables = await _manual_variables(body.template_key, body.student_id, None, {})
    msg = await queue_message(body.template_key, body.student_id, body.recipient,
                              f"collection:{body.idem_key}", variables, created_by=user, allow_skipped=False)
    if msg.get("skipped"):
        raise HTTPException(status_code=400, detail="Nomor WhatsApp penerima tidak valid")
    if not msg.get("duplicate") and msg["status"] == "queued":
        msg = await attempt_send(msg["id"], user)
    snap = await _sisa_snapshot(s)
    wa_status = msg.get("status", "unknown")
    doc = {"id": new_id(), "student_id": s["id"], "student_nama": s.get("nama_lengkap", ""),
            "actor_id": user["id"], "actor_name": user.get("name", ""), "actor_role": user.get("role", ""),
            "created_at": now_iso(), "channel": "whatsapp", "outcome": body.outcome,
            "note": (body.note or "").strip(), "next_follow_up_at": body.next_follow_up_at,
            "next_follow_up_note": (body.next_follow_up_note or "").strip(),
            "sisa_snapshot": snap, "template_key": body.template_key,
            "template_version": tpl["version"], "variables": variables,
            "wa_message_id": msg.get("id"), "wa_status": wa_status,
            "wa_dry_run": bool(msg.get("dry_run")), "idem_key": body.idem_key}
    try:
        await db.collection_activities.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.collection_activities.find_one({"idem_key": body.idem_key}, {"_id": 0})
        if existing:
            return {**clean(existing), "duplicate": True, "wa_sent": bool((existing.get("wa_status") or "") == "sent")}
        raise
    await log_audit("collection", doc["id"], "send_wa", user, None,
                    {"student_id": s["id"], "template": body.template_key, "wa_message_id": msg.get("id"),
                     "wa_status": wa_status})
    return {**clean(doc), "wa_sent": wa_status == "sent", "duplicate": bool(msg.get("duplicate"))}


@router.put("/collections/activities/{aid}")
async def update_activity(aid: str, body: ActivityUpdateIn, user: dict = Depends(COL_WRITE)):
    old = await db.collection_activities.find_one({"id": aid}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Activity tidak ditemukan")
    if not (body.alasan or "").strip():
        raise HTTPException(status_code=400, detail="Alasan koreksi wajib diisi (audit)")
    upd = {}
    if body.outcome is not None:
        if body.outcome not in OUTCOMES:
            raise HTTPException(status_code=400, detail=f"Outcome tidak valid: {body.outcome}")
        upd["outcome"] = body.outcome
    if body.note is not None:
        if not body.note.strip():
            raise HTTPException(status_code=400, detail="Catatan tidak boleh kosong")
        upd["note"] = body.note.strip()
    if body.next_follow_up_at is not None:
        _check_fu_date(body.next_follow_up_at)
        upd["next_follow_up_at"] = body.next_follow_up_at
    if body.next_follow_up_note is not None:
        upd["next_follow_up_note"] = body.next_follow_up_note.strip()
    if not upd:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan")
    upd["updated_at"] = now_iso()
    await db.collection_activities.update_one({"id": aid}, {"$set": upd})
    new = await db.collection_activities.find_one({"id": aid}, {"_id": 0})
    await log_audit("collection", aid, "update", user,
                    {k: old.get(k) for k in upd if k != "updated_at"},
                    {k: new.get(k) for k in upd if k != "updated_at"}, body.alasan.strip())
    return clean(new)
