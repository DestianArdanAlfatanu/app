import sys, time
import seed_demo_data as S

print("t0 login", flush=True)
S.TOK["hr"] = S.login("hr@lpk.id", "password123")
print("t1 logged in", flush=True)
body = {"nama": "Probe Emp", "tipe": "guru", "jabatan": "Pengajar",
        "spesialisasi": "Bahasa Jepang N5", "sertifikat": ["JLPT N3"],
        "honor_per_pertemuan": 100000, "gaji_pokok": 0, "tunjangan": 0,
        "no_hp": S.mk_phone(), "email": S.mk_email("Probe", "Emp"),
        "nik": S.mk_nik("Banyumas", "1990-05-17"),
        "alamat": "Kec. Sokaraja, Kab. Banyumas",
        "tanggal_masuk": "2024-01-01", "status_kerja": "tetap"}
print("t2 body built", flush=True)
t0 = time.time()
r = S.api("POST", "/employees", "hr", json=body)
print("t3 POST done", round(time.time() - t0, 2), r.get("id"), flush=True)
