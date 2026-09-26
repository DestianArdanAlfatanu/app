from typing import Optional, List, Dict, Any
from datetime import date, timedelta
import calendar
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pg_mongo import DuplicateKeyError

from core import db, require_roles, new_id, now_iso, today_str, today, clean, log_audit

router = APIRouter()
HR = require_roles("hr")
HR_READ = require_roles("hr", "admin", "finance", "guru", "marketing", "staff")
HR_ATT_READ = require_roles("hr", "admin")
HR_ATT_WRITE = require_roles("hr")
LEAVE_READ = require_roles("hr", "admin")
LEAVE_CREATE = require_roles("hr", "admin")
LEAVE_DECIDE = require_roles("hr")
PAYROLL_READ = require_roles("hr", "admin", "finance")
PAYROLL_WRITE = require_roles("hr")
PAYROLL_APPROVE = require_roles("owner")
PAYROLL_PAY = require_roles("finance")

LEAVE_STATUSES = ["menunggu", "disetujui", "ditolak"]
LEAVE_ACTIVE = ["menunggu", "disetujui"]

# Status absensi karyawan. "cuti" disiapkan untuk forward compatibility fase
# Leave berikutnya, tetapi tidak ditawarkan di UI tahap ini.
HR_ATT_STATUSES = ["hadir", "terlambat", "izin", "sakit", "alfa", "cuti"]
HR_ATT_UI_STATUSES = ["hadir", "terlambat", "izin", "sakit", "alfa"]
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


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
    rows = await db.employees.find(q, {"_id": 0}).sort("nama", 1).to_list(None)
    classes = await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1, "guru_id": 1, "jadwal": 1, "status": 1}).to_list(None)
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


# ---------- Absensi Karyawan/Guru ----------
class HrAttendanceRecord(BaseModel):
    employee_id: str
    status: str
    jam_masuk: Optional[str] = None
    jam_pulang: Optional[str] = None
    keterangan: Optional[str] = ""


class HrAttendanceIn(BaseModel):
    tanggal: str
    records: List[HrAttendanceRecord]


def _validate_time(value: Optional[str], field: str):
    if value in (None, ""):
        return
    if not TIME_RE.match(value):
        raise HTTPException(status_code=400, detail=f"Format {field} tidak valid, gunakan HH:MM")


def _validate_hr_record(r: HrAttendanceRecord):
    if r.status not in HR_ATT_STATUSES:
        raise HTTPException(status_code=400, detail="Status absensi tidak valid")
    _validate_time(r.jam_masuk, "jam masuk")
    _validate_time(r.jam_pulang, "jam pulang")


def _recap_counts(rows: list) -> Dict[str, Any]:
    counts = {"hadir": 0, "terlambat": 0, "izin": 0, "sakit": 0, "alfa": 0, "cuti": 0}
    for r in rows:
        st = r.get("status")
        if st in counts:
            counts[st] += 1
    total = sum(counts.values())
    hadir_like = counts["hadir"] + counts["terlambat"]
    counts["total"] = total
    counts["persentase"] = round(hadir_like / total * 100, 1) if total else 0
    return counts


@router.get("/hr/attendance")
async def list_hr_attendance(dari: Optional[str] = None, sampai: Optional[str] = None,
                             employee_id: Optional[str] = None, tipe: Optional[str] = None,
                             user: dict = Depends(HR_ATT_READ)):
    q: Dict[str, Any] = {}
    if dari or sampai:
        q["tanggal"] = {}
        if dari:
            q["tanggal"]["$gte"] = dari
        if sampai:
            q["tanggal"]["$lte"] = sampai
    if employee_id:
        q["employee_id"] = employee_id
    if tipe:
        emps = await db.employees.find({"tipe": tipe}, {"_id": 0, "id": 1}).to_list(None)
        q["employee_id"] = {"$in": [e["id"] for e in emps]}
    rows = await db.employee_attendances.find(q, {"_id": 0}).sort([("tanggal", -1), ("employee_id", 1)]).to_list(None)
    names = {e["id"]: {"nama": e["nama"], "tipe": e.get("tipe"), "jabatan": e.get("jabatan")}
             for e in await db.employees.find({}, {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "jabatan": 1}).to_list(None)}
    for r in rows:
        info = names.get(r["employee_id"], {})
        r["employee_nama"] = info.get("nama")
        r["tipe"] = info.get("tipe")
        r["jabatan"] = info.get("jabatan")
    return rows


@router.post("/hr/attendance")
async def save_hr_attendance(body: HrAttendanceIn, user: dict = Depends(HR_ATT_WRITE)):
    if not body.tanggal or body.tanggal > today_str():
        raise HTTPException(status_code=400, detail="Tanggal absensi tidak boleh melebihi hari ini")
    if not body.records:
        raise HTTPException(status_code=400, detail="Minimal satu record absensi")
    emp_ids = list({r.employee_id for r in body.records})
    found = {e["id"] for e in await db.employees.find({"id": {"$in": emp_ids}}, {"_id": 0, "id": 1}).to_list(len(emp_ids))}
    missing = [eid for eid in emp_ids if eid not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Karyawan tidak ditemukan: {missing[0]}")
    for r in body.records:
        _validate_hr_record(r)
        await db.employee_attendances.update_one(
            {"employee_id": r.employee_id, "tanggal": body.tanggal},
            {"$set": {"status": r.status, "jam_masuk": r.jam_masuk or None, "jam_pulang": r.jam_pulang or None,
                      "keterangan": r.keterangan or "", "dicatat_oleh": user["name"], "updated_at": now_iso()},
             "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)
    await log_audit("hr_attendance", body.tanggal, "save", user, None,
                    {"tanggal": body.tanggal, "jumlah": len(body.records)})
    return {"ok": True, "jumlah": len(body.records)}


@router.get("/hr/attendance/recap")
async def hr_attendance_recap(dari: Optional[str] = None, sampai: Optional[str] = None,
                              tipe: Optional[str] = None, user: dict = Depends(HR_ATT_READ)):
    match: Dict[str, Any] = {}
    if dari or sampai:
        match["tanggal"] = {}
        if dari:
            match["tanggal"]["$gte"] = dari
        if sampai:
            match["tanggal"]["$lte"] = sampai
    pipeline = [{"$match": match}, {"$group": {"_id": {"e": "$employee_id", "st": "$status"}, "n": {"$sum": 1}}}]
    rows = await db.employee_attendances.aggregate(pipeline).to_list(None)
    per_emp: Dict[str, Dict[str, int]] = {}
    for r in rows:
        per_emp.setdefault(r["_id"]["e"], {"hadir": 0, "terlambat": 0, "izin": 0, "sakit": 0, "alfa": 0, "cuti": 0})
        if r["_id"]["st"] in per_emp[r["_id"]["e"]]:
            per_emp[r["_id"]["e"]][r["_id"]["st"]] = r["n"]
    q_emp: Dict[str, Any] = {"tipe": tipe} if tipe else {}
    emps = await db.employees.find(q_emp, {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "jabatan": 1, "aktif": 1}).sort("nama", 1).to_list(None)
    out = []
    for e in emps:
        c = per_emp.get(e["id"], {"hadir": 0, "terlambat": 0, "izin": 0, "sakit": 0, "alfa": 0, "cuti": 0})
        total = sum(c.values())
        hadir_like = c["hadir"] + c["terlambat"]
        out.append({"employee_id": e["id"], "nama": e["nama"], "tipe": e.get("tipe"), "jabatan": e.get("jabatan"),
                    "aktif": e.get("aktif", True), **c, "total": total,
                    "persentase": round(hadir_like / total * 100, 1) if total else 0})
    return out


# ---------- Cuti / Leave ----------
class LeaveIn(BaseModel):
    employee_id: str
    jenis: Optional[str] = "Cuti"
    dari: str
    sampai: str
    alasan: Optional[str] = ""


class LeaveDecideIn(BaseModel):
    setuju: bool
    alasan: Optional[str] = ""


def _parse_day(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Tanggal cuti tidak valid pada {field}, gunakan YYYY-MM-DD")


def _leave_dates(dari: str, sampai: str) -> List[str]:
    d0, d1 = _parse_day(dari, "dari"), _parse_day(sampai, "sampai")
    if d0 > d1:
        raise HTTPException(status_code=400, detail="Tanggal mulai tidak boleh setelah tanggal selesai")
    out, d = [], d0
    while d <= d1:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


async def _find_overlap(employee_id: str, dari: str, sampai: str, exclude_id: Optional[str] = None):
    q: Dict[str, Any] = {"employee_id": employee_id, "status": {"$in": LEAVE_ACTIVE},
                         "dari": {"$lte": sampai}, "sampai": {"$gte": dari}}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    return await db.leaves.find_one(q, {"_id": 0})


async def _mark_cuti_range(employee_id: str, days: List[str], user: dict):
    for t in days:
        await db.employee_attendances.update_one(
            {"employee_id": employee_id, "tanggal": t},
            {"$set": {"status": "cuti", "jam_masuk": None, "jam_pulang": None,
                      "keterangan": "Cuti disetujui", "dicatat_oleh": user["name"], "updated_at": now_iso()},
             "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)


def _enrich_leaves(rows: list, names: dict) -> list:
    for r in rows:
        info = names.get(r["employee_id"], {})
        r["employee_nama"] = info.get("nama")
        r["tipe"] = info.get("tipe")
        r["jabatan"] = info.get("jabatan")
    return rows


async def _employee_names() -> dict:
    return {e["id"]: {"nama": e["nama"], "tipe": e.get("tipe"), "jabatan": e.get("jabatan")}
            for e in await db.employees.find({}, {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "jabatan": 1}).to_list(None)}


@router.get("/leaves")
async def list_leaves(status: Optional[str] = None, employee_id: Optional[str] = None,
                      dari: Optional[str] = None, sampai: Optional[str] = None,
                      user: dict = Depends(LEAVE_READ)):
    q: Dict[str, Any] = {}
    if status:
        if status not in LEAVE_STATUSES:
            raise HTTPException(status_code=400, detail="Status cuti tidak valid")
        q["status"] = status
    if employee_id:
        q["employee_id"] = employee_id
    if dari:
        q["sampai"] = {"$gte": dari}
    if sampai:
        q.setdefault("sampai", {})["$lte"] = sampai
    if dari and sampai:
        q["dari"] = {"$lte": sampai}
    rows = await db.leaves.find(q, {"_id": 0}).sort([("dari", -1), ("created_at", -1)]).to_list(None)
    return _enrich_leaves(rows, await _employee_names())


@router.post("/leaves")
async def create_leave(body: LeaveIn, user: dict = Depends(LEAVE_CREATE)):
    if not await db.employees.find_one({"id": body.employee_id}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    days = _leave_dates(body.dari, body.sampai)
    if await _find_overlap(body.employee_id, body.dari, body.sampai):
        raise HTTPException(status_code=409, detail="Pengajuan cuti bertabrakan dengan pengajuan cuti yang sudah ada")
    doc = {"id": new_id(), "employee_id": body.employee_id, "jenis": body.jenis or "Cuti",
           "dari": body.dari[:10], "sampai": body.sampai[:10], "durasi_hari": len(days),
           "alasan": body.alasan or "", "status": "menunggu",
           "approver_id": None, "decided_at": None, "reject_reason": "", "attendance_marked": False,
           "created_by": user["name"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.leaves.insert_one(doc)
    await log_audit("leave", doc["id"], "create", user, None,
                    {"employee_id": body.employee_id, "dari": doc["dari"], "sampai": doc["sampai"], "durasi_hari": len(days)})
    return _enrich_leaves([clean(doc)], await _employee_names())[0]


@router.put("/leaves/{leave_id}/decide")
async def decide_leave(leave_id: str, body: LeaveDecideIn, user: dict = Depends(LEAVE_DECIDE)):
    lv = await db.leaves.find_one({"id": leave_id}, {"_id": 0})
    if not lv:
        raise HTTPException(status_code=404, detail="Pengajuan cuti tidak ditemukan")
    if lv["status"] != "menunggu":
        raise HTTPException(status_code=400, detail="Pengajuan cuti sudah diproses")
    if not body.setuju and not (body.alasan or "").strip():
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi")
    if body.setuju:
        days = _leave_dates(lv["dari"], lv["sampai"])
        if await _find_overlap(lv["employee_id"], lv["dari"], lv["sampai"], exclude_id=leave_id):
            raise HTTPException(status_code=409, detail="Pengajuan cuti bertabrakan dengan pengajuan cuti yang sudah ada")
        upd = {"status": "disetujui", "approver_id": user["id"], "approver_name": user["name"], "decided_at": now_iso(),
               "reject_reason": "", "attendance_marked": True, "updated_at": now_iso()}
        res = await db.leaves.update_one({"id": leave_id, "status": "menunggu"}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(status_code=409, detail="Pengajuan cuti sudah diproses oleh pengguna lain")
        await _mark_cuti_range(lv["employee_id"], days, user)
        await log_audit("leave", leave_id, "approve", user, {"status": "menunggu"},
                        {"status": "disetujui", "dari": lv["dari"], "sampai": lv["sampai"]})
    else:
        upd = {"status": "ditolak", "approver_id": user["id"], "approver_name": user["name"], "decided_at": now_iso(),
               "reject_reason": body.alasan.strip(), "updated_at": now_iso()}
        res = await db.leaves.update_one({"id": leave_id, "status": "menunggu"}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(status_code=409, detail="Pengajuan cuti sudah diproses oleh pengguna lain")
        await log_audit("leave", leave_id, "reject", user, {"status": "menunggu"},
                        {"status": "ditolak"}, body.alasan.strip())
    return _enrich_leaves([clean(await db.leaves.find_one({"id": leave_id}, {"_id": 0}))], await _employee_names())[0]


# ---------- Payroll & Honor (B1: satu model per guru) ----------
PAYROLL_STATUSES = ["draft", "disetujui", "dibayar"]


class PotonganItem(BaseModel):
    jenis: Optional[str] = ""
    nominal: float = 0
    keterangan: Optional[str] = ""
    source_ref: Optional[Dict[str, Any]] = None


# P1.4 provenance: allowlist tipe sumber + kata kunci kewajiban eksternal.
SOURCE_TYPES = ["class_attendance", "work_hours", "manual_reason", "external_doc", "payroll_correction"]
EXTERNAL_POTONGAN_KINDS = ("kasbon", "pinjaman", "hutang", "insiden", "denda", "ganti rugi")


class PayrollCalcItem(BaseModel):
    employee_id: str
    honor_pertemuan: Optional[int] = None
    honor_note: Optional[str] = ""
    lembur: Optional[float] = 0
    lembur_reason: Optional[str] = ""
    lembur_source_note: Optional[str] = ""
    bonus: Optional[float] = 0
    bonus_reason: Optional[str] = ""
    potongan: Optional[List[PotonganItem]] = []


class PayrollCalcIn(BaseModel):
    periode: str
    items: Optional[List[PayrollCalcItem]] = None
    employee_ids: Optional[List[str]] = None
    preview: Optional[bool] = False


class PayrollUpdateIn(BaseModel):
    honor_pertemuan: Optional[int] = None
    honor_note: Optional[str] = None
    lembur: Optional[float] = None
    lembur_reason: Optional[str] = None
    lembur_source_note: Optional[str] = None
    bonus: Optional[float] = None
    bonus_reason: Optional[str] = None
    potongan: Optional[List[PotonganItem]] = None
    alasan: Optional[str] = ""


def _check_source_type(v: Optional[str], field: str = "source_type"):
    if v and v not in SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipe sumber tidak valid: {v}")


def _sanitize_potongan(items: List[Any], strict: bool) -> List[dict]:
    """Validasi + normalisasi item potongan. strict=True (create): keterangan
    wajib; kewajiban eksternal wajib source_note. strict=False (koreksi):
    alasan umum request menjadi penutup (kompatibilitas data lama)."""
    out = []
    for p in (items or []):
        d = p.model_dump() if hasattr(p, "model_dump") else dict(p)
        ket = (d.get("keterangan") or "").strip()
        if strict and not ket:
            raise HTTPException(status_code=400, detail="Keterangan potongan wajib diisi")
        ref = d.get("source_ref") or None
        if ref:
            _check_source_type(ref.get("source_type"))
            ref = {"source_type": ref.get("source_type"),
                   "source_id": ref.get("source_id"),
                   "source_note": (ref.get("source_note") or "").strip()}
        if strict and (d.get("jenis") or "").strip().lower() in EXTERNAL_POTONGAN_KINDS \
                and not (ref and ref.get("source_note")):
            raise HTTPException(status_code=400,
                                detail=f"Potongan '{d.get('jenis')}' wajib memiliki source reference/note")
        out.append({"jenis": (d.get("jenis") or "").strip(), "nominal": d.get("nominal", 0),
                    "keterangan": ket, "source_ref": ref})
    return out


def _check_amount_reasons(bonus: float, bonus_reason: Optional[str],
                          lembur: float, lembur_reason: Optional[str], strict: bool):
    """Create (strict): bonus/lembur positif wajib reason. Koreksi: alasan umum
    menjadi penutup bila reason spesifik tidak diberikan (kompatibilitas)."""
    if not strict:
        return (bonus_reason or "").strip(), (lembur_reason or "").strip()
    if float(bonus or 0) > 0 and not (bonus_reason or "").strip():
        raise HTTPException(status_code=400, detail="Reason bonus wajib diisi bila bonus > 0")
    if float(lembur or 0) > 0 and not (lembur_reason or "").strip():
        raise HTTPException(status_code=400, detail="Reason lembur wajib diisi bila lembur > 0")
    return (bonus_reason or "").strip(), (lembur_reason or "").strip()


class PayrollPayIn(BaseModel):
    account_id: str


def _parse_periode(periode: str):
    try:
        y, m = periode.split("-")
        y, m = int(y), int(m)
        if not (2000 <= y <= 2100 and 1 <= m <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Periode tidak valid, gunakan YYYY-MM")
    dim = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, dim), dim


def _num(value: Any, field: str) -> float:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Nominal {field} tidak valid")
    if n < 0:
        raise HTTPException(status_code=400, detail=f"Nominal {field} tidak boleh negatif")
    return n


def _is_honor_model(emp: dict) -> bool:
    return emp.get("tipe") == "guru" and float(emp.get("honor_per_pertemuan") or 0) > 0


async def _attendance_counts(employee_id: str, wstart: date, wend: date) -> Dict[str, int]:
    rows = await db.employee_attendances.find(
        {"employee_id": employee_id, "tanggal": {"$gte": wstart.isoformat(), "$lte": wend.isoformat()}},
        {"_id": 0, "status": 1}).to_list(None)
    counts = {"hadir": 0, "terlambat": 0, "izin": 0, "sakit": 0, "cuti": 0, "alfa": 0}
    for r in rows:
        if r.get("status") in counts:
            counts[r["status"]] += 1
    return counts


def _active_window(emp: dict, pstart: date, pend: date):
    """Jendela aktif inklusif + jumlah hari. Konsisten dipakai base, tunjangan, dan counts alfa (F1)."""
    start = pstart
    try:
        if emp.get("tanggal_masuk"):
            start = max(pstart, date.fromisoformat(emp["tanggal_masuk"][:10]))
    except ValueError:
        pass
    end = pend
    try:
        if emp.get("kontrak_berakhir"):
            end = min(pend, date.fromisoformat(emp["kontrak_berakhir"][:10]))
    except ValueError:
        pass
    if end < start:
        return start, end, 0
    return start, end, (end - start).days + 1


async def _calc_one(emp: dict, periode: str, pstart: date, pend: date, dim: int,
                   honor_pertemuan: Optional[int], lembur: float, bonus: float,
                   potongan: List[dict], prov: Optional[dict] = None) -> Dict[str, Any]:
    honor_model = _is_honor_model(emp)
    if honor_model and honor_pertemuan is None:
        raise HTTPException(status_code=400, detail=f"Jumlah pertemuan aktual wajib diisi untuk {emp.get('nama')}")
    meetings = int(honor_pertemuan or 0)
    if meetings < 0:
        raise HTTPException(status_code=400, detail="Jumlah pertemuan tidak boleh negatif")
    wstart, wend, hari_aktif = _active_window(emp, pstart, pend)
    att = await _attendance_counts(emp["id"], wstart, wend)
    gaji = round(float(emp.get("gaji_pokok") or 0))
    tunj = round(float(emp.get("tunjangan") or 0))
    tarif = round(float(emp.get("honor_per_pertemuan") or 0))
    if honor_model:
        base = tarif * meetings
        tunjangan = tunj if hari_aktif > 0 else 0
    else:
        base = round(gaji / dim * hari_aktif) if dim else 0
        tunjangan = round(tunj / dim * hari_aktif) if dim else 0
    pot_alfa = round(gaji / dim * att["alfa"]) if dim else 0
    pot_items = [{"jenis": p.get("jenis", ""), "nominal": round(_num(p.get("nominal", 0), "potongan")),
                  "keterangan": p.get("keterangan", "")} for p in (potongan or [])]
    lembur_n, bonus_n = round(_num(lembur, "lembur")), round(_num(bonus, "bonus"))
    bruto = base + tunjangan + lembur_n + bonus_n
    bersih = bruto - pot_alfa - sum(p["nominal"] for p in pot_items)
    return {
        "snapshot": {"nama": emp.get("nama"), "tipe": emp.get("tipe"), "jabatan": emp.get("jabatan"),
                     "gaji_pokok": gaji, "tunjangan": tunj, "honor_per_pertemuan": tarif,
                     "model": "honor" if honor_model else "bulanan"},
        "komponen": {"attendance": att, "hari_aktif": hari_aktif, "hari_kalender": dim,
                     "base": base, "tunjangan_hitung": tunjangan,
                     "honor_pertemuan": meetings, "honor_total": tarif * meetings,
                     "lembur": lembur_n, "bonus": bonus_n, "potongan": pot_items,
                     "potongan_alfa": pot_alfa, "komponen_lain": [],
                     "provenance": prov or {}},
        "bruto": bruto, "bersih": bersih,
    }


async def _next_slip_no() -> str:
    c = await db.counters.find_one_and_update({"_id": "slip"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return f"SLIP-{today().strftime('%Y%m')}-{c['seq']:04d}"


@router.get("/payrolls")
async def list_payrolls(periode: Optional[str] = None, employee_id: Optional[str] = None,
                        tipe: Optional[str] = None, status: Optional[str] = None,
                        user: dict = Depends(PAYROLL_READ)):
    q: Dict[str, Any] = {}
    if periode:
        _parse_periode(periode)
        q["periode"] = periode
    if employee_id:
        q["employee_id"] = employee_id
    if status:
        if status not in PAYROLL_STATUSES:
            raise HTTPException(status_code=400, detail="Status payroll tidak valid")
        q["status"] = status
    rows = await db.payrolls.find(q, {"_id": 0}).sort([("periode", -1), ("employee_nama", 1)]).to_list(None)
    if tipe:
        rows = [r for r in rows if r.get("snapshot", {}).get("tipe") == tipe]
    return rows


@router.get("/payrolls/suggest-meetings")
async def suggest_meetings(employee_id: str, periode: str, user: dict = Depends(PAYROLL_WRITE)):
    """P1.4 D1: read-only meeting suggestion per guru per periode.
    Distinct (tanggal, guru_id, class_id) dari classes.guru_id + student attendance.
    Attendance siswa hanya evidence; unverified_presence=True selalu.
    Tidak membuat/mengubah payroll, attendance, atau honor."""
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    pstart, pend, _ = _parse_periode(periode)
    classes = await db.classes.find({"guru_id": employee_id}, {"_id": 0, "id": 1, "nama": 1}).to_list(None)
    names = {c["id"]: c.get("nama", "") for c in classes}
    if not names:
        return {"employee_id": employee_id, "periode": periode, "suggested_meetings": 0, "suggestions": []}
    rows = await db.attendance.find(
        {"class_id": {"$in": list(names.keys())},
         "tanggal": {"$gte": pstart.isoformat(), "$lte": pend.isoformat()}},
        {"_id": 0, "class_id": 1, "tanggal": 1, "student_id": 1}).to_list(None)
    grouped: Dict[tuple, set] = {}
    for r in rows:
        grouped.setdefault((r["tanggal"], r["class_id"]), set()).add(r.get("student_id"))
    suggestions = [{"tanggal": t, "guru_id": employee_id, "class_id": c, "class_nama": names.get(c, ""),
                    "evidence_count": len(s), "unverified_presence": True}
                   for (t, c), s in sorted(grouped.items())]
    return {"employee_id": employee_id, "periode": periode,
            "suggested_meetings": len(suggestions), "suggestions": suggestions}


@router.get("/payrolls/{pay_id}")
async def get_payroll(pay_id: str, user: dict = Depends(PAYROLL_READ)):
    p = await db.payrolls.find_one({"id": pay_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payroll tidak ditemukan")
    return p


@router.post("/payrolls/calculate")
async def calculate_payrolls(body: PayrollCalcIn, user: dict = Depends(PAYROLL_WRITE)):
    pstart, pend, dim = _parse_periode(body.periode)
    items = {i.employee_id: i for i in (body.items or [])}
    emp_ids = list(items.keys()) + [e for e in (body.employee_ids or []) if e not in items]
    if not emp_ids:
        emps = await db.employees.find({"aktif": True}, {"_id": 0}).sort("nama", 1).to_list(None)
    else:
        emps = await db.employees.find({"id": {"$in": emp_ids}}, {"_id": 0}).to_list(len(emp_ids))
        found = {e["id"] for e in emps}
        missing = [e for e in emp_ids if e not in found]
        if missing:
            raise HTTPException(status_code=404, detail=f"Karyawan tidak ditemukan: {missing[0]}")
    out, skipped = [], []
    for emp in emps:
        if await db.payrolls.find_one({"periode": body.periode, "employee_id": emp["id"]}, {"_id": 0, "id": 1}):
            skipped.append(emp["id"])
            continue
        it = items.get(emp["id"]) or PayrollCalcItem(employee_id=emp["id"])
        bonus_reason, lembur_reason = _check_amount_reasons(it.bonus or 0, it.bonus_reason,
                                                            it.lembur or 0, it.lembur_reason, strict=True)
        pot = _sanitize_potongan([p.model_dump() for p in (it.potongan or [])], strict=True)
        prov = {"meetings": {"note": (it.honor_note or "").strip(), "actor": user["name"], "at": now_iso()},
                "lembur": {"reason": lembur_reason, "source_note": (it.lembur_source_note or "").strip()},
                "bonus": {"reason": bonus_reason},
                "potongan": pot, "updated_by": user["name"], "updated_at": now_iso()}
        calc = await _calc_one(emp, body.periode, pstart, pend, dim, it.honor_pertemuan,
                               it.lembur or 0, it.bonus or 0,
                               [{"jenis": p["jenis"], "nominal": p["nominal"], "keterangan": p["keterangan"]}
                                for p in pot], prov)
        calc["komponen"]["potongan"] = pot
        doc = {"id": new_id(), "periode": body.periode, "employee_id": emp["id"],
               "employee_nama": emp.get("nama"), "no_slip": await _next_slip_no(),
               **calc, "status": "draft", "account_id": None, "account_nama": None, "transaction_id": None,
               "calculated_by": user["name"], "calculated_at": now_iso(),
               "approved_by": None, "approved_at": None, "paid_by": None, "paid_at": None,
               "created_at": now_iso(), "updated_at": now_iso()}
        if body.preview:
            out.append({**doc, "preview": True})
        else:
            try:
                await db.payrolls.insert_one(doc)
            except DuplicateKeyError:
                canon = await db.payrolls.find_one({"periode": body.periode, "employee_id": emp["id"]},
                                                   {"_id": 0, "id": 1})
                if canon:
                    skipped.append(emp["id"])
                    continue
                raise
            await log_audit("payroll", doc["id"], "create", user, None,
                            {"periode": body.periode, "employee": emp.get("nama"), "bersih": doc["bersih"]})
            out.append(clean(doc))
    return {"rows": out, "skipped": skipped}


@router.put("/payrolls/{pay_id}")
async def update_payroll(pay_id: str, body: PayrollUpdateIn, user: dict = Depends(PAYROLL_WRITE)):
    p = await db.payrolls.find_one({"id": pay_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payroll tidak ditemukan")
    if p["status"] != "draft":
        raise HTTPException(status_code=400, detail="Hanya payroll draft yang dapat diubah")
    if not (body.alasan or "").strip():
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi untuk audit")
    emp = await db.employees.find_one({"id": p["employee_id"]}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    pstart, pend, dim = _parse_periode(p["periode"])
    old_pot = p["komponen"].get("potongan", [])
    old_prov = p["komponen"].get("provenance", {}) or {}
    new_pot = _sanitize_potongan([x.model_dump() for x in body.potongan], strict=False) \
        if body.potongan is not None else old_pot
    new_bonus = body.bonus if body.bonus is not None else p["komponen"].get("bonus", 0)
    new_lembur = body.lembur if body.lembur is not None else p["komponen"].get("lembur", 0)
    bonus_reason, lembur_reason = _check_amount_reasons(new_bonus, body.bonus_reason,
                                                        new_lembur, body.lembur_reason, strict=False)
    alasan = body.alasan.strip()
    if float(new_bonus or 0) > 0 and not bonus_reason:
        bonus_reason = alasan
    if float(new_lembur or 0) > 0 and not lembur_reason:
        lembur_reason = alasan
    old_meet = (old_prov.get("meetings") or {}) if isinstance(old_prov, dict) else {}
    prov = {"meetings": {"note": body.honor_note.strip() if body.honor_note is not None else old_meet.get("note", ""),
                         "actor": user["name"], "at": now_iso()},
            "lembur": {"reason": lembur_reason,
                       "source_note": body.lembur_source_note.strip() if body.lembur_source_note is not None
                       else ((old_prov.get("lembur") or {}).get("source_note", "") if isinstance(old_prov, dict) else "")},
            "bonus": {"reason": bonus_reason},
            "potongan": new_pot, "updated_by": user["name"], "updated_at": now_iso()}
    calc = await _calc_one(emp, p["periode"], pstart, pend, dim,
                           body.honor_pertemuan if body.honor_pertemuan is not None else p["komponen"].get("honor_pertemuan", 0),
                           new_lembur, new_bonus,
                           [{"jenis": x["jenis"], "nominal": x["nominal"], "keterangan": x["keterangan"]}
                            for x in new_pot], prov)
    calc["komponen"]["potongan"] = new_pot
    before = {"bersih": p["bersih"], "bruto": p["bruto"], "bonus": p["komponen"].get("bonus"),
              "lembur": p["komponen"].get("lembur"), "honor_pertemuan": p["komponen"].get("honor_pertemuan"),
              "potongan": old_pot, "provenance": p["komponen"].get("provenance", {})}
    await db.payrolls.update_one({"id": pay_id}, {"$set": {**calc, "updated_at": now_iso()}})
    await log_audit("payroll", pay_id, "update", user, before,
                    {"bersih": calc["bersih"], "bruto": calc["bruto"], "bonus": calc["komponen"].get("bonus"),
                     "lembur": calc["komponen"].get("lembur"),
                     "honor_pertemuan": calc["komponen"].get("honor_pertemuan"),
                     "potongan": new_pot, "provenance": prov}, alasan)
    return clean(await db.payrolls.find_one({"id": pay_id}, {"_id": 0}))


@router.post("/payrolls/{pay_id}/approve")
async def approve_payroll(pay_id: str, user: dict = Depends(PAYROLL_APPROVE)):
    p = await db.payrolls.find_one({"id": pay_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payroll tidak ditemukan")
    if p["status"] != "draft":
        raise HTTPException(status_code=400, detail="Hanya payroll draft yang dapat disetujui")
    res = await db.payrolls.update_one({"id": pay_id, "status": "draft"},
                                       {"$set": {"status": "disetujui", "approved_by": user["name"],
                                                 "approved_at": now_iso(), "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail="Payroll sudah diproses oleh pengguna lain")
    await log_audit("payroll", pay_id, "approve", user, {"status": "draft"},
                    {"status": "disetujui", "bersih": p["bersih"]})
    return clean(await db.payrolls.find_one({"id": pay_id}, {"_id": 0}))


@router.post("/payrolls/{pay_id}/pay")
async def pay_payroll(pay_id: str, body: PayrollPayIn, user: dict = Depends(PAYROLL_PAY)):
    p = await db.payrolls.find_one({"id": pay_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payroll tidak ditemukan")
    if p.get("transaction_id"):
        tx = await db.transactions.find_one({"id": p["transaction_id"]}, {"_id": 0})
        if tx:
            return {**clean(p), "already_paid": True}
    if p["status"] != "disetujui":
        raise HTTPException(status_code=400, detail="Hanya payroll yang disetujui yang dapat dibayar")
    if (p.get("bersih") or 0) <= 0:
        await log_audit("payroll", pay_id, "pay_rejected", user, {"status": p["status"]},
                        {"bersih": p.get("bersih")}, "Net payroll nol atau negatif")
        raise HTTPException(status_code=400, detail="Payroll dengan bersih nol atau negatif tidak dapat dibayar")
    acc = await db.accounts.find_one({"id": body.account_id}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    kategori = "Honor Guru" if p.get("snapshot", {}).get("model") == "honor" else "Gaji"
    tx = {"id": new_id(), "jenis": "pengeluaran", "kategori": kategori, "nominal": p["bersih"],
          "tanggal": today_str(), "deskripsi": f"{kategori} - {p.get('employee_nama')} ({p['periode']}, {p['no_slip']})",
          "account_id": body.account_id, "account_nama": acc["nama"], "metode": "transfer", "bukti_file_id": None,
          "ref_type": "payroll", "ref_id": pay_id, "petugas": user["name"], "created_at": now_iso()}
    try:
        await db.transactions.insert_one(tx)
    except DuplicateKeyError:
        tx2 = await db.transactions.find_one({"ref_type": "payroll", "ref_id": pay_id}, {"_id": 0})
        if not tx2:
            raise
        cur = await db.payrolls.find_one({"id": pay_id}, {"_id": 0})
        if not cur.get("transaction_id"):
            await db.payrolls.update_one({"id": pay_id}, {"$set": {"status": "dibayar", "account_id": tx2["account_id"],
                                                                   "account_nama": tx2.get("account_nama"), "transaction_id": tx2["id"],
                                                                   "paid_by": user["name"], "paid_at": now_iso(),
                                                                   "updated_at": now_iso()}})
            await log_audit("payroll", pay_id, "pay", user, {"status": "disetujui"},
                            {"status": "dibayar", "bersih": p["bersih"], "transaction_id": tx2["id"]})
        return {**clean(await db.payrolls.find_one({"id": pay_id}, {"_id": 0})), "already_paid": True}
    await db.payrolls.update_one({"id": pay_id}, {"$set": {"status": "dibayar", "account_id": body.account_id,
                                                           "account_nama": acc["nama"], "transaction_id": tx["id"],
                                                           "paid_by": user["name"], "paid_at": now_iso(),
                                                           "updated_at": now_iso()}})
    await log_audit("payroll", pay_id, "pay", user, {"status": "disetujui"},
                    {"status": "dibayar", "bersih": p["bersih"], "transaction_id": tx["id"]})
    await log_audit("transaction", tx["id"], "create", user, None,
                    {"jenis": "pengeluaran", "kategori": kategori, "nominal": p["bersih"]})
    return clean(await db.payrolls.find_one({"id": pay_id}, {"_id": 0}))
