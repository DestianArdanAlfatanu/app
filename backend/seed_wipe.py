"""WIPE business collections for demo reset. SAFETY: only runs on local dev DB lpk.
Keeps: users (minus 2 student TEST residue), whatsapp_templates.
Run from backend/: .venv/Scripts/python.exe seed_wipe.py
"""
from pymongo import MongoClient
import os

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = os.environ.get("DB_NAME", "lpk")

assert "127.0.0.1" in MONGO_URL or "localhost" in MONGO_URL, f"REFUSE: not local ({MONGO_URL})"
assert DB_NAME == "lpk", f"REFUSE: unexpected DB ({DB_NAME})"

d = MongoClient(MONGO_URL)[DB_NAME]

BUSINESS = ["employees", "students", "classes", "attendance", "grades", "exams",
            "selections", "documents", "job_orders", "interviews", "payments",
            "transactions", "payrolls", "expenses", "leaves", "employee_attendances",
            "reconciliations", "collection_activities", "candidate_followups",
            "departure_profiles", "departure_checklist", "notifications", "audit_logs",
            "accounts", "counters", "whatsapp_messages", "whatsapp_events", "login_attempts"]

total = 0
for c in BUSINESS:
    n = d[c].delete_many({}).deleted_count
    total += n
    print(f"{c}: {n}")
print(f"TOTAL removed: {total}")
print("kept users:", d.users.count_documents({}),
      "| templates:", d.whatsapp_templates.count_documents({}))
# remove obvious TEST residue user accounts (student role test accounts)
res = list(d.users.find({"email": {"$regex": "^p[34]c0@lpk.id"}}, {"_id": 0, "id": 1, "email": 1}))
for u in res:
    d.users.delete_many({"id": u["id"]})
    print("removed residue user:", u["email"])
