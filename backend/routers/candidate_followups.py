"""Candidate Follow-up P1.2 — antrean & histori follow-up prospek (calon_siswa).

Manusia memutuskan & berkomunikasi; sistem mencatat, menjadwalkan, mengingatkan.
Bukan modul finance: tidak ada snapshot/tagihan/saldo. Konversi ke siswa tetap
via PUT /students/{id}/status (history tertaut student_id yang sama).
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pg_mongo import DuplicateKeyError

from core import (db, require_roles, new_id, now_iso, today_str, clean, log_audit)
from routers.whatsapp import (queue_message, attempt_send, wa_config, get_template,
                              render_template, mask_phone, TEMPLATE_VARS)

router = APIRouter()

CF_READ = require_roles("owner", "admin", "marketing", "staff")
CF_WRITE = require_roles("owner", "admin", "marketing", "staff")
NOTIF_CANDIDATE = ["owner", "admin", "marketing"]

CHANNELS = ["whatsapp", "phone", "in_person", "sosmed", "kunjungan", "other"]
OUTCOMES = ["terhubungi", "janji_datang", "minat", "mendaftar", "tidak_aktif",
            "nomor_salah", "menolak", "lainnya"]
CLOSED_OUTCOMES = ["mendaftar", "menolak", "tidak_aktif"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NAMA_LPK = "LPK"


class FollowupIn(BaseModel):
    student_id: str
    channel: str
    outcome: str
    note: str
    next_follow_up_at: Optional[str] = None
    next_follow_up_note: Optional[str] = ""
    idem_key: Optional[str] = None


class FollowupSendWaIn(BaseModel):
    student_id: str
    recipient: str = "siswa"
    outcome: str = "terhubungi"
    note: str = ""
    next_follow_up_at: Optional[str] = None
    next_follow_up_note: Optional[str] = ""
    tanggal_follow_up: Optional[str] = ""
    idem_key: str


class FollowupUpdateIn(BaseModel):
    outcome: Optional[str] = None
    note: Optional[str] = None
    next_follow_up_at: Optional[str] = None
    next_follow_up_note: Optional[str] = None
    alasan: str = ""


async def _candidate_or_404(sid: str) -> dict:
    s = await db.students.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    return s


def _require_candidate(s: dict):
    if s.get("status") != "calon_siswa":
        raise HTTPException(status_code=400,
                            detail=f"Hanya calon siswa yang dapat di-follow-up (status kini: {s.get('status')})")


def _check_enums(channel: str, outcome: str):
    if channel not in CHANNELS:
        raise HTTPException(status_code=400, detail=f"Channel tidak valid: {channel}")
    if outcome not in OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Outcome tidak valid: {outcome}")


def _check_fu_date(v: Optional[str]):
    if v is not None and not DATE_RE.match(v):
        raise HTTPException(status_code=400, detail="next_follow_up_at harus format YYYY-MM-DD")


def _prospect_snapshot(s: dict) -> dict:
    return {"status": s.get("status"), "sumber_prospek": s.get("sumber_prospek", ""),
            "pemilik_lead": s.get("pemilik_lead", "")}


@router.get("/candidate-followups/overview")
async def cf_overview(user: dict = Depends(CF_READ)):
    calons = await db.students.find({"status": "calon_siswa"}, {"_id": 0, "id": 1, "nama_lengkap": 1}).to_list(None)
    acts = await db.candidate_followups.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    latest = {}
    for a in acts:
        latest.setdefault(a["student_id"], a)
    t = today_str()
    due, overdue, closed, never = [], [], [], []
    for c in calons:
        a = latest.get(c["id"])
        if not a:
            never.append({"id": c["id"], "nama_lengkap": c["nama_lengkap"]})
        elif a.get("outcome") in CLOSED_OUTCOMES:
            closed.append({"id": c["id"], "nama_lengkap": c["nama_lengkap"],
                           "outcome": a.get("outcome"), "last_at": a.get("created_at")})
        elif a.get("next_follow_up_at"):
            fu = a["next_follow_up_at"]
            item = {"id": c["id"], "nama_lengkap": c["nama_lengkap"], "next_follow_up_at": fu,
                    "next_follow_up_note": a.get("next_follow_up_note", ""),
                    "last_outcome": a.get("outcome"), "last_at": a.get("created_at")}
            if fu < t:
                overdue.append(item)
            elif fu == t:
                due.append(item)
    return {"total_calon": len(calons), "never_contacted": never, "due_today": due,
            "overdue": overdue, "closed": closed,
            "recent": [{k: a.get(k) for k in ("id", "student_id", "student_nama", "channel", "outcome",
                                              "created_at", "actor_name", "wa_status")} for a in acts[:20]]}


@router.get("/candidate-followups/summary-map")
async def cf_summary_map(user: dict = Depends(CF_READ)):
    acts = await db.candidate_followups.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    out = {}
    for a in acts:
        if a["student_id"] in out:
            out[a["student_id"]]["count"] += 1
            continue
        out[a["student_id"]] = {"last_contacted": a["created_at"], "last_outcome": a["outcome"],
                                "last_channel": a["channel"],
                                "next_follow_up_at": a.get("next_follow_up_at"),
                                "next_follow_up_note": a.get("next_follow_up_note", ""),
                                "follow_up_status": ("closed" if a.get("outcome") in CLOSED_OUTCOMES else "open"),
                                "count": 1}
    return out


@router.get("/candidate-followups/students/{sid}/activities")
async def cf_history(sid: str, user: dict = Depends(CF_READ)):
    await _candidate_or_404(sid)
    rows = await db.candidate_followups.find({"student_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return [clean(r) for r in rows]


@router.get("/candidate-followups/preview")
async def cf_preview(student_id: str, recipient: str = "siswa",
                     tanggal_follow_up: str = "", user: dict = Depends(CF_READ)):
    from routers.whatsapp import _manual_variables
    s = await _candidate_or_404(student_id)
    if recipient not in ("siswa", "wali"):
        raise HTTPException(status_code=400, detail="Recipient tidak valid")
    tpl = await get_template("followup_calon")
    if not tpl:
        raise HTTPException(status_code=400, detail="Template tidak aktif")
    variables = await _manual_variables("followup_calon", student_id, None,
                                        {"tanggal_follow_up": tanggal_follow_up})
    body = render_template(tpl["body"], tpl.get("variables") or TEMPLATE_VARS.get("followup_calon", []), variables)
    phone = s.get("wa_student_phone") or s.get("no_hp") or ""
    if recipient == "wali":
        phone = s.get("wa_guardian_phone") or s.get("no_hp_orang_tua") or ""
    cfg = wa_config()
    return {"template_key": "followup_calon", "template_version": tpl["version"], "body": body,
            "recipient": recipient,
            "recipient_name": s.get("nama_lengkap") if recipient == "siswa" else s.get("nama_orang_tua"),
            "phone_masked": mask_phone(phone or ""),
            "wa_enabled": cfg["enabled"], "dry_run": cfg["dry_run"]}


@router.post("/candidate-followups/activities")
async def cf_create(body: FollowupIn, user: dict = Depends(CF_WRITE)):
    _check_enums(body.channel, body.outcome)
    if not (body.note or "").strip():
        raise HTTPException(status_code=400, detail="Catatan wajib diisi")
    _check_fu_date(body.next_follow_up_at)
    s = await _candidate_or_404(body.student_id)
    _require_candidate(s)
    doc = {"id": new_id(), "student_id": s["id"], "student_nama": s.get("nama_lengkap", ""),
            "actor_id": user["id"], "actor_name": user.get("name", ""), "actor_role": user.get("role", ""),
            "created_at": now_iso(), "channel": body.channel, "outcome": body.outcome,
            "note": body.note.strip(), "next_follow_up_at": body.next_follow_up_at,
            "next_follow_up_note": (body.next_follow_up_note or "").strip(),
            "prospect_snapshot": _prospect_snapshot(s),
            "template_key": None, "wa_message_id": None, "wa_status": None}
    if body.idem_key:
        doc["idem_key"] = body.idem_key
    try:
        await db.candidate_followups.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.candidate_followups.find_one({"idem_key": body.idem_key}, {"_id": 0}) if body.idem_key else None
        if existing:
            return {**clean(existing), "duplicate": True}
        raise
    await log_audit("candidate_followup", doc["id"], "create", user, None,
                    {"student_id": s["id"], "channel": body.channel, "outcome": body.outcome})
    return clean(doc)


@router.post("/candidate-followups/activities/send-wa")
async def cf_send_wa(body: FollowupSendWaIn, user: dict = Depends(CF_WRITE)):
    from routers.whatsapp import _manual_variables
    if body.outcome not in OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Outcome tidak valid: {body.outcome}")
    if body.recipient not in ("siswa", "wali"):
        raise HTTPException(status_code=400, detail="Recipient tidak valid")
    _check_fu_date(body.next_follow_up_at)
    s = await _candidate_or_404(body.student_id)
    _require_candidate(s)
    dup = await db.candidate_followups.find_one({"idem_key": body.idem_key}, {"_id": 0})
    if dup:
        return {**clean(dup), "duplicate": True, "wa_sent": bool((dup.get("wa_status") or "") == "sent")}
    cfg = wa_config()
    if not cfg["enabled"]:
        raise HTTPException(status_code=400, detail="WhatsApp belum diaktifkan — catat sebagai follow-up manual")
    tpl = await get_template("followup_calon")
    if not tpl:
        raise HTTPException(status_code=400, detail="Template tidak aktif")
    variables = await _manual_variables("followup_calon", body.student_id, None,
                                        {"tanggal_follow_up": body.tanggal_follow_up or ""})
    msg = await queue_message("followup_calon", body.student_id, body.recipient,
                              f"calon:{body.idem_key}", variables, created_by=user, allow_skipped=False)
    if msg.get("skipped"):
        raise HTTPException(status_code=400, detail="Nomor WhatsApp penerima tidak valid")
    if not msg.get("duplicate") and msg["status"] == "queued":
        msg = await attempt_send(msg["id"], user)
    wa_status = msg.get("status", "unknown")
    doc = {"id": new_id(), "student_id": s["id"], "student_nama": s.get("nama_lengkap", ""),
            "actor_id": user["id"], "actor_name": user.get("name", ""), "actor_role": user.get("role", ""),
            "created_at": now_iso(), "channel": "whatsapp", "outcome": body.outcome,
            "note": (body.note or "").strip(), "next_follow_up_at": body.next_follow_up_at,
            "next_follow_up_note": (body.next_follow_up_note or "").strip(),
            "prospect_snapshot": _prospect_snapshot(s),
            "template_key": "followup_calon", "template_version": tpl["version"], "variables": variables,
            "wa_message_id": msg.get("id"), "wa_status": wa_status,
            "wa_dry_run": bool(msg.get("dry_run")), "idem_key": body.idem_key}
    try:
        await db.candidate_followups.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.candidate_followups.find_one({"idem_key": body.idem_key}, {"_id": 0})
        if existing:
            return {**clean(existing), "duplicate": True, "wa_sent": bool((existing.get("wa_status") or "") == "sent")}
        raise
    await log_audit("candidate_followup", doc["id"], "send_wa", user, None,
                    {"student_id": s["id"], "template": "followup_calon", "wa_message_id": msg.get("id"),
                     "wa_status": wa_status})
    return {**clean(doc), "wa_sent": wa_status == "sent", "duplicate": bool(msg.get("duplicate"))}


@router.put("/candidate-followups/activities/{aid}")
async def cf_update(aid: str, body: FollowupUpdateIn, user: dict = Depends(CF_WRITE)):
    old = await db.candidate_followups.find_one({"id": aid}, {"_id": 0})
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
    await db.candidate_followups.update_one({"id": aid}, {"$set": upd})
    new = await db.candidate_followups.find_one({"id": aid}, {"_id": 0})
    await log_audit("candidate_followup", aid, "update", user,
                    {k: old.get(k) for k in upd if k != "updated_at"},
                    {k: new.get(k) for k in upd if k != "updated_at"}, body.alasan.strip())
    return clean(new)
