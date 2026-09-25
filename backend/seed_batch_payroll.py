"""DEV-ONLY payroll batch: attendance + calculate/approve/pay via API. No wipe."""
import requests
from datetime import date

API = "http://127.0.0.1:8000/api"
T = {}
for r, e, p in [("hr", "hr@lpk.id", "password123"), ("owner", "owner@lpk.id", "owner123"),
                ("finance", "finance@lpk.id", "password123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]
H = {"Authorization": "Bearer " + T["hr"]}
HO = {"Authorization": "Bearer " + T["owner"]}
HF = {"Authorization": "Bearer " + T["finance"]}


def post(path, role, body):
    r = requests.post(API + path, headers={"Authorization": "Bearer " + T[role]}, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL POST {path}: {r.status_code} {r.text[:200]}"
    return r.json()


emps = requests.get(API + "/employees", headers=H, timeout=15).json()
by_name = {e["nama"]: e["id"] for e in emps}
print("employees:", len(by_name))

# attendance Sept 1-24 weekdays
import random
random.seed(77)
alfa_done = 0
for day in range(1, 25):
    dt = date(2026, 9, day)
    if dt.weekday() >= 6:
        continue
    recs = []
    for nm, eid in by_name.items():
        r = random.random()
        if nm in ("Yoga Pratama", "Nina Kurnia") and dt.isoformat() in ("2026-09-09", "2026-09-16") and alfa_done < 2:
            st, alfa_done = "alfa", alfa_done + 1
            rec = {"employee_id": eid, "status": st, "keterangan": "Tanpa kabar"}
        else:
            st = "hadir" if r < 0.93 else ("terlambat" if r < 0.96 else ("izin" if r < 0.98 else "sakit"))
            rec = {"employee_id": eid, "status": st,
                   "jam_masuk": f"07:{random.randint(25, 59):02d}" if st in ("hadir", "terlambat") else None,
                   "jam_pulang": f"16:{random.randint(0, 59):02d}" if st in ("hadir", "terlambat") else None}
            if st == "terlambat":
                rec["jam_masuk"] = f"08:{random.randint(5, 25):02d}"
        recs.append(rec)
    post("/hr/attendance", "hr", {"tanggal": dt.isoformat(), "records": recs})
print("attendance ok")

HONOR = {"Haryanto Wijaya": 22, "Siti Kurniawati": 20, "Bambang Sutrisno": 21, "Agus Setyawan": 19}
for per in ("2026-08", "2026-09"):
    items = []
    for nm, eid in by_name.items():
        it = {"employee_id": eid}
        if nm in HONOR:
            it["honor_pertemuan"] = HONOR[nm] + (0 if per == "2026-08" else -2)
            it["honor_note"] = "Konfirmasi rekap kelas"
        items.append(it)
    if per == "2026-09":
        for it in items:
            if it["employee_id"] == by_name["Dian Puspita"]:
                it.update({"bonus": 300000, "bonus_reason": "Kinerja penagihan baik"})
            if it["employee_id"] == by_name["Yoga Pratama"]:
                it.update({"lembur": 250000, "lembur_reason": "Lembur persiapan ujian",
                           "lembur_source_note": "2026-09-18",
                           "potongan": [{"jenis": "Kasbon", "nominal": 200000, "keterangan": "Kasbon tengah bulan",
                                          "source_ref": {"source_type": "external_doc", "source_note": "Slip kasbon"}}]})
    r = post("/payrolls/calculate", "hr", {"periode": per, "items": items})
    assert len(r["rows"]) == len(by_name), r
    for row in r["rows"]:
        post(f"/payrolls/{row['id']}/approve", "owner", {})
    print(f"{per}: {len(r['rows'])} approved")
    if per == "2026-08":
        acc = requests.get(API + "/finance/accounts", headers=HF, timeout=15).json()[0]["id"]
        for row in r["rows"]:
            post(f"/payrolls/{row['id']}/pay", "finance", {"account_id": acc})
        print("2026-08 paid")

# leave 2 September payrolls as draft: recalc not possible (unique) -> instead create draft via correction? No:
# drafts demonstrated by September unapproved? All approved above. Use October draft instead:
ro = post("/payrolls/calculate", "hr", {"periode": "2026-10", "items": [{"employee_id": by_name["Teguh Firmansyah"]}]})
print("draft example:", ro["rows"][0]["status"])
