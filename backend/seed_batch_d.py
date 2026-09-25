"""DEV-ONLY Batch D: trigger notification sync per role + mark some read."""
import requests

API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]
print("BEFORE:", d.notifications.count_documents({}))
T = {}
for r, e, p in [("owner", "owner@lpk.id", "owner123"), ("admin", "admin@lpk.id", "password123"),
                ("finance", "finance@lpk.id", "password123"), ("hr", "hr@lpk.id", "password123"),
                ("guru", "guru@lpk.id", "password123"), ("marketing", "marketing@lpk.id", "password123"),
                ("staff", "staff@lpk.id", "password123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]
for role in ("owner", "admin", "finance", "hr", "guru", "marketing", "staff"):
    H = {"Authorization": "Bearer " + T[role]}
    rows = requests.get(API + "/notifications", headers=H, timeout=30).json()
    assert isinstance(rows, list), f"FAIL {role}"
    for n in rows[:2]:
        r = requests.post(API + f"/notifications/{n['id']}/read", headers=H, timeout=15)
        assert r.status_code == 200, f"FAIL read {role}: {r.text[:150]}"
    print(f"  {role}: {len(rows)} notifs, 2 marked read")
print("BATCH D done")
