from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import db, require_roles, new_id, now_iso, clean, log_audit, compute_age, JLPT_ORDER, payment_summary_map, fee_total, grade_average

router = APIRouter()
WRITE = require_roles("admin", "marketing")
READ = require_roles("admin", "marketing", "staff", "finance", "hr", "guru")


class JobOrderIn(BaseModel):
    perusahaan: str
    posisi: str
    lokasi: Optional[str] = ""
    jumlah_kebutuhan: int = 1
    gaji: Optional[str] = ""
    jam_kerja: Optional[str] = ""
    persyaratan: Optional[str] = ""
    usia_min: Optional[int] = 18
    usia_max: Optional[int] = 30
    jenis_kelamin: Optional[str] = "semua"
    min_jlpt: Optional[str] = "N4"
    jenis_pekerjaan: Optional[str] = ""
    tanggal_interview: Optional[str] = None
    status: Optional[str] = "terbuka"


class InterviewIn(BaseModel):
    job_order_id: str
    student_id: str
    tanggal: str
    hasil: Optional[str] = "menunggu"
    catatan: Optional[str] = ""


@router.get("/job-orders")
async def list_jobs(user: dict = Depends(READ)):
    rows = await db.job_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    ivs = await db.interviews.find({}, {"_id": 0, "job_order_id": 1, "hasil": 1}).to_list(5000)
    for r in rows:
        mine = [i for i in ivs if i["job_order_id"] == r["id"]]
        r["jumlah_kandidat"] = len(mine)
        r["jumlah_lulus"] = sum(1 for i in mine if i["hasil"] == "lulus")
    return rows


@router.post("/job-orders")
async def create_job(body: JobOrderIn, user: dict = Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "created_at": now_iso()}
    await db.job_orders.insert_one(doc)
    await log_audit("job_order", doc["id"], "create", user, None, {"perusahaan": body.perusahaan, "posisi": body.posisi})
    return clean(doc)


@router.put("/job-orders/{job_id}")
async def update_job(job_id: str, body: JobOrderIn, user: dict = Depends(WRITE)):
    if not await db.job_orders.find_one({"id": job_id}):
        raise HTTPException(status_code=404, detail="Job order tidak ditemukan")
    await db.job_orders.update_one({"id": job_id}, {"$set": body.model_dump()})
    return clean(await db.job_orders.find_one({"id": job_id}, {"_id": 0}))


@router.delete("/job-orders/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_roles("admin"))):
    await db.job_orders.delete_one({"id": job_id})
    return {"ok": True}


@router.get("/job-orders/{job_id}/candidates")
async def candidates(job_id: str, user: dict = Depends(READ)):
    job = await db.job_orders.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job order tidak ditemukan")
    students = await db.students.find({"status": {"$in": ["pelatihan", "ujian", "lulus", "matching"]}}, {"_id": 0}).to_list(5000)
    existing = {i["student_id"] for i in await db.interviews.find({"job_order_id": job_id}, {"_id": 0, "student_id": 1}).to_list(1000)}
    out = []
    for s in students:
        usia = compute_age(s.get("tanggal_lahir"))
        checks = {
            "usia": usia is not None and (job.get("usia_min") or 0) <= usia <= (job.get("usia_max") or 99),
            "jenis_kelamin": job.get("jenis_kelamin", "semua") == "semua" or s.get("jenis_kelamin") == job.get("jenis_kelamin"),
            "bahasa": JLPT_ORDER.get(s.get("kemampuan_bahasa_jepang", "-"), 0) >= JLPT_ORDER.get(job.get("min_jlpt", "-"), 0),
        }
        skor = sum(checks.values())
        out.append({"id": s["id"], "nama_lengkap": s["nama_lengkap"], "usia": usia, "jenis_kelamin": s.get("jenis_kelamin"),
                    "kemampuan_bahasa_jepang": s.get("kemampuan_bahasa_jepang"), "status": s["status"], "checks": checks,
                    "memenuhi": skor == 3, "skor": skor, "nilai_rata": await grade_average(s["id"]), "sudah_interview": s["id"] in existing})
    out.sort(key=lambda x: (-x["skor"], -(x["nilai_rata"] or 0)))
    return {"job": job, "candidates": out}


@router.get("/interviews")
async def list_interviews(job_order_id: Optional[str] = None, user: dict = Depends(READ)):
    q = {"job_order_id": job_order_id} if job_order_id else {}
    return await db.interviews.find(q, {"_id": 0}).sort("tanggal", -1).to_list(2000)


@router.post("/interviews")
async def create_interview(body: InterviewIn, user: dict = Depends(WRITE)):
    job = await db.job_orders.find_one({"id": body.job_order_id}, {"_id": 0})
    s = await db.students.find_one({"id": body.student_id}, {"_id": 0})
    if not job or not s:
        raise HTTPException(status_code=404, detail="Job order / siswa tidak ditemukan")
    doc = {**body.model_dump(), "id": new_id(), "perusahaan": job["perusahaan"], "posisi": job["posisi"],
           "student_nama": s["nama_lengkap"], "created_at": now_iso()}
    await db.interviews.insert_one(doc)
    if s["status"] in ("lulus", "ujian", "pelatihan"):
        await db.students.update_one({"id": s["id"]}, {"$set": {"status": "matching"}, "$push": {"status_history": {
            "status": "matching", "tanggal": now_iso(), "oleh": user["name"], "catatan": f"Dijadwalkan interview {job['perusahaan']}"}}})
    await log_audit("interview", doc["id"], "create", user, None, {"student": s["nama_lengkap"], "perusahaan": job["perusahaan"]})
    return clean(doc)


@router.put("/interviews/{iv_id}")
async def update_interview(iv_id: str, body: InterviewIn, user: dict = Depends(WRITE)):
    old = await db.interviews.find_one({"id": iv_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Interview tidak ditemukan")
    await db.interviews.update_one({"id": iv_id}, {"$set": {"tanggal": body.tanggal, "hasil": body.hasil, "catatan": body.catatan}})
    if body.hasil == "lulus" and old["hasil"] != "lulus":
        await db.students.update_one({"id": old["student_id"]}, {"$set": {"status": "pemberkasan", "job_order_id": old["job_order_id"]},
                                                                 "$push": {"status_history": {"status": "pemberkasan", "tanggal": now_iso(), "oleh": user["name"],
                                                                                              "catatan": f"Lulus interview {old['perusahaan']}"}}})
    await log_audit("interview", iv_id, "update", user, {"hasil": old["hasil"]}, {"hasil": body.hasil}, body.catatan or "")
    return clean(await db.interviews.find_one({"id": iv_id}, {"_id": 0}))
