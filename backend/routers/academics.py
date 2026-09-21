from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import db, require_roles, new_id, now_iso, today_str, clean, log_audit

router = APIRouter()
WRITE = require_roles("admin", "guru")
READ = require_roles("admin", "guru", "marketing", "staff", "hr", "finance")
GRADE_COMPONENTS = ["hiragana", "katakana", "kanji", "grammar", "listening", "speaking", "reading", "writing", "budaya", "kedisiplinan"]


class ClassIn(BaseModel):
    nama: str
    guru_id: Optional[str] = None
    jadwal: List[Dict[str, str]] = []
    ruangan: Optional[str] = ""
    materi: Optional[str] = ""
    level: Optional[str] = "Dasar"
    status: Optional[str] = "aktif"
    tanggal_mulai: Optional[str] = None
    tanggal_selesai: Optional[str] = None


class EnrollIn(BaseModel):
    student_ids: List[str]


class AttendanceIn(BaseModel):
    class_id: str
    tanggal: str
    records: List[Dict[str, str]]


class GradeIn(BaseModel):
    student_id: str
    class_id: Optional[str] = None
    periode: str
    komponen: Dict[str, float]
    catatan: Optional[str] = ""


class ExamIn(BaseModel):
    nama: str
    jenis: str
    tanggal: str
    class_id: Optional[str] = None
    passing_grade: float = 70
    keterangan: Optional[str] = ""


class ExamResultsIn(BaseModel):
    results: List[Dict[str, Any]]


async def with_teacher(classes: list) -> list:
    teachers = {t["id"]: t["nama"] for t in await db.employees.find({"tipe": "guru"}, {"_id": 0, "id": 1, "nama": 1}).to_list(500)}
    for c in classes:
        c["guru_nama"] = teachers.get(c.get("guru_id"))
        c["jumlah_siswa"] = len(c.get("student_ids", []))
    return classes


@router.get("/classes")
async def list_classes(user: dict = Depends(READ)):
    q = {"guru_id": user.get("employee_id")} if user["role"] == "guru" else {}
    return await with_teacher(await db.classes.find(q, {"_id": 0}).sort("created_at", -1).to_list(500))


@router.post("/classes")
async def create_class(body: ClassIn, user: dict = Depends(require_roles("admin"))):
    doc = {**body.model_dump(), "id": new_id(), "student_ids": [], "created_at": now_iso()}
    await db.classes.insert_one(doc)
    await log_audit("class", doc["id"], "create", user, None, {"nama": body.nama})
    return (await with_teacher([clean(doc)]))[0]


@router.get("/classes/{class_id}")
async def get_class(class_id: str, user: dict = Depends(READ)):
    c = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
    c = (await with_teacher([c]))[0]
    c["students"] = await db.students.find({"id": {"$in": c.get("student_ids", [])}}, {"_id": 0, "id": 1, "nama_lengkap": 1, "status": 1, "jenis_kelamin": 1}).to_list(500)
    return c


@router.put("/classes/{class_id}")
async def update_class(class_id: str, body: ClassIn, user: dict = Depends(require_roles("admin"))):
    if not await db.classes.find_one({"id": class_id}):
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
    await db.classes.update_one({"id": class_id}, {"$set": body.model_dump()})
    return (await with_teacher([await db.classes.find_one({"id": class_id}, {"_id": 0})]))[0]


@router.delete("/classes/{class_id}")
async def delete_class(class_id: str, user: dict = Depends(require_roles("admin"))):
    await db.classes.delete_one({"id": class_id})
    await db.students.update_many({"class_id": class_id}, {"$set": {"class_id": None}})
    await log_audit("class", class_id, "delete", user)
    return {"ok": True}


@router.post("/classes/{class_id}/students")
async def enroll(class_id: str, body: EnrollIn, user: dict = Depends(require_roles("admin"))):
    c = await db.classes.find_one({"id": class_id})
    if not c:
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
    await db.classes.update_one({"id": class_id}, {"$addToSet": {"student_ids": {"$each": body.student_ids}}})
    await db.students.update_many({"id": {"$in": body.student_ids}}, {"$set": {"class_id": class_id}})
    await log_audit("class", class_id, "enroll", user, None, {"student_ids": body.student_ids})
    return {"ok": True}


@router.delete("/classes/{class_id}/students/{student_id}")
async def unenroll(class_id: str, student_id: str, user: dict = Depends(require_roles("admin"))):
    await db.classes.update_one({"id": class_id}, {"$pull": {"student_ids": student_id}})
    await db.students.update_one({"id": student_id, "class_id": class_id}, {"$set": {"class_id": None}})
    return {"ok": True}


# ---------- Absensi ----------
@router.get("/attendance")
async def get_attendance(class_id: str, tanggal: Optional[str] = None, user: dict = Depends(READ)):
    q: Dict[str, Any] = {"class_id": class_id}
    if tanggal:
        q["tanggal"] = tanggal
    return await db.attendance.find(q, {"_id": 0}).sort("tanggal", -1).to_list(5000)


@router.post("/attendance")
async def save_attendance(body: AttendanceIn, user: dict = Depends(WRITE)):
    if user["role"] == "guru":
        c = await db.classes.find_one({"id": body.class_id})
        if not c or c.get("guru_id") != user.get("employee_id"):
            raise HTTPException(status_code=403, detail="Anda bukan pengajar kelas ini")
    for r in body.records:
        if r["status"] not in ("hadir", "izin", "sakit", "alfa"):
            raise HTTPException(status_code=400, detail="Status absensi tidak valid")
        await db.attendance.update_one(
            {"class_id": body.class_id, "student_id": r["student_id"], "tanggal": body.tanggal},
            {"$set": {"status": r["status"], "dicatat_oleh": user["name"], "updated_at": now_iso()},
             "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)
    await log_audit("attendance", body.class_id, "save", user, None, {"tanggal": body.tanggal, "jumlah": len(body.records)})
    return {"ok": True, "jumlah": len(body.records)}


@router.get("/attendance/recap")
async def attendance_recap(class_id: str, user: dict = Depends(READ)):
    pipeline = [{"$match": {"class_id": class_id}},
                {"$group": {"_id": {"s": "$student_id", "st": "$status"}, "n": {"$sum": 1}}}]
    rows = await db.attendance.aggregate(pipeline).to_list(10000)
    out: Dict[str, Dict[str, int]] = {}
    for r in rows:
        out.setdefault(r["_id"]["s"], {"hadir": 0, "izin": 0, "sakit": 0, "alfa": 0})[r["_id"]["st"]] = r["n"]
    for sid, c in out.items():
        total = sum(c.values())
        c["total"] = total
        c["persentase"] = round(c["hadir"] / total * 100, 1) if total else 0
    return out


# ---------- Nilai ----------
@router.get("/grades")
async def list_grades(student_id: Optional[str] = None, class_id: Optional[str] = None, user: dict = Depends(READ)):
    q: Dict[str, Any] = {}
    if student_id:
        q["student_id"] = student_id
    if class_id:
        q["class_id"] = class_id
    rows = await db.grades.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    names = {s["id"]: s["nama_lengkap"] for s in await db.students.find({"id": {"$in": [r["student_id"] for r in rows]}}, {"_id": 0, "id": 1, "nama_lengkap": 1}).to_list(2000)}
    for r in rows:
        r["student_nama"] = names.get(r["student_id"])
    return rows


@router.post("/grades")
async def create_grade(body: GradeIn, user: dict = Depends(WRITE)):
    vals = [v for v in body.komponen.values() if v is not None]
    if not vals:
        raise HTTPException(status_code=400, detail="Minimal satu komponen nilai")
    doc = {**body.model_dump(), "id": new_id(), "nilai_akhir": round(sum(vals) / len(vals), 1), "guru": user["name"], "created_at": now_iso()}
    await db.grades.insert_one(doc)
    await log_audit("grade", doc["id"], "create", user, None, {"student_id": body.student_id, "nilai_akhir": doc["nilai_akhir"]})
    return clean(doc)


@router.put("/grades/{grade_id}")
async def update_grade(grade_id: str, body: GradeIn, user: dict = Depends(WRITE)):
    old = await db.grades.find_one({"id": grade_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Nilai tidak ditemukan")
    vals = [v for v in body.komponen.values() if v is not None]
    upd = {**body.model_dump(), "nilai_akhir": round(sum(vals) / len(vals), 1) if vals else 0}
    await db.grades.update_one({"id": grade_id}, {"$set": upd})
    await log_audit("grade", grade_id, "update", user, {"nilai_akhir": old["nilai_akhir"]}, {"nilai_akhir": upd["nilai_akhir"]})
    return clean(await db.grades.find_one({"id": grade_id}, {"_id": 0}))


@router.delete("/grades/{grade_id}")
async def delete_grade(grade_id: str, user: dict = Depends(WRITE)):
    await db.grades.delete_one({"id": grade_id})
    return {"ok": True}


# ---------- Ujian ----------
@router.get("/exams")
async def list_exams(user: dict = Depends(READ)):
    rows = await db.exams.find({}, {"_id": 0}).sort("tanggal", -1).to_list(500)
    for e in rows:
        res = e.get("results", [])
        e["jumlah_peserta"] = len(res)
        e["rata_rata"] = round(sum(r["nilai"] for r in res) / len(res), 1) if res else None
        e["jumlah_lulus"] = sum(1 for r in res if r["nilai"] >= e.get("passing_grade", 70))
    return rows


@router.post("/exams")
async def create_exam(body: ExamIn, user: dict = Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "results": [], "created_at": now_iso()}
    await db.exams.insert_one(doc)
    return clean(doc)


@router.put("/exams/{exam_id}/results")
async def set_results(exam_id: str, body: ExamResultsIn, user: dict = Depends(WRITE)):
    if not await db.exams.find_one({"id": exam_id}):
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")
    results = [{"student_id": r["student_id"], "nilai": float(r["nilai"])} for r in body.results if r.get("nilai") not in (None, "")]
    await db.exams.update_one({"id": exam_id}, {"$set": {"results": results, "updated_at": now_iso()}})
    await log_audit("exam", exam_id, "results", user, None, {"jumlah": len(results)})
    return {"ok": True}


@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: str, user: dict = Depends(require_roles("admin"))):
    await db.exams.delete_one({"id": exam_id})
    return {"ok": True}
