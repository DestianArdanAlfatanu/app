"""Departure Readiness P1.3 — antrean & checklist kesiapan keberangkatan.

Manusia memverifikasi & memutuskan; sistem mencatat, menurunkan readiness,
mengingatkan. Aditif: memakai students/documents/interviews/job_orders existing
tanpa menduplikasi master. Finansial hanya warning, bukan blocker.
"""
from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pg_mongo import DuplicateKeyError

from core import (db, require_roles, new_id, now_iso, today_str, clean, log_audit,
                  payment_summary_map, fee_total, today)

router = APIRouter()

DEP_READ = require_roles("owner", "admin", "staff", "finance", "hr", "guru", "marketing")
DEP_WRITE = require_roles("owner", "admin", "staff")
DEP_VERIFY = require_roles("owner", "admin", "staff", "finance", "hr")
DEP_FINAL = require_roles("owner")
NOTIF_DEP = ["owner", "admin", "staff"]

PROFILE_STATUSES = ["disiapkan", "siap", "tertunda", "berangkat"]

REQUIREMENTS = [
    {"code": "passport", "name": "Passport", "doc_jenis": "Paspor"},
    {"code": "coe", "name": "COE", "doc_jenis": "COE"},
    {"code": "visa", "name": "Visa", "doc_jenis": "Visa"},
    {"code": "medical", "name": "Medical Check-up", "doc_jenis": "Medical Check-up"},
    {"code": "ticket", "name": "Ticket", "doc_jenis": "Tiket"},
    {"code": "contract", "name": "Kontrak Kerja", "doc_jenis": "Kontrak Kerja"},
]
REQ_BY_CODE = {r["code"]: r for r in REQUIREMENTS}
ITEM_STATUSES = ["pending", "verified", "rejected", "exception"]


class ProfileIn(BaseModel):
    student_id: str
    job_order_id: Optional[str] = None
    target_departure_date: Optional[str] = None
    destination: Optional[str] = None
    departure_location: Optional[str] = None
    pic_user_id: Optional[str] = None
    pic_name: Optional[str] = ""
    notes: Optional[str] = ""


class ProfileUpdateIn(BaseModel):
    target_departure_date: Optional[str] = None
    actual_departure_date: Optional[str] = None
    destination: Optional[str] = None
    departure_location: Optional[str] = None
    pic_user_id: Optional[str] = None
    pic_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    ticket_airline: Optional[str] = None
    flight_number: Optional[str] = None
    departure_datetime: Optional[str] = None
    arrival_datetime: Optional[str] = None
    departure_airport: Optional[str] = None
    arrival_airport: Optional[str] = None
    ticket_document_id: Optional[str] = None
    alasan: str = ""


class VerifyIn(BaseModel):
    document_id: Optional[str] = None
    note: Optional[str] = ""


class RejectIn(BaseModel):
    reason: str


class ExceptionIn(BaseModel):
    reason: str


class DecisionIn(BaseModel):
    reason: str = ""


async def _student_or_404(sid: str) -> dict:
    s = await db.students.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    return s


async def _profile_or_404(pid: str) -> dict:
    p = await db.departure_profiles.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Departure profile tidak ditemukan")
    return p


def _blank_profile(s: dict, user: dict, body: ProfileIn) -> dict:
    return {"id": new_id(), "student_id": s["id"], "student_nama": s.get("nama_lengkap", ""),
            "job_order_id": body.job_order_id, "target_departure_date": body.target_departure_date,
            "actual_departure_date": None, "destination": body.destination or "",
            "departure_location": body.departure_location or "",
            "pic_user_id": body.pic_user_id, "pic_name": body.pic_name or "",
            "status": "disiapkan", "notes": body.notes or "",
            "ticket_airline": None, "flight_number": None, "departure_datetime": None,
            "arrival_datetime": None, "departure_airport": None, "arrival_airport": None,
            "ticket_document_id": None,
            "final_decision": None, "final_decision_by": None, "final_decision_at": None,
            "final_decision_reason": None,
            "created_by": user["id"], "created_at": now_iso(), "updated_at": now_iso()}


def _blank_items(profile: dict) -> list:
    return [{"id": new_id(), "departure_profile_id": profile["id"], "student_id": profile["student_id"],
             "requirement_code": r["code"], "requirement_name": r["name"], "required": True,
             "conditional": False, "document_id": None, "status": "pending",
             "verified_by": None, "verified_at": None, "verification_note": "",
             "rejected_reason": "", "exception_status": "none", "exception_reason": "",
             "exception_approved_by": None, "exception_approved_at": None,
             "created_at": now_iso(), "updated_at": now_iso()} for r in REQUIREMENTS]


async def _enrich_profile(p: dict) -> dict:
    p = clean(p)
    if p.get("job_order_id"):
        job = await db.jobs.find_one({"id": p["job_order_id"]}, {"_id": 0}) or \
            await db.job_orders.find_one({"id": p["job_order_id"]}, {"_id": 0})
        if job:
            p["company"] = job.get("perusahaan", "")
            p["position"] = job.get("posisi", "")
            if not p.get("destination"):
                p["destination"] = job.get("lokasi", "")
    return p


async def compute_readiness(profile: dict) -> dict:
    """Satu-satunya source of truth readiness. Derived, tanpa tulis."""
    items = await db.departure_checklist.find({"departure_profile_id": profile["id"]}, {"_id": 0}).to_list(None)
    s = await db.students.find_one({"id": profile["student_id"]}, {"_id": 0})
    t = today_str()
    ref_date = profile.get("target_departure_date") or t
    blockers, warnings = [], []
    n_ver = n_pen = n_rej = n_exc = 0
    for it in items:
        if not it.get("required", True):
            continue
        st = it.get("status")
        if st == "verified":
            n_ver += 1
        elif st == "exception":
            n_exc += 1
        elif st == "rejected":
            n_rej += 1
            blockers.append(f"{it['requirement_name']}: rejected — {it.get('rejected_reason', '')}".strip())
        else:
            n_pen += 1
            blockers.append(f"{it['requirement_name']}: belum diverifikasi")
        if it.get("document_id") and st == "verified":
            doc = await db.documents.find_one({"id": it["document_id"], "is_deleted": False}, {"_id": 0})
            if doc and doc.get("tanggal_kadaluarsa") and doc["tanggal_kadaluarsa"] < ref_date:
                blockers.append(f"{it['requirement_name']}: dokumen expired {doc['tanggal_kadaluarsa']}")
    if s:
        pay = await payment_summary_map([s["id"]])
        sisa = max(fee_total(s) - pay.get(s["id"], {}).get("bayar", 0), 0)
        if sisa > 0:
            warnings.append(f"Sisa tagihan Rp{sisa:,.0f} (informasi, bukan blocker)".replace(",", "."))
    if profile.get("final_decision") == "BLOCKED":
        blockers.append(f"Keputusan BLOCKED oleh {profile.get('final_decision_by', '')}: "
                        f"{profile.get('final_decision_reason', '')}".strip())
    days = None
    if profile.get("target_departure_date"):
        try:
            days = (_date.fromisoformat(profile["target_departure_date"]) - today()).days
        except ValueError:
            pass
    if blockers:
        status = "BLOCKED"
    elif profile.get("final_decision") == "READY" and n_pen == 0 and n_rej == 0:
        status = "READY"
    else:
        status = "NOT_READY"
    return {"readiness_status": status, "checklist_total": len([i for i in items if i.get("required", True)]),
            "checklist_verified": n_ver, "checklist_pending": n_pen, "checklist_rejected": n_rej,
            "checklist_exception": n_exc, "blockers": blockers, "warnings": warnings,
            "target_departure_date": profile.get("target_departure_date"), "days_to_departure": days}


@router.get("/departures")
async def list_departures(status: Optional[str] = None, user: dict = Depends(DEP_READ)):
    q = {}
    if status:
        q["status"] = status
    rows = await db.departure_profiles.find(q, {"_id": 0}).sort("created_at", -1).to_list(None)
    out = []
    for p in rows:
        p = await _enrich_profile(p)
        p["readiness"] = await compute_readiness(p)
        out.append(p)
    return out


@router.get("/departures/{pid}")
async def get_departure(pid: str, user: dict = Depends(DEP_READ)):
    p = await db.departure_profiles.find_one({"id": pid}, {"_id": 0})
    if not p:
        p = await db.departure_profiles.find_one({"student_id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Departure profile tidak ditemukan")
    p = await _enrich_profile(p)
    p["readiness"] = await compute_readiness(p)
    return p


@router.get("/departures/{pid}/readiness")
async def get_readiness(pid: str, user: dict = Depends(DEP_READ)):
    p = await _profile_or_404(pid)
    return await compute_readiness(p)


@router.post("/departures")
async def create_departure(body: ProfileIn, user: dict = Depends(DEP_WRITE)):
    s = await _student_or_404(body.student_id)
    if await db.departure_profiles.find_one({"student_id": s["id"]}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=409, detail="Siswa sudah memiliki departure profile")
    if body.job_order_id:
        job = await db.jobs.find_one({"id": body.job_order_id}, {"_id": 0, "id": 1}) or \
            await db.job_orders.find_one({"id": body.job_order_id}, {"_id": 0, "id": 1})
        if not job:
            raise HTTPException(status_code=404, detail="Job order tidak ditemukan")
    doc = _blank_profile(s, user, body)
    try:
        await db.departure_profiles.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Siswa sudah memiliki departure profile")
    await db.departure_checklist.insert_many(_blank_items(doc))
    await log_audit("departure", doc["id"], "create", user, None,
                    {"student_id": s["id"], "job_order_id": body.job_order_id})
    p = await _enrich_profile(clean(doc))
    p["readiness"] = await compute_readiness(doc)
    return p


@router.put("/departures/{pid}")
async def update_departure(pid: str, body: ProfileUpdateIn, user: dict = Depends(DEP_WRITE)):
    old = await _profile_or_404(pid)
    if not (body.alasan or "").strip():
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi (audit)")
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k != "alasan"}
    if "status" in upd and upd["status"] not in PROFILE_STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak valid")
    if upd.get("status") == "berangkat" and old.get("status") != "berangkat":
        ready = await compute_readiness(old)
        if ready["readiness_status"] != "READY":
            raise HTTPException(status_code=400, detail="Belum READY: status berangkat butuh keputusan final READY dari Owner")
    if not upd:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan")
    upd["updated_at"] = now_iso()
    await db.departure_profiles.update_one({"id": pid}, {"$set": upd})
    new = await _profile_or_404(pid)
    await log_audit("departure", pid, "update", user,
                    {k: old.get(k) for k in upd if k != "updated_at"},
                    {k: new.get(k) for k in upd if k != "updated_at"}, body.alasan.strip())
    p = await _enrich_profile(new)
    p["readiness"] = await compute_readiness(new)
    return p


@router.get("/departures/{pid}/checklist")
async def get_checklist(pid: str, user: dict = Depends(DEP_READ)):
    await _profile_or_404(pid)
    rows = await db.departure_checklist.find({"departure_profile_id": pid}, {"_id": 0}).to_list(None)
    out = []
    for it in rows:
        it = clean(it)
        if it.get("document_id"):
            doc = await db.documents.find_one({"id": it["document_id"]}, {"_id": 0})
            if doc:
                it["document"] = {"jenis": doc.get("jenis"), "tanggal_kadaluarsa": doc.get("tanggal_kadaluarsa"),
                                  "file_id": doc.get("file_id"), "is_deleted": doc.get("is_deleted", False)}
        out.append(it)
    return out


async def _item_or_404(pid: str, item_id: str) -> dict:
    it = await db.departure_checklist.find_one({"id": item_id, "departure_profile_id": pid}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Checklist item tidak ditemukan")
    return it


@router.put("/departures/{pid}/checklist/{item_id}/verify")
async def verify_item(pid: str, item_id: str, body: VerifyIn, user: dict = Depends(DEP_VERIFY)):
    await _profile_or_404(pid)
    old = await _item_or_404(pid, item_id)
    doc = None
    if body.document_id:
        doc = await db.documents.find_one({"id": body.document_id}, {"_id": 0})
        if not doc or doc.get("is_deleted"):
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
        if doc.get("student_id") != old["student_id"]:
            raise HTTPException(status_code=400, detail="Dokumen milik siswa lain")
        if doc.get("tanggal_kadaluarsa") and doc["tanggal_kadaluarsa"] < today_str():
            raise HTTPException(status_code=400, detail="Dokumen sudah expired — tidak dapat diverifikasi")
    upd = {"status": "verified", "document_id": body.document_id, "verified_by": user.get("name", ""),
           "verified_at": now_iso(), "verification_note": (body.note or "").strip(),
           "rejected_reason": "", "exception_status": "none", "updated_at": now_iso()}
    await db.departure_checklist.update_one({"id": item_id}, {"$set": upd})
    await log_audit("departure_checklist", item_id, "verify", user,
                    {"status": old.get("status")}, {"status": "verified", "document_id": body.document_id})
    return clean(await db.departure_checklist.find_one({"id": item_id}, {"_id": 0}))


@router.post("/departures/{pid}/checklist/{item_id}/reject")
async def reject_item(pid: str, item_id: str, body: RejectIn, user: dict = Depends(DEP_VERIFY)):
    await _profile_or_404(pid)
    old = await _item_or_404(pid, item_id)
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi")
    upd = {"status": "rejected", "rejected_reason": body.reason.strip(), "verified_by": None,
           "verified_at": None, "updated_at": now_iso()}
    await db.departure_checklist.update_one({"id": item_id}, {"$set": upd})
    await log_audit("departure_checklist", item_id, "reject", user,
                    {"status": old.get("status")}, {"status": "rejected"}, body.reason.strip())
    return clean(await db.departure_checklist.find_one({"id": item_id}, {"_id": 0}))


@router.post("/departures/{pid}/checklist/{item_id}/exception")
async def request_exception(pid: str, item_id: str, body: ExceptionIn, user: dict = Depends(DEP_VERIFY)):
    await _profile_or_404(pid)
    old = await _item_or_404(pid, item_id)
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan exception wajib diisi")
    if user.get("role") == "owner":
        upd = {"status": "exception", "exception_status": "approved",
               "exception_reason": body.reason.strip(), "exception_approved_by": user.get("name", ""),
               "exception_approved_at": now_iso(), "updated_at": now_iso()}
        action = "exception_approve"
    else:
        upd = {"exception_status": "requested", "exception_reason": body.reason.strip(),
               "updated_at": now_iso()}
        action = "exception_request"
    await db.departure_checklist.update_one({"id": item_id}, {"$set": upd})
    await log_audit("departure_checklist", item_id, action, user,
                    {"status": old.get("status"), "exception_status": old.get("exception_status")},
                    {"status": upd.get("status", old.get("status")), "exception_status": upd["exception_status"]},
                    body.reason.strip())
    return clean(await db.departure_checklist.find_one({"id": item_id}, {"_id": 0}))


@router.post("/departures/{pid}/ready")
async def mark_ready(pid: str, body: DecisionIn, user: dict = Depends(DEP_FINAL)):
    old = await _profile_or_404(pid)
    ready = await compute_readiness(old)
    if ready["blockers"]:
        raise HTTPException(status_code=400, detail=f"Belum READY: {ready['blockers'][0]}")
    upd = {"final_decision": "READY", "final_decision_by": user.get("name", ""),
           "final_decision_at": now_iso(), "final_decision_reason": (body.reason or "").strip(),
           "status": "siap", "updated_at": now_iso()}
    await db.departure_profiles.update_one({"id": pid}, {"$set": upd})
    await log_audit("departure", pid, "ready", user, {"final_decision": old.get("final_decision")},
                    {"final_decision": "READY"}, (body.reason or "").strip() or "Final READY")
    new = await _profile_or_404(pid)
    p = await _enrich_profile(new)
    p["readiness"] = await compute_readiness(new)
    return p


@router.post("/departures/{pid}/block")
async def mark_blocked(pid: str, body: DecisionIn, user: dict = Depends(DEP_FINAL)):
    old = await _profile_or_404(pid)
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan BLOCKED wajib diisi")
    upd = {"final_decision": "BLOCKED", "final_decision_by": user.get("name", ""),
           "final_decision_at": now_iso(), "final_decision_reason": body.reason.strip(),
           "status": "tertunda", "updated_at": now_iso()}
    await db.departure_profiles.update_one({"id": pid}, {"$set": upd})
    await log_audit("departure", pid, "block", user, {"final_decision": old.get("final_decision")},
                    {"final_decision": "BLOCKED"}, body.reason.strip())
    new = await _profile_or_404(pid)
    p = await _enrich_profile(new)
    p["readiness"] = await compute_readiness(new)
    return p
