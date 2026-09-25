"""DEV-ONLY Batch A: payments + finance from existing DB. No wipe, fail-fast."""
import os, random
import requests
from datetime import date

random.seed(20260924)
API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]

T = {}
for r, e, p in [("finance", "finance@lpk.id", "password123"),
                ("owner", "owner@lpk.id", "owner123"),
                ("admin", "admin@lpk.id", "password123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]
H = {"Authorization": "Bearer " + T["finance"]}
HO = {"Authorization": "Bearer " + T["owner"]}


def post(path, role, body):
    r = requests.post(API + path, headers={"Authorization": "Bearer " + T[role]}, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL POST {path}: {r.status_code} {r.text[:200]}"
    return r.json()


print("BEFORE payments:", d.payments.count_documents({}), "tx:", d.transactions.count_documents({}))
acts = list(d.students.find({"status": {"$in": ["pelatihan", "ujian", "matching"]}}, {"_id": 0, "id": 1}))
alums = list(d.students.find({"status": "alumni"}, {"_id": 0, "id": 1}))
accs = [a["id"] for a in d.accounts.find({}, {"_id": 0, "id": 1})]
print(f"actives={len(acts)} alumni={len(alums)} accounts={len(accs)}")

# alumni history (2024-2025)
ALUMNI_DATES = ["2024-06-12", "2024-09-14", "2025-02-10", "2025-05-18"]
for s in alums:
    for k, nom in enumerate([5000000, 5000000, 3500000, 5000000]):
        post("/payments", "finance", {"student_id": s["id"], "nominal": nom,
            "tanggal": ALUMNI_DATES[k],
            "metode": random.choice(["cash", "transfer", "qris"]), "jenis": "Cicilan",
            "account_id": random.choice(accs)})

def sept(n):
    days = list(range(1, 25)); random.shuffle(days)
    return [f"2026-09-{x:02d}" for x in sorted(days[:n])]

lunas = partial = odl = none = 0
sept_income = 0
for i, s in enumerate(acts):
    r = random.random()
    if r < 0.38:
        lunas += 1
        dates = ["2026-06-12", "2026-07-14", "2026-08-16", sept(1)[0]]
        for nom, tgl in zip([5000000, 5000000, 5000000, 3500000], dates):
            post("/payments", "finance", {"student_id": s["id"], "nominal": nom, "tanggal": tgl,
                "metode": random.choice(["cash", "transfer", "qris"]), "jenis": "Cicilan",
                "account_id": random.choice(accs)})
            if tgl.startswith("2026-09"):
                sept_income += nom
    elif r < 0.73:
        partial += 1
        plans = [[(5000000, "2026-07-10")], [(5000000, "2026-07-10"), (3000000, sept(1)[0])]]
        for nom, tgl in random.choice(plans):
            post("/payments", "finance", {"student_id": s["id"], "nominal": nom, "tanggal": tgl,
                "metode": random.choice(["cash", "transfer"]), "jenis": "Cicilan", "account_id": random.choice(accs)})
            if tgl.startswith("2026-09"):
                sept_income += nom
    elif r < 0.88:
        odl += 1
        post("/payments", "finance", {"student_id": s["id"], "nominal": 2000000, "tanggal": "2026-07-05",
            "metode": "cash", "jenis": "Cicilan", "account_id": accs[0]})
    else:
        none += 1
print(f"A1 done: lunas={lunas} partial={partial} overdue={odl} none={none} sept_income={sept_income}")
print("AFTER payments:", d.payments.count_documents({}), "tx:", d.transactions.count_documents({}))

EXP = [("Gaji Karyawan Agustus", "Gaji", 38500000, "2026-09-02", "dibayar"),
       ("Honor Guru Agustus", "Honor Guru", 14200000, "2026-09-03", "dibayar"),
       ("Sewa Gedung September", "Sewa Gedung", 7500000, "2026-09-01", "dibayar"),
       ("Tagihan Listrik Agustus", "Listrik", 1350000, "2026-09-07", "dibayar"),
       ("Catering Asrama", "Makan Siswa", 4800000, "2026-09-09", "dibayar"),
       ("Langganan Internet", "Internet", 550000, "2026-09-05", "dibayar"),
       ("Belanja ATK", "ATK", 620000, "2026-09-11", "dibayar"),
       ("Antar Jemput Dokumen", "Transportasi", 890000, "2026-09-14", "dibayar"),
       ("Tagihan Air", "Air", 340000, "2026-09-16", "dibayar"),
       ("Servis AC Kelas", "Perawatan", 1100000, "2026-09-18", "dibayar"),
       ("Kebutuhan Operasional", "Operasional Lainnya", 1800000, "2026-09-20", "disetujui"),
       ("Pajak Bulanan", "Pajak", 2400000, "2026-09-21", "disetujui"),
       ("Belanja ATK Tambahan", "ATK", 750000, "2026-09-22", "diajukan"),
       ("Transportasi Jemput", "Transportasi", 500000, "2026-09-23", "draft"),
       ("Pengadaan Proyektor", "Operasional Lainnya", 3000000, "2026-09-19", "ditolak")]
for judul, kat, nom, tgl, target in EXP:
    e = post("/expenses", "finance", {"judul": judul, "kategori": kat, "nominal": nom,
        "tanggal": tgl, "deskripsi": judul, "account_id": accs[1]})
    if target == "draft":
        continue
    post(f"/expenses/{e['id']}/submit", "finance", {})
    if target == "diajukan":
        continue
    decider = "owner" if nom >= 1000000 else "finance"
    post(f"/expenses/{e['id']}/decide", decider, {"setuju": target != "ditolak",
        "alasan": "Sesuai kebutuhan" if target != "ditolak" else "Bukan prioritas"})
    if target == "dibayar":
        post(f"/expenses/{e['id']}/pay", "finance", {"account_id": accs[1]})
print("A2 expenses ok")
