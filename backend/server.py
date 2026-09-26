from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import asyncio
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from core import db, client, logger
from seed import seed_admin, seed_demo
from routers import auth, students, academics, finance, hr, jobs, dashboard, whatsapp, portal, collections, candidate_followups, departures

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Sistem LPK Jepang")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Sistem LPK API aktif"}


for r in (auth, students, academics, finance, hr, jobs, dashboard, whatsapp, portal, collections, candidate_followups, departures):
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
    await db.users.create_index("student_id", unique=True, sparse=True)
    await db.students.create_index("id", unique=True)
    await db.students.create_index("status")
    await db.payments.create_index("student_id")
    await db.transactions.create_index("tanggal")
    await db.attendance.create_index([("class_id", 1), ("student_id", 1), ("tanggal", 1)], unique=True)
    await db.employee_attendances.create_index([("employee_id", 1), ("tanggal", 1)], unique=True)
    await db.employee_attendances.create_index("tanggal")
    await db.leaves.create_index([("employee_id", 1), ("dari", 1), ("sampai", 1)])
    await db.leaves.create_index("status")
    await db.payrolls.create_index([("periode", 1), ("employee_id", 1)], unique=True)
    await db.payrolls.create_index("periode")
    try:
        await db.transactions.drop_index("uniq_payroll_tx")
    except Exception:
        pass
    await db.transactions.create_index([("ref_type", 1), ("ref_id", 1)], unique=True,
                                       partialFilterExpression={"ref_type": {"$in": ["payroll", "expense"]}},
                                       name="uniq_linked_tx")
    await db.payments.create_index("idem_key", unique=True,
                                   partialFilterExpression={"idem_key": {"$exists": True}},
                                   name="uniq_payment_idem")
    await db.expenses.create_index("status")
    await db.notifications.create_index("dedupe_key", unique=True, name="uniq_notif_dedupe")
    await db.notifications.create_index("roles")
    await db.notifications.create_index("recipients")
    await db.whatsapp_templates.create_index("key", unique=True)
    await db.whatsapp_messages.create_index("idempotency_key", unique=True, name="uniq_wa_idem")
    await db.whatsapp_messages.create_index([("student_id", 1), ("created_at", -1)])
    await db.whatsapp_messages.create_index([("status", 1), ("next_retry_at", 1)])
    await db.whatsapp_events.create_index("provider_event_id", unique=True, name="uniq_wa_event")
    await db.audit_logs.create_index("timestamp")
    await db.collection_activities.create_index("id", unique=True)
    await db.collection_activities.create_index("student_id")
    await db.collection_activities.create_index("next_follow_up_at")
    await db.collection_activities.create_index("idem_key", unique=True,
                                                partialFilterExpression={"idem_key": {"$exists": True}},
                                                name="uniq_collection_idem")
    await db.candidate_followups.create_index("id", unique=True)
    await db.candidate_followups.create_index("student_id")
    await db.candidate_followups.create_index("next_follow_up_at")
    await db.candidate_followups.create_index("idem_key", unique=True,
                                              partialFilterExpression={"idem_key": {"$exists": True}},
                                              name="uniq_candidate_idem")
    await db.departure_profiles.create_index("id", unique=True)
    await db.departure_profiles.create_index("student_id", unique=True, name="uniq_departure_student")
    await db.departure_profiles.create_index("status")
    await db.departure_profiles.create_index("target_departure_date")
    await db.departure_profiles.create_index("job_order_id")
    await db.departure_checklist.create_index("id", unique=True)
    await db.departure_checklist.create_index("departure_profile_id")
    await db.departure_checklist.create_index("student_id")
    await db.departure_checklist.create_index("status")
    await db.departure_checklist.create_index("requirement_code")
    await db.login_attempts.create_index("identifier")
    await seed_admin()
    if os.environ.get("LPK_DISABLE_STARTUP_DEMO_SEED", "").lower() not in ("1", "true", "yes"):
        await seed_demo()
    else:
        logger.info("Startup demo seed disabled via LPK_DISABLE_STARTUP_DEMO_SEED")
    try:
        from routers.whatsapp import seed_templates
        await seed_templates()
    except Exception as e:
        logger.error(f"Seed template WA gagal: {e}")
    try:
        from document_storage import storage_root
        logger.info(f"Local document storage siap: {storage_root()}")
    except Exception as e:
        logger.error(f"Local document storage gagal init: {e}")


NOTIF_SYNC_INTERVAL = int(os.environ.get("LPK_NOTIF_SYNC_SECONDS", "300"))


async def _periodic_notification_sync():
    """Sinkronisasi notifikasi + retry WhatsApp berkala, tanpa menunggu ada pengguna yang membuka aplikasi."""
    from routers.dashboard import _sync_notifications
    while True:
        await asyncio.sleep(NOTIF_SYNC_INTERVAL)
        try:
            await _sync_notifications()
        except Exception as e:
            logger.error(f"Sinkronisasi notifikasi berkala gagal: {e}")


@app.on_event("startup")
async def start_background_jobs():
    app.state.notif_job = asyncio.create_task(_periodic_notification_sync())


@app.on_event("shutdown")
async def shutdown_db_client():
    job = getattr(app.state, "notif_job", None)
    if job:
        job.cancel()
    await client.aclose()
