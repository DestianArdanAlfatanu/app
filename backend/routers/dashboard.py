from typing import Optional, Dict, Any
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query

from core import (db, get_current_user, require_roles, period_range, today_str, payment_summary_map, fee_total,
                  attendance_summary, grade_average, doc_progress, STUDENT_STATUSES, compute_age)
from routers.finance import account_balances

router = APIRouter()


@router.get("/dashboard")
async def dashboard(period: str = "bulan", user: dict = Depends(get_current_user)):
    start, end = period_range(period)
    students = await db.students.find({}, {"_id": 0, "id": 1, "status": 1, "fee_plan": 1, "created_at": 1}).to_list(10000)
    by_status = {s: 0 for s in STUDENT_STATUSES}
    for s in students:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
    baru = sum(1 for s in students if s["created_at"][:10] >= start)
    aktif_statuses = ["diterima", "pelatihan", "ujian", "lulus", "matching", "pemberkasan", "visa"]
    out: Dict[str, Any] = {"period": period, "dari": start, "sampai": end, "siswa": {
        "total": len(students), "calon": by_status["calon_siswa"] + by_status["pendaftaran"] + by_status["seleksi"],
        "aktif": sum(by_status[s] for s in aktif_statuses), "pelatihan": by_status["pelatihan"], "lulus": by_status["lulus"],
        "gagal": by_status["gagal"], "berangkat": by_status["berangkat"], "alumni": by_status["alumni"], "baru_periode": baru,
        "per_status": by_status}}
    role = user["role"]
    if role in ("owner", "admin", "finance"):
        rows = await db.transactions.aggregate([{"$match": {"tanggal": {"$gte": start, "$lte": end}}},
                                                {"$group": {"_id": "$jenis", "n": {"$sum": "$nominal"}}}]).to_list(5)
        m = {r["_id"]: r["n"] for r in rows}
        pay = await payment_summary_map()
        piutang = sum(max(fee_total(s) - pay.get(s["id"], {}).get("bayar", 0), 0) for s in students if s["status"] not in ("calon_siswa", "gagal"))
        tunggakan = sum(1 for s in students if s["status"] not in ("calon_siswa", "gagal", "alumni") and fee_total(s) - pay.get(s["id"], {}).get("bayar", 0) > 0)
        today_pay = await db.payments.aggregate([{"$match": {"tanggal": today_str()}}, {"$group": {"_id": None, "n": {"$sum": "$nominal"}}}]).to_list(1)
        accounts = await account_balances()
        out["keuangan"] = {"pemasukan": m.get("pemasukan", 0), "pengeluaran": m.get("pengeluaran", 0), "saldo_kas": sum(a["saldo"] for a in accounts),
                           "piutang": piutang, "siswa_tunggakan": tunggakan, "pembayaran_hari_ini": today_pay[0]["n"] if today_pay else 0,
                           "accounts": [{"nama": a["nama"], "saldo": a["saldo"]} for a in accounts]}
    guru = await db.employees.count_documents({"tipe": "guru", "aktif": True})
    karyawan = await db.employees.count_documents({"tipe": "karyawan", "aktif": True})
    kelas_aktif = await db.classes.find({"status": "aktif"}, {"_id": 0, "id": 1, "nama": 1, "jadwal": 1, "guru_id": 1}).to_list(100)
    hari_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    today_name = hari_map[date.today().weekday()]
    teachers = {t["id"]: t["nama"] for t in await db.employees.find({"tipe": "guru"}, {"_id": 0, "id": 1, "nama": 1}).to_list(200)}
    jadwal_hari_ini = [{"kelas": c["nama"], "guru": teachers.get(c.get("guru_id")), **j} for c in kelas_aktif for j in c.get("jadwal", []) if j.get("hari") == today_name]
    upcoming = (date.today() + timedelta(days=14)).isoformat()
    exams = await db.exams.find({"tanggal": {"$gte": today_str(), "$lte": upcoming}}, {"_id": 0}).to_list(50)
    ujian_peserta = 0
    for e in exams:
        if e.get("class_id"):
            c = await db.classes.find_one({"id": e["class_id"]}, {"_id": 0, "student_ids": 1})
            ujian_peserta += len(c.get("student_ids", [])) if c else 0
    interviews = await db.interviews.find({"tanggal": {"$gte": today_str()}, "hasil": "menunggu"}, {"_id": 0}).sort("tanggal", 1).to_list(20)
    out["operasional"] = {"guru": guru, "karyawan": karyawan, "kelas_aktif": len(kelas_aktif), "jadwal_hari_ini": jadwal_hari_ini,
                          "ujian_mendatang": [{"nama": e["nama"], "tanggal": e["tanggal"], "jenis": e["jenis"]} for e in exams],
                          "siswa_akan_ujian": ujian_peserta, "interview_mendatang": interviews[:5],
                          "job_order_terbuka": await db.job_orders.count_documents({"status": "terbuka"})}
    absen_today = await db.attendance.find({"tanggal": today_str(), "status": {"$ne": "hadir"}}, {"_id": 0}).to_list(200)
    out["absensi_hari_ini"] = {"tidak_hadir": len(absen_today)}
    recent = await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(8)
    out["aktivitas_terbaru"] = recent
    return out


@router.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    t = today_str()
    soon = (date.today() + timedelta(days=30)).isoformat()
    items = []
    role = user["role"]
    if role in ("owner", "admin", "finance"):
        students = await db.students.find({"status": {"$nin": ["calon_siswa", "gagal", "alumni"]}}, {"_id": 0}).to_list(5000)
        pay = await payment_summary_map()
        for s in students:
            sisa = fee_total(s) - pay.get(s["id"], {}).get("bayar", 0)
            jt = s.get("jatuh_tempo")
            if sisa > 0 and jt and jt <= (date.today() + timedelta(days=7)).isoformat():
                items.append({"tipe": "pembayaran", "level": "danger" if jt < t else "warning", "judul": f"Tagihan {s['nama_lengkap']}",
                              "pesan": f"Sisa Rp{sisa:,.0f} {'terlambat' if jt < t else 'jatuh tempo'} {jt}", "link": f"/siswa/{s['id']}", "tanggal": jt})
    docs = await db.documents.find({"is_deleted": False, "tanggal_kadaluarsa": {"$ne": None, "$lte": soon}}, {"_id": 0}).to_list(500)
    names = {s["id"]: s["nama_lengkap"] for s in await db.students.find({"id": {"$in": [d["student_id"] for d in docs]}}, {"_id": 0, "id": 1, "nama_lengkap": 1}).to_list(500)}
    for d in docs:
        items.append({"tipe": "dokumen", "level": "danger" if d["tanggal_kadaluarsa"] < t else "warning", "judul": f"{d['jenis']} - {names.get(d['student_id'], '')}",
                      "pesan": f"{'Sudah expired' if d['tanggal_kadaluarsa'] < t else 'Akan expired'} {d['tanggal_kadaluarsa']}", "link": f"/siswa/{d['student_id']}", "tanggal": d["tanggal_kadaluarsa"]})
    for iv in await db.interviews.find({"tanggal": {"$gte": t, "$lte": (date.today() + timedelta(days=7)).isoformat()}, "hasil": "menunggu"}, {"_id": 0}).to_list(100):
        items.append({"tipe": "interview", "level": "info", "judul": f"Interview {iv['student_nama']}", "pesan": f"{iv['perusahaan']} - {iv['posisi']} pada {iv['tanggal']}",
                      "link": "/job-order", "tanggal": iv["tanggal"]})
    if role in ("owner", "admin", "guru"):
        absen = await db.attendance.find({"tanggal": t, "status": "alfa"}, {"_id": 0}).to_list(100)
        anames = {s["id"]: s["nama_lengkap"] for s in await db.students.find({"id": {"$in": [a["student_id"] for a in absen]}}, {"_id": 0, "id": 1, "nama_lengkap": 1}).to_list(100)}
        for a in absen:
            items.append({"tipe": "absensi", "level": "warning", "judul": f"{anames.get(a['student_id'], '')} tidak hadir", "pesan": "Alfa hari ini", "link": f"/siswa/{a['student_id']}", "tanggal": t})
    if role in ("owner", "hr", "admin"):
        for e in await db.employees.find({"kontrak_berakhir": {"$ne": None, "$lte": soon}, "aktif": True}, {"_id": 0}).to_list(100):
            items.append({"tipe": "kontrak", "level": "warning", "judul": f"Kontrak {e['nama']}", "pesan": f"Berakhir {e['kontrak_berakhir']}", "link": "/sdm", "tanggal": e["kontrak_berakhir"]})
    items.sort(key=lambda x: x["tanggal"] or "")
    return items


@router.get("/search")
async def search(q: str = Query(..., min_length=1), user: dict = Depends(get_current_user)):
    rows = await db.students.find({"$or": [{"nama_lengkap": {"$regex": q, "$options": "i"}}, {"nik": {"$regex": q}}]}, {"_id": 0}).to_list(8)
    pay = await payment_summary_map([r["id"] for r in rows])
    classes = {c["id"]: c["nama"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(200)}
    out = []
    for s in rows:
        iv = await db.interviews.find_one({"student_id": s["id"]}, {"_id": 0}, sort=[("tanggal", -1)])
        out.append({"id": s["id"], "nama_lengkap": s["nama_lengkap"], "status": s["status"], "kelas": classes.get(s.get("class_id")),
                    "pembayaran": {"total": fee_total(s), "bayar": pay.get(s["id"], {}).get("bayar", 0)},
                    "absensi": await attendance_summary(s["id"]), "nilai": await grade_average(s["id"]),
                    "job_order": iv["perusahaan"] if iv else None, "dokumen": await doc_progress(s["id"])})
    return {"students": out}


@router.get("/audit-logs")
async def audit_logs(entity: Optional[str] = None, limit: int = 200, user: dict = Depends(require_roles("admin", "finance", "hr"))):
    q = {"entity": entity} if entity else {}
    return await db.audit_logs.find(q, {"_id": 0}).sort("timestamp", -1).to_list(limit)


@router.get("/reports/students")
async def report_students(user: dict = Depends(require_roles("admin", "marketing", "hr", "finance"))):
    students = await db.students.find({}, {"_id": 0}).to_list(10000)
    pay = await payment_summary_map()
    classes = {c["id"]: c["nama"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(200)}
    rows = []
    for s in students:
        total = fee_total(s)
        bayar = pay.get(s["id"], {}).get("bayar", 0)
        rows.append({"nama": s["nama_lengkap"], "nik": s.get("nik"), "jenis_kelamin": s.get("jenis_kelamin"), "usia": compute_age(s.get("tanggal_lahir")),
                     "status": s["status"], "kelas": classes.get(s.get("class_id")), "bahasa": s.get("kemampuan_bahasa_jepang"),
                     "total_tagihan": total, "dibayar": bayar, "sisa": max(total - bayar, 0), "kehadiran": (await attendance_summary(s["id"]))["persentase"],
                     "nilai": await grade_average(s["id"]), "dokumen": (await doc_progress(s["id"]))["lengkap"], "no_hp": s.get("no_hp")})
    per_status = {}
    for r in rows:
        per_status[r["status"]] = per_status.get(r["status"], 0) + 1
    return {"rows": rows, "per_status": per_status}


@router.get("/reports/finance")
async def report_finance(dari: Optional[str] = None, sampai: Optional[str] = None, user: dict = Depends(require_roles("admin", "finance"))):
    q: Dict[str, Any] = {}
    if dari or sampai:
        q["tanggal"] = {k: v for k, v in (("$gte", dari), ("$lte", sampai)) if v}
    rows = await db.transactions.find(q, {"_id": 0}).sort("tanggal", 1).to_list(20000)
    accs = {a["id"]: a["nama"] for a in await db.accounts.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(50)}
    for r in rows:
        r["account_nama"] = accs.get(r["account_id"])
    pemasukan = sum(r["nominal"] for r in rows if r["jenis"] == "pemasukan")
    pengeluaran = sum(r["nominal"] for r in rows if r["jenis"] == "pengeluaran")
    per_kat: Dict[str, float] = {}
    for r in rows:
        per_kat[f"{r['jenis']}|{r['kategori']}"] = per_kat.get(f"{r['jenis']}|{r['kategori']}", 0) + r["nominal"]
    return {"rows": rows, "pemasukan": pemasukan, "pengeluaran": pengeluaran, "laba": pemasukan - pengeluaran,
            "per_kategori": [{"jenis": k.split("|")[0], "kategori": k.split("|")[1], "nominal": v} for k, v in per_kat.items()],
            "accounts": await account_balances()}


@router.get("/reports/hr")
async def report_hr(user: dict = Depends(require_roles("admin", "hr"))):
    emps = await db.employees.find({}, {"_id": 0}).to_list(1000)
    classes = await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1, "guru_id": 1}).to_list(500)
    for e in emps:
        e["jumlah_kelas"] = sum(1 for c in classes if c.get("guru_id") == e["id"])
    return {"rows": emps, "total_gaji": sum(e.get("gaji_pokok", 0) + e.get("tunjangan", 0) for e in emps if e.get("aktif", True))}


@router.get("/reports/training")
async def report_training(class_id: Optional[str] = None, user: dict = Depends(require_roles("admin", "guru", "hr"))):
    q = {"class_id": class_id} if class_id else {"class_id": {"$ne": None}}
    students = await db.students.find(q, {"_id": 0, "id": 1, "nama_lengkap": 1, "class_id": 1, "status": 1}).to_list(5000)
    classes = {c["id"]: c["nama"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(200)}
    rows = []
    for s in students:
        att = await attendance_summary(s["id"])
        exams = await db.exams.find({"results.student_id": s["id"]}, {"_id": 0, "nama": 1, "tanggal": 1, "results": 1}).sort("tanggal", 1).to_list(50)
        rows.append({"nama": s["nama_lengkap"], "kelas": classes.get(s["class_id"]), "status": s["status"], **att, "nilai": await grade_average(s["id"]),
                     "ujian": [{"nama": e["nama"], "tanggal": e["tanggal"], "nilai": next((r["nilai"] for r in e["results"] if r["student_id"] == s["id"]), None)} for e in exams]})
    return {"rows": rows}
