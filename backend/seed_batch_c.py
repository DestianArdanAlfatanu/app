"""DEV-ONLY Batch C: documents + departure readiness."""
import requests, random

random.seed(20260924)
API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]
T = {}
for r, e, p in [("admin", "admin@lpk.id", "password123"), ("owner", "owner@lpk.id", "owner123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]
HA = {"Authorization": "Bearer " + T["admin"]}
HO = {"Authorization": "Bearer " + T["owner"]}
print("BEFORE docs:", d.documents.count_documents({}), "dep:", d.departure_profiles.count_documents({}))


def doc(sid, jenis, kat, exp=None):
    data = {"jenis": jenis, "kategori": kat}
    if exp:
        data["tanggal_kadaluarsa"] = exp
    r = requests.post(API + f"/students/{sid}/documents", headers=HA, data=data, timeout=30)
    assert r.status_code == 200, f"FAIL doc {jenis}: {r.status_code} {r.text[:150]}"
    return r.json()


acts = list(d.students.find({"status": {"$in": ["pelatihan", "ujian", "matching"]}},
                            {"_id": 0, "id": 1, "status": 1}))
alums = list(d.students.find({"status": "alumni"}, {"_id": 0, "id": 1})[:6])
for s in acts:
    doc(s["id"], "KTP", "identitas")
    doc(s["id"], "Kartu Keluarga", "identitas")
    doc(s["id"], "Ijazah", "pendidikan")
    if s["status"] in ("ujian", "matching"):
        doc(s["id"], "SKCK", "identitas")
for s in alums:
    for j, k in [("KTP", "identitas"), ("Ijazah", "pendidikan"), ("Paspor", "jepang")]:
        doc(s["id"], j, k)
print("basic docs ok")

dep_cands = [s for s in acts if s.get("status") == "matching"][:5]
if len(dep_cands) < 5:
    dep_cands += [s for s in acts if s.get("status") == "ujian"][:5 - len(dep_cands)]
for s in dep_cands:
    for kat, jenis in [("identitas", "KTP"), ("identitas", "Kartu Keluarga"), ("identitas", "SKCK"),
                       ("pendidikan", "Ijazah"), ("kesehatan", "Medical Check-up"),
                       ("jepang", "Paspor"), ("jepang", "Sertifikat JLPT"), ("jepang", "COE"),
                       ("jepang", "Visa"), ("jepang", "Tiket"), ("kontrak", "Kontrak Kerja")]:
        exp = None
        if jenis in ("Paspor", "Visa"):
            exp = "2029-05-10"
        elif jenis == "Medical Check-up":
            exp = "2026-11-20"
        elif jenis == "SKCK":
            exp = "2025-12-01" if s == dep_cands[0] else "2027-01-15"
        doc(s["id"], jenis, kat, exp)
print("departure docs ok")

jobs = list(d.job_orders.find({"status": "terbuka"}, {"_id": 0, "id": 1})[:3])
PIDS = []
for i, s in enumerate(dep_cands):
    body = {"student_id": s["id"], "target_departure_date": f"2026-1{['0', '1'][i % 2]}-{10 + i:02d}",
            "destination": ["Osaka", "Tokyo", "Aichi"][i % 3], "pic_name": "Yoga Pratama"}
    if i < 3 and jobs:
        body["job_order_id"] = jobs[i % len(jobs)]["id"]
    r = requests.post(API + "/departures", headers=HA, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL departure: {r.status_code} {r.text[:150]}"
    PIDS.append(r.json()["id"])
print("profiles:", len(PIDS))
for i, pid in enumerate(PIDS):
    items = requests.get(API + f"/departures/{pid}/checklist", headers=HA, timeout=15).json()
    mp = {it["requirement_code"]: it for it in items}
    docs = {x["jenis"]: x["id"] for x in
            requests.get(API + f"/students/{dep_cands[i]['id']}/documents", headers=HA, timeout=15).json()}
    jmap = {"passport": "Paspor", "coe": "COE", "visa": "Visa", "medical": "Medical Check-up",
            "ticket": "Tiket", "contract": "Kontrak Kerja"}
    verify_n = 6 if i < 2 else (4 if i < 4 else 2)
    for code in list(mp.keys())[:verify_n]:
        did = docs.get(jmap[code])
        r = requests.put(API + f"/departures/{pid}/checklist/{mp[code]['id']}/verify", headers=HA,
                         json={"document_id": did, "note": "Dokumen valid"}, timeout=15)
        assert r.status_code == 200, f"FAIL verify {code}: {r.status_code} {r.text[:150]}"
    if i == 0:
        assert requests.post(API + f"/departures/{pid}/ready", headers=HO,
                             json={"reason": "Berkas lengkap"}).status_code == 200
        assert requests.put(API + f"/departures/{pid}", headers=HA,
                            json={"status": "siap", "alasan": "Diverifikasi"}).status_code == 200
    if i == 4:
        assert requests.post(API + f"/departures/{pid}/block", headers=HO,
                             json={"reason": "Menunggu revisi COE"}).status_code == 200
print("BATCH C done")
