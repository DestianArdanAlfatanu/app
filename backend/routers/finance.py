from typing import Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import (db, require_roles, new_id, now_iso, today_str, clean, log_audit, period_range,
                  payment_summary_map, fee_total)

router = APIRouter()
FIN = require_roles("finance")
FIN_READ = require_roles("finance", "admin")
INCOME_CATS = ["Pembayaran Siswa", "Pendaftaran", "Pelatihan", "Asrama", "Administrasi", "Pendapatan Lainnya"]
EXPENSE_CATS = ["Gaji", "Honor Guru", "Listrik", "Internet", "Air", "Sewa Gedung", "Makan Siswa", "Transportasi", "ATK",
                "Perawatan", "Pajak", "Operasional Lainnya"]


class AccountIn(BaseModel):
    nama: str
    jenis: str = "bank"
    bank: Optional[str] = ""
    no_rekening: Optional[str] = ""
    saldo_awal: float = 0


class TransactionIn(BaseModel):
    jenis: str
    kategori: str
    nominal: float
    tanggal: str
    deskripsi: Optional[str] = ""
    account_id: str
    metode: Optional[str] = "transfer"
    bukti_file_id: Optional[str] = None
    alasan: Optional[str] = ""


class PaymentIn(BaseModel):
    student_id: str
    nominal: float
    tanggal: str
    metode: str = "cash"
    jenis: Optional[str] = "Cicilan"
    no_transaksi: Optional[str] = ""
    account_id: str
    catatan: Optional[str] = ""
    bukti_file_id: Optional[str] = None
    alasan: Optional[str] = ""


class ReconIn(BaseModel):
    account_id: str
    tanggal: str
    saldo_aktual: float
    alasan: Optional[str] = ""


async def account_balances() -> list:
    accounts = await db.accounts.find({}, {"_id": 0}).to_list(50)
    rows = await db.transactions.aggregate([{"$group": {"_id": {"a": "$account_id", "j": "$jenis"}, "n": {"$sum": "$nominal"}}}]).to_list(500)
    agg: Dict[str, Dict[str, float]] = {}
    for r in rows:
        agg.setdefault(r["_id"]["a"], {})[r["_id"]["j"]] = r["n"]
    for a in accounts:
        m = agg.get(a["id"], {})
        a["pemasukan"] = m.get("pemasukan", 0)
        a["pengeluaran"] = m.get("pengeluaran", 0)
        a["saldo"] = a.get("saldo_awal", 0) + a["pemasukan"] - a["pengeluaran"]
    return accounts


@router.get("/finance/categories")
async def categories(user: dict = Depends(FIN_READ)):
    return {"pemasukan": INCOME_CATS, "pengeluaran": EXPENSE_CATS}


@router.get("/finance/accounts")
async def list_accounts(user: dict = Depends(FIN_READ)):
    return await account_balances()


@router.post("/finance/accounts")
async def create_account(body: AccountIn, user: dict = Depends(FIN)):
    doc = {**body.model_dump(), "id": new_id(), "created_at": now_iso()}
    await db.accounts.insert_one(doc)
    await log_audit("account", doc["id"], "create", user, None, {"nama": body.nama, "saldo_awal": body.saldo_awal})
    return clean(doc)


@router.put("/finance/accounts/{acc_id}")
async def update_account(acc_id: str, body: AccountIn, user: dict = Depends(FIN)):
    old = await db.accounts.find_one({"id": acc_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    await db.accounts.update_one({"id": acc_id}, {"$set": body.model_dump()})
    await log_audit("account", acc_id, "update", user, {"saldo_awal": old.get("saldo_awal")}, {"saldo_awal": body.saldo_awal})
    return clean(await db.accounts.find_one({"id": acc_id}, {"_id": 0}))


@router.get("/finance/transactions")
async def list_transactions(jenis: Optional[str] = None, kategori: Optional[str] = None, account_id: Optional[str] = None,
                            dari: Optional[str] = None, sampai: Optional[str] = None, user: dict = Depends(FIN_READ)):
    q: Dict[str, Any] = {}
    if jenis:
        q["jenis"] = jenis
    if kategori:
        q["kategori"] = kategori
    if account_id:
        q["account_id"] = account_id
    if dari or sampai:
        q["tanggal"] = {}
        if dari:
            q["tanggal"]["$gte"] = dari
        if sampai:
            q["tanggal"]["$lte"] = sampai
    rows = await db.transactions.find(q, {"_id": 0}).sort([("tanggal", -1), ("created_at", -1)]).to_list(5000)
    accs = {a["id"]: a["nama"] for a in await db.accounts.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(50)}
    for r in rows:
        r["account_nama"] = accs.get(r["account_id"])
    return rows


@router.post("/finance/transactions")
async def create_transaction(body: TransactionIn, user: dict = Depends(FIN)):
    if body.jenis not in ("pemasukan", "pengeluaran"):
        raise HTTPException(status_code=400, detail="Jenis transaksi tidak valid")
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    if not await db.accounts.find_one({"id": body.account_id}):
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    doc = {**body.model_dump(exclude={"alasan"}), "id": new_id(), "ref_type": "manual", "ref_id": None,
           "petugas": user["name"], "created_at": now_iso()}
    await db.transactions.insert_one(doc)
    await log_audit("transaction", doc["id"], "create", user, None, {"jenis": body.jenis, "kategori": body.kategori, "nominal": body.nominal})
    return clean(doc)


@router.put("/finance/transactions/{tx_id}")
async def update_transaction(tx_id: str, body: TransactionIn, user: dict = Depends(FIN)):
    old = await db.transactions.find_one({"id": tx_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    if old.get("ref_type") == "payment":
        raise HTTPException(status_code=400, detail="Transaksi pembayaran siswa harus diubah dari modul Pembayaran")
    if not body.alasan:
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi")
    upd = body.model_dump(exclude={"alasan"})
    await db.transactions.update_one({"id": tx_id}, {"$set": upd})
    await log_audit("transaction", tx_id, "update", user, {"nominal": old["nominal"], "kategori": old["kategori"]},
                    {"nominal": body.nominal, "kategori": body.kategori}, body.alasan)
    return clean(await db.transactions.find_one({"id": tx_id}, {"_id": 0}))


@router.delete("/finance/transactions/{tx_id}")
async def delete_transaction(tx_id: str, alasan: str = "", user: dict = Depends(require_roles())):
    old = await db.transactions.find_one({"id": tx_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    if old.get("ref_type") == "payment":
        raise HTTPException(status_code=400, detail="Hapus melalui modul Pembayaran")
    await db.transactions.delete_one({"id": tx_id})
    await log_audit("transaction", tx_id, "delete", user, {"nominal": old["nominal"], "kategori": old["kategori"]}, None, alasan)
    return {"ok": True}


@router.get("/finance/summary")
async def finance_summary(period: str = "bulan", user: dict = Depends(FIN_READ)):
    start, end = period_range(period)
    rows = await db.transactions.aggregate([{"$match": {"tanggal": {"$gte": start, "$lte": end}}},
                                            {"$group": {"_id": "$jenis", "n": {"$sum": "$nominal"}}}]).to_list(10)
    m = {r["_id"]: r["n"] for r in rows}
    accounts = await account_balances()
    today_pay = await db.payments.aggregate([{"$match": {"tanggal": today_str()}}, {"$group": {"_id": None, "n": {"$sum": "$nominal"}}}]).to_list(1)
    students = await db.students.find({"status": {"$nin": ["calon_siswa", "gagal"]}}, {"_id": 0, "id": 1, "fee_plan": 1}).to_list(5000)
    pay = await payment_summary_map()
    piutang = sum(max(fee_total(s) - pay.get(s["id"], {}).get("bayar", 0), 0) for s in students)
    by_cat = await db.transactions.aggregate([{"$match": {"tanggal": {"$gte": start, "$lte": end}, "jenis": "pengeluaran"}},
                                              {"$group": {"_id": "$kategori", "n": {"$sum": "$nominal"}}}, {"$sort": {"n": -1}}]).to_list(50)
    return {"period": period, "dari": start, "sampai": end, "pemasukan": m.get("pemasukan", 0), "pengeluaran": m.get("pengeluaran", 0),
            "laba": m.get("pemasukan", 0) - m.get("pengeluaran", 0), "saldo_kas": sum(a["saldo"] for a in accounts),
            "accounts": accounts, "piutang": piutang, "pembayaran_hari_ini": today_pay[0]["n"] if today_pay else 0,
            "pengeluaran_per_kategori": [{"kategori": r["_id"], "nominal": r["n"]} for r in by_cat]}


@router.get("/finance/cashflow")
async def cashflow(bulan: int = 6, user: dict = Depends(FIN_READ)):
    rows = await db.transactions.aggregate([{"$group": {"_id": {"b": {"$substr": ["$tanggal", 0, 7]}, "j": "$jenis"}, "n": {"$sum": "$nominal"}}}]).to_list(500)
    m: Dict[str, Dict[str, float]] = {}
    for r in rows:
        m.setdefault(r["_id"]["b"], {"pemasukan": 0, "pengeluaran": 0})[r["_id"]["j"]] = r["n"]
    t = date.today()
    out = []
    for i in range(bulan - 1, -1, -1):
        y, mo = t.year, t.month - i
        while mo <= 0:
            mo += 12
            y -= 1
        key = f"{y}-{mo:02d}"
        out.append({"bulan": key, **m.get(key, {"pemasukan": 0, "pengeluaran": 0})})
    return out


# ---------- Pembayaran Siswa ----------
async def next_receipt_no() -> str:
    n = await db.payments.count_documents({}) + 1
    return f"KW-{date.today().strftime('%Y%m')}-{n:04d}"


@router.get("/payments")
async def list_payments(student_id: Optional[str] = None, dari: Optional[str] = None, sampai: Optional[str] = None,
                        user: dict = Depends(FIN_READ)):
    q: Dict[str, Any] = {}
    if student_id:
        q["student_id"] = student_id
    if dari or sampai:
        q["tanggal"] = {k: v for k, v in (("$gte", dari), ("$lte", sampai)) if v}
    rows = await db.payments.find(q, {"_id": 0}).sort([("tanggal", -1), ("created_at", -1)]).to_list(5000)
    return rows


@router.post("/payments")
async def create_payment(body: PaymentIn, user: dict = Depends(FIN)):
    s = await db.students.find_one({"id": body.student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    acc = await db.accounts.find_one({"id": body.account_id}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tujuan tidak ditemukan")
    pay = await payment_summary_map([s["id"]])
    sudah = pay.get(s["id"], {}).get("bayar", 0)
    total = fee_total(s)
    doc = {**body.model_dump(exclude={"alasan"}), "id": new_id(), "no_kwitansi": await next_receipt_no(),
           "student_nama": s["nama_lengkap"], "account_nama": acc["nama"], "petugas": user["name"],
           "sisa_setelah": max(total - sudah - body.nominal, 0), "created_at": now_iso()}
    await db.payments.insert_one(doc)
    await db.transactions.insert_one({"id": new_id(), "jenis": "pemasukan", "kategori": "Pembayaran Siswa", "nominal": body.nominal,
                                      "tanggal": body.tanggal, "deskripsi": f"Pembayaran {body.jenis} - {s['nama_lengkap']} ({doc['no_kwitansi']})",
                                      "account_id": body.account_id, "metode": body.metode, "bukti_file_id": body.bukti_file_id,
                                      "ref_type": "payment", "ref_id": doc["id"], "petugas": user["name"], "created_at": now_iso()})
    await log_audit("payment", doc["id"], "create", user, None, {"student": s["nama_lengkap"], "nominal": body.nominal, "no_kwitansi": doc["no_kwitansi"]})
    return clean(doc)


@router.put("/payments/{pay_id}")
async def update_payment(pay_id: str, body: PaymentIn, user: dict = Depends(FIN)):
    old = await db.payments.find_one({"id": pay_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    if not body.alasan:
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi untuk audit")
    acc = await db.accounts.find_one({"id": body.account_id}, {"_id": 0})
    upd = {**body.model_dump(exclude={"alasan", "student_id"}), "account_nama": acc["nama"] if acc else old.get("account_nama")}
    await db.payments.update_one({"id": pay_id}, {"$set": upd})
    await db.transactions.update_one({"ref_type": "payment", "ref_id": pay_id},
                                     {"$set": {"nominal": body.nominal, "tanggal": body.tanggal, "account_id": body.account_id, "metode": body.metode}})
    await log_audit("payment", pay_id, "update", user, {"nominal": old["nominal"], "tanggal": old["tanggal"], "metode": old["metode"]},
                    {"nominal": body.nominal, "tanggal": body.tanggal, "metode": body.metode}, body.alasan)
    return clean(await db.payments.find_one({"id": pay_id}, {"_id": 0}))


@router.delete("/payments/{pay_id}")
async def delete_payment(pay_id: str, alasan: str = "", user: dict = Depends(require_roles())):
    old = await db.payments.find_one({"id": pay_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    await db.payments.delete_one({"id": pay_id})
    await db.transactions.delete_one({"ref_type": "payment", "ref_id": pay_id})
    await log_audit("payment", pay_id, "delete", user, {"nominal": old["nominal"], "student": old["student_nama"]}, None, alasan)
    return {"ok": True}


@router.get("/payments/{pay_id}/receipt")
async def receipt(pay_id: str, user: dict = Depends(FIN_READ)):
    p = await db.payments.find_one({"id": pay_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    s = await db.students.find_one({"id": p["student_id"]}, {"_id": 0})
    pay = await payment_summary_map([p["student_id"]])
    total = fee_total(s) if s else 0
    bayar = pay.get(p["student_id"], {}).get("bayar", 0)
    return {**p, "total_tagihan": total, "total_dibayar": bayar, "sisa": max(total - bayar, 0), "fee_plan": s.get("fee_plan", []) if s else [],
            "alamat": s.get("alamat", {}) if s else {}, "no_hp": s.get("no_hp") if s else ""}


@router.get("/payments-arrears")
async def arrears(filter: Optional[str] = None, user: dict = Depends(FIN_READ)):
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
            if jt < t:
                kondisi = "terlambat"
            elif jt == t:
                kondisi = "hari_ini"
            else:
                kondisi = "akan_jatuh_tempo"
        if filter and filter != kondisi:
            continue
        out.append({"id": s["id"], "nama_lengkap": s["nama_lengkap"], "status": s["status"], "no_hp": s.get("no_hp"), "total": total,
                    "bayar": bayar, "sisa": sisa, "jatuh_tempo": jt, "kondisi": kondisi, "terakhir": pay.get(s["id"], {}).get("terakhir")})
    out.sort(key=lambda x: (x["jatuh_tempo"] or "9999"))
    return out


# ---------- Rekonsiliasi ----------
@router.get("/finance/reconciliations")
async def list_recon(user: dict = Depends(FIN_READ)):
    rows = await db.reconciliations.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return rows


@router.post("/finance/reconciliations")
async def create_recon(body: ReconIn, user: dict = Depends(FIN)):
    accounts = {a["id"]: a for a in await account_balances()}
    acc = accounts.get(body.account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    selisih = body.saldo_aktual - acc["saldo"]
    if selisih != 0 and not body.alasan:
        raise HTTPException(status_code=400, detail="Alasan selisih wajib diisi")
    doc = {"id": new_id(), "account_id": body.account_id, "account_nama": acc["nama"], "tanggal": body.tanggal,
           "saldo_sistem": acc["saldo"], "saldo_aktual": body.saldo_aktual, "selisih": selisih, "alasan": body.alasan,
           "petugas": user["name"], "created_at": now_iso()}
    await db.reconciliations.insert_one(doc)
    await log_audit("reconciliation", doc["id"], "create", user, {"saldo_sistem": acc["saldo"]}, {"saldo_aktual": body.saldo_aktual}, body.alasan)
    return clean(doc)
