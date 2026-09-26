from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import (db, require_roles, new_id, now_iso, today_str, clean, log_audit, period_range,
                  payment_summary_map, fee_total, parse_date, today)
from pg_mongo import DuplicateKeyError

router = APIRouter()
FIN = require_roles("finance")
FIN_READ = require_roles("finance", "admin")
EXP_READ = require_roles("finance", "admin", "staff", "marketing")
EXP_WRITE = require_roles("finance", "staff", "marketing")
EXP_APPROVE = require_roles("finance")
EXP_PAY = require_roles("finance")
INCOME_CATS = ["Pembayaran Siswa", "Pendaftaran", "Pelatihan", "Asrama", "Administrasi", "Pendapatan Lainnya"]
EXPENSE_CATS = ["Gaji", "Honor Guru", "Listrik", "Internet", "Air", "Sewa Gedung", "Makan Siswa", "Transportasi", "ATK",
                "Perawatan", "Pajak", "Operasional Lainnya"]
LINKED_TYPES = ("payment", "payroll", "expense")
# BDN-01: nominal >= threshold wajib Owner; di bawah threshold Finance boleh approve.
EXPENSE_OWNER_THRESHOLD = 1000000
EXPENSE_STATUSES = ["draft", "diajukan", "disetujui", "ditolak", "dibayar", "dibatalkan"]


def _check_kategori(jenis: str, kategori: str):
    allowed = INCOME_CATS if jenis == "pemasukan" else EXPENSE_CATS
    if kategori not in allowed:
        raise HTTPException(status_code=400, detail=f"Kategori tidak valid untuk {jenis}")


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
    idem_key: Optional[str] = ""


class ReconIn(BaseModel):
    account_id: str
    tanggal: str
    saldo_aktual: float
    alasan: Optional[str] = ""


async def account_balances() -> list:
    accounts = await db.accounts.find({}, {"_id": 0}).to_list(None)
    rows = await db.transactions.aggregate([{"$group": {"_id": {"a": "$account_id", "j": "$jenis"}, "n": {"$sum": "$nominal"}}}]).to_list(None)
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
    rows = await db.transactions.find(q, {"_id": 0}).sort([("tanggal", -1), ("created_at", -1)]).to_list(None)
    accs = {a["id"]: a["nama"] for a in await db.accounts.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(None)}
    for r in rows:
        r["account_nama"] = accs.get(r["account_id"])
    return rows


@router.post("/finance/transactions")
async def create_transaction(body: TransactionIn, user: dict = Depends(FIN)):
    if body.jenis not in ("pemasukan", "pengeluaran"):
        raise HTTPException(status_code=400, detail="Jenis transaksi tidak valid")
    _check_kategori(body.jenis, body.kategori)
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    body.tanggal = parse_date(body.tanggal)
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
    if old.get("ref_type") in LINKED_TYPES:
        raise HTTPException(status_code=400, detail="Transaksi tertaut (payment/payroll/expense) tidak dapat diubah manual. Gunakan modul asalnya.")
    if not body.alasan:
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi")
    if body.jenis not in ("pemasukan", "pengeluaran"):
        raise HTTPException(status_code=400, detail="Jenis transaksi tidak valid")
    _check_kategori(body.jenis, body.kategori)
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    body.tanggal = parse_date(body.tanggal)
    if not await db.accounts.find_one({"id": body.account_id}):
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    upd = body.model_dump(exclude={"alasan"})
    await db.transactions.update_one({"id": tx_id}, {"$set": upd})
    await log_audit("transaction", tx_id, "update", user, {"nominal": old["nominal"], "kategori": old["kategori"]},
                    {"nominal": body.nominal, "kategori": body.kategori}, body.alasan)
    return clean(await db.transactions.find_one({"id": tx_id}, {"_id": 0}))


@router.delete("/finance/transactions/{tx_id}")
async def delete_transaction(tx_id: str, alasan: str = "", user: dict = Depends(require_roles("owner"))):
    old = await db.transactions.find_one({"id": tx_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    if old.get("ref_type") in LINKED_TYPES:
        raise HTTPException(status_code=400, detail="Transaksi tertaut (payment/payroll/expense) tidak dapat dihapus manual. Gunakan modul asalnya.")
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
    students = await db.students.find({"status": {"$nin": ["calon_siswa", "gagal"]}}, {"_id": 0, "id": 1, "fee_plan": 1}).to_list(None)
    pay = await payment_summary_map()
    piutang = sum(max(fee_total(s) - pay.get(s["id"], {}).get("bayar", 0), 0) for s in students)
    by_cat = await db.transactions.aggregate([{"$match": {"tanggal": {"$gte": start, "$lte": end}, "jenis": "pengeluaran"}},
                                              {"$group": {"_id": "$kategori", "n": {"$sum": "$nominal"}}}, {"$sort": {"n": -1}}]).to_list(None)
    return {"period": period, "dari": start, "sampai": end, "pemasukan": m.get("pemasukan", 0), "pengeluaran": m.get("pengeluaran", 0),
            "laba": m.get("pemasukan", 0) - m.get("pengeluaran", 0), "saldo_kas": sum(a["saldo"] for a in accounts),
            "accounts": accounts, "piutang": piutang, "pembayaran_hari_ini": today_pay[0]["n"] if today_pay else 0,
            "pengeluaran_per_kategori": [{"kategori": r["_id"], "nominal": r["n"]} for r in by_cat]}


@router.get("/finance/cashflow")
async def cashflow(bulan: int = 6, user: dict = Depends(FIN_READ)):
    rows = await db.transactions.aggregate([{"$group": {"_id": {"b": {"$substr": ["$tanggal", 0, 7]}, "j": "$jenis"}, "n": {"$sum": "$nominal"}}}]).to_list(None)
    m: Dict[str, Dict[str, float]] = {}
    for r in rows:
        m.setdefault(r["_id"]["b"], {"pemasukan": 0, "pengeluaran": 0})[r["_id"]["j"]] = r["n"]
    t = today()
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
    c = await db.counters.find_one_and_update({"_id": "kwitansi"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return f"KW-{today().strftime('%Y%m')}-{c['seq']:04d}"


@router.get("/payments")
async def list_payments(student_id: Optional[str] = None, dari: Optional[str] = None, sampai: Optional[str] = None,
                        user: dict = Depends(FIN_READ)):
    q: Dict[str, Any] = {}
    if student_id:
        q["student_id"] = student_id
    if dari or sampai:
        q["tanggal"] = {k: v for k, v in (("$gte", dari), ("$lte", sampai)) if v}
    rows = await db.payments.find(q, {"_id": 0}).sort([("tanggal", -1), ("created_at", -1)]).to_list(None)
    return rows


@router.post("/payments")
async def create_payment(body: PaymentIn, user: dict = Depends(FIN)):
    if body.idem_key:
        dup = await db.payments.find_one({"idem_key": body.idem_key}, {"_id": 0})
        if dup:
            return await _resolve_duplicate_payment(dup, user)
    s = await db.students.find_one({"id": body.student_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    body.tanggal = parse_date(body.tanggal)
    acc = await db.accounts.find_one({"id": body.account_id}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tujuan tidak ditemukan")
    pay = await payment_summary_map([s["id"]])
    sudah = pay.get(s["id"], {}).get("bayar", 0)
    total = fee_total(s)
    _check_not_overpaid(body.nominal, total, sudah)
    doc = {**body.model_dump(exclude={"alasan"}), "id": new_id(), "no_kwitansi": await next_receipt_no(),
           "student_nama": s["nama_lengkap"], "account_nama": acc["nama"], "petugas": user["name"],
           "sisa_setelah": max(total - sudah - body.nominal, 0), "created_at": now_iso()}
    if not doc.get("idem_key"):
        doc.pop("idem_key", None)
    try:
        await db.payments.insert_one(doc)
    except DuplicateKeyError:
        dup = await db.payments.find_one({"idem_key": body.idem_key}, {"_id": 0}) if body.idem_key else None
        if dup:
            return await _resolve_duplicate_payment(dup, user)
        raise
    await db.transactions.insert_one(_payment_tx(doc, s))
    await log_audit("payment", doc["id"], "create", user, None, {"student": s["nama_lengkap"], "nominal": body.nominal, "no_kwitansi": doc["no_kwitansi"]})
    try:
        from routers.whatsapp import dispatch_event
        await dispatch_event("payment_received", s["id"], f"pay:{doc['id']}",
                             {"nama": s["nama_lengkap"],
                              "jumlah": f"Rp{body.nominal:,.0f}".replace(",", "."),
                              "tanggal": body.tanggal, "nomor_kwitansi": doc["no_kwitansi"]},
                             ["siswa", "wali"])
    except Exception as ex:
        from core import logger as _logger
        _logger.error(f"WA payment_received gagal: {ex}")
    return clean(doc)


def _check_not_overpaid(nominal: float, total: float, sudah: float) -> None:
    sisa = max(total - sudah, 0)
    if nominal > sisa:
        raise HTTPException(status_code=400, detail=f"Nominal melebihi sisa tagihan (Rp{sisa:,.0f})".replace(",", "."))


def _payment_tx(doc: dict, s: dict) -> dict:
    return {"id": new_id(), "jenis": "pemasukan", "kategori": "Pembayaran Siswa", "nominal": doc["nominal"],
            "tanggal": doc["tanggal"], "deskripsi": f"Pembayaran {doc.get('jenis')} - {s['nama_lengkap']} ({doc['no_kwitansi']})",
            "account_id": doc["account_id"], "metode": doc.get("metode"), "bukti_file_id": doc.get("bukti_file_id"),
            "ref_type": "payment", "ref_id": doc["id"], "petugas": doc.get("petugas"), "created_at": now_iso()}


async def _resolve_duplicate_payment(dup: dict, user: dict) -> dict:
    """Idempotent retry: kembalikan payment existing; pulihkan tx bila hilang (partial failure healing)."""
    tx = await db.transactions.find_one({"ref_type": "payment", "ref_id": dup["id"]}, {"_id": 0})
    healed = False
    if not tx:
        s = await db.students.find_one({"id": dup["student_id"]}, {"_id": 0})
        if s:
            await db.transactions.insert_one(_payment_tx(dup, s))
            healed = True
            await log_audit("transaction", dup["id"], "heal", user, None,
                            {"ref_type": "payment", "ref_id": dup["id"], "nominal": dup["nominal"]})
    return {**clean(dup), "duplicate": True, "healed": healed}


@router.put("/payments/{pay_id}")
async def update_payment(pay_id: str, body: PaymentIn, user: dict = Depends(FIN)):
    old = await db.payments.find_one({"id": pay_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    if not body.alasan:
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi untuk audit")
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    body.tanggal = parse_date(body.tanggal)
    acc = await db.accounts.find_one({"id": body.account_id}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tujuan tidak ditemukan")
    s = await db.students.find_one({"id": old["student_id"]}, {"_id": 0})
    total = fee_total(s) if s else 0
    sudah_lain = (await payment_summary_map([old["student_id"]])).get(old["student_id"], {}).get("bayar", 0) - old["nominal"]
    _check_not_overpaid(body.nominal, total, sudah_lain)
    upd = {**body.model_dump(exclude={"alasan", "student_id"}), "account_nama": acc["nama"],
           "sisa_setelah": max(total - sudah_lain - body.nominal, 0)}
    upd.pop("idem_key", None)
    await db.payments.update_one({"id": pay_id}, {"$set": upd, "$unset": {"idem_key": ""}})
    await db.transactions.update_one({"ref_type": "payment", "ref_id": pay_id},
                                     {"$set": {"nominal": body.nominal, "tanggal": body.tanggal, "account_id": body.account_id, "metode": body.metode}})
    await log_audit("payment", pay_id, "update", user, {"nominal": old["nominal"], "tanggal": old["tanggal"], "metode": old["metode"]},
                    {"nominal": body.nominal, "tanggal": body.tanggal, "metode": body.metode}, body.alasan)
    return clean(await db.payments.find_one({"id": pay_id}, {"_id": 0}))


@router.delete("/payments/{pay_id}")
async def delete_payment(pay_id: str, alasan: str = "", user: dict = Depends(require_roles("owner"))):
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
    students = await db.students.find({"status": {"$nin": ["calon_siswa", "gagal", "alumni"]}}, {"_id": 0}).to_list(None)
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
    rows = await db.reconciliations.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
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


# ---------- Expense Request / Approval ----------
class ExpenseIn(BaseModel):
    judul: str
    kategori: str
    nominal: float
    tanggal: str
    deskripsi: Optional[str] = ""
    account_id: Optional[str] = ""
    bukti_file_id: Optional[str] = None


class ExpenseUpdateIn(BaseModel):
    judul: Optional[str] = None
    kategori: Optional[str] = None
    nominal: Optional[float] = None
    tanggal: Optional[str] = None
    deskripsi: Optional[str] = None
    account_id: Optional[str] = None
    bukti_file_id: Optional[str] = None
    alasan: Optional[str] = ""


class ExpenseDecideIn(BaseModel):
    setuju: bool
    alasan: Optional[str] = ""


class ExpensePayIn(BaseModel):
    account_id: Optional[str] = None


async def _next_expense_no() -> str:
    c = await db.counters.find_one_and_update({"_id": "expense"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return f"EXP-{today().strftime('%Y%m')}-{c['seq']:04d}"


def _expense_actor_ok(exp: dict, user: dict) -> bool:
    return user["role"] in ("owner", "finance") or exp.get("created_by_id") == user["id"]


def _expense_hist(exp: dict, aksi: str, user: dict, alasan: str = "") -> list:
    h = exp.get("history", [])
    h.append({"aksi": aksi, "oleh": user["name"], "role": user["role"],
              "tanggal": now_iso(), **({"alasan": alasan} if alasan else {})})
    return h


@router.get("/expenses")
async def list_expenses(status: Optional[str] = None, dari: Optional[str] = None, sampai: Optional[str] = None,
                        user: dict = Depends(EXP_READ)):
    q: Dict[str, Any] = {}
    if status:
        if status not in EXPENSE_STATUSES:
            raise HTTPException(status_code=400, detail="Status expense tidak valid")
        q["status"] = status
    if dari or sampai:
        q["tanggal"] = {k: v for k, v in (("$gte", dari), ("$lte", sampai)) if v}
    rows = await db.expenses.find(q, {"_id": 0}).sort([("tanggal", -1), ("created_at", -1)]).to_list(None)
    accs = {a["id"]: a["nama"] for a in await db.accounts.find({}, {"_id": 0, "id": 1, "nama": 1}).to_list(None)}
    for r in rows:
        r["account_nama"] = accs.get(r["account_id"])
    return rows


@router.get("/expenses/{exp_id}")
async def get_expense(exp_id: str, user: dict = Depends(EXP_READ)):
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    return exp


@router.post("/expenses")
async def create_expense(body: ExpenseIn, user: dict = Depends(EXP_WRITE)):
    if body.nominal <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    _check_kategori("pengeluaran", body.kategori)
    if body.account_id and not await db.accounts.find_one({"id": body.account_id}):
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    doc = {**body.model_dump(), "id": new_id(), "no_ref": await _next_expense_no(), "status": "draft",
           "transaction_id": None, "created_by": user["name"], "created_by_id": user["id"],
           "approved_by": None, "approved_at": None, "paid_by": None, "paid_at": None,
           "history": [], "created_at": now_iso(), "updated_at": now_iso()}
    doc["history"] = _expense_hist(doc, "create", user)
    await db.expenses.insert_one(doc)
    await log_audit("expense", doc["id"], "create", user, None, {"judul": body.judul, "nominal": body.nominal})
    return clean(doc)


@router.put("/expenses/{exp_id}")
async def update_expense(exp_id: str, body: ExpenseUpdateIn, user: dict = Depends(EXP_WRITE)):
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    if exp["status"] != "draft":
        raise HTTPException(status_code=400, detail="Hanya draft yang dapat diubah")
    if not _expense_actor_ok(exp, user):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk mengubah pengajuan ini")
    if not (body.alasan or "").strip():
        raise HTTPException(status_code=400, detail="Alasan perubahan wajib diisi untuk audit")
    upd = {k: v for k, v in body.model_dump(exclude={"alasan"}).items() if v is not None}
    if "nominal" in upd and upd["nominal"] <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    if "kategori" in upd:
        _check_kategori("pengeluaran", upd["kategori"])
    if "account_id" in upd and not await db.accounts.find_one({"id": upd["account_id"]}):
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    before = {k: exp.get(k) for k in upd}
    await db.expenses.update_one({"id": exp_id}, {"$set": {**upd, "history": _expense_hist(exp, "update", user, body.alasan.strip()), "updated_at": now_iso()}})
    await log_audit("expense", exp_id, "update", user, before, {k: upd[k] for k in before}, body.alasan.strip())
    return clean(await db.expenses.find_one({"id": exp_id}, {"_id": 0}))


@router.post("/expenses/{exp_id}/submit")
async def submit_expense(exp_id: str, user: dict = Depends(EXP_WRITE)):
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    if exp["status"] != "draft":
        raise HTTPException(status_code=400, detail="Hanya draft yang dapat diajukan")
    if not _expense_actor_ok(exp, user):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk mengajukan ini")
    res = await db.expenses.update_one({"id": exp_id, "status": "draft"},
                                       {"$set": {"status": "diajukan", "history": _expense_hist(exp, "submit", user), "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail="Pengajuan sudah diproses oleh pengguna lain")
    await log_audit("expense", exp_id, "submit", user, {"status": "draft"}, {"status": "diajukan"})
    return clean(await db.expenses.find_one({"id": exp_id}, {"_id": 0}))


@router.post("/expenses/{exp_id}/cancel")
async def cancel_expense(exp_id: str, user: dict = Depends(EXP_WRITE)):
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    if exp["status"] != "draft":
        raise HTTPException(status_code=400, detail="Hanya draft yang dapat dibatalkan")
    if not _expense_actor_ok(exp, user):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk membatalkan ini")
    res = await db.expenses.update_one({"id": exp_id, "status": "draft"},
                                       {"$set": {"status": "dibatalkan", "history": _expense_hist(exp, "cancel", user), "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail="Pengajuan sudah diproses oleh pengguna lain")
    await log_audit("expense", exp_id, "cancel", user, {"status": "draft"}, {"status": "dibatalkan"})
    return clean(await db.expenses.find_one({"id": exp_id}, {"_id": 0}))


@router.post("/expenses/{exp_id}/decide")
async def decide_expense(exp_id: str, body: ExpenseDecideIn, user: dict = Depends(EXP_APPROVE)):
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    if exp["status"] != "diajukan":
        raise HTTPException(status_code=400, detail="Hanya pengajuan yang diajukan yang dapat diputuskan")
    # Pemisahan tugas: pembuat pengajuan tidak memutuskan pengajuannya sendiri (owner dikecualikan).
    if exp.get("created_by_id") == user["id"] and user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Pengajuan milik sendiri harus diputuskan oleh pengguna lain")
    if body.setuju and exp["nominal"] >= EXPENSE_OWNER_THRESHOLD and user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Nominal di atas Rp1.000.000 membutuhkan persetujuan Owner")
    if not body.setuju and not (body.alasan or "").strip():
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi")
    if body.setuju:
        upd = {"status": "disetujui", "approved_by": user["name"], "approved_at": now_iso()}
        res = await db.expenses.update_one({"id": exp_id, "status": "diajukan"},
                                           {"$set": {**upd, "history": _expense_hist(exp, "approve", user), "updated_at": now_iso()}})
        if not res.matched_count:
            raise HTTPException(status_code=409, detail="Pengajuan sudah diproses oleh pengguna lain")
        await log_audit("expense", exp_id, "approve", user, {"status": "diajukan"}, {"status": "disetujui", "nominal": exp["nominal"]})
    else:
        res = await db.expenses.update_one({"id": exp_id, "status": "diajukan"},
                                           {"$set": {"status": "ditolak", "history": _expense_hist(exp, "reject", user, body.alasan.strip()), "updated_at": now_iso()}})
        if not res.matched_count:
            raise HTTPException(status_code=409, detail="Pengajuan sudah diproses oleh pengguna lain")
        await log_audit("expense", exp_id, "reject", user, {"status": "diajukan"}, {"status": "ditolak"}, body.alasan.strip())
    return clean(await db.expenses.find_one({"id": exp_id}, {"_id": 0}))


@router.post("/expenses/{exp_id}/pay")
async def pay_expense(exp_id: str, body: ExpensePayIn, user: dict = Depends(EXP_PAY)):
    exp = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
    if not exp:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    if exp.get("transaction_id"):
        tx = await db.transactions.find_one({"id": exp["transaction_id"]}, {"_id": 0})
        if tx:
            return {**clean(exp), "already_paid": True}
    if exp["status"] != "disetujui":
        raise HTTPException(status_code=400, detail="Hanya expense yang disetujui yang dapat dibayar")
    account_id = body.account_id or exp["account_id"]
    acc = await db.accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    tx = {"id": new_id(), "jenis": "pengeluaran", "kategori": exp["kategori"], "nominal": exp["nominal"],
          "tanggal": today_str(), "deskripsi": f"{exp['judul']} ({exp['no_ref']})",
          "account_id": account_id, "account_nama": acc["nama"], "metode": "transfer", "bukti_file_id": exp.get("bukti_file_id"),
          "ref_type": "expense", "ref_id": exp_id, "petugas": user["name"], "created_at": now_iso()}
    try:
        await db.transactions.insert_one(tx)
    except DuplicateKeyError:
        tx2 = await db.transactions.find_one({"ref_type": "expense", "ref_id": exp_id}, {"_id": 0})
        if not tx2:
            raise
        cur = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
        if not cur.get("transaction_id"):
            await db.expenses.update_one({"id": exp_id}, {"$set": {"status": "dibayar", "account_id": tx2["account_id"],
                                                                   "transaction_id": tx2["id"], "paid_by": user["name"],
                                                                   "paid_at": now_iso(),
                                                                   "history": _expense_hist(cur, "pay", user),
                                                                   "updated_at": now_iso()}})
            await log_audit("expense", exp_id, "pay", user, {"status": "disetujui"},
                            {"status": "dibayar", "nominal": exp["nominal"], "transaction_id": tx2["id"]})
        return {**clean(await db.expenses.find_one({"id": exp_id}, {"_id": 0})), "already_paid": True}
    await db.expenses.update_one({"id": exp_id}, {"$set": {"status": "dibayar", "account_id": account_id,
                                                           "transaction_id": tx["id"], "paid_by": user["name"],
                                                           "paid_at": now_iso(),
                                                           "history": _expense_hist(exp, "pay", user),
                                                           "updated_at": now_iso()}})
    await log_audit("expense", exp_id, "pay", user, {"status": "disetujui"},
                    {"status": "dibayar", "nominal": exp["nominal"], "transaction_id": tx["id"]})
    await log_audit("transaction", tx["id"], "create", user, None,
                    {"jenis": "pengeluaran", "kategori": exp["kategori"], "nominal": exp["nominal"]})
    return clean(await db.expenses.find_one({"id": exp_id}, {"_id": 0}))
