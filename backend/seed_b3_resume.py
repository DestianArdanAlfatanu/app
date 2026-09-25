"""DEV-ONLY B3 resume: skip already-covered targets."""
import requests

API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]
t = requests.post(API + "/auth/login", json={"email": "finance@lpk.id", "password": "password123"},
                  timeout=15).json()["token"]
H = {"Authorization": "Bearer " + t}
have = {a["student_id"] for a in d.collection_activities.find({}, {"_id": 0, "student_id": 1})}
od = [x for x in requests.get(API + "/payments-arrears", headers=H, timeout=20).json()
      if x.get("kondisi") == "terlambat" and x["id"] not in have][:6]
acts = [("phone", "contacted", "Sudah dihubungi, janji transfer", "2026-09-26"),
        ("whatsapp", "contacted", "Ingatkan via WA manual (catatan)", "2026-09-28"),
        ("phone", "promised_payment", "Janji bayar setelah gajian", "2026-10-02"),
        ("in_person", "no_response", "Datang ke rumah, tidak ada orang", "2026-09-30"),
        ("phone", "promised_payment", "Minta keringanan cicilan", "2026-09-20"),
        ("phone", "contacted", "Akan dibayar minggu ini", "2026-09-27")]
for o, (ch, oc, note, fu) in zip(od, acts):
    body = {"student_id": o["id"], "channel": ch, "outcome": oc, "note": note,
            "next_follow_up_at": fu, "next_follow_up_note": "Follow-up pembayaran"}
    r = requests.post(API + "/collections/activities", headers=H, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL {o['nama_lengkap']}: {r.status_code} {r.text[:200]}"
    print(f"  {o['nama_lengkap']}: 200")
print("B3 resume done:", len(od))
