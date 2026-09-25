"""DEV-ONLY resume: jalankan phase_grades dari data yang sudah ada di DB.
Tidak wipe, tidak menyentuh phase lain.
Usage: .venv/Scripts/python.exe seed_resume_grades.py
"""
import os
import seed_demo_data as S
from pymongo import MongoClient

d = MongoClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))[
    os.environ.get("DB_NAME", "lpk")]

print("== resume grades/exams dari DB ==")
print("before: grades =", d.grades.count_documents({}), "exams =", d.exams.count_documents({}))

S.TOK["admin"] = S.login("admin@lpk.id", "password123")

S.CLASSES = list(d.classes.find({}, {"_id": 0}))
by_class = {}
for s in d.students.find({"class_id": {"$ne": None}}, {"_id": 0, "id": 1, "class_id": 1}):
    by_class.setdefault(s["class_id"], []).append(s["id"])
S.ACTIVES = []
for ci, c in enumerate(S.CLASSES):
    for sid in by_class.get(c["id"], []):
        S.ACTIVES.append({"id": sid, "class_idx": ci})
print(f"classes={len(S.CLASSES)} students_in_class={sum(len(v) for v in by_class.values())}")

S.PHASE.append("grades")
S.phase_grades()

print("after: grades =", d.grades.count_documents({}), "exams =", d.exams.count_documents({}))
from collections import Counter
print("grades per class:", dict(Counter(
    x.get("class_id", "?")[:8] for x in d.grades.find({}, {"_id": 0, "class_id": 1}))))
print("students with grades:", len(d.grades.distinct("student_id")))
print("students without grades:", d.students.count_documents({}) - len(d.grades.distinct("student_id")))
