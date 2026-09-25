"""DEV-ONLY Batch B: candidate follow-ups + matching/interviews + collections."""
import requests, random
from datetime import date

random.seed(20260924)
API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]
T = {}
for r, e, p in [("marketing", "marketing@lpk.id", "password123"),
                ("admin", "admin@lpk.id", "password123"),
                ("finance", "finance@lpk.id", "password123"),
                ("owner", "owner@lpk.id", "owner123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]


def post(path, role, body):
    r = requests.post(API + path, headers={"Authorization": "Bearer " + T[role]}, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL POST {path}: {r.status_code} {r.text[:200]}"
    return r.json()


cands = list(d.students.find({"status": {"$in": ["calon_siswa", "pendaftaran", "seleksi", "diterima"]}},
                             {"_id": 0, "id": 1, "nama_lengkap": 1, "status": 1}))
print("B1 candidates:", len(cands))
CF = [("phone", "terhubungi", "Sudah dihubungi, respons baik"),
      ("whatsapp", "terhubungi", "Chat WA manual: kirim brosur biaya (catatan manual)"),
      ("in_person", "minat", "Datang ke LPK, tertarik program"),
      ("sosmed", "janji_datang", "DM Instagram, janji survei"),
      ("kunjungan", "terhubungi", "Kunjungan ke sekolah"),
      ("phone", "no_response", "Tidak menjawab 2x panggilan"),
      ("whatsapp", "minat", "WA manual: tanya jadwal (catatan manual)"),
      ("phone", "menolak", "Memilih bekerja lokal"),
      ("in_person", "tidak_aktif", "Nomor tidak aktif saat dihubungi ulang")]
n_fu = 0
for i, c in enumerate(cands[:12]):
    ch, oc, note = CF[i % len(CF)]
    fu = ["2026-09-26", "2026-09-28", "2026-09-20", "2026-10-02", None][i % 5]
    body = {"student_id": c["id"], "channel": ch, "outcome": oc, "note": note}
    if fu and oc not in ("menolak", "tidak_aktif"):
        body.update({"next_follow_up_at": fu, "next_follow_up_note": "Hubungi lagi"})
        n_fu += 1
    post("/candidate-followups/activities", "marketing", body)
print("B1 followups ok, with next_fu:", n_fu)
print("B1 count:", d.candidate_followups.count_documents({}))

JOBS = [("Sakura Care Support Co., Ltd. (Demo)", "Caregiver (Kaigo)", "Osaka", 5, "¥200.000/bulan", "Shift",
         "Sabar, komunikatif, minimal N4", 19, 30, "semua", "N4", "Kaigo", "2026-10-06", "terbuka"),
        ("Hikari Food Service (Demo)", "Food Service", "Tokyo", 4, "¥185.000/bulan", "09:00-18:00",
         "Ramah, siap lembur", 19, 28, "semua", "N5", "Food Service", "2026-10-13", "terbuka"),
        ("Mirai Manufacturing Japan (Demo)", "Operator Produksi", "Aichi", 6, "¥195.000/bulan", "08:00-17:00",
         "Sehat, tidak buta warna", 19, 30, "L", "N4", "Manufaktur", "2026-09-30", "terbuka"),
        ("Taiyo Farm Hokkaido (Demo)", "Pertanian", "Hokkaido", 4, "¥180.000/bulan", "07:00-16:00",
         "Terbiasa kerja fisik", 20, 32, "L", "N5", "Pertanian", None, "terbuka"),
        ("Fuji Building Clean (Demo)", "Building Cleaning", "Kanagawa", 3, "¥190.000/bulan", "Shift",
         "Teliti, disiplin", 19, 35, "semua", "N5", "Cleaning", None, "selesai"),
        ("Naniwa Hotel Group (Demo)", "Hotel Staff", "Osaka", 2, "¥195.000/bulan", "Shift",
         "Berpenampilan rapi, N4", 19, 28, "P", "N4", "Hospitality", None, "selesai"),
        ("Kobe Steel Works (Demo)", "Welding", "Hyogo", 4, "¥210.000/bulan", "08:00-17:00",
         "Pengalaman las diutamakan", 20, 32, "L", "N4", "Manufaktur", None, "selesai")]
JIDS = []
for per, pos, lok, jum, gaji, jam, sy, umin, umax, jk, jlpt, jns, tgliv, st in JOBS:
    j = post("/job-orders", "marketing", {"perusahaan": per, "posisi": pos, "lokasi": lok,
        "jumlah_kebutuhan": jum, "gaji": gaji, "jam_kerja": jam, "persyaratan": sy,
        "usia_min": umin, "usia_max": umax, "jenis_kelamin": jk, "min_jlpt": jlpt,
        "jenis_pekerjaan": jns, "tanggal_interview": tgliv, "status": st})
    JIDS.append(j["id"])
print("B2 jobs:", len(JIDS))
matching = list(d.students.find({"status": "matching"}, {"_id": 0, "id": 1, "nama_lengkap": 1}))[:6]
alums = list(d.students.find({"status": "alumni"}, {"_id": 0, "id": 1, "nama_lengkap": 1})[:5])
sched = [(matching[0]["id"], 0, "2026-10-06", "menunggu"), (matching[1]["id"], 1, "2026-10-13", "menunggu"),
         (matching[2]["id"], 2, "2026-09-30", "menunggu")]
hist = [(alums[0]["id"], 4, "2025-08-12", "lulus"), (alums[1]["id"], 5, "2025-09-02", "lulus"),
        (alums[2]["id"], 6, "2025-07-20", "lulus"), (alums[3]["id"], 4, "2025-08-12", "gagal"),
        (alums[4]["id"], 5, "2025-09-02", "gagal")]
for sid, ji, tgl, hasil in sched + hist:
    post("/interviews", "marketing", {"job_order_id": JIDS[ji], "student_id": sid,
        "tanggal": tgl, "hasil": hasil, "catatan": ""})
print("B2 interviews:", d.interviews.count_documents({}))

od = [x for x in requests.get(API + "/payments-arrears", headers={"Authorization": "Bearer " + T["finance"]},
      timeout=30).json() if x.get("kondisi") in ("terlambat", "hari_ini")][:7]
print("B3 overdue found:", len(od))
acts = [("phone", "contacted", "Sudah dihubungi, janji transfer", "2026-09-26"),
        ("whatsapp", "contacted", "Ingatkan via WA manual (catatan)", "2026-09-28"),
        ("phone", "promised_payment", "Janji bayar setelah gajian", "2026-10-02"),
        ("in_person", "no_response", "Datang ke rumah, tidak ada orang", "2026-09-30"),
        ("phone", "promised_payment", "Minta keringanan cicilan", "2026-09-20"),
        ("whatsapp", "no_response", "Chat WA manual belum dibalas (catatan)", None),
        ("phone", "contacted", "Akan dibayar minggu ini", "2026-09-27")]
for (sid_d, fu_note) in zip([o["id"] for o in od], acts):
    ch, oc, note, fu = fu_note
    body = {"student_id": sid_d, "channel": ch, "outcome": oc, "note": note}
    if fu:
        body.update({"next_follow_up_at": fu, "next_follow_up_note": "Follow-up pembayaran"})
    post("/collections/activities", "finance", body)
print("B3 activities:", d.collection_activities.count_documents({}))
