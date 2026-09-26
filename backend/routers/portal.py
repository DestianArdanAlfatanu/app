from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Form
from pydantic import BaseModel, EmailStr

from core import (db, get_current_user, hash_password, verify_password, create_access_token,
                  new_id, now_iso, today_str, clean, log_audit, payment_summary_map, fee_total,
                  attendance_summary, grade_average, doc_progress, compute_age, save_upload, DOC_TYPES,
                  login_locked, record_login_failure, file_response, logger, revoke_tokens)
from document_storage import storage as doc_storage, ALLOWED_DOC_EXTENSIONS

router = APIRouter()


class PortalLoginIn(BaseModel):
    email: EmailStr
    password: str


class PortalPasswordIn(BaseModel):
    old_password: str
    new_password: str


class PortalConsentIn(BaseModel):
    wa_student_opt_in: bool


def _principal(user: dict) -> str:
    if user.get("role") != "student" or not user.get("student_id"):
        raise HTTPException(status_code=403, detail="Akses portal siswa ditolak")
    return user["student_id"]


async def get_current_student(request: Request) -> dict:
    user = await get_current_user(request)
    sid = _principal(user)
    if user.get("must_change_password"):
        raise HTTPException(status_code=403, detail="Wajib ganti password terlebih dahulu")
    s = await db.students.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Data siswa tidak ditemukan")
    return {"user": user, "student": s, "sid": sid}


async def get_current_student_lenient(request: Request) -> dict:
    user = await get_current_user(request)
    sid = _principal(user)
    s = await db.students.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Data siswa tidak ditemukan")
    return {"user": user, "student": s, "sid": sid}


def _profile(s: dict) -> dict:
    return {
        "id": s["id"], "nama_lengkap": s.get("nama_lengkap"), "nik": s.get("nik"),
        "tempat_lahir": s.get("tempat_lahir"), "tanggal_lahir": s.get("tanggal_lahir"),
        "jenis_kelamin": s.get("jenis_kelamin"), "alamat": s.get("alamat") or {},
        "no_hp": s.get("no_hp"), "email": s.get("email"),
        "nama_orang_tua": s.get("nama_orang_tua"), "no_hp_orang_tua": s.get("no_hp_orang_tua"),
        "pendidikan_terakhir": s.get("pendidikan_terakhir"), "nama_sekolah": s.get("nama_sekolah"),
        "jurusan": s.get("jurusan"), "status": s.get("status"), "usia": compute_age(s.get("tanggal_lahir")),
        "status_history": [
            {k: h.get(k) for k in ("status", "tanggal", "catatan")} for h in (s.get("status_history") or [])
        ],
    }


def _pay_view(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "tanggal", "nominal", "metode", "jenis", "no_transaksi", "no_kwitansi", "catatan")}


@router.post("/student/auth/login")
async def student_login(body: PortalLoginIn, request: Request):
    email = body.email.lower().strip()
    ident = f"{request.client.host if request.client else 'x'}:{email}"
    if await login_locked(ident):
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan. Coba lagi dalam 15 menit")
    user = await db.users.find_one({"email": email})
    if not user or user.get("role") != "student" or not verify_password(body.password, user.get("password_hash", "")):
        await record_login_failure(ident)
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if not user.get("aktif", True):
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan")
    await db.login_attempts.delete_one({"identifier": ident})
    access = create_access_token(user)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    out = clean(dict(user))
    out.pop("password_hash", None)
    out.pop("token_version", None)
    return {"token": access, "user": out}


@router.post("/student/auth/logout")
async def student_logout(response: Response, user: dict = Depends(get_current_user)):
    await revoke_tokens(user["id"])
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/student/auth/me")
async def student_me(ctx: dict = Depends(get_current_student_lenient)):
    out = clean(dict(ctx["user"]))
    out.pop("password_hash", None)
    return out


@router.post("/student/auth/change-password")
async def student_change_password(body: PortalPasswordIn, request: Request):
    user = await get_current_user(request)
    _principal(user)
    if not body.new_password or len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
    current = await db.users.find_one({"id": user["id"]})
    if not current or not verify_password(body.old_password, current.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Password lama salah")
    if body.new_password == body.old_password:
        raise HTTPException(status_code=400, detail="Password baru harus berbeda dari password lama")
    await db.users.update_one({"id": user["id"]},
                              {"$set": {"password_hash": hash_password(body.new_password),
                                        "must_change_password": False}})
    # Cabut sesi lain (mis. perangkat yang dicuri) lalu terbitkan token baru untuk sesi ini.
    await revoke_tokens(user["id"])
    await log_audit("user", user["id"], "password_change", user, None, None)
    return {"ok": True, "token": create_access_token(await db.users.find_one({"id": user["id"]}))}


@router.get("/student/dashboard")
async def student_dashboard(ctx: dict = Depends(get_current_student)):
    s, sid = ctx["student"], ctx["sid"]
    att = await attendance_summary(sid)
    pay = await payment_summary_map([sid])
    total = fee_total(s)
    bayar = pay.get(sid, {}).get("bayar", 0)
    docs = await db.documents.find({"student_id": sid, "is_deleted": False}, {"_id": 0}).to_list(None)
    expiring = sum(1 for d in docs if d.get("tanggal_kadaluarsa"))
    notif = await _own_notifications(sid, ctx["user"]["id"], limit=5)
    unread = await _own_unread_count(sid, ctx["user"]["id"])
    kelas_nama = None
    if s.get("class_id"):
        c = await db.classes.find_one({"id": s["class_id"]}, {"_id": 0, "nama": 1})
        kelas_nama = c.get("nama") if c else None
    return {
        "profile": {"nama": s.get("nama_lengkap"), "status": s.get("status"), "kelas": kelas_nama},
        "academic": {"kehadiran": att.get("persentase"), "nilai_rata": await grade_average(sid)},
        "finance": {"total": total, "bayar": bayar, "sisa": max(total - bayar, 0),
                    "jatuh_tempo": s.get("jatuh_tempo")},
        "documents": {"total": len(docs), "with_expiry": expiring},
        "notifications": {"unread": unread, "recent": notif},
        "whatsapp": {"opt_in": bool(s.get("wa_student_opt_in", False))},
    }


@router.get("/student/profile")
async def student_profile(ctx: dict = Depends(get_current_student)):
    s = ctx["student"]
    if s.get("class_id"):
        c = await db.classes.find_one({"id": s["class_id"]}, {"_id": 0, "nama": 1})
        s = {**s, "kelas_nama": c.get("nama") if c else None}
    return _profile(s)


@router.get("/student/class")
async def student_class(ctx: dict = Depends(get_current_student)):
    s = ctx["student"]
    if not s.get("class_id"):
        return {"kelas": None, "jadwal": []}
    c = await db.classes.find_one({"id": s["class_id"]}, {"_id": 0})
    if not c:
        return {"kelas": None, "jadwal": []}
    guru = None
    if c.get("guru_id"):
        g = await db.employees.find_one({"id": c["guru_id"]}, {"_id": 0, "nama": 1})
        guru = g.get("nama") if g else None
    return {"kelas": {"id": c["id"], "nama": c.get("nama"), "guru": guru, "ruangan": c.get("ruangan"),
                      "materi": c.get("materi"), "level": c.get("level")},
            "jadwal": c.get("jadwal") or []}


@router.get("/student/attendance")
async def student_attendance(ctx: dict = Depends(get_current_student)):
    sid = ctx["sid"]
    rows = await db.attendance.find({"student_id": sid}, {"_id": 0}).sort("tanggal", -1).to_list(None)
    return {"recap": await attendance_summary(sid),
            "rows": [{k: r.get(k) for k in ("tanggal", "status", "jam_masuk", "jam_pulang", "keterangan")} for r in rows]}


@router.get("/student/grades")
async def student_grades(ctx: dict = Depends(get_current_student)):
    sid = ctx["sid"]
    rows = await db.grades.find({"student_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return {"rows": [{k: r.get(k) for k in ("periode", "komponen", "nilai_akhir", "catatan", "created_at")} for r in rows]}


@router.get("/student/exams")
async def student_exams(ctx: dict = Depends(get_current_student)):
    sid = ctx["sid"]
    exams = await db.exams.find({"results.student_id": sid}, {"_id": 0}).sort("tanggal", 1).to_list(None)
    out = []
    for e in exams:
        nilai = next((r["nilai"] for r in e.get("results", []) if r.get("student_id") == sid), None)
        out.append({"exam_id": e["id"], "nama": e.get("nama"), "jenis": e.get("jenis"),
                    "tanggal": e.get("tanggal"), "passing_grade": e.get("passing_grade", 70),
                    "nilai": nilai, "lulus": nilai is not None and nilai >= e.get("passing_grade", 70)})
    return {"rows": out}


@router.get("/student/payments")
async def student_payments(ctx: dict = Depends(get_current_student)):
    s, sid = ctx["student"], ctx["sid"]
    pay = await payment_summary_map([sid])
    total = fee_total(s)
    bayar = pay.get(sid, {}).get("bayar", 0)
    rows = await db.payments.find({"student_id": sid}, {"_id": 0}).sort("tanggal", -1).to_list(None)
    return {"fee_plan": s.get("fee_plan") or [], "total": total, "bayar": bayar,
            "sisa": max(total - bayar, 0), "jatuh_tempo": s.get("jatuh_tempo"),
            "rows": [_pay_view(p) for p in rows]}


@router.get("/student/payments/{pay_id}")
async def student_payment_detail(pay_id: str, ctx: dict = Depends(get_current_student)):
    p = await db.payments.find_one({"id": pay_id, "student_id": ctx["sid"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    return _pay_view(p)


@router.get("/student/documents")
async def student_documents(ctx: dict = Depends(get_current_student)):
    sid = ctx["sid"]
    docs = await db.documents.find({"student_id": sid, "is_deleted": False}, {"_id": 0}).to_list(None)
    by_jenis = {d["jenis"]: d for d in docs}
    out = []
    for kategori, jenis in DOC_TYPES:
        d = by_jenis.get(jenis)
        if d:
            out.append({k: d.get(k) for k in ("id", "kategori", "jenis", "status", "tanggal_upload",
                                             "tanggal_kadaluarsa", "original_filename",
                                             "rejected_reason", "has_file")} | {"has_file": bool(d.get("file_id"))})
        else:
            out.append({"id": None, "kategori": kategori, "jenis": jenis, "status": "belum",
                        "tanggal_upload": None, "tanggal_kadaluarsa": None, "has_file": False})
    return {"rows": out}


@router.post("/student/documents")
async def student_doc_upload(jenis: str = Form(...), file: UploadFile = File(None),
                             ctx: dict = Depends(get_current_student)):
    """Upload dokumen milik sendiri. student_id diambil dari sesi login (ctx.sid),
    bukan dari frontend. Selalu pending_verification; verifikasi tetap staf-side."""
    sid, user = ctx["sid"], ctx["user"]
    known = {j: k for k, j in DOC_TYPES}
    if jenis not in known:
        raise HTTPException(status_code=400, detail="Jenis dokumen tidak dikenal")
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Pilih file terlebih dahulu (PDF/JPG/PNG/WebP, maks 10MB)")
    try:
        file_rec = await save_upload(file, user, "dokumen", allowed_exts=ALLOWED_DOC_EXTENSIONS, scope=sid)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upload gagal: {e}")
    doc = {"id": new_id(), "student_id": sid, "jenis": jenis, "kategori": known[jenis], "status": "pending_verification",
           "file_id": file_rec["id"], "original_filename": file_rec["original_filename"],
           "content_type": file_rec["content_type"],
           "tanggal_upload": today_str(), "tanggal_kadaluarsa": None, "uploaded_by": user["name"],
           "verified_by": None, "verified_at": None, "verification_note": "",
           "rejected_reason": "", "is_deleted": False, "created_at": now_iso()}
    old = await db.documents.find({"student_id": sid, "jenis": jenis, "is_deleted": False}, {"_id": 0, "file_id": 1}).to_list(None)
    try:
        await db.documents.update_many({"student_id": sid, "jenis": jenis, "is_deleted": False}, {"$set": {"is_deleted": True}})
        await db.documents.insert_one(doc)
    except Exception:
        try:
            doc_storage.delete(file_rec["storage_path"])
        except Exception:
            pass
        try:
            await db.files.delete_one({"id": file_rec["id"]})
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Upload gagal: metadata tidak dapat disimpan")
    for o in old:
        if o.get("file_id"):
            try:
                rec = await db.files.find_one({"id": o["file_id"]}, {"_id": 0, "storage_path": 1})
                if rec:
                    doc_storage.delete(rec["storage_path"])
                    await db.files.update_one({"id": o["file_id"]}, {"$set": {"is_deleted": True}})
            except Exception:
                pass
    await log_audit("document", doc["id"], "upload", user, None, {"student_id": sid, "jenis": jenis})
    return clean(doc)


@router.get("/student/documents/{doc_id}/download")
async def student_doc_download(doc_id: str, ctx: dict = Depends(get_current_student)):
    sid = ctx["sid"]
    d = await db.documents.find_one({"id": doc_id, "student_id": sid, "is_deleted": False}, {"_id": 0})
    if not d or not d.get("file_id"):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    rec = await db.files.find_one({"id": d["file_id"], "is_deleted": False})
    if not rec:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    try:
        data, _ = doc_storage.open(rec["storage_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File tidak ditemukan di penyimpanan server")
    except Exception as e:
        logger.error(f"Gagal membaca file dokumen {doc_id}: {e}")
        raise HTTPException(status_code=502, detail="Gagal mengambil file")
    return file_response(data, rec)


@router.get("/student/departure")
async def student_departure(ctx: dict = Depends(get_current_student)):
    """Read-only ringkasan keberangkatan milik sendiri. Tanpa verify/decision."""
    from routers.departures import compute_readiness
    sid = ctx["sid"]
    p = await db.departure_profiles.find_one({"student_id": sid}, {"_id": 0})
    if not p:
        return {"profile": None, "readiness": None, "checklist": []}
    r = await compute_readiness(p)
    items = await db.departure_checklist.find({"departure_profile_id": p["id"]}, {"_id": 0}).to_list(None)
    safe = [{"requirement_code": i.get("requirement_code"), "requirement_name": i.get("requirement_name"),
             "status": i.get("status"),
             "verified_at": i.get("verified_at"),
             "has_exception": bool(i.get("status") == "exception")} for i in items]
    return {"profile": {"status": p.get("status"),
                        "target_departure_date": p.get("target_departure_date"),
                        "actual_departure_date": p.get("actual_departure_date"),
                        "destination": p.get("destination"),
                        "final_decision": p.get("final_decision")},
            "readiness": {"readiness_status": r["readiness_status"],
                          "checklist_verified": r["checklist_verified"],
                          "checklist_total": r["checklist_total"],
                          "blockers": [b for b in r["blockers"] if "Rp" not in b],
                          "warnings": r["warnings"],
                          "days_to_departure": r["days_to_departure"]},
            "checklist": safe}


async def _own_notification_ids(sid: str) -> set:
    doc_ids = {d["id"] async for d in db.documents.find({"student_id": sid}, {"_id": 0, "id": 1})}
    iv_ids = {i["id"] async for i in db.interviews.find({"student_id": sid}, {"_id": 0, "id": 1})}
    return doc_ids, iv_ids


async def _own_notifications(sid: str, user_id: str, limit: int = 100):
    doc_ids, iv_ids = await _own_notification_ids(sid)
    rows = await db.notifications.find({}, {"_id": 0}).sort("tanggal", -1).to_list(None)
    out = []
    for n in rows:
        et, eid = n.get("entity_type"), n.get("entity_id")
        mine = (et == "student" and eid == sid) or (et == "document" and eid in doc_ids) or \
               (et == "interview" and eid in iv_ids)
        if not mine:
            continue
        out.append({**{k: n.get(k) for k in ("id", "tipe", "level", "judul", "pesan", "tanggal")},
                    "read": user_id in (n.get("read_by") or [])})
        if len(out) >= limit:
            break
    return out


async def _own_unread_count(sid: str, user_id: str) -> int:
    return sum(1 for n in await _own_notifications(sid, user_id, limit=2000) if not n["read"])


@router.get("/student/notifications")
async def student_notifications(ctx: dict = Depends(get_current_student)):
    rows = await _own_notifications(ctx["sid"], ctx["user"]["id"])
    return {"unread": sum(1 for r in rows if not r["read"]), "rows": rows}


@router.post("/student/notifications/{notif_id}/read")
async def student_notif_read(notif_id: str, ctx: dict = Depends(get_current_student)):
    sid, user = ctx["sid"], ctx["user"]
    n = await db.notifications.find_one({"id": notif_id}, {"_id": 0})
    if not n:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    doc_ids, iv_ids = await _own_notification_ids(sid)
    mine = (n.get("entity_type") == "student" and n.get("entity_id") == sid) or \
           (n.get("entity_type") == "document" and n.get("entity_id") in doc_ids) or \
           (n.get("entity_type") == "interview" and n.get("entity_id") in iv_ids)
    if not mine:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    await db.notifications.update_one({"id": notif_id}, {"$addToSet": {"read_by": user["id"]}})
    return {"ok": True}


@router.post("/student/notifications/read-all")
async def student_notif_read_all(ctx: dict = Depends(get_current_student)):
    sid, user = ctx["sid"], ctx["user"]
    rows = await _own_notifications(sid, user["id"], limit=2000)
    ids = [r["id"] for r in rows if not r["read"]]
    if ids:
        await db.notifications.update_many({"id": {"$in": ids}}, {"$addToSet": {"read_by": user["id"]}})
    return {"ok": True, "marked": len(ids)}


@router.get("/student/whatsapp-consent")
async def student_wa_consent(ctx: dict = Depends(get_current_student_lenient)):
    s = ctx["student"]
    return {"wa_student_phone": s.get("wa_student_phone"), "wa_student_opt_in": bool(s.get("wa_student_opt_in", False)),
            "wa_guardian_phone": s.get("wa_guardian_phone"),
            "wa_guardian_opt_in": bool(s.get("wa_guardian_opt_in", False))}


@router.put("/student/whatsapp-consent")
async def student_wa_consent_update(body: PortalConsentIn, ctx: dict = Depends(get_current_student)):
    sid, user = ctx["sid"], ctx["user"]
    before = bool(ctx["student"].get("wa_student_opt_in", False))
    if before != body.wa_student_opt_in:
        await db.students.update_one({"id": sid}, {"$set": {"wa_student_opt_in": body.wa_student_opt_in}})
        await log_audit("student", sid, "wa_consent", user, {"wa_student_opt_in": before},
                        {"wa_student_opt_in": body.wa_student_opt_in})
    return {"ok": True, "wa_student_opt_in": body.wa_student_opt_in}
