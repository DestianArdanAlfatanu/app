import os
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from zoneinfo import ZoneInfo

import bcrypt
import jwt
from fastapi import Request, HTTPException, Depends, Query
from pg_mongo import PgClient

client = PgClient(os.environ["DATABASE_URL"])
db = client[os.environ.get("DB_NAME", "lpk")]
logger = logging.getLogger("lpk")

ROLES = ["owner", "admin", "finance", "hr", "guru", "marketing", "staff"]
STUDENT_STATUSES = [
    "calon_siswa", "pendaftaran", "seleksi", "diterima", "pelatihan", "ujian",
    "lulus", "matching", "pemberkasan", "visa", "berangkat", "alumni", "gagal",
]
DOC_TYPES = [
    ("identitas", "KTP"), ("identitas", "Kartu Keluarga"), ("identitas", "Akta Kelahiran"), ("identitas", "SKCK"),
    ("pendidikan", "Ijazah"), ("pendidikan", "Transkrip Nilai"),
    ("kesehatan", "Medical Check-up"),
    ("jepang", "Paspor"), ("jepang", "Sertifikat JLPT"), ("jepang", "COE"), ("jepang", "Visa"), ("jepang", "Tiket"),
    ("kontrak", "Kontrak Kerja"),
]
JLPT_ORDER = {"-": 0, "N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}
JWT_ALGORITHM = "HS256"
# Zona waktu bisnis untuk "hari ini" (tanggal transaksi, absensi, jatuh tempo). Timestamp tetap disimpan UTC.
BUSINESS_TZ = ZoneInfo(os.environ.get("LPK_TZ", "Asia/Jakarta"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> date:
    return datetime.now(BUSINESS_TZ).date()


def today_str() -> str:
    return today().isoformat()


def local_day_start_utc(d: date) -> str:
    """Awal hari lokal d dalam UTC ISO, untuk membandingkan dengan timestamp now_iso()."""
    return datetime(d.year, d.month, d.day, tzinfo=BUSINESS_TZ).astimezone(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def clean(doc):
    if doc:
        doc.pop("_id", None)
    return doc


def clean_list(docs):
    return [clean(d) for d in docs]


def compute_age(tanggal_lahir: Optional[str]) -> Optional[int]:
    if not tanggal_lahir:
        return None
    try:
        b = date.fromisoformat(tanggal_lahir[:10])
    except ValueError:
        return None
    t = today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def period_range(period: str):
    t = today()
    if period == "hari":
        start = t
    elif period == "minggu":
        start = t - timedelta(days=t.weekday())
    elif period == "tahun":
        start = t.replace(month=1, day=1)
    else:
        start = t.replace(day=1)
    return start.isoformat(), t.isoformat()


# ---------- Auth ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {"sub": user_id, "email": email, "role": role, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh", "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def public_user(user: dict) -> dict:
    user = clean(dict(user))
    user.pop("password_hash", None)
    return user


async def user_from_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Tipe token tidak valid")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user or not user.get("aktif", True):
        raise HTTPException(status_code=401, detail="Pengguna tidak ditemukan")
    return public_user(user)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Belum login")
    return await user_from_token(token)


def require_roles(*roles):
    async def dep(user: dict = Depends(get_current_user)):
        if user["role"] == "owner" or user["role"] in roles:
            return user
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini")
    return dep


async def guru_class_ids(user: dict) -> Optional[set]:
    """Kelas milik guru yang login; None untuk role non-guru (tidak dibatasi)."""
    if user.get("role") != "guru":
        return None
    rows = await db.classes.find({"guru_id": user.get("employee_id")}, {"_id": 0, "id": 1}).to_list(None)
    return {c["id"] for c in rows}


async def ensure_guru_class(user: dict, class_id: Optional[str]) -> None:
    own = await guru_class_ids(user)
    if own is not None and class_id not in own:
        raise HTTPException(status_code=403, detail="Anda bukan pengajar kelas ini")


async def ensure_guru_student(user: dict, student_id: str) -> None:
    own = await guru_class_ids(user)
    if own is None:
        return
    s = await db.students.find_one({"id": student_id}, {"_id": 0, "class_id": 1})
    if not s or s.get("class_id") not in own:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke siswa ini")


def parse_date(value: Optional[str], field: str = "Tanggal", allow_future: bool = True) -> Optional[str]:
    """Validasi tanggal ISO YYYY-MM-DD; kembalikan string ternormalisasi."""
    if value in (None, ""):
        return value
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} tidak valid (format YYYY-MM-DD)")
    if not allow_future and d > today():
        raise HTTPException(status_code=400, detail=f"{field} tidak boleh di masa depan")
    return d.isoformat()


def deny_student(user: dict) -> dict:
    """Tolak role student pada endpoint internal. Aditif; perilaku staff tidak berubah."""
    if user.get("role") == "student":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    return user


# ---------- Login throttling ----------
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15


async def login_locked(ident: str) -> bool:
    a = await db.login_attempts.find_one({"identifier": ident})
    return bool(a and a.get("count", 0) >= LOGIN_MAX_ATTEMPTS and a.get("locked_until", "") > now_iso())


async def record_login_failure(ident: str) -> None:
    """Catat gagal login. Setelah masa kunci habis hitungan mulai dari 1 lagi, bukan langsung terkunci ulang."""
    locked = (datetime.now(timezone.utc) + timedelta(minutes=LOGIN_LOCK_MINUTES)).isoformat()
    a = await db.login_attempts.find_one({"identifier": ident})
    if a and a.get("count", 0) >= LOGIN_MAX_ATTEMPTS and a.get("locked_until", "") <= now_iso():
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {"count": 1, "locked_until": locked}})
    else:
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"locked_until": locked}},
                                           upsert=True)


# ---------- Audit ----------
async def log_audit(entity: str, entity_id: str, action: str, user: dict, before=None, after=None, alasan: str = ""):
    await db.audit_logs.insert_one({
        "id": new_id(), "entity": entity, "entity_id": entity_id, "action": action,
        "before": before, "after": after, "user_id": user["id"], "user_name": user["name"],
        "user_role": user["role"], "alasan": alasan, "timestamp": now_iso(),
    })


async def save_upload(file, user: dict, folder: str, allowed_exts=None, scope: str = None) -> dict:
    """Simpan file upload ke LocalDocumentStorage milik server (lihat document_storage.py).

    Bukan silent fallback: ini implementasi storage terpilih, eksplisit menggantikan
    object storage eksternal. Validasi tipe/ukuran lebih dulu; file ditulis atomic
    (tmp + rename) sebelum metadata dibuat sehingga tidak ada metadata palsu.
    """
    from document_storage import storage, extension_of, EXT_CONTENT_TYPES, MAX_UPLOAD_SIZE, sanitize_component
    ext = extension_of(file.filename)
    if allowed_exts is not None and ext not in allowed_exts:
        raise HTTPException(status_code=400,
                            detail=f"Format file tidak didukung (. {ext or 'tanpa ekstensi'}). Gunakan: {', '.join(sorted(allowed_exts))}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 10MB")
    content_type = EXT_CONTENT_TYPES.get(ext) or file.content_type or "application/octet-stream"
    file_id = new_id()
    owner = sanitize_component(scope or user["id"])
    key = f"{sanitize_component(folder)}/{owner}/{file_id}.{ext}"
    try:
        size = storage.save(key, data)
    except Exception as e:
        logger.error(f"Gagal menyimpan file lokal: {e}")
        raise HTTPException(status_code=502, detail="Upload gagal: file tidak dapat disimpan di server")
    rec = {"id": file_id, "storage_path": key, "original_filename": file.filename,
           "content_type": content_type, "size": size,
           "is_deleted": False, "uploaded_by": user["name"], "created_at": now_iso()}
    try:
        await db.files.insert_one(rec)
    except Exception:
        try:
            storage.delete(key)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Upload gagal: metadata tidak dapat disimpan")
    return clean(rec)


# ---------- Shared aggregations ----------
async def payment_summary_map(student_ids=None):
    match = {} if student_ids is None else {"student_id": {"$in": student_ids}}
    pipeline = [{"$match": match}, {"$group": {"_id": "$student_id", "bayar": {"$sum": "$nominal"}, "terakhir": {"$max": "$tanggal"}}}]
    rows = await db.payments.aggregate(pipeline).to_list(None)
    return {r["_id"]: {"bayar": r["bayar"], "terakhir": r["terakhir"]} for r in rows}


def fee_total(student: dict) -> float:
    return sum(float(i.get("nominal", 0)) for i in student.get("fee_plan", []))


async def attendance_summary(student_id: str) -> dict:
    rows = await db.attendance.find({"student_id": student_id}, {"_id": 0, "status": 1}).to_list(None)
    counts = {"hadir": 0, "izin": 0, "sakit": 0, "alfa": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    total = sum(counts.values())
    persen = round(counts["hadir"] / total * 100, 1) if total else 0
    return {**counts, "total": total, "persentase": persen}


async def grade_average(student_id: str):
    rows = await db.grades.find({"student_id": student_id}, {"_id": 0, "nilai_akhir": 1}).to_list(None)
    if not rows:
        return None
    return round(sum(r["nilai_akhir"] for r in rows) / len(rows), 1)


async def doc_progress(student_id: str) -> dict:
    docs = await db.documents.find({"student_id": student_id, "is_deleted": False}, {"_id": 0, "jenis": 1, "status": 1}).to_list(None)
    ada = {d["jenis"] for d in docs if d.get("status") in ("tersedia", "verified")}
    return {"lengkap": len(ada), "total": len(DOC_TYPES)}
