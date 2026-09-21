from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from core import db, client, init_storage, logger
from seed import seed_admin, seed_demo
from routers import auth, students, academics, finance, hr, jobs, dashboard

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Sistem LPK Jepang")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Sistem LPK API aktif"}


for r in (auth, students, academics, finance, hr, jobs, dashboard):
    api_router.include_router(r.router)
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.students.create_index("id", unique=True)
    await db.students.create_index("status")
    await db.payments.create_index("student_id")
    await db.transactions.create_index("tanggal")
    await db.attendance.create_index([("class_id", 1), ("student_id", 1), ("tanggal", 1)], unique=True)
    await db.audit_logs.create_index("timestamp")
    await db.login_attempts.create_index("identifier")
    await seed_admin()
    await seed_demo()
    try:
        init_storage()
        logger.info("Object storage siap")
    except Exception as e:
        logger.error(f"Object storage gagal init: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
