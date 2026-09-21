from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import db, require_roles, new_id, now_iso, clean, log_audit

router = APIRouter()
HR = require_roles("hr")
HR_READ = require_roles("hr", "admin", "finance", "guru", "marketing", "staff")


class EmployeeIn(BaseModel):
    nama: str
    tipe: str = "karyawan"
    nik: Optional[str] = ""
    jabatan: Optional[str] = ""
    no_hp: Optional[str] = ""
    email: Optional[str] = ""
    alamat: Optional[str] = ""
    tanggal_masuk: Optional[str] = None
    status_kerja: Optional[str] = "tetap"
    gaji_pokok: Optional[float] = 0
    tunjangan: Optional[float] = 0
    honor_per_pertemuan: Optional[float] = 0
    spesialisasi: Optional[str] = ""
    sertifikat: Optional[List[str]] = []
    kontrak_berakhir: Optional[str] = None
    aktif: bool = True


@router.get("/employees")
async def list_employees(tipe: Optional[str] = None, user: dict = Depends(HR_READ)):
    q = {"tipe": tipe} if tipe else {}
    rows = await db.employees.find(q, {"_id": 0}).sort("nama", 1).to_list(1000)
    classes = await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1, "guru_id": 1, "jadwal": 1, "status": 1}).to_list(500)
    if user["role"] not in ("owner", "hr", "admin", "finance"):
        for r in rows:
            r.pop("gaji_pokok", None); r.pop("tunjangan", None); r.pop("honor_per_pertemuan", None); r.pop("nik", None)
    for r in rows:
        r["kelas"] = [c for c in classes if c.get("guru_id") == r["id"]]
    return rows


@router.post("/employees")
async def create_employee(body: EmployeeIn, user: dict = Depends(HR)):
    doc = {**body.model_dump(), "id": new_id(), "created_at": now_iso()}
    await db.employees.insert_one(doc)
    await log_audit("employee", doc["id"], "create", user, None, {"nama": body.nama, "tipe": body.tipe})
    return clean(doc)


@router.put("/employees/{emp_id}")
async def update_employee(emp_id: str, body: EmployeeIn, user: dict = Depends(HR)):
    old = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    upd = body.model_dump()
    await db.employees.update_one({"id": emp_id}, {"$set": upd})
    before = {k: old.get(k) for k in ("gaji_pokok", "jabatan", "status_kerja", "aktif") if old.get(k) != upd.get(k)}
    if before:
        await log_audit("employee", emp_id, "update", user, before, {k: upd[k] for k in before})
    return clean(await db.employees.find_one({"id": emp_id}, {"_id": 0}))


@router.delete("/employees/{emp_id}")
async def delete_employee(emp_id: str, user: dict = Depends(HR)):
    await db.employees.delete_one({"id": emp_id})
    await log_audit("employee", emp_id, "delete", user)
    return {"ok": True}
