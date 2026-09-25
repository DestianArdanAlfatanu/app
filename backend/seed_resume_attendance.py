"""DEV-ONLY resume: jalankan phase_attendance dari data yang sudah ada di DB.
Tidak wipe, tidak menyentuh phase lain. Menghapus 16 attendance records parsial
yang salah tanggal dari run sebelumnya, lalu mengisi ulang yang benar.
Usage: .venv/Scripts/python.exe seed_resume_attendance.py
"""
import os
import seed_demo_data as S
from pymongo import MongoClient

d = MongoClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))[
    os.environ.get("DB_NAME", "lpk")]

print("== resume attendance dari DB ==")
print("before: attendance =", d.attendance.count_documents({}))

# hapus records parsial run gagal (semuanya milik 6 kelas demo; koleksi hanya berisi itu)
cids = [c["id"] for c in d.classes.find({}, {"_id": 0, "id": 1})]
print("partial delete:", d.attendance.delete_many({"class_id": {"$in": cids}}).deleted_count)

# login sebagai admin (butuh token untuk phase)
S.TOK["admin"] = S.login("admin@lpk.id", "password123")

# bangun CLASSES + ACTIVES dari DB (bukan dari globals run sebelumnya)
S.CLASSES = list(d.classes.find({}, {"_id": 0}))
by_class = {}
for s in d.students.find({"class_id": {"$ne": None}}, {"_id": 0, "id": 1, "class_id": 1}):
    by_class.setdefault(s["class_id"], []).append(s["id"])
S.ACTIVES = []
for ci, c in enumerate(S.CLASSES):
    for sid in by_class.get(c["id"], []):
        S.ACTIVES.append({"id": sid, "class_idx": ci})
print(f"classes={len(S.CLASSES)} students_in_class={sum(len(v) for v in by_class.values())}")

S.PHASE.append("attendance")
S.phase_attendance()

print("after: attendance =", d.attendance.count_documents({}))
from collections import Counter
print("by status:", dict(Counter(
    x["status"] for x in d.attendance.find({}, {"_id": 0, "status": 1}))))
