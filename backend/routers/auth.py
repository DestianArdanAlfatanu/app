from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from core import (db, hash_password, verify_password, create_access_token, create_refresh_token, public_user,
                  get_current_user, require_roles, new_id, now_iso, ROLES, clean_list, log_audit)
from pymongo.errors import DuplicateKeyError

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


def set_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower().strip()
    ident = f"{request.client.host if request.client else 'x'}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5 and attempt.get("locked_until", "") > now_iso():
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan. Coba lagi dalam 15 menit")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        from datetime import datetime, timezone, timedelta
        locked = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"locked_until": locked}}, upsert=True)
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if not user.get("aktif", True):
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan")
    await db.login_attempts.delete_one({"identifier": ident})
    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    set_cookies(response, access, refresh)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    return {"token": access, "user": public_user(user)}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/users")
async def list_users(user: dict = Depends(require_roles("owner", "admin", "hr"))):
    rows = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(500)
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
    upd = {"name": body.name, "email": body.email.lower().strip(), "role": body.role, "employee_id": body.employee_id, "aktif": body.aktif}
    if body.password:
        upd["password_hash"] = hash_password(body.password)
    await db.users.update_one({"id": user_id}, {"$set": upd})
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
