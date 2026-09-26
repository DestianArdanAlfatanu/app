from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from core import (db, hash_password, verify_password, create_access_token, public_user, revoke_tokens,
                  get_current_user, require_roles, new_id, now_iso, ROLES, clean_list, log_audit,
                  login_locked, record_login_failure)
from pg_mongo import DuplicateKeyError

router = APIRouter()


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserIn(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    role: str
    employee_id: Optional[str] = None
    student_id: Optional[str] = None
    must_change_password: Optional[bool] = False
    aktif: bool = True


@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.lower().strip()
    ident = f"{request.client.host if request.client else 'x'}:{email}"
    if await login_locked(ident):
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan. Coba lagi dalam 15 menit")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await record_login_failure(ident)
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if not user.get("aktif", True):
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan")
    if user.get("role") == "student":
        raise HTTPException(status_code=403, detail="Akun siswa, silakan masuk lewat Portal Siswa")
    await db.login_attempts.delete_one({"identifier": ident})
    access = create_access_token(user)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    return {"token": access, "user": public_user(user)}


@router.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    await revoke_tokens(user["id"])
    # Bersihkan cookie sisa versi lama (tidak lagi dipakai untuk autentikasi).
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/users")
async def list_users(user: dict = Depends(require_roles("owner", "admin", "hr"))):
    rows = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(None)
    return rows


@router.post("/users")
async def create_user(body: UserIn, user: dict = Depends(get_current_user)):
    if body.role == "student":
        if user["role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini")
        if not body.student_id or not await db.students.find_one({"id": body.student_id}):
            raise HTTPException(status_code=400, detail="student_id tidak valid")
        if await db.users.find_one({"student_id": body.student_id}):
            raise HTTPException(status_code=409, detail="Siswa sudah memiliki akun")
    elif user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini")
    if body.role not in ROLES and body.role != "student":
        raise HTTPException(status_code=400, detail="Role tidak valid")
    if not body.password or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
    email = body.email.lower().strip()
    dup = await db.users.find_one({"email": email})
    if dup:
        # RV-DEF-01: a student-provisioning race loser can slip past the
        # student_id pre-check and land here after the winner's insert.
        # Same (email, student_id) -> the race was lost -> 409, never 400.
        # A genuinely different owner keeps existing 400. Non-student unchanged.
        if body.role == "student" and dup.get("student_id") == body.student_id:
            raise HTTPException(status_code=409, detail="Siswa sudah memiliki akun")
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    doc = {"id": new_id(), "name": body.name, "email": email, "role": body.role, "employee_id": body.employee_id,
           "student_id": body.student_id if body.role == "student" else None,
           "must_change_password": True if body.role == "student" else False,
           "aktif": body.aktif, "password_hash": hash_password(body.password), "created_at": now_iso()}
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError as e:
        # RV-DEF-01: last-resort deterministic mapping for student provisioning.
        # Re-query instead of trusting check order/timing: any conflict involving
        # this student_id (winner already persisted) -> 409. Genuine cross-user
        # email conflict keeps existing 400. Non-student path unchanged.
        if body.role == "student":
            if await db.users.find_one({"student_id": body.student_id}):
                raise HTTPException(status_code=409, detail="Siswa sudah memiliki akun")
            by_email = await db.users.find_one({"email": email})
            if by_email and by_email.get("student_id") == body.student_id:
                raise HTTPException(status_code=409, detail="Siswa sudah memiliki akun")
        detail = str(getattr(e, "details", "") or "")
        if "student_id" in detail:
            raise HTTPException(status_code=409, detail="Siswa sudah memiliki akun")
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    await log_audit("user", doc["id"], "create", user, None, {"email": email, "role": body.role})
    return public_user(doc)


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UserIn, user: dict = Depends(require_roles("owner"))):
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")
    if body.role not in ROLES and body.role != "student":
        raise HTTPException(status_code=400, detail="Role tidak valid")
    if (existing["role"] == "student") != (body.role == "student"):
        raise HTTPException(status_code=400, detail="Akun siswa tidak dapat diubah menjadi akun staff (atau sebaliknya)")
    upd = {"name": body.name, "email": body.email.lower().strip(), "role": body.role, "employee_id": body.employee_id, "aktif": body.aktif}
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
        upd["password_hash"] = hash_password(body.password)
        if body.role == "student":
            upd["must_change_password"] = True  # password dari admin harus diganti siswa saat login berikutnya
    try:
        await db.users.update_one({"id": user_id}, {"$set": upd})
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    # Password, role atau status aktif berubah -> sesi lama user itu tidak boleh terus berlaku.
    if body.password or body.role != existing["role"] or body.aktif != existing.get("aktif", True):
        await revoke_tokens(user_id)
    await log_audit("user", user_id, "update", user, {"role": existing["role"], "aktif": existing.get("aktif", True)},
                    {"role": body.role, "aktif": body.aktif})
    return public_user(await db.users.find_one({"id": user_id}))


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_roles("owner"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun sendiri")
    await db.users.delete_one({"id": user_id})
    await log_audit("user", user_id, "delete", user)
    return {"ok": True}
