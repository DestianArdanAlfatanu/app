import requests, time, random
random.seed(20260924)
API = "http://127.0.0.1:8000/api"
t = requests.post(API + "/auth/login", json={"email": "hr@lpk.id", "password": "password123"}, timeout=15).json()["token"]
H = {"Authorization": f"Bearer {t}"}
body = {"nama": "Probe Guru", "tipe": "guru", "jabatan": "Pengajar", "spesialisasi": "X",
        "sertifikat": ["JLPT N3"], "honor_per_pertemuan": 100000, "gaji_pokok": 0, "tunjangan": 0,
        "no_hp": "082999900001", "email": "probe.guru99@gmail.com", "nik": "33020101990001",
        "alamat": "Kec. Sokaraja, Kab. Banyumas", "tanggal_masuk": "2024-01-01", "status_kerja": "tetap"}
for i in range(3):
    t0 = time.time()
    try:
        r = requests.post(API + "/employees", headers=H, json=body, timeout=20)
        print(i, r.status_code, round(time.time() - t0, 2))
        if r.status_code == 200:
            requests.delete(API + "/employees/" + r.json()["id"], headers=H, timeout=15)
    except Exception as e:
        print(i, "EXC", round(time.time() - t0, 2), str(e)[:100])
    body = dict(body)
    body["email"] = f"probe.guru99.{i}@gmail.com"
    body["nik"] = f"3302010199000{i+2}"
    body["no_hp"] = f"0829999000{i+2:02d}"
print("done")
