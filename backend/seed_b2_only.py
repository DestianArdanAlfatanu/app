"""DEV-ONLY B2: job orders + interviews."""
import requests

API = "http://127.0.0.1:8000/api"
from pymongo import MongoClient
d = MongoClient("mongodb://127.0.0.1:27017")["lpk"]
T = {}
for r, e, p in [("marketing", "marketing@lpk.id", "password123"),
                ("admin", "admin@lpk.id", "password123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]
print("BEFORE jobs:", d.job_orders.count_documents({}), "interviews:", d.interviews.count_documents({}))


def post(path, role, body):
    r = requests.post(API + path, headers={"Authorization": "Bearer " + T[role]}, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL POST {path}: {r.status_code} {r.text[:200]}"
    return r.json()


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
print("jobs created:", len(JIDS))
matching = list(d.students.find({"status": "matching"}, {"_id": 0, "id": 1, "nama_lengkap": 1})[:3])
alums = list(d.students.find({"status": "alumni"}, {"_id": 0, "id": 1, "nama_lengkap": 1})[:5])
print("matching pool:", len(matching), "alumni pool:", len(alums))
for sid, ji, tgl in [(matching[0]["id"], 0, "2026-10-06"), (matching[1]["id"], 1, "2026-10-13"),
                     (matching[2]["id"], 2, "2026-09-30")]:
    post("/interviews", "marketing", {"job_order_id": JIDS[ji], "student_id": sid,
        "tanggal": tgl, "hasil": "menunggu", "catatan": ""})
for sid, ji, tgl, hasil in [(alums[0]["id"], 4, "2025-08-12", "lulus"), (alums[1]["id"], 5, "2025-09-02", "lulus"),
                            (alums[2]["id"], 6, "2025-07-20", "lulus"), (alums[3]["id"], 4, "2025-08-12", "gagal"),
                            (alums[4]["id"], 5, "2025-09-02", "gagal")]:
    post("/interviews", "marketing", {"job_order_id": JIDS[ji], "student_id": sid,
        "tanggal": tgl, "hasil": hasil, "catatan": ""})
print("B2 done. jobs:", d.job_orders.count_documents({}), "interviews:", d.interviews.count_documents({}))
