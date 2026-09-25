"""DEV-ONLY B1: candidate follow-ups for calon_siswa only."""
import requests

API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]
T = {}
for r, e, p in [("marketing", "marketing@lpk.id", "password123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]

before = d.candidate_followups.count_documents({})

cands = list(d.students.find({"status": "calon_siswa"}, {"_id": 0, "id": 1, "nama_lengkap": 1}))
print("eligible calon_siswa:", len(cands))
CF = [("phone", "terhubungi", "Sudah dihubungi, respons baik", "2026-09-26"),
      ("whatsapp", "terhubungi", "Chat WA manual: kirim brosur biaya (catatan manual)", "2026-09-28"),
      ("in_person", "minat", "Datang ke LPK, tertarik program", "2026-09-20"),
      ("sosmed", "janji_datang", "DM Instagram, janji survei", "2026-10-02"),
      ("kunjungan", "terhubungi", "Kunjungan ke sekolah", None),
      ("phone", "lainnya", "Tidak menjawab 2x panggilan", "2026-09-30")]
for i, c in enumerate(cands):
    ch, oc, note, fu = CF[i % len(CF)]
    body = {"student_id": c["id"], "channel": ch, "outcome": oc, "note": note}
    if fu:
        body.update({"next_follow_up_at": fu, "next_follow_up_note": "Hubungi lagi"})
    r = requests.post(API + "/candidate-followups/activities",
                      headers={"Authorization": "Bearer " + T["marketing"]}, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL {c['nama_lengkap']}: {r.status_code} {r.text[:200]}"
    print(f"  {c['nama_lengkap']}: 200")
print("B1 done. before:", before, "after:", d.candidate_followups.count_documents({}))
