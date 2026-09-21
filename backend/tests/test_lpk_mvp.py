"""Backend tests for Sistem LPK Jepang MVP."""
import os
import io
import base64
import pytest
import requests
from datetime import date

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fall back to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "owner": ("owner@lpk.id", "owner123"),
    "admin": ("admin@lpk.id", "password123"),
    "finance": ("finance@lpk.id", "password123"),
    "hr": ("hr@lpk.id", "password123"),
    "guru": ("guru@lpk.id", "password123"),
    "marketing": ("marketing@lpk.id", "password123"),
    "staff": ("staff@lpk.id", "password123"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return r


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def tokens():
    out = {}
    for role, (email, pwd) in CREDS.items():
        r = _login(email, pwd)
        assert r.status_code == 200, f"login {role} failed: {r.status_code} {r.text}"
        out[role] = r.json()["token"]
    return out


# ---------------- AUTH ----------------
class TestAuth:
    def test_login_owner(self):
        r = _login(*CREDS["owner"])
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and "user" in d
        assert d["user"]["email"] == "owner@lpk.id"
        assert d["user"]["role"] == "owner"

    def test_login_wrong_password(self):
        r = _login("owner@lpk.id", "wrongpwd")
        assert r.status_code == 401
        assert "salah" in r.json().get("detail", "").lower()

    def test_me(self, tokens):
        r = requests.get(f"{API}/auth/me", headers=_headers(tokens["owner"]))
        assert r.status_code == 200
        assert r.json()["role"] == "owner"

    def test_guru_cannot_post_payment(self, tokens):
        r = requests.post(f"{API}/payments",
                          headers=_headers(tokens["guru"]),
                          json={"student_id": "x", "nominal": 100000, "tanggal": date.today().isoformat(),
                                "metode": "tunai", "account_id": "x"})
        assert r.status_code == 403

    def test_finance_cannot_post_employee(self, tokens):
        r = requests.post(f"{API}/employees",
                          headers=_headers(tokens["finance"]),
                          json={"name": "TEST_x", "role": "guru"})
        assert r.status_code == 403

    def test_nonowner_cannot_create_user(self, tokens):
        r = requests.post(f"{API}/users",
                          headers=_headers(tokens["admin"]),
                          json={"name": "TEST_u", "email": "test_nou@x.id", "password": "abcdef", "role": "staff"})
        assert r.status_code == 403


# ---------------- STUDENTS ----------------
class TestStudents:
    @pytest.fixture(scope="class")
    def student_id(self, tokens):
        r = requests.post(f"{API}/students",
                          headers=_headers(tokens["admin"]),
                          json={"nama_lengkap": "TEST_Budi Santoso", "jenis_kelamin": "L",
                                "tanggal_lahir": "2000-05-10", "no_hp": "0811",
                                "alamat": {"jalan": "Jl. Test", "kota": "Jakarta"}})
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        return sid

    def test_list_enriched(self, tokens):
        r = requests.get(f"{API}/students", headers=_headers(tokens["admin"]))
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        if rows:
            row = rows[0]
            assert "pembayaran" in row
            assert set(["total", "bayar", "sisa"]).issubset(row["pembayaran"].keys())

    def test_created_default_feeplan(self, tokens, student_id):
        r = requests.get(f"{API}/students/{student_id}", headers=_headers(tokens["admin"]))
        assert r.status_code == 200
        prof = r.json()
        total = prof["pembayaran"]["total"]
        assert total == 18500000, f"expected 18,500,000, got {total}"
        assert prof["status_history"], "status_history missing"

    def test_status_change(self, tokens, student_id):
        r = requests.put(f"{API}/students/{student_id}/status",
                         headers=_headers(tokens["admin"]),
                         json={"status": "seleksi", "catatan": "TEST"})
        assert r.status_code == 200, r.text
        r2 = requests.get(f"{API}/students/{student_id}", headers=_headers(tokens["admin"]))
        d = r2.json()
        assert d["status"] == "seleksi"
        assert any(h["status"] == "seleksi" for h in d["status_history"])

    def test_selection(self, tokens, student_id):
        r = requests.post(f"{API}/students/{student_id}/selections",
                          headers=_headers(tokens["admin"]),
                          json={"tanggal": date.today().isoformat(), "jenis": "wawancara",
                                "hasil": "lulus", "catatan": "ok"})
        assert r.status_code == 200, r.text

    def test_documents_checklist(self, tokens, student_id):
        r = requests.get(f"{API}/students/{student_id}/documents", headers=_headers(tokens["admin"]))
        assert r.status_code == 200
        docs = r.json()
        assert len(docs) == 13, f"expected 13 doc checklist items, got {len(docs)}"

    def test_doc_status_toggle(self, tokens, student_id):
        r = requests.put(f"{API}/students/{student_id}/documents/status",
                         headers=_headers(tokens["admin"]),
                         json={"jenis": "KTP", "kategori": "identitas", "status": "tersedia"})
        assert r.status_code == 200, r.text

    def test_doc_upload_and_download(self, tokens, student_id):
        # 1x1 PNG
        png_b64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeI"
                   "mDPMAAAAASUVORK5CYII=")
        png = base64.b64decode(png_b64)
        files = {"file": ("test.png", io.BytesIO(png), "image/png")}
        data = {"jenis": "KTP", "kategori": "identitas"}
        r = requests.post(f"{API}/students/{student_id}/documents",
                          headers=_headers(tokens["admin"]), files=files, data=data)
        if r.status_code != 200:
            pytest.skip(f"Object storage upload not available: {r.status_code} {r.text[:200]}")
        doc = r.json()
        file_id = doc.get("file_id")
        if not file_id:
            pytest.skip("No file_id in response")
        r2 = requests.get(f"{API}/files/{file_id}?auth={tokens['admin']}")
        assert r2.status_code == 200
        assert len(r2.content) > 0


# ---------------- PAYMENTS ----------------
class TestPayments:
    @pytest.fixture(scope="class")
    def ctx(self, tokens):
        # pick an existing student and account
        s = requests.get(f"{API}/students", headers=_headers(tokens["admin"])).json()
        a = requests.get(f"{API}/finance/accounts", headers=_headers(tokens["finance"])).json()
        assert s and a, "need seeded students & accounts"
        return {"student_id": s[0]["id"], "account_id": a[0]["id"], "saldo_before": a[0]["saldo"]}

    def test_create_payment(self, tokens, ctx):
        r = requests.post(f"{API}/payments", headers=_headers(tokens["finance"]),
                          json={"student_id": ctx["student_id"], "nominal": 500000,
                                "tanggal": date.today().isoformat(), "metode": "tunai",
                                "account_id": ctx["account_id"], "keterangan": "TEST payment"})
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["no_kwitansi"].startswith("KW-")
        ctx["payment_id"] = p["id"]
        # verify saldo went up
        a = requests.get(f"{API}/finance/accounts", headers=_headers(tokens["finance"])).json()
        after = next(x["saldo"] for x in a if x["id"] == ctx["account_id"])
        assert after == ctx["saldo_before"] + 500000, f"saldo not updated: {after} vs {ctx['saldo_before']}+500000"
        # verify transaction created
        tx = requests.get(f"{API}/finance/transactions", headers=_headers(tokens["finance"])).json()
        assert any(t.get("ref_type") == "payment" and t.get("ref_id") == p["id"] for t in tx)

    def test_receipt(self, tokens, ctx):
        pid = ctx.get("payment_id")
        assert pid
        r = requests.get(f"{API}/payments/{pid}/receipt", headers=_headers(tokens["finance"]))
        assert r.status_code == 200
        d = r.json()
        for k in ("total_tagihan", "total_dibayar", "sisa"):
            assert k in d, f"missing {k}"

    def test_update_without_alasan(self, tokens, ctx):
        pid = ctx.get("payment_id")
        r = requests.put(f"{API}/payments/{pid}", headers=_headers(tokens["finance"]),
                         json={"student_id": ctx["student_id"], "nominal": 600000,
                               "tanggal": date.today().isoformat(), "account_id": ctx["account_id"],
                               "metode": "tunai"})
        assert r.status_code == 400, r.text

    def test_update_with_alasan(self, tokens, ctx):
        pid = ctx.get("payment_id")
        r = requests.put(f"{API}/payments/{pid}", headers=_headers(tokens["finance"]),
                         json={"student_id": ctx["student_id"], "nominal": 600000,
                               "tanggal": date.today().isoformat(), "account_id": ctx["account_id"],
                               "metode": "tunai", "alasan": "TEST koreksi"})
        assert r.status_code == 200, r.text

    def test_arrears(self, tokens):
        r = requests.get(f"{API}/payments-arrears?filter=terlambat", headers=_headers(tokens["finance"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- FINANCE ----------------
class TestFinance:
    def test_summary(self, tokens):
        r = requests.get(f"{API}/finance/summary?period=bulan", headers=_headers(tokens["finance"]))
        assert r.status_code == 200
        d = r.json()
        for k in ("pemasukan", "pengeluaran", "saldo_kas", "piutang", "accounts"):
            assert k in d

    def test_expense_reduces_saldo(self, tokens):
        # Use last account to avoid race with parallel payment tests on first account
        acc = requests.get(f"{API}/finance/accounts", headers=_headers(tokens["finance"])).json()
        aid = acc[-1]["id"]
        before = acc[-1]["saldo"]
        r = requests.post(f"{API}/finance/transactions", headers=_headers(tokens["finance"]),
                          json={"jenis": "pengeluaran", "kategori": "operasional", "nominal": 100000,
                                "deskripsi": "TEST expense", "tanggal": date.today().isoformat(),
                                "account_id": aid})
        assert r.status_code == 200, r.text
        acc2 = requests.get(f"{API}/finance/accounts", headers=_headers(tokens["finance"])).json()
        after = next(x["saldo"] for x in acc2 if x["id"] == aid)
        assert after == before - 100000, f"expected {before - 100000}, got {after}"

    def test_tx_update_needs_alasan(self, tokens):
        tx = requests.get(f"{API}/finance/transactions", headers=_headers(tokens["finance"])).json()
        # find a manual tx (not from payment)
        manual = next((t for t in tx if t.get("ref_type") != "payment"), None)
        assert manual, "no manual transaction found"
        tid = manual["id"]
        r = requests.put(f"{API}/finance/transactions/{tid}", headers=_headers(tokens["finance"]),
                         json={"jenis": manual["jenis"], "kategori": manual["kategori"],
                               "nominal": 12345, "tanggal": manual["tanggal"],
                               "account_id": manual["account_id"]})
        assert r.status_code == 400, r.text

    def test_reconciliation_selisih(self, tokens):
        acc = requests.get(f"{API}/finance/accounts", headers=_headers(tokens["finance"])).json()
        aid = acc[0]["id"]
        sistem = acc[0]["saldo"]
        # no alasan with selisih != 0 should 400
        r = requests.post(f"{API}/finance/reconciliations", headers=_headers(tokens["finance"]),
                          json={"account_id": aid, "tanggal": date.today().isoformat(),
                                "saldo_aktual": sistem + 5000})
        assert r.status_code == 400
        r2 = requests.post(f"{API}/finance/reconciliations", headers=_headers(tokens["finance"]),
                           json={"account_id": aid, "tanggal": date.today().isoformat(),
                                 "saldo_aktual": sistem + 5000, "alasan": "TEST selisih kas"})
        assert r2.status_code == 200
        assert r2.json().get("selisih") == 5000

    def test_cashflow(self, tokens):
        r = requests.get(f"{API}/finance/cashflow", headers=_headers(tokens["finance"]))
        assert r.status_code == 200
        assert len(r.json()) == 6


# ---------------- ACADEMICS ----------------
class TestAcademics:
    def test_classes_enriched(self, tokens):
        r = requests.get(f"{API}/classes", headers=_headers(tokens["admin"]))
        assert r.status_code == 200
        rows = r.json()
        assert rows
        assert "guru_nama" in rows[0] and "jumlah_siswa" in rows[0]

    def test_attendance_upsert(self, tokens):
        cls = requests.get(f"{API}/classes", headers=_headers(tokens["admin"])).json()
        cid = cls[0]["id"]
        det = requests.get(f"{API}/classes/{cid}", headers=_headers(tokens["admin"])).json()
        students = det.get("students") or det.get("siswa") or []
        if not students:
            pytest.skip("no students in class")
        sid = students[0]["id"]
        today = date.today().isoformat()
        payload = {"class_id": cid, "tanggal": today,
                   "records": [{"student_id": sid, "status": "hadir"}]}
        r1 = requests.post(f"{API}/attendance", headers=_headers(tokens["admin"]), json=payload)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(f"{API}/attendance", headers=_headers(tokens["admin"]), json=payload)
        assert r2.status_code == 200, "second upsert should not fail"
        rec = requests.get(f"{API}/attendance/recap?class_id={cid}", headers=_headers(tokens["admin"]))
        assert rec.status_code == 200
        d = rec.json()
        # recap is a dict keyed by student_id
        assert isinstance(d, dict)
        if d:
            first = next(iter(d.values()))
            assert "persentase" in first

    def test_grade_computed(self, tokens):
        cls = requests.get(f"{API}/classes", headers=_headers(tokens["admin"])).json()
        cid = cls[0]["id"]
        det = requests.get(f"{API}/classes/{cid}", headers=_headers(tokens["admin"])).json()
        students = det.get("students") or []
        if not students:
            pytest.skip("no students")
        sid = students[0]["id"]
        r = requests.post(f"{API}/grades", headers=_headers(tokens["admin"]),
                          json={"student_id": sid, "class_id": cid, "periode": "TEST_2026-Q1",
                                "komponen": {"tulis": 80, "lisan": 90}})
        assert r.status_code == 200, r.text
        assert abs(r.json()["nilai_akhir"] - 85) < 0.01

    def test_guru_attendance_own_class_only(self, tokens):
        cls = requests.get(f"{API}/classes", headers=_headers(tokens["admin"])).json()
        # find class not taught by guru user
        guru_me = requests.get(f"{API}/auth/me", headers=_headers(tokens["guru"])).json()
        emp_id = guru_me.get("employee_id")
        other = next((c for c in cls if c.get("guru_id") != emp_id), None)
        if not other:
            pytest.skip("no other class")
        r = requests.post(f"{API}/attendance", headers=_headers(tokens["guru"]),
                          json={"class_id": other["id"], "tanggal": date.today().isoformat(), "records": []})
        assert r.status_code == 403


# ---------------- JOB ORDERS ----------------
class TestJobs:
    def test_list_and_candidates(self, tokens):
        r = requests.get(f"{API}/job-orders", headers=_headers(tokens["admin"]))
        assert r.status_code == 200
        rows = r.json()
        if not rows:
            pytest.skip("no job orders")
        jid = rows[0]["id"]
        c = requests.get(f"{API}/job-orders/{jid}/candidates", headers=_headers(tokens["admin"]))
        assert c.status_code == 200
        d = c.json()
        cands = d.get("candidates", [])
        assert isinstance(cands, list)
        if cands:
            first = cands[0]
            assert "checks" in first and "memenuhi" in first


# ---------------- DASHBOARD / MISC ----------------
class TestDashboard:
    @pytest.mark.parametrize("p", ["hari", "minggu", "bulan", "tahun"])
    def test_dashboard(self, tokens, p):
        r = requests.get(f"{API}/dashboard?period={p}", headers=_headers(tokens["owner"]))
        assert r.status_code == 200
        d = r.json()
        assert "siswa" in d and "operasional" in d
        assert "keuangan" in d  # owner has access

    def test_dashboard_guru_no_finance(self, tokens):
        r = requests.get(f"{API}/dashboard?period=bulan", headers=_headers(tokens["guru"]))
        assert r.status_code == 200
        d = r.json()
        assert d.get("keuangan") in (None, {}, False) or "keuangan" not in d

    def test_notifications(self, tokens):
        r = requests.get(f"{API}/notifications", headers=_headers(tokens["admin"]))
        assert r.status_code == 200

    def test_search(self, tokens):
        r = requests.get(f"{API}/search?q=Budi", headers=_headers(tokens["admin"]))
        assert r.status_code == 200

    def test_audit_logs(self, tokens):
        r = requests.get(f"{API}/audit-logs?entity=payment", headers=_headers(tokens["owner"]))
        assert r.status_code == 200

    @pytest.mark.parametrize("kind", ["students", "finance", "hr", "training"])
    def test_reports(self, tokens, kind):
        r = requests.get(f"{API}/reports/{kind}", headers=_headers(tokens["owner"]))
        assert r.status_code == 200
