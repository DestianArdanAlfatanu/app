from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Header
from fastapi.responses import Response
from pydantic import BaseModel

from core import (db, require_roles, get_current_user, deny_student, new_id, now_iso, today_str, clean, clean_list, log_audit,
                  STUDENT_STATUSES, DOC_TYPES, payment_summary_map, fee_total, attendance_summary, grade_average,
                  doc_progress, compute_age, save_upload, user_from_token)
from document_storage import storage as doc_storage, ALLOWED_DOC_EXTENSIONS

router = APIRouter()
WRITE = require_roles("admin", "marketing", "staff")
READ = require_roles("admin", "marketing", "staff", "finance", "hr", "guru")
# Role yang boleh melihat data pembayaran siswa (konsisten dengan modul pembayaran & reports).
FIN_VISIBLE = ("owner", "admin", "finance", "hr")
# P1.2: sumber prospek terkontrol (controlled free-text).
SUMBER_PROSPEK = ["referral", "sosmed", "iklan", "sekolah", "kunjungan", "lainnya"]


class StudentIn(BaseModel):
    nama_lengkap: str
    nik: Optional[str] = ""
    no_kk: Optional[str] = ""
    tempat_lahir: Optional[str] = ""
    tanggal_lahir: Optional[str] = None
    jenis_kelamin: Optional[str] = "L"
    alamat: Optional[Dict[str, str]] = {}
    no_hp: Optional[str] = ""
    email: Optional[str] = ""
    nama_orang_tua: Optional[str] = ""
    no_hp_orang_tua: Optional[str] = ""
    pendidikan_terakhir: Optional[str] = ""
    nama_sekolah: Optional[str] = ""
    jurusan: Optional[str] = ""
    tahun_lulus: Optional[str] = ""
    tinggi_badan: Optional[float] = None
    berat_badan: Optional[float] = None
    status_pernikahan: Optional[str] = "belum_menikah"
    riwayat_pekerjaan: Optional[str] = ""
    riwayat_kesehatan: Optional[str] = ""
    kemampuan_bahasa_jepang: Optional[str] = "-"
    status: Optional[str] = "calon_siswa"
    fee_plan: Optional[List[Dict[str, Any]]] = None
    jatuh_tempo: Optional[str] = None
    catatan: Optional[str] = ""
    sumber_prospek: Optional[str] = ""
    pemilik_lead: Optional[str] = ""
    wa_student_phone: Optional[str] = ""
    wa_guardian_phone: Optional[str] = ""
    wa_student_opt_in: Optional[bool] = None
    wa_guardian_opt_in: Optional[bool] = None
    wa_student_verified_at: Optional[str] = None
    wa_guardian_verified_at: Optional[str] = None


def apply_wa_contact(doc: dict, existing: Optional[dict] = None) -> dict:
    """Normalisasi non-destruktif: source no_hp* dipertahankan, representasi wa_* diperbarui.
    Nilai consent None berarti 'jangan ubah' (update); saat create diisi False."""
    from routers.whatsapp import normalize_phone
    base = existing or {}
    if doc.get("no_hp"):
        doc["wa_student_phone"] = normalize_phone(doc["no_hp"]) or ""
    elif not doc.get("wa_student_phone"):
        doc["wa_student_phone"] = base.get("wa_student_phone", "")
    if doc.get("no_hp_orang_tua"):
        doc["wa_guardian_phone"] = normalize_phone(doc["no_hp_orang_tua"]) or ""
    elif not doc.get("wa_guardian_phone"):
        doc["wa_guardian_phone"] = base.get("wa_guardian_phone", "")
    if doc.get("wa_student_opt_in") is None:
        doc["wa_student_opt_in"] = base.get("wa_student_opt_in", False)
    if doc.get("wa_guardian_opt_in") is None:
        doc["wa_guardian_opt_in"] = base.get("wa_guardian_opt_in", False)
    if doc.get("wa_student_verified_at") is None:
        doc["wa_student_verified_at"] = base.get("wa_student_verified_at")
    if doc.get("wa_guardian_verified_at") is None:
        doc["wa_guardian_verified_at"] = base.get("wa_guardian_verified_at")
    return doc


class StatusIn(BaseModel):
    status: str
    catatan: Optional[str] = ""


class SelectionIn(BaseModel):
    jenis: str
    hasil: str
    nilai: Optional[float] = None
    catatan: Optional[str] = ""
    tanggal: Optional[str] = None


class FeePlanIn(BaseModel):
    items: List[Dict[str, Any]]
    jatuh_tempo: Optional[str] = None


class DocStatusIn(BaseModel):
    jenis: str
    kategori: str
    status: str
    tanggal_kadaluarsa: Optional[str] = None


class DocVerifyIn(BaseModel):
    note: Optional[str] = ""


class DocRejectIn(BaseModel):
    reason: str


DEFAULT_FEE_PLAN = [
    {"nama": "Pendaftaran", "nominal": 500000}, {"nama": "Pelatihan", "nominal": 8000000},
    {"nama": "Asrama", "nominal": 3000000}, {"nama": "Dokumen", "nominal": 2000000},
    {"nama": "Keberangkatan", "nominal": 5000000},
]


async def enrich(students: list, user: Optional[dict] = None) -> list:
    ids = [s["id"] for s in students]
    show_pay = (user or {}).get("role", "owner") in FIN_VISIBLE
    pay = await payment_summary_map(ids) if show_pay else {}
    classes = {c["id"]: c["nama"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(500)}
    out = []
    for s in students:
        total = fee_total(s)
        bayar = pay.get(s["id"], {}).get("bayar", 0)
        if show_pay:
            s["pembayaran"] = {"total": total, "bayar": bayar, "sisa": max(total - bayar, 0)}
        s["kelas_nama"] = classes.get(s.get("class_id"))
        s["usia"] = compute_age(s.get("tanggal_lahir"))
        out.append(s)
    return out


@router.get("/students")
async def list_students(status: Optional[str] = None, q: Optional[str] = None, class_id: Optional[str] = None,
                        user: dict = Depends(READ)):
    query: Dict[str, Any] = {}
    if status:
        query["status"] = {"$in": status.split(",")}
    if class_id:
        query["class_id"] = class_id
    if q:
        query["$or"] = [{"nama_lengkap": {"$regex": q, "$options": "i"}}, {"nik": {"$regex": q}}, {"no_hp": {"$regex": q}}]
    if user["role"] == "guru" and not class_id:
        emp_classes = await db.classes.find({"guru_id": user.get("employee_id")}, {"_id": 0, "id": 1}).to_list(100)
        query["class_id"] = {"$in": [c["id"] for c in emp_classes]}
    rows = await db.students.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return await enrich(rows, user)


@router.post("/students")
async def create_student(body: StudentIn, user: dict = Depends(WRITE)):
    if body.status not in STUDENT_STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak valid")
    if body.sumber_prospek and body.sumber_prospek not in SUMBER_PROSPEK:
        raise HTTPException(status_code=400, detail="Sumber prospek tidak valid")
    if body.nik and await db.students.find_one({"nik": body.nik}):
        raise HTTPException(status_code=400, detail="NIK sudah terdaftar")
    doc = body.model_dump()
    doc = apply_wa_contact(doc)
    doc.update({"id": new_id(), "fee_plan": body.fee_plan or DEFAULT_FEE_PLAN, "class_id": None,
                "status_history": [{"status": body.status, "tanggal": now_iso(), "oleh": user["name"], "catatan": "Pendaftaran awal"}],
                "created_at": now_iso(), "created_by": user["name"]})
    await db.students.insert_one(doc)
    await log_audit("student", doc["id"], "create", user, None, {"nama": doc["nama_lengkap"], "status": doc["status"]})
    return (await enrich([clean(doc)], user))[0]


@router.get("/students/{student_id}")
async def get_student(student_id: str, user: dict = Depends(READ)):
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    if user["role"] == "guru":
        emp_classes = await db.classes.find({"guru_id": user.get("employee_id")}, {"_id": 0, "id": 1}).to_list(100)
        if s.get("class_id") not in [c["id"] for c in emp_classes]:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke siswa ini")
    s = (await enrich([s], user))[0]
    s["absensi"] = await attendance_summary(student_id)
    s["nilai_rata"] = await grade_average(student_id)
    s["dokumen"] = await doc_progress(student_id)
    if user["role"] in FIN_VISIBLE:
        s["payments"] = await db.payments.find({"student_id": student_id}, {"_id": 0}).sort("tanggal", -1).to_list(200)
    else:
        s["payments"] = []
    s["selections"] = await db.selections.find({"student_id": student_id}, {"_id": 0}).sort("tanggal", -1).to_list(100)
    s["grades"] = await db.grades.find({"student_id": student_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    s["attendance_rows"] = await db.attendance.find({"student_id": student_id}, {"_id": 0}).sort("tanggal", -1).to_list(60)
    s["interviews"] = await db.interviews.find({"student_id": student_id}, {"_id": 0}).sort("tanggal", -1).to_list(50)
    exams = await db.exams.find({"results.student_id": student_id}, {"_id": 0}).sort("tanggal", 1).to_list(100)
    s["exam_results"] = [{"exam_id": e["id"], "nama": e["nama"], "jenis": e["jenis"], "tanggal": e["tanggal"], "passing_grade": e.get("passing_grade", 70),
                          "nilai": next((r["nilai"] for r in e["results"] if r["student_id"] == student_id), None)} for e in exams]
    if s.get("class_id"):
        s["kelas"] = await db.classes.find_one({"id": s["class_id"]}, {"_id": 0})
    return s


@router.put("/students/{student_id}")
async def update_student(student_id: str, body: StudentIn, user: dict = Depends(WRITE)):
    existing = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    if body.sumber_prospek and body.sumber_prospek not in SUMBER_PROSPEK:
        raise HTTPException(status_code=400, detail="Sumber prospek tidak valid")
    upd = body.model_dump(exclude={"status", "fee_plan"})
    upd = apply_wa_contact(upd, existing)
    await db.students.update_one({"id": student_id}, {"$set": upd})
    diff_before = {k: existing.get(k) for k in upd if existing.get(k) != upd[k]}
    diff_after = {k: upd[k] for k in diff_before}
    if diff_before:
        await log_audit("student", student_id, "update", user, diff_before, diff_after)
    return (await enrich([await db.students.find_one({"id": student_id}, {"_id": 0})], user))[0]


@router.delete("/students/{student_id}")
async def delete_student(student_id: str, user: dict = Depends(require_roles("admin"))):
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    await db.students.delete_one({"id": student_id})
    await log_audit("student", student_id, "delete", user, {"nama": s["nama_lengkap"]}, None)
    return {"ok": True}


@router.put("/students/{student_id}/status")
async def change_status(student_id: str, body: StatusIn, user: dict = Depends(WRITE)):
    if body.status not in STUDENT_STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak valid")
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    hist = {"status": body.status, "tanggal": now_iso(), "oleh": user["name"], "catatan": body.catatan}
    await db.students.update_one({"id": student_id}, {"$set": {"status": body.status}, "$push": {"status_history": hist}})
    await log_audit("student", student_id, "status", user, {"status": s["status"]}, {"status": body.status}, body.catatan or "")
    return {"ok": True, "status": body.status}


@router.put("/students/{student_id}/fee-plan")
async def set_fee_plan(student_id: str, body: FeePlanIn, user: dict = Depends(require_roles("admin", "finance"))):
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    items = [{"nama": i["nama"], "nominal": float(i["nominal"])} for i in body.items]
    upd = {"fee_plan": items}
    if body.jatuh_tempo is not None:
        upd["jatuh_tempo"] = body.jatuh_tempo
    await db.students.update_one({"id": student_id}, {"$set": upd})
    await log_audit("student", student_id, "fee_plan", user, {"total": fee_total(s)}, {"total": sum(i["nominal"] for i in items)})
    return {"ok": True, "total": sum(i["nominal"] for i in items)}


# ---------- Seleksi ----------
@router.post("/students/{student_id}/selections")
async def add_selection(student_id: str, body: SelectionIn, user: dict = Depends(WRITE)):
    if not await db.students.find_one({"id": student_id}):
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    doc = {**body.model_dump(), "id": new_id(), "student_id": student_id, "tanggal": body.tanggal or today_str(),
           "petugas": user["name"], "created_at": now_iso()}
    await db.selections.insert_one(doc)
    await log_audit("selection", doc["id"], "create", user, None, {"jenis": body.jenis, "hasil": body.hasil, "student_id": student_id})
    return clean(doc)


@router.delete("/selections/{sel_id}")
async def delete_selection(sel_id: str, user: dict = Depends(WRITE)):
    await db.selections.delete_one({"id": sel_id})
    return {"ok": True}


# ---------- Dokumen ----------
@router.get("/students/{student_id}/documents")
async def list_documents(student_id: str, user: dict = Depends(READ)):
    docs = await db.documents.find({"student_id": student_id, "is_deleted": False}, {"_id": 0}).to_list(200)
    by_jenis = {d["jenis"]: d for d in docs}
    out = []
    for kategori, jenis in DOC_TYPES:
        d = by_jenis.get(jenis)
        out.append(d or {"id": None, "student_id": student_id, "kategori": kategori, "jenis": jenis, "status": "belum",
                         "file_id": None, "tanggal_upload": None, "tanggal_kadaluarsa": None, "uploaded_by": None})
    for d in docs:
        if d["jenis"] not in dict((j, k) for k, j in DOC_TYPES):
            out.append(d)
    return out


@router.post("/students/{student_id}/documents")
async def upload_document(student_id: str, jenis: str = Form(...), kategori: str = Form("lainnya"),
                          tanggal_kadaluarsa: Optional[str] = Form(None), file: Optional[UploadFile] = File(None),
                          user: dict = Depends(WRITE)):
    if not await db.students.find_one({"id": student_id}):
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    file_rec = None
    if file and file.filename:
        try:
            file_rec = await save_upload(file, user, "dokumen", allowed_exts=ALLOWED_DOC_EXTENSIONS, scope=student_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upload gagal: {e}")
    doc = {"id": new_id(), "student_id": student_id, "jenis": jenis, "kategori": kategori, "status": "pending_verification",
           "file_id": file_rec["id"] if file_rec else None, "original_filename": file_rec["original_filename"] if file_rec else None,
           "content_type": file_rec["content_type"] if file_rec else None,
           "tanggal_upload": today_str(), "tanggal_kadaluarsa": tanggal_kadaluarsa or None, "uploaded_by": user["name"],
           "verified_by": None, "verified_at": None, "verification_note": "",
           "rejected_reason": "", "is_deleted": False, "created_at": now_iso()}
    old = await db.documents.find({"student_id": student_id, "jenis": jenis, "is_deleted": False}, {"_id": 0, "file_id": 1}).to_list(50)
    try:
        await db.documents.update_many({"student_id": student_id, "jenis": jenis, "is_deleted": False}, {"$set": {"is_deleted": True}})
        await db.documents.insert_one(doc)
    except Exception:
        if file_rec:
            try:
                doc_storage.delete(file_rec["storage_path"])
            except Exception:
                pass
            try:
                await db.files.delete_one({"id": file_rec["id"]})
            except Exception:
                pass
        raise HTTPException(status_code=502, detail="Upload gagal: metadata tidak dapat disimpan")
    if file_rec and old:
        for o in old:
            if o.get("file_id"):
                try:
                    rec = await db.files.find_one({"id": o["file_id"]}, {"_id": 0, "storage_path": 1})
                    if rec:
                        doc_storage.delete(rec["storage_path"])
                        await db.files.update_one({"id": o["file_id"]}, {"$set": {"is_deleted": True}})
                except Exception:
                    pass
    await log_audit("document", doc["id"], "upload", user, None, {"student_id": student_id, "jenis": jenis})
    return clean(doc)


@router.put("/students/{student_id}/documents/status")
async def set_doc_status(student_id: str, body: DocStatusIn, user: dict = Depends(WRITE)):
    if body.status == "belum":
        await db.documents.update_many({"student_id": student_id, "jenis": body.jenis, "is_deleted": False}, {"$set": {"is_deleted": True}})
        return {"ok": True}
    existing = await db.documents.find_one({"student_id": student_id, "jenis": body.jenis, "is_deleted": False})
    if existing:
        await db.documents.update_one({"id": existing["id"]}, {"$set": {"status": body.status, "tanggal_kadaluarsa": body.tanggal_kadaluarsa}})
        return clean(await db.documents.find_one({"id": existing["id"]}, {"_id": 0}))
    doc = {"id": new_id(), "student_id": student_id, "jenis": body.jenis, "kategori": body.kategori, "status": body.status,
           "file_id": None, "tanggal_upload": today_str(), "tanggal_kadaluarsa": body.tanggal_kadaluarsa, "uploaded_by": user["name"],
           "is_deleted": False, "created_at": now_iso()}
    await db.documents.insert_one(doc)
    return clean(doc)


@router.put("/students/{student_id}/documents/{doc_id}/verify")
async def verify_document(student_id: str, doc_id: str, body: DocVerifyIn, user: dict = Depends(WRITE)):
    doc = await db.documents.find_one({"id": doc_id, "student_id": student_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    await db.documents.update_one({"id": doc_id}, {"$set": {"status": "verified",
        "verified_by": user["name"], "verified_at": now_iso(),
        "verification_note": (body.note or "").strip(), "rejected_reason": ""}})
    await log_audit("document", doc_id, "verify", user, {"status": doc.get("status")}, {"status": "verified"})
    return clean(await db.documents.find_one({"id": doc_id}, {"_id": 0}))


@router.put("/students/{student_id}/documents/{doc_id}/reject")
async def reject_document(student_id: str, doc_id: str, body: DocRejectIn, user: dict = Depends(WRITE)):
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi")
    doc = await db.documents.find_one({"id": doc_id, "student_id": student_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    await db.documents.update_one({"id": doc_id}, {"$set": {"status": "rejected",
        "rejected_reason": body.reason.strip(), "verified_by": None, "verified_at": None}})
    await log_audit("document", doc_id, "reject", user, {"status": doc.get("status")},
                    {"status": "rejected"}, body.reason.strip())
    return clean(await db.documents.find_one({"id": doc_id}, {"_id": 0}))


@router.get("/files/{file_id}")
async def download_file(file_id: str, authorization: str = Header(None), auth: str = Query(None)):
    token = auth or (authorization[7:] if authorization and authorization.startswith("Bearer ") else None)
    if not token:
        raise HTTPException(status_code=401, detail="Belum login")
    deny_student(await user_from_token(token))
    rec = await db.files.find_one({"id": file_id, "is_deleted": False})
    if not rec:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    try:
        data, _ = doc_storage.open(rec["storage_path"])
        ct = rec.get("content_type") or "application/octet-stream"
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File tidak ditemukan di penyimpanan server")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal mengambil file: {e}")
    return Response(content=data, media_type=rec.get("content_type") or ct,
                    headers={"Content-Disposition": f'inline; filename="{rec["original_filename"]}"'})


@router.post("/upload")
async def generic_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    deny_student(user)
    try:
        return await save_upload(file, user, "bukti")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upload gagal: {e}")
