import os
import random
from datetime import date, timedelta

from core import db, hash_password, verify_password, new_id, now_iso, DOC_TYPES

random.seed(7)


def d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower()
    pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"id": new_id(), "email": email, "password_hash": hash_password(pw), "name": "Owner LPK",
                                   "role": "owner", "aktif": True, "created_at": now_iso()})
    elif not verify_password(pw, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(pw)}})


async def seed_demo():
    if await db.students.count_documents({}) > 0:
        return
    teachers = [
        {"id": new_id(), "nama": "Suci Rahmawati", "tipe": "guru", "jabatan": "Pengajar Bahasa Jepang", "spesialisasi": "Bahasa Jepang N5-N3", "sertifikat": ["JLPT N2"], "honor_per_pertemuan": 150000, "gaji_pokok": 3500000, "tunjangan": 500000, "no_hp": "081234000001", "email": "suci@lpk.id", "status_kerja": "tetap", "tanggal_masuk": "2023-02-01", "aktif": True, "nik": "3201010101010001", "alamat": "Bandung", "kontrak_berakhir": None, "created_at": now_iso()},
        {"id": new_id(), "nama": "Hendra Wijaya", "tipe": "guru", "jabatan": "Pengajar Budaya & Keterampilan", "spesialisasi": "Budaya Jepang, Kaigo", "sertifikat": ["JLPT N3", "Kaigo Level 1"], "honor_per_pertemuan": 125000, "gaji_pokok": 3000000, "tunjangan": 300000, "no_hp": "081234000002", "email": "hendra@lpk.id", "status_kerja": "kontrak", "tanggal_masuk": "2024-06-01", "aktif": True, "nik": "3201010101010002", "alamat": "Cimahi", "kontrak_berakhir": (date.today() + timedelta(days=20)).isoformat(), "created_at": now_iso()},
        {"id": new_id(), "nama": "Yuki Tanaka", "tipe": "guru", "jabatan": "Native Speaker", "spesialisasi": "Kaiwa / Speaking", "sertifikat": [], "honor_per_pertemuan": 250000, "gaji_pokok": 0, "tunjangan": 0, "no_hp": "081234000003", "email": "yuki@lpk.id", "status_kerja": "freelance", "tanggal_masuk": "2025-01-10", "aktif": True, "nik": "", "alamat": "Bandung", "kontrak_berakhir": None, "created_at": now_iso()},
    ]
    employees = [
        {"id": new_id(), "nama": "Dewi Lestari", "tipe": "karyawan", "jabatan": "Admin Keuangan", "gaji_pokok": 4000000, "tunjangan": 500000, "honor_per_pertemuan": 0, "no_hp": "081234000010", "email": "finance@lpk.id", "status_kerja": "tetap", "tanggal_masuk": "2022-08-01", "aktif": True, "nik": "3201010101010010", "alamat": "Bandung", "spesialisasi": "", "sertifikat": [], "kontrak_berakhir": None, "created_at": now_iso()},
        {"id": new_id(), "nama": "Rizky Pratama", "tipe": "karyawan", "jabatan": "Staff Marketing", "gaji_pokok": 3200000, "tunjangan": 300000, "honor_per_pertemuan": 0, "no_hp": "081234000011", "email": "marketing@lpk.id", "status_kerja": "kontrak", "tanggal_masuk": "2024-03-15", "aktif": True, "nik": "3201010101010011", "alamat": "Bandung", "spesialisasi": "", "sertifikat": [], "kontrak_berakhir": (date.today() + timedelta(days=120)).isoformat(), "created_at": now_iso()},
        {"id": new_id(), "nama": "Sari Handayani", "tipe": "karyawan", "jabatan": "HR & Administrasi", "gaji_pokok": 3800000, "tunjangan": 400000, "honor_per_pertemuan": 0, "no_hp": "081234000012", "email": "hr@lpk.id", "status_kerja": "tetap", "tanggal_masuk": "2023-01-05", "aktif": True, "nik": "3201010101010012", "alamat": "Bandung", "spesialisasi": "", "sertifikat": [], "kontrak_berakhir": None, "created_at": now_iso()},
    ]
    await db.employees.insert_many(teachers + employees)

    users = [
        ("Admin LPK", "admin@lpk.id", "admin", None), ("Dewi Lestari", "finance@lpk.id", "finance", employees[0]["id"]),
        ("Sari Handayani", "hr@lpk.id", "hr", employees[2]["id"]), ("Suci Rahmawati", "guru@lpk.id", "guru", teachers[0]["id"]),
        ("Rizky Pratama", "marketing@lpk.id", "marketing", employees[1]["id"]), ("Staff LPK", "staff@lpk.id", "staff", None),
    ]
    for name, email, role, emp in users:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"id": new_id(), "name": name, "email": email, "role": role, "employee_id": emp, "aktif": True,
                                       "password_hash": hash_password("password123"), "created_at": now_iso()})

    accounts = [
        {"id": new_id(), "nama": "Kas Tunai", "jenis": "kas", "bank": "", "no_rekening": "", "saldo_awal": 10000000, "created_at": now_iso()},
        {"id": new_id(), "nama": "BCA Operasional", "jenis": "bank", "bank": "BCA", "no_rekening": "1234567890", "saldo_awal": 120000000, "created_at": now_iso()},
        {"id": new_id(), "nama": "BRI Siswa", "jenis": "bank", "bank": "BRI", "no_rekening": "0987654321", "saldo_awal": 25000000, "created_at": now_iso()},
    ]
    await db.accounts.insert_many(accounts)

    classes = [
        {"id": new_id(), "nama": "Jepang Dasar A", "guru_id": teachers[0]["id"], "level": "N5", "ruangan": "R-101", "materi": "Minna no Nihongo 1", "status": "aktif",
         "jadwal": [{"hari": "Senin", "jam_mulai": "08:00", "jam_selesai": "10:00"}, {"hari": "Rabu", "jam_mulai": "08:00", "jam_selesai": "10:00"}, {"hari": "Jumat", "jam_mulai": "08:00", "jam_selesai": "10:00"}],
         "tanggal_mulai": d(60), "tanggal_selesai": None, "student_ids": [], "created_at": now_iso()},
        {"id": new_id(), "nama": "Jepang Menengah B", "guru_id": teachers[1]["id"], "level": "N4", "ruangan": "R-102", "materi": "Minna no Nihongo 2 + Budaya", "status": "aktif",
         "jadwal": [{"hari": "Selasa", "jam_mulai": "13:00", "jam_selesai": "15:00"}, {"hari": "Kamis", "jam_mulai": "13:00", "jam_selesai": "15:00"}],
         "tanggal_mulai": d(120), "tanggal_selesai": None, "student_ids": [], "created_at": now_iso()},
    ]
    fee = [{"nama": "Pendaftaran", "nominal": 500000}, {"nama": "Pelatihan", "nominal": 8000000}, {"nama": "Asrama", "nominal": 3000000},
           {"nama": "Dokumen", "nominal": 2000000}, {"nama": "Keberangkatan", "nominal": 5000000}]
    names = [("Budi Santoso", "L", "2001-03-12", "N4", "pelatihan", 0), ("Andi Saputra", "L", "2000-07-21", "N5", "pelatihan", 0), ("Siti Aminah", "P", "2002-01-05", "N5", "pelatihan", 0),
             ("Rina Marlina", "P", "1999-11-30", "N4", "pelatihan", 0), ("Dedi Kurniawan", "L", "1998-05-17", "N4", "lulus", 1), ("Fitri Handayani", "P", "2001-09-09", "N3", "matching", 1),
             ("Agus Setiawan", "L", "1997-02-14", "N4", "pemberkasan", 1), ("Lina Wati", "P", "2000-12-01", "N4", "visa", 1), ("Joko Susilo", "L", "1996-06-25", "N3", "berangkat", None),
             ("Maya Sari", "P", "1995-04-18", "N3", "alumni", None), ("Eko Prasetyo", "L", "2003-08-08", "-", "calon_siswa", None), ("Nur Hidayah", "P", "2002-10-10", "N5", "seleksi", None),
             ("Wahyu Ramadhan", "L", "2001-01-20", "-", "pendaftaran", None), ("Putri Ayu", "P", "2003-03-03", "N5", "diterima", None), ("Fajar Nugroho", "L", "1999-09-19", "N4", "ujian", 0)]
    kab = ["Bandung", "Garut", "Tasikmalaya", "Cianjur", "Sumedang"]
    students = []
    for i, (nama, jk, tl, jlpt, status, cls) in enumerate(names):
        sid = new_id()
        students.append({"id": sid, "nama_lengkap": nama, "nik": f"32010{i:02d}{tl.replace('-', '')[2:]}0001", "no_kk": f"3201{i:012d}", "tempat_lahir": random.choice(kab),
                         "tanggal_lahir": tl, "jenis_kelamin": jk, "alamat": {"desa": f"Desa {i + 1}", "kecamatan": "Cileunyi", "kabupaten": random.choice(kab), "provinsi": "Jawa Barat"},
                         "no_hp": f"0812{i:04d}5678", "email": f"{nama.split()[0].lower()}@mail.com", "nama_orang_tua": f"Bapak {nama.split()[-1]}", "no_hp_orang_tua": f"0813{i:04d}1234",
                         "pendidikan_terakhir": random.choice(["SMA", "SMK", "D3"]), "nama_sekolah": f"SMK Negeri {i + 1} {random.choice(kab)}", "jurusan": random.choice(["Teknik Mesin", "Otomotif", "Keperawatan", "IPA"]),
                         "tahun_lulus": str(int(tl[:4]) + 18), "tinggi_badan": random.randint(155, 178), "berat_badan": random.randint(48, 75), "status_pernikahan": "belum_menikah",
                         "riwayat_pekerjaan": "", "riwayat_kesehatan": "Sehat", "kemampuan_bahasa_jepang": jlpt, "status": status, "fee_plan": fee,
                         "jatuh_tempo": (date.today() + timedelta(days=random.choice([-10, -3, 0, 5, 20, 45]))).isoformat() if status not in ("calon_siswa", "alumni", "berangkat") else None,
                         "class_id": classes[cls]["id"] if cls is not None else None, "catatan": "",
                         "status_history": [{"status": "calon_siswa", "tanggal": d(90 + i), "oleh": "Rizky Pratama", "catatan": "Pendaftaran awal"}, {"status": status, "tanggal": d(30 + i), "oleh": "Admin LPK", "catatan": "Update status"}],
                         "created_at": (date.today() - timedelta(days=90 + i * 3)).isoformat() + "T08:00:00+00:00", "created_by": "Rizky Pratama"})
        if cls is not None:
            classes[cls]["student_ids"].append(sid)
    await db.students.insert_many(students)
    await db.classes.insert_many(classes)

    payments, transactions = [], []
    n = 0
    for s in students:
        if s["status"] in ("calon_siswa", "pendaftaran", "seleksi"):
            continue
        plan = [5000000, 5000000, 3500000, 5000000] if s["status"] in ("alumni", "berangkat", "visa") else random.choice([[5000000], [5000000, 5000000], [500000, 3000000], [5000000, 5000000, 3500000]])
        for k, nominal in enumerate(plan):
            n += 1
            acc = random.choice(accounts)
            tgl = d(random.randint(1, 80))
            pid = new_id()
            payments.append({"id": pid, "student_id": s["id"], "student_nama": s["nama_lengkap"], "nominal": nominal, "tanggal": tgl, "metode": random.choice(["cash", "transfer", "qris"]),
                             "jenis": "Pendaftaran" if k == 0 and nominal == 500000 else "Cicilan", "no_transaksi": f"TRX{n:05d}", "account_id": acc["id"], "account_nama": acc["nama"],
                             "catatan": "", "bukti_file_id": None, "petugas": "Dewi Lestari", "no_kwitansi": f"KW-{tgl[:4]}{tgl[5:7]}-{n:04d}", "sisa_setelah": 0, "created_at": tgl + "T09:00:00+00:00"})
            transactions.append({"id": new_id(), "jenis": "pemasukan", "kategori": "Pembayaran Siswa", "nominal": nominal, "tanggal": tgl, "deskripsi": f"Pembayaran Cicilan - {s['nama_lengkap']}",
                                 "account_id": acc["id"], "metode": "transfer", "bukti_file_id": None, "ref_type": "payment", "ref_id": pid, "petugas": "Dewi Lestari", "created_at": tgl + "T09:00:00+00:00"})
    exp = [("Gaji", 12000000, "Gaji karyawan bulan lalu"), ("Honor Guru", 6500000, "Honor pengajar"), ("Listrik", 1250000, "Tagihan PLN"), ("Internet", 550000, "Indihome"),
           ("Sewa Gedung", 7500000, "Sewa gedung bulanan"), ("Makan Siswa", 4200000, "Catering asrama"), ("ATK", 480000, "Pembelian ATK"), ("Transportasi", 750000, "Antar jemput dokumen"),
           ("Air", 320000, "PDAM"), ("Perawatan", 900000, "Servis AC")]
    for k, (kat, nominal, desk) in enumerate(exp):
        for m in range(3):
            tgl = (date.today() - timedelta(days=5 + m * 30 + k)).isoformat()
            transactions.append({"id": new_id(), "jenis": "pengeluaran", "kategori": kat, "nominal": nominal + (m * 10000), "tanggal": tgl, "deskripsi": desk,
                                 "account_id": accounts[1]["id"] if nominal > 1000000 else accounts[0]["id"], "metode": "transfer" if nominal > 1000000 else "cash",
                                 "bukti_file_id": None, "ref_type": "manual", "ref_id": None, "petugas": "Dewi Lestari", "created_at": tgl + "T10:00:00+00:00"})
    await db.payments.insert_many(payments)
    await db.transactions.insert_many(transactions)

    att, grades = [], []
    komps = ["hiragana", "katakana", "kanji", "grammar", "listening", "speaking", "reading", "writing", "budaya", "kedisiplinan"]
    for c in classes:
        days = [j["hari"] for j in c["jadwal"]]
        hari_idx = {"Senin": 0, "Selasa": 1, "Rabu": 2, "Kamis": 3, "Jumat": 4, "Sabtu": 5, "Minggu": 6}
        for back in range(0, 45):
            day = date.today() - timedelta(days=back)
            if [k for k, v in hari_idx.items() if v == day.weekday()][0] not in days:
                continue
            for sid in c["student_ids"]:
                att.append({"id": new_id(), "class_id": c["id"], "student_id": sid, "tanggal": day.isoformat(),
                            "status": random.choices(["hadir", "izin", "sakit", "alfa"], weights=[88, 5, 4, 3])[0], "dicatat_oleh": "Suci Rahmawati", "created_at": now_iso(), "updated_at": now_iso()})
        for sid in c["student_ids"]:
            for periode in ["Bulan 1", "Bulan 2"]:
                komp = {k: random.randint(65, 98) for k in komps}
                grades.append({"id": new_id(), "student_id": sid, "class_id": c["id"], "periode": periode, "komponen": komp, "catatan": "",
                               "nilai_akhir": round(sum(komp.values()) / len(komp), 1), "guru": "Suci Rahmawati", "created_at": now_iso()})
    await db.attendance.insert_many(att)
    await db.grades.insert_many(grades)

    exams = [{"id": new_id(), "nama": "Ujian Bulanan 1", "jenis": "Ujian bulanan", "tanggal": d(35), "class_id": classes[0]["id"], "passing_grade": 70, "keterangan": "",
              "results": [{"student_id": sid, "nilai": random.randint(60, 95)} for sid in classes[0]["student_ids"]], "created_at": now_iso()},
             {"id": new_id(), "nama": "Try Out JLPT N5", "jenis": "Try Out JLPT", "tanggal": d(7), "class_id": classes[0]["id"], "passing_grade": 80, "keterangan": "",
              "results": [{"student_id": sid, "nilai": random.randint(65, 98)} for sid in classes[0]["student_ids"]], "created_at": now_iso()},
             {"id": new_id(), "nama": "Ujian Akhir N4", "jenis": "Ujian akhir", "tanggal": (date.today() + timedelta(days=6)).isoformat(), "class_id": classes[1]["id"], "passing_grade": 75, "keterangan": "",
              "results": [], "created_at": now_iso()}]
    await db.exams.insert_many(exams)

    sel = []
    for s in students:
        if s["status"] in ("calon_siswa", "pendaftaran"):
            continue
        for jenis, hasil in (("administrasi", "lulus"), ("kesehatan", "lulus"), ("fisik", "lulus")):
            sel.append({"id": new_id(), "student_id": s["id"], "jenis": jenis, "hasil": hasil, "nilai": None, "catatan": "", "tanggal": d(70), "petugas": "Admin LPK", "created_at": now_iso()})
        if s["status"] != "seleksi":
            sel.append({"id": new_id(), "student_id": s["id"], "jenis": "bahasa", "hasil": "lulus", "nilai": random.randint(70, 95), "catatan": "", "tanggal": d(68), "petugas": "Suci Rahmawati", "created_at": now_iso()})
            sel.append({"id": new_id(), "student_id": s["id"], "jenis": "wawancara", "hasil": "lulus", "nilai": random.randint(75, 95), "catatan": "Motivasi baik", "tanggal": d(66), "petugas": "Admin LPK", "created_at": now_iso()})
    await db.selections.insert_many(sel)

    docs = []
    for s in students:
        if s["status"] in ("calon_siswa",):
            continue
        n_docs = {"pendaftaran": 2, "seleksi": 4, "diterima": 5, "pelatihan": 6, "ujian": 7, "lulus": 8, "matching": 9, "pemberkasan": 10, "visa": 12, "berangkat": 13, "alumni": 13}.get(s["status"], 4)
        for kategori, jenis in DOC_TYPES[:n_docs]:
            exp_date = (date.today() + timedelta(days=random.choice([15, 200, 900]))).isoformat() if jenis in ("Paspor", "Visa", "Medical Check-up", "SKCK") else None
            docs.append({"id": new_id(), "student_id": s["id"], "jenis": jenis, "kategori": kategori, "status": "tersedia", "file_id": None, "original_filename": None, "content_type": None,
                         "tanggal_upload": d(random.randint(5, 60)), "tanggal_kadaluarsa": exp_date, "uploaded_by": "Admin LPK", "is_deleted": False, "created_at": now_iso()})
    await db.documents.insert_many(docs)

    jobs = [{"id": new_id(), "perusahaan": "ABC Manufacturing Co., Ltd.", "posisi": "Operator Produksi", "lokasi": "Aichi", "jumlah_kebutuhan": 5, "gaji": "¥180.000/bulan", "jam_kerja": "08:00-17:00",
             "persyaratan": "Sehat, tidak buta warna, siap shift", "usia_min": 19, "usia_max": 30, "jenis_kelamin": "L", "min_jlpt": "N4", "jenis_pekerjaan": "Manufaktur",
             "tanggal_interview": (date.today() + timedelta(days=5)).isoformat(), "status": "terbuka", "created_at": now_iso()},
            {"id": new_id(), "perusahaan": "Sakura Kaigo Center", "posisi": "Caregiver (Kaigo)", "lokasi": "Osaka", "jumlah_kebutuhan": 3, "gaji": "¥200.000/bulan", "jam_kerja": "Shift",
             "persyaratan": "Sabar, komunikatif, N4", "usia_min": 19, "usia_max": 35, "jenis_kelamin": "semua", "min_jlpt": "N4", "jenis_pekerjaan": "Kaigo",
             "tanggal_interview": (date.today() + timedelta(days=12)).isoformat(), "status": "terbuka", "created_at": now_iso()},
            {"id": new_id(), "perusahaan": "Nihon Kensetsu", "posisi": "Tukang Konstruksi", "lokasi": "Tokyo", "jumlah_kebutuhan": 8, "gaji": "¥190.000/bulan", "jam_kerja": "08:00-17:00",
             "persyaratan": "Fisik kuat", "usia_min": 20, "usia_max": 32, "jenis_kelamin": "L", "min_jlpt": "N5", "jenis_pekerjaan": "Konstruksi", "tanggal_interview": None, "status": "selesai", "created_at": now_iso()}]
    await db.job_orders.insert_many(jobs)
    by_name = {s["nama_lengkap"]: s for s in students}
    ivs = [("Fitri Handayani", jobs[1], "menunggu", (date.today() + timedelta(days=12)).isoformat()), ("Dedi Kurniawan", jobs[0], "menunggu", (date.today() + timedelta(days=5)).isoformat()),
           ("Agus Setiawan", jobs[0], "lulus", d(20)), ("Lina Wati", jobs[1], "lulus", d(45)), ("Joko Susilo", jobs[2], "lulus", d(120)), ("Maya Sari", jobs[1], "lulus", d(300))]
    await db.interviews.insert_many([{"id": new_id(), "job_order_id": j["id"], "student_id": by_name[nm]["id"], "student_nama": nm, "perusahaan": j["perusahaan"], "posisi": j["posisi"],
                                      "tanggal": tgl, "hasil": hasil, "catatan": "", "created_at": now_iso()} for nm, j, hasil, tgl in ivs])
    await db.audit_logs.insert_one({"id": new_id(), "entity": "system", "entity_id": "seed", "action": "seed", "before": None, "after": {"info": "Data demo dibuat"},
                                    "user_id": "system", "user_name": "Sistem", "user_role": "owner", "alasan": "", "timestamp": now_iso()})
