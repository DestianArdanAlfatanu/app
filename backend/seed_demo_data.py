"""REALISTIC DEMO SEED — LPK Banyumas/Cilacap/Kebumen (deterministic, SEED=20260924).

Usage (from backend/):
  1. .venv/Scripts/python.exe seed_wipe.py        # wipe business data (keeps users+templates)
  2. .venv/Scripts/python.exe seed_demo_data.py   # seed via API (proves business rules)

Requires backend running on REACT_APP_BACKEND_URL (default http://127.0.0.1:8000).
Rerunnable ONLY on empty business collections (wipe first). No app code touched.
"""
import os
import random
import requests
from datetime import date, timedelta

random.seed(20260924)

API = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/") + "/api"
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "password123")
OWNER_PWD = os.environ.get("ADMIN_PASSWORD", "owner123")

TOK = {}
PHASE = ["init"]


def login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"SEED FAILED\nphase: login\nentity: {email}\nstatus: {r.status_code}"
    return r.json()["token"]


def api(method, path, role, json=None, data=None, expect=(200,), label=""):
    """Single attempt for writes (no blind retry: a timeout may have already
    committed server-side). One retry only for safe GETs on connection errors."""
    H = {"Authorization": f"Bearer {TOK[role]}"}
    tag = f"[SEED {PHASE[-1]}] {label or (method + ' ' + path)}" if label else f"{method} {path} [{role}]"
    attempts = 2 if method == "GET" else 1
    last = None
    import time as _t
    t0 = _t.time()
    for _ in range(attempts):
        try:
            if data is not None:
                r = requests.request(method, API + path, headers=H, data=data, timeout=45)
            else:
                r = requests.request(method, API + path, headers=H, json=json, timeout=45)
            last = r
            break
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
            continue
    if isinstance(last, Exception):
        raise SystemExit(f"SEED FAILED\nphase: {PHASE[-1]}\nentity: {label}\nendpoint: {method} {path}\nerror: {last}")
    dt = _t.time() - t0
    if dt > 10:
        print(f"[SEED SLOW {dt:.0f}s] {tag}", flush=True)
    assert last.status_code in expect, (
        f"SEED FAILED\nphase: {PHASE[-1]}\nentity: {label}\nendpoint: {method} {path}\n"
        f"status: {last.status_code}\nerror: {last.text[:200]}")
    return last.json()


def check_empty():
    from pymongo import MongoClient
    d = MongoClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))[
        os.environ.get("DB_NAME", "lpk")]
    non_empty = {c: d[c].count_documents({}) for c in
                 ("students", "employees", "classes", "payments", "transactions", "payrolls", "expenses")}
    bad = {c: n for c, n in non_empty.items() if n > 0}
    assert not bad, f"SEED REFUSED: business collections not empty: {bad} (run seed_wipe.py first)"


# ---------------- identity pools ----------------
MALE = ["Rizky", "Fajar", "Dimas", "Bagas", "Andi", "Budi", "Agus", "Dedi", "Eko", "Wahyu",
        "Yoga", "Ilham", "Reza", "Farhan", "Aldi", "Bima", "Cahyo", "Danang", "Endra", "Fikri",
        "Galih", "Hendra", "Irvan", "Joko", "Lutfi", "Maulana", "Nanda", "Oktav", "Pandu", "Teguh", "Dian", "Yoga"]
FEMALE = ["Aulia", "Nabila", "Salsabila", "Rani", "Siti", "Dewi", "Putri", "Maya", "Lina", "Fitri",
          "Intan", "Ratna", "Dina", "Wulan", "Ayu", "Bella", "Citra", "Dian", "Erna", "Fani",
          "Gita", "Hana", "Indah", "Kartika", "Melati", "Nita", "Puput", "Rina", "Sari", "Nina", "Dian", "Ayu"]
LAST = ["Maulana", "Ramadhan", "Pratama", "Rahmawati", "Putri", "Nuraini", "Aditya", "Puspitasari",
        "Santoso", "Saputra", "Aminah", "Marlina", "Kurniawan", "Handayani", "Setiawan", "Wati",
        "Susilo", "Sari", "Prasetyo", "Hidayah", "Nugroho", "Firmansyah", "Puspita", "Saputra",
        "Wulandari", "Kusuma", "Hidayat", "Nugraha", "Saputra", "Wijaya", "Setiawan", "Hakim",
        "Fauzi", "Ridwan", "Saputra", "Hidayat", "Kurnia", "Nugroho", "Pramudya", "Raharjo",
        "Setiawan", "Saputra", "Wibowo", "Yuliana", "Saputri", "Anggraini", "Febrianti", "Hapsari",
        "Maharani", "Oktaviani", "Pangestu", "Rachmawati", "Safitri", "Utami", "Wulandari", "Yani",
        "Saputra", "Hidayat", "Nugroho", "Pratama", "Kusumo", "Hartono", "Gunawan", "Saputra"]

KAB = {"Banyumas": ["Sokaraja", "Purwokerto Utara", "Banyumas", "Cilongok", "Ajibarang", "Gumelar", "Pekuncen", "Sumbang", "Kembaran", "Patikraja"],
       "Cilacap": ["Kroya", "Cilacap Utara", "Majenang", "Sidareja", "Kedungreja", "Sampang", "Adipala", "Nusawungu"],
       "Kebumen": ["Gombong", "Kebumen", "Pejagoan", "Sruweng", "Karanganyar", "Buluspesantren", "Ambal", "Klirong"]}
SCHOOLS = {"Banyumas": ["SMAN 1 Purwokerto", "SMKN 1 Purwokerto", "SMKN 2 Purwokerto", "MAN 1 Banyumas", "SMK Muhammadiyah Purwokerto"],
           "Cilacap": ["SMAN 1 Cilacap", "SMKN 1 Cilacap", "SMK Muhammadiyah Kroya", "SMAN 1 Majenang", "MAN 1 Cilacap"],
           "Kebumen": ["SMAN 1 Gombong", "SMKN 1 Kebumen", "SMAN 1 Kebumen", "SMK Negeri 1 Buluspesantren", "MA Negeri 1 Kebumen"]}
KABCODE = {"Banyumas": "3302", "Cilacap": "3301", "Kebumen": "3305"}

used_phone, used_nik, used_email, used_name = set(), set(), set(), set()
_phone_c, _nik_c, _mail_c = [0], [0], [0]


def mk_phone():
    while True:
        _phone_c[0] += 1
        p = f"08{(1000000000 + (_phone_c[0] * 7919) % 9000000000):010d}"
        if len(p) == 12 and p not in used_phone:
            used_phone.add(p)
            return p


def mk_nik(kab, dob):
    while True:
        _nik_c[0] += 1
        n = f"{KABCODE[kab]}{dob[8:10]}{dob[5:7]}{dob[2:4]}{_nik_c[0] % 1000000:06d}"
        assert len(n) == 16 and n.isdigit()
        if n not in used_nik:
            used_nik.add(n)
            return n


def mk_email(first, last):
    base = f"{first.lower()}.{last.lower()}"
    e = base + "@gmail.com"
    while e in used_email:
        _mail_c[0] += 1
        e = f"{base}{_mail_c[0]}@gmail.com"
    used_email.add(e)
    return e


def mk_name(gender):
    while True:
        first = random.choice(MALE if gender == "L" else FEMALE)
        last = random.choice(LAST)
        if first.lower() in last.lower():
            continue
        nm = f"{first} {last}"
        if nm not in used_name:
            used_name.add(nm)
            return nm, first, last


def pick_kab():
    r = random.random()
    return "Banyumas" if r < 0.45 else ("Cilacap" if r < 0.75 else "Kebumen")


def sept_days(n, start=1, end=24):
    days = [d for d in range(start, end + 1)]
    random.shuffle(days)
    return [f"2026-09-{d:02d}" for d in sorted(days[:n])]


def sept_weekdays():
    out = []
    for day in range(1, 25):
        dt = date(2026, 9, day)
        if dt.weekday() < 6:
            out.append(dt.isoformat())
    return out


FEE = [{"nama": "Pendaftaran", "nominal": 500000}, {"nama": "Pelatihan", "nominal": 8000000},
       {"nama": "Asrama", "nominal": 3000000}, {"nama": "Dokumen", "nominal": 2000000},
       {"nama": "Keberangkatan", "nominal": 5000000}]
KOMPS = ["hiragana", "katakana", "kanji", "grammar", "listening", "speaking", "reading", "writing", "budaya", "kedisiplinan"]



def phase_login():
    print("== login ==")
    for role, em, pw in [("owner", "owner@lpk.id", OWNER_PWD), ("admin", "admin@lpk.id", "password123"),
                         ("finance", "finance@lpk.id", "password123"), ("hr", "hr@lpk.id", "password123"),
                         ("marketing", "marketing@lpk.id", "password123")]:
        TOK[role] = login(em, pw)
    print("login ok:", sorted(TOK.keys()))
    PHASE.append("preflight")
    check_empty()
    print("preflight: business collections empty")
    PHASE.append("accounts")



def phase_accounts():
    global ACCS
    print("== accounts ==")
    ACCS = {}
    for nama, jenis, bank, norek, awal in [("Kas Tunai", "kas", "", "", 10000000),
                                           ("BCA Operasional", "bank", "BCA", "8460055221", 120000000),
                                           ("BRI LPK", "bank", "BRI", "002901023344501", 25000000)]:
        ACCS[nama] = api("POST", "/finance/accounts", "finance",
                         {"nama": nama, "jenis": jenis, "bank": bank, "no_rekening": norek, "saldo_awal": awal})["id"]
    print("accounts:", list(ACCS.keys()))



def phase_employees():
    global EMPS
    print("== employees ==")
    TEACHERS = [
        ("Haryanto Wijaya", "Bahasa Jepang N5", ["JLPT N3"], 100000, 0, 0),
        ("Siti Kurniawati", "Kaiwa N5", ["JLPT N3"], 100000, 0, 0),
        ("Bambang Sutrisno", "Bunpou N4", ["JLPT N2"], 125000, 0, 0),
        ("Dewi Anggraini", "Kanji & Choukai N4", ["JLPT N2"], 0, 4200000, 500000),
        ("Agus Setyawan", "Bahasa Jepang N3", ["JLPT N2"], 150000, 0, 0),
        ("Rina Marlina", "Tokutei Ginou", ["JLPT N2", "SSW Kaigo"], 0, 4500000, 500000),
    ]
    STAFF = [
        ("Teguh Firmansyah", "Staff Administrasi", 3800000, 400000, "admin"),
        ("Dian Puspita", "Staf Keuangan", 4200000, 500000, "finance"),
        ("Eko Saputra", "Staf HRD", 4000000, 400000, "hr"),
        ("Yoga Pratama", "Staf Marketing", 3500000, 300000, "marketing"),
        ("Nina Kurnia", "Staf Operasional", 3200000, 250000, "staff"),
    ]
    EMPS = {}
    kab = "Banyumas"
    for i, (nama, spec, ser, honor, gaji, tunj) in enumerate(TEACHERS):
        first, last = nama.split()[0], nama.split()[-1]
        dob = f"{random.randint(1985, 1995)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        e = api("POST", "/employees", "hr", {"nama": nama, "tipe": "guru", "jabatan": "Pengajar",
            "spesialisasi": spec, "sertifikat": ser, "honor_per_pertemuan": honor,
            "gaji_pokok": gaji, "tunjangan": tunj, "no_hp": mk_phone(), "email": mk_email(first, last),
            "nik": mk_nik(kab, dob), "alamat": f"Kec. Sokaraja, Kab. {kab}",
            "tanggal_masuk": f"2024-{random.randint(1, 9):02d}-01", "status_kerja": "tetap" if i % 2 == 0 else "kontrak"})
        EMPS[nama] = e["id"]
    for nama, jab, gaji, tunj, role in STAFF:
        first, last = nama.split()[0], nama.split()[-1]
        dob = f"{random.randint(1988, 1998)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        e = api("POST", "/employees", "hr", {"nama": nama, "tipe": "karyawan", "jabatan": jab,
            "gaji_pokok": gaji, "tunjangan": tunj, "honor_per_pertemuan": 0, "no_hp": mk_phone(),
            "email": mk_email(first, last), "nik": mk_nik("Banyumas", dob),
            "alamat": f"Kec. Purwokerto Utara, Kab. Banyumas",
            "tanggal_masuk": f"2023-{random.randint(1, 12):02d}-01", "status_kerja": "tetap"})
        EMPS[nama] = e["id"]
    print("employees:", len(EMPS))



def phase_users():
    print("== users ==")
    users = {u["email"]: u for u in api("GET", "/users", "owner")}
    link = {"finance@lpk.id": "Dian Puspita", "hr@lpk.id": "Eko Saputra", "marketing@lpk.id": "Yoga Pratama",
            "guru@lpk.id": "Haryanto Wijaya", "admin@lpk.id": "Teguh Firmansyah"}
    for email, empnama in link.items():
        u = users[email]
        api("PUT", f"/users/{u['id']}", "owner", {"name": u["name"], "email": email, "role": u["role"],
            "employee_id": EMPS[empnama], "aktif": True})
    for nama in ["Siti Kurniawati", "Bambang Sutrisno", "Dewi Anggraini", "Agus Setyawan", "Rina Marlina"]:
        first, last = nama.split()[0], nama.split()[-1]
        em = mk_email(first, last)
        try:
            api("POST", "/users", "owner", {"name": nama, "email": em, "role": "guru",
                "employee_id": EMPS[nama], "password": DEMO_PASSWORD})
        except AssertionError:
            pass
    print("users linked + guru accounts ok")



def phase_classes():
    global CLASSES
    print("== classes ==")
    SLOTS = [("08:00", "09:30"), ("10:00", "11:30"), ("13:00", "14:30")]
    CLASSDEF = [("N5 A", "N5", "Haryanto Wijaya", "R-101", "Minna no Nihongo I", [("Senin", 0), ("Rabu", 0), ("Jumat", 0)]),
                ("N5 B", "N5", "Siti Kurniawati", "R-102", "Minna no Nihongo I + Kaiwa", [("Senin", 1), ("Rabu", 1), ("Jumat", 1)]),
                ("N4 A", "N4", "Bambang Sutrisno", "R-101", "Minna no Nihongo II + Bunpou", [("Selasa", 0), ("Kamis", 0), ("Sabtu", 0)]),
                ("N4 B", "N4", "Dewi Anggraini", "R-102", "Kanji & Choukai N4", [("Selasa", 1), ("Kamis", 1), ("Sabtu", 1)]),
                ("N3 A", "N3", "Agus Setyawan", "R-103", "Chukyu + JLPT N3", [("Senin", 2), ("Rabu", 2), ("Jumat", 2)]),
                ("N3 B", "N3", "Rina Marlina", "R-103", "Tokutei Ginou (SSW)", [("Selasa", 2), ("Kamis", 2), ("Sabtu", 2)])]
    CLASSES = []
    for nama, level, guru, room, materi, sched in CLASSDEF:
        c = api("POST", "/classes", "admin", {"nama": nama, "guru_id": EMPS[guru], "level": level,
            "ruangan": room, "materi": materi, "status": "aktif",
            "jadwal": [{"hari": h, "jam_mulai": SLOTS[s][0], "jam_selesai": SLOTS[s][1]} for h, s in sched],
            "tanggal_mulai": "2026-06-01"})
        CLASSES.append(c)
    print("classes:", [c["nama"] for c in CLASSES])

LEVEL_JLPT = {"N5 A": "N5", "N5 B": "N5", "N4 A": "N4", "N4 B": "N4", "N3 A": "N3", "N3 B": "N3"}


def make_student(gender, kab, status_chain, fee_jt, sekolah=None, jlpt="-"):
    nm, first, last = mk_name(gender)
    dob = f"{random.randint(1998, 2005)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    kec = random.choice(KAB[kab])
    s = api("POST", "/students", "marketing", {"nama_lengkap": nm, "nik": mk_nik(kab, dob),
        "tempat_lahir": kec, "tanggal_lahir": dob, "jenis_kelamin": gender,
        "alamat": {"desa": f"Desa {random.choice(['Karangsari', 'Kedungwringin', 'Sidamulya', 'Banjarparakan', 'Candinegara'])}",
                   "kecamatan": kec, "kabupaten": f"Kab. {kab}", "provinsi": "Jawa Tengah"},
        "no_hp": mk_phone(), "email": mk_email(first, last),
        "nama_orang_tua": f"{random.choice(['Slamet', 'Warsito', 'Paijan', 'Sutarmo', 'Dulhani'])} {last}",
        "no_hp_orang_tua": mk_phone(),
        "pendidikan_terakhir": random.choice(["SMA", "SMK", "SMK", "MA"]),
        "nama_sekolah": sekolah or random.choice(SCHOOLS[kab]),
        "jurusan": random.choice(["Teknik Kendaraan Ringan", "Teknik Mesin", "Keperawatan", "IPA", "IPS", "Tata Boga"]),
        "tahun_lulus": str(random.randint(2019, 2025)),
        "tinggi_badan": random.randint(155, 178), "berat_badan": random.randint(45, 72),
        "kemampuan_bahasa_jepang": jlpt, "catatan": ""})
    for st in status_chain:
        api("PUT", f"/students/{s['id']}/status", "admin", {"status": st, "catatan": "Demo seed"})
    if fee_jt is not None:
        api("PUT", f"/students/{s['id']}/fee-plan", "finance",
            {"items": FEE, "jatuh_tempo": fee_jt})
    return api("GET", f"/students/{s['id']}", "admin")




def phase_students():
    global ACTIVES
    print("== 78 active students ==")
    ACTIVES = []
    plan78 = [(i, "pelatihan") for i in range(56)] + [(i, "ujian") for i in range(56, 70)] + [(i, "matching") for i in range(70, 78)]
    random.shuffle(plan78)
    for idx, (slot, target) in enumerate(plan78):
        ci = idx % 6
        kab = pick_kab()
        gender = "L" if random.random() < 0.55 else "P"
        chain = ["pendaftaran", "seleksi", "diterima", "pelatihan"]
        if target in ("ujian", "matching"):
            chain.append("ujian")
        if target == "matching":
            chain += ["lulus", "matching"]
        jt = random.choice(["2026-08-10", "2026-08-25", "2026-09-05", "2026-09-12", "2026-09-20", "2026-09-28", "2026-10-05", "2026-10-15"])
        s = make_student(gender, kab, chain, jt, jlpt=LEVEL_JLPT[CLASSES[ci]["nama"]])
        api("POST", f"/classes/{CLASSES[ci]['id']}/students", "admin", {"student_ids": [s["id"]]})
        ACTIVES.append({**s, "class_idx": ci, "jlpt": LEVEL_JLPT[CLASSES[ci]["nama"]]})
        if idx % 5 == 0:
            print(f"  [STUDENT {idx + 1}/78]", flush=True)
    print("actives:", len(ACTIVES))



def phase_alumni():
    global ALUMNI
    print("== alumni (18) ==")
    ALUMNI = []
    for i in range(18):
        kab = pick_kab()
        gender = "L" if random.random() < 0.6 else "P"
        jlpt = random.choice(["N4", "N4", "N3"])
        s = make_student(gender, kab, ["pendaftaran", "seleksi", "diterima", "pelatihan", "ujian", "lulus",
                                       "matching", "pemberkasan", "visa", "berangkat", "alumni"],
                         random.choice(["2024-11-10", "2025-02-15", "2025-05-20"]), jlpt=jlpt)
        ALUMNI.append(s)
    print("alumni:", len(ALUMNI))



def phase_candidates():
    global CANDS
    print("== candidates (15) ==")
    CANDS = []
    cand_defs = [("calon_siswa", [], 6), ("pendaftaran", ["pendaftaran"], 4),
                 ("seleksi", ["pendaftaran", "seleksi"], 3), ("diterima", ["pendaftaran", "seleksi", "diterima"], 2)]
    SRCS = ["referral", "sosmed", "sekolah", "iklan", "kunjungan", "lainnya"]
    for status, chain, n in cand_defs:
        for _ in range(n):
            kab = pick_kab()
            gender = "L" if random.random() < 0.5 else "P"
            nm, first, last = mk_name(gender)
            dob = f"{random.randint(2000, 2006)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            kec = random.choice(KAB[kab])
            s = api("POST", "/students", "marketing", {"nama_lengkap": nm, "nik": mk_nik(kab, dob),
                "tempat_lahir": kec, "tanggal_lahir": dob, "jenis_kelamin": gender,
                "alamat": {"desa": "Desa Sidayu", "kecamatan": kec, "kabupaten": f"Kab. {kab}", "provinsi": "Jawa Tengah"},
                "no_hp": mk_phone(), "email": mk_email(first, last),
                "nama_orang_tua": f"Suwarno {last}", "no_hp_orang_tua": mk_phone(),
                "pendidikan_terakhir": random.choice(["SMA", "SMK", "MA"]),
                "nama_sekolah": random.choice(SCHOOLS[kab]), "sumber_prospek": random.choice(SRCS),
                "pemilik_lead": "Yoga Pratama"})
            for st in chain:
                api("PUT", f"/students/{s['id']}/status", "marketing", {"status": st, "catatan": "Demo seed"})
            CANDS.append(api("GET", f"/students/{s['id']}", "admin"))
    print("candidates:", len(CANDS))



def phase_attendance():
    print("== attendance (8 minggu) ==")
    HARI = {"Senin": 0, "Selasa": 1, "Rabu": 2, "Kamis": 3, "Jumat": 4, "Sabtu": 5}
    att_n = 0
    for ci, c in enumerate(CLASSES):
        sched_days = {HARI[j["hari"]] for j in c["jadwal"]}
        sids = [s["id"] for s in ACTIVES if s["class_idx"] == ci]
        for back in range(0, 56):
            day = date.today() - timedelta(days=back)
            if day.weekday() not in sched_days or day.isoformat() > "2026-09-24":
                continue
            recs = []
            for sid in sids:
                r = random.random()
                st = "hadir" if r < 0.9 else ("izin" if r < 0.94 else ("sakit" if r < 0.975 else "alfa"))
                recs.append({"student_id": sid, "status": st})
            api("POST", "/attendance", "admin", {"class_id": c["id"], "tanggal": day.isoformat(), "records": recs})
            att_n += len(recs)
    print("attendance records:", att_n)



def phase_grades():
    print("== grades + exams ==")
    for ci, c in enumerate(CLASSES):
        for s in [x for x in ACTIVES if x["class_idx"] == ci]:
            for per in ("2026-07", "2026-08"):
                base = random.choice([random.randint(70, 90)] * 6 + [random.randint(60, 69)] + [random.randint(91, 97)])
                komp = {k: max(55, min(100, base + random.randint(-6, 6))) for k in KOMPS}
                api("POST", "/grades", "admin", {"student_id": s["id"], "class_id": c["id"],
                    "periode": per, "komponen": komp, "catatan": ""})
    ex1 = api("POST", "/exams", "admin", {"nama": "Ujian Bulanan September", "jenis": "Ujian bulanan",
        "tanggal": "2026-09-10", "class_id": CLASSES[0]["id"], "passing_grade": 70, "keterangan": ""})
    api("PUT", f"/exams/{ex1['id']}/results", "admin",
        {"results": [{"student_id": s["id"], "nilai": random.randint(62, 96)} for s in ACTIVES if s["class_idx"] == 0]})
    ex2 = api("POST", "/exams", "admin", {"nama": "Try Out JLPT N4", "jenis": "Try Out JLPT",
        "tanggal": "2026-09-17", "class_id": CLASSES[2]["id"], "passing_grade": 80, "keterangan": ""})
    api("PUT", f"/exams/{ex2['id']}/results", "admin",
        {"results": [{"student_id": s["id"], "nilai": random.randint(65, 98)} for s in ACTIVES if s["class_idx"] == 2]})
    api("POST", "/exams", "admin", {"nama": "Ujian Akhir N3", "jenis": "Ujian akhir",
        "tanggal": "2026-10-02", "class_id": CLASSES[4]["id"], "passing_grade": 75, "keterangan": ""})
    print("grades + exams ok")



def phase_selections():
    print("== selections ==")
    for s in ACTIVES + [c for c in CANDS if c["status"] not in ("calon_siswa",)]:
        for jenis, hasil in (("administrasi", "lulus"), ("kesehatan", "lulus"), ("fisik", "lulus")):
            api("POST", f"/students/{s['id']}/selections", "admin",
                {"jenis": jenis, "hasil": hasil, "tanggal": "2026-06-15"})
        if s.get("status") not in ("pendaftaran", "seleksi"):
            api("POST", f"/students/{s['id']}/selections", "admin",
                {"jenis": "bahasa", "hasil": "lulus", "nilai": random.randint(70, 95), "tanggal": "2026-06-20"})
    print("selections ok")



def phase_followups():
    print("== candidate follow-ups ==")
    CF_CH = ["whatsapp", "phone", "in_person", "sosmed", "kunjungan"]
    CF_OUT = ["terhubungi", "janji_datang", "minat"]
    for i, c in enumerate(CANDS[:9]):
        nfu = 1 + (i % 3)
        for k in range(nfu):
            fu = (date.today() + timedelta(days=random.choice([-6, -2, 0, 3, 7]))).isoformat() if k == nfu - 1 else None
            api("POST", "/candidate-followups/activities", "marketing",
                {"student_id": c["id"], "channel": random.choice(CF_CH),
                 "outcome": random.choice(CF_OUT),
                 "note": random.choice(["Sudah dihubungi, respons baik", "Minta brosur biaya", "Akan diskusi dengan orang tua",
                                        "Janji datang ke LPK", "Tanya jadwal dan biaya"]),
                 "next_follow_up_at": fu,
                 "next_follow_up_note": "Hubungi lagi" if fu else ""})
    print("candidate follow-ups ok")



def phase_payments():
    print("== payments (Jun-Sep) ==")
    BILLED = ACTIVES + ALUMNI
    ACCLIST = list(ACCS.values())
    lunas_n = partial_n = od_n = none_n = 0
    sept_pay = 0
    for i, s in enumerate(BILLED):
        r = random.random()
        total = 18500000
        if s in ALUMNI:
            plan = [5000000, 5000000, 3500000, 5000000]
            for k, nom in enumerate(plan):
                api("POST", "/payments", "finance", {"student_id": s["id"], "nominal": nom,
                    "tanggal": f"2024-{random.randint(6, 11):02d}-{random.randint(1, 28):02d}" if k < 2 else f"2025-{random.randint(1, 6):02d}-{random.randint(1, 28):02d}",
                    "metode": random.choice(["cash", "transfer", "qris"]), "jenis": "Cicilan",
                    "account_id": random.choice(ACCLIST)})
            continue
        if r < 0.38:
            lunas_n += 1
            parts = [5000000, 5000000, 5000000, 3500000]
            dates = ["2026-06-12", "2026-07-14", "2026-08-16", sept_days(1)[0]]
            for nom, tgl in zip(parts, dates):
                api("POST", "/payments", "finance", {"student_id": s["id"], "nominal": nom, "tanggal": tgl,
                    "metode": random.choice(["cash", "transfer", "qris"]), "jenis": "Cicilan", "account_id": random.choice(ACCLIST)})
                if tgl.startswith("2026-09"):
                    sept_pay += nom
        elif r < 0.73:
            partial_n += 1
            for nom, tgl in [(5000000, "2026-07-10"), (3000000, sept_days(1)[0])][: random.choice([1, 2, 2])]:
                api("POST", "/payments", "finance", {"student_id": s["id"], "nominal": nom, "tanggal": tgl,
                    "metode": random.choice(["cash", "transfer"]), "jenis": "Cicilan", "account_id": random.choice(ACCLIST)})
                if tgl.startswith("2026-09"):
                    sept_pay += nom
        elif r < 0.88:
            od_n += 1
            api("POST", "/payments", "finance", {"student_id": s["id"], "nominal": 2000000,
                "tanggal": "2026-07-05", "metode": "cash", "jenis": "Cicilan", "account_id": ACCLIST[0]})
        else:
            none_n += 1
    print(f"lunas={lunas_n} partial={partial_n} overdue-light={od_n} none={none_n} sept_income≈{sept_pay}")



def phase_expenses():
    print("== expenses ==")
    EXP = [("Gaji Karyawan Agustus", "Gaji", 38500000, "2026-09-02", "Gaji karyawan bulan Agustus", "dibayar"),
           ("Honor Guru Agustus", "Honor Guru", 14200000, "2026-09-03", "Honor pengajar bulan Agustus", "dibayar"),
           ("Sewa Gedung September", "Sewa Gedung", 7500000, "2026-09-01", "Sewa gedung bulan September", "dibayar"),
           ("Tagihan Listrik Agustus", "Listrik", 1350000, "2026-09-07", "Tagihan PLN", "dibayar"),
           ("Catering Asrama", "Makan Siswa", 4800000, "2026-09-09", "Catering asrama minggu ke-2", "dibayar"),
           ("Langganan Internet", "Internet", 550000, "2026-09-05", "Indihome September", "dibayar"),
           ("Belanja ATK", "ATK", 620000, "2026-09-11", "Kertas, tinta, map", "dibayar"),
           ("Antar Jemput Dokumen", "Transportasi", 890000, "2026-09-14", "Bensin + tol", "dibayar"),
           ("Tagihan Air", "Air", 340000, "2026-09-16", "PDAM", "dibayar"),
           ("Servis AC Kelas", "Perawatan", 1100000, "2026-09-18", "Servis AC R-101", "dibayar"),
           ("Kebutuhan Operasional", "Operasional Lainnya", 1800000, "2026-09-20", "Kebutuhan operasional", "disetujui"),
           ("Pajak Bulanan", "Pajak", 2400000, "2026-09-21", "Pajak bulan berjalan", "disetujui"),
           ("Belanja ATK Tambahan", "ATK", 750000, "2026-09-22", "Spidol dan papan tulis", "diajukan"),
           ("Transportasi Jemput", "Transportasi", 500000, "2026-09-23", "Jemput siswa baru", "draft"),
           ("Pengadaan Proyektor", "Operasional Lainnya", 3000000, "2026-09-19", "Proyektor ruang kelas", "ditolak")]
    for judul, kat, nom, tgl, desk, target in EXP:
        e = api("POST", "/expenses", "finance", {"judul": judul, "kategori": kat, "nominal": nom,
            "tanggal": tgl, "deskripsi": desk, "account_id": ACCS["BCA Operasional"]})
        eid = e["id"]
        if target == "draft":
            continue
        api("POST", f"/expenses/{eid}/submit", "finance")
        if target == "diajukan":
            continue
        decider = "owner" if nom >= 1000000 else "finance"
        api("POST", f"/expenses/{eid}/decide", decider, {"setuju": target != "ditolak",
            "alasan": "Sesuai kebutuhan operasional" if target != "ditolak" else "Bukan prioritas bulan ini"})
        if target == "dibayar":
            api("POST", f"/expenses/{eid}/pay", "finance", {"account_id": ACCS["BCA Operasional"]})
    print("expenses ok")



def phase_hr_attendance():
    print("== employee attendance + leaves (Sept) ==")
    EMPIDS = list(EMPS.values())
    for day in sept_weekdays():
        recs = []
        for eid in EMPIDS:
            r = random.random()
            st = "hadir" if r < 0.93 else ("terlambat" if r < 0.96 else ("izin" if r < 0.98 else "sakit"))
            rec = {"employee_id": eid, "status": st,
                   "jam_masuk": f"07:{random.randint(25, 59):02d}" if st in ("hadir", "terlambat") else None,
                   "jam_pulang": f"16:{random.randint(0, 59):02d}" if st in ("hadir", "terlambat") else None}
            if st == "terlambat":
                rec["jam_masuk"] = f"08:{random.randint(5, 25):02d}"
            recs.append(rec)
        api("POST", "/hr/attendance", "hr", {"tanggal": day, "records": recs})
    by_name = {v: k for k, v in EMPS.items()}
    lv1 = api("POST", "/leaves", "hr", {"employee_id": EMPS["Nina Kurnia"], "jenis": "Cuti",
        "dari": "2026-09-08", "sampai": "2026-09-10", "alasan": "Acara keluarga di Kebumen"})
    api("PUT", f"/leaves/{lv1['id']}/decide", "hr", {"setuju": True, "alasan": "Disetujui"})
    lv2 = api("POST", "/leaves", "hr", {"employee_id": EMPS["Yoga Pratama"], "jenis": "Izin",
        "dari": "2026-09-15", "sampai": "2026-09-15", "alasan": "Keperluan pribadi"})
    api("PUT", f"/leaves/{lv2['id']}/decide", "hr", {"setuju": False, "alasan": "Jadwal kunjungan sekolah padat"})
    api("POST", "/leaves", "hr", {"employee_id": EMPS["Dewi Anggraini"], "jenis": "Cuti",
        "dari": "2026-09-28", "sampai": "2026-09-29", "alasan": "Rencana cuti akhir bulan"})
    api("POST", "/hr/attendance", "hr", {"tanggal": "2026-09-09", "records": [
        {"employee_id": EMPS["Yoga Pratama"], "status": "alfa", "keterangan": "Tanpa kabar"}]})
    api("POST", "/hr/attendance", "hr", {"tanggal": "2026-09-16", "records": [
        {"employee_id": EMPS["Agus Setyawan"], "status": "alfa", "keterangan": "Tanpa kabar"}]})
    print("attendance + leaves ok")



def phase_payroll():
    print("== payroll Aug + Sep ==")
    HONOR_MEET = {"Haryanto Wijaya": 22, "Siti Kurniawati": 20, "Bambang Sutrisno": 21, "Agus Setyawan": 19}
    for per in ("2026-08", "2026-09"):
        items = []
        for nama, eid in EMPS.items():
            it = {"employee_id": eid}
            if nama in HONOR_MEET:
                it["honor_pertemuan"] = HONOR_MEET[nama] + (0 if per == "2026-08" else -2)
                it["honor_note"] = "Konfirmasi rekap kelas"
            items.append(it)
        items[7].update({"bonus": 300000, "bonus_reason": "Kinerja penagihan baik"})
        items[9].update({"lembur": 250000, "lembur_reason": "Lembur persiapan ujian",
                         "lembur_source_note": "2026-08-28 s.d. 2026-08-29" if per == "2026-08" else "2026-09-18",
                         "potongan": [{"jenis": "Kasbon", "nominal": 200000, "keterangan": "Kasbon tengah bulan",
                                        "source_ref": {"source_type": "external_doc", "source_note": "Slip kasbon"}}]})
        r = api("POST", "/payrolls/calculate", "hr", {"periode": per, "items": items})
        assert len(r["rows"]) == len(EMPS), r
        for row in r["rows"]:
            api("POST", f"/payrolls/{row['id']}/approve", "owner", {})
        print(f"payroll {per}: {len(r['rows'])} approved")
        if per == "2026-08":
            for row in r["rows"]:
                api("POST", f"/payrolls/{row['id']}/pay", "finance", {"account_id": ACCS["BCA Operasional"]})
            print("payroll 2026-08 paid")



def phase_jobs():
    global JOBIDS
    print("== job orders + interviews ==")
    JOBS = [
        ("Sakura Care Support Co., Ltd. (Demo)", "Caregiver (Kaigo)", "Osaka", 5, "¥200.000/bulan", "Shift",
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
         "Pengalaman las diutamakan", 20, 32, "L", "N4", "Manufaktur", None, "selesai"),
    ]
    JOBIDS = []
    for per, pos, lok, jum, gaji, jam, sy, umin, umax, jk, jlpt, jns, tgliv, st in JOBS:
        j = api("POST", "/job-orders", "marketing", {"perusahaan": per, "posisi": pos, "lokasi": lok,
            "jumlah_kebutuhan": jum, "gaji": gaji, "jam_kerja": jam, "persyaratan": sy,
            "usia_min": umin, "usia_max": umax, "jenis_kelamin": jk, "min_jlpt": jlpt,
            "jenis_pekerjaan": jns, "tanggal_interview": tgliv, "status": st})
        JOBIDS.append(j["id"])
    match_students = [s for s in ACTIVES if s["status"] == "matching"]
    iv_plan = [(match_students[0], 0, "2026-10-06", "menunggu"), (match_students[1], 1, "2026-10-13", "menunggu"),
               (match_students[2], 2, "2026-09-30", "menunggu")]
    for s, ji, tgl, hasil in iv_plan:
        api("POST", "/interviews", "marketing", {"job_order_id": JOBIDS[ji], "student_id": s["id"],
            "tanggal": tgl, "hasil": hasil, "catatan": ""})
    for s, ji, tgl, hasil in [(ALUMNI[0], 4, "2025-08-12", "lulus"), (ALUMNI[1], 5, "2025-09-02", "lulus"),
                              (ALUMNI[2], 6, "2025-07-20", "lulus"), (ALUMNI[3], 4, "2025-08-12", "gagal"),
                              (ALUMNI[4], 5, "2025-09-02", "gagal")]:
        api("POST", "/interviews", "marketing", {"job_order_id": JOBIDS[ji], "student_id": s["id"],
            "tanggal": tgl, "hasil": hasil, "catatan": ""})
    print("jobs + interviews ok")



def phase_dep_students():
    global DEPST
    print("== departure students (5) ==")
    DEPST = []
    for i, (st, job) in enumerate([("pemberkasan", 0), ("pemberkasan", 2), ("visa", 0), ("visa", 1), ("visa", 2)]):
        kab = pick_kab()
        gender = "L" if i % 2 == 0 else "P"
        s = make_student(gender, kab, ["pendaftaran", "seleksi", "diterima", "pelatihan", "ujian", "lulus",
                                       "matching", "pemberkasan"] + (["visa"] if st == "visa" else []),
                         "2026-07-15", jlpt="N4" if i < 3 else "N3")
        api("POST", "/interviews", "marketing", {"job_order_id": JOBIDS[job], "student_id": s["id"],
            "tanggal": "2026-08-20", "hasil": "lulus", "catatan": ""})
        DEPST.append(s)
    print("departure students:", len(DEPST))



def phase_documents():
    print("== documents ==")
    BASIC_DOCS = [("identitas", "KTP"), ("identitas", "Kartu Keluarga"), ("pendidikan", "Ijazah")]
    for s in ACTIVES:
        for kat, jenis in BASIC_DOCS[:3] if s["status"] == "pelatihan" else BASIC_DOCS[:2]:
            api("POST", f"/students/{s['id']}/documents", "admin",
                data={"jenis": jenis, "kategori": kat})
        if s["status"] in ("ujian", "matching"):
            api("POST", f"/students/{s['id']}/documents", "admin", data={"jenis": "SKCK", "kategori": "identitas"})
    for s in DEPST:
        for kat, jenis in [("identitas", "KTP"), ("identitas", "Kartu Keluarga"), ("identitas", "SKCK"),
                           ("pendidikan", "Ijazah"), ("kesehatan", "Medical Check-up"), ("jepang", "Paspor"),
                           ("jepang", "Sertifikat JLPT"), ("jepang", "COE"), ("jepang", "Visa"),
                           ("jepang", "Tiket"), ("kontrak", "Kontrak Kerja")]:
            exp = None
            if jenis in ("Paspor", "Visa"):
                exp = "2029-05-10"
            elif jenis == "Medical Check-up":
                exp = "2026-11-20"
            elif jenis == "SKCK":
                exp = "2025-12-01" if s == DEPST[0] else "2027-01-15"
            api("POST", f"/students/{s['id']}/documents", "admin",
                data={"jenis": jenis, "kategori": kat, **({"tanggal_kadaluarsa": exp} if exp else {})})
    for s in ALUMNI[:6]:
        for kat, jenis in [("identitas", "KTP"), ("pendidikan", "Ijazah"), ("jepang", "Paspor")]:
            api("POST", f"/students/{s['id']}/documents", "admin", data={"jenis": jenis, "kategori": kat})
    print("documents ok")



def phase_departures():
    print("== departures ==")
    for i, s in enumerate(DEPST):
        p = api("POST", "/departures", "admin", {"student_id": s["id"], "job_order_id": JOBIDS[i % 3],
            "target_departure_date": f"2026-1{['0', '1'][i % 2]}-{10 + i:02d}",
            "destination": ["Osaka", "Tokyo", "Aichi"][i % 3], "pic_name": "Yoga Pratama"})
        items = api("GET", f"/departures/{p['id']}/checklist", "admin")
        mp = {it["requirement_code"]: it["id"] for it in items}
        docs = {d["jenis"]: d["id"] for d in api("GET", f"/students/{s['id']}/documents", "admin")}
        docmap = {"passport": "Paspor", "coe": "COE", "visa": "Visa", "medical": "Medical Check-up",
                  "ticket": "Tiket", "contract": "Kontrak Kerja"}
        verify_n = 6 if i < 2 else (4 if i < 4 else 2)
        for code in list(mp.keys())[:verify_n]:
            api("PUT", f"/departures/{p['id']}/checklist/{mp[code]}/verify", "admin",
                {"document_id": docs.get(docmap[code]), "note": "Dokumen valid"})
        if i == 0:
            api("POST", f"/departures/{p['id']}/ready", "owner", {"reason": "Berkas lengkap, siap berangkat"})
            api("PUT", f"/departures/{p['id']}", "admin",
                {"status": "siap", "alasan": "Diverifikasi lengkap"})
        if i == 4:
            api("POST", f"/departures/{p['id']}/block", "owner", {"reason": "Menunggu revisi COE dari kumiai"})
    print("departures ok")



def phase_collections():
    print("== collections ==")
    od = [s for s in ACTIVES if s.get("jatuh_tempo") and s["jatuh_tempo"] < "2026-09-24"][:8]
    for i, s in enumerate(od):
        ch = ["phone", "whatsapp", "in_person"][i % 3]
        oc = ["contacted", "promised_payment", "no_response"][i % 3]
        fu = ["2026-09-26", "2026-09-28", "2026-09-20", "2026-10-02", None, "2026-09-30"][i % 6]
        api("POST", "/collections/activities", "finance", {"student_id": s["id"], "channel": ch,
            "outcome": oc, "note": random.choice(["Sudah dihubungi, janji transfer", "Minta keringanan jadwal",
                "Tidak menjawab telepon", "Akan dibayar setelah gajian", "Sudah diingatkan via WA"]),
            **({"next_follow_up_at": fu, "next_follow_up_note": "Follow-up pembayaran"} if fu else {})})
    print("collections ok")



def phase_summary():
    print()
    print("================ SEED COMPLETE ================")
    print(f"active={len(ACTIVES)} alumni={len(ALUMNI)} candidates={len(CANDS)} departure={len(DEPST)}")
    print("teachers=6 staff=5 classes=6 jobs=7")


PHASES = [("login", phase_login), ("accounts", phase_accounts), ("employees", phase_employees),
          ("users", phase_users), ("classes", phase_classes), ("students", phase_students),
          ("alumni", phase_alumni), ("candidates", phase_candidates), ("attendance", phase_attendance),
          ("grades", phase_grades), ("selections", phase_selections), ("followups", phase_followups),
          ("payments", phase_payments), ("expenses", phase_expenses), ("hr_attendance", phase_hr_attendance),
          ("payroll", phase_payroll), ("jobs", phase_jobs), ("dep_students", phase_dep_students),
          ("documents", phase_documents), ("departures", phase_departures),
          ("collections", phase_collections), ("summary", phase_summary)]

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--list-phases" in args:
        print(" ".join(n for n, _ in PHASES))
    else:
        start = 0
        if "--from-phase" in args:
            want = args[args.index("--from-phase") + 1]
            start = next(i for i, (n, _) in enumerate(PHASES) if n == want)
        for name, fn in PHASES[start:]:
            fn()
