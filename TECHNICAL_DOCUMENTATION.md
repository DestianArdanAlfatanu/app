# SISTEM DIGITAL LPK — TECHNICAL DOCUMENTATION

> Dokumen ini disusun murni dari inspeksi repository yang aktif (source code, manifest dependency, konfigurasi).
> Tidak ada klaim tanpa bukti. Versi library diambil dari `backend/requirements.txt` dan `frontend/package.json`.
> Tidak ada secret, token, password, isi `.env`, maupun data sensitif dalam dokumen ini.

## 1. Executive Summary

Sistem Digital LPK adalah aplikasi operasional terpusat untuk Lembaga Pelatihan Kerja (LPK) penyaluran tenaga kerja ke Jepang. Sistem mengintegrasikan seluruh alur operasional — dari calon siswa hingga keberangkatan — dalam satu aplikasi web dengan API terpusat, kontrol akses berbasis peran, jejak audit, dan penyimpanan dokumen persisten di server.

**Arsitektur ringkas:**

```text
Browser (React SPA, 2 shell: Staff & Student Portal)
   ↓ HTTPS/JSON (axios, JWT Bearer + cookie)
Backend API (FastAPI, router per domain, prefix /api)
   ↓ business/domain logic (Python, di dalam router + core.py)
PostgreSQL (adapter `pg_mongo`: tabel JSONB per koleksi; index unik/parsial)
   ↓
LocalDocumentStorage (filesystem server; metadata di PostgreSQL)
```

**Karakter utama yang terbukti dari kode:**

- API-first: ±161 route handler di 12 router domain.
- Keamanan berlapis: JWT + RBAC backend (`require_roles`, owner bypass, `deny_student`) + guard frontend (`AuthContext.MODULES`, `Guard`, `PortalGuard`).
- Integritas data: snapshot payroll, idempotency key pembayaran/koleksi/follow-up/WhatsApp, index unik database, audit trail dengan before/after.
- Dokumen: upload → `pending_verification` → `verified`/`rejected`; verifikasi selalu staf-side; binary di filesystem server (bukan public URL, bukan `/tmp`).
- WhatsApp (E1): antrean + template + idempotency + consent + retry; provider aktual hanya via `requests` (Meta Cloud API URL default dari env).

---

## 2. Tech Stack

| Layer | Technology | Version | Peran | Bukti di Repository |
|---|---|---|---|---|
| Frontend | React (+ React DOM) | 19.0.0 | UI SPA, 2 shell (staff + portal siswa) | `frontend/package.json`, `frontend/src/App.js` |
| Frontend routing | react-router-dom | 7.15.0 | Routing staff & portal + guard per modul | `frontend/package.json`, `frontend/src/App.js` |
| Frontend HTTP | axios | 1.18.0 | Satu instance API (`baseURL`, Bearer interceptor, 401 redirect) | `frontend/package.json`, `frontend/src/lib/api.js` |
| Frontend styling | Tailwind CSS (+ tailwindcss-animate) | 3.4.17 / 1.0.7 | Utility CSS + token desain shadcn | `frontend/package.json`, `frontend/tailwind.config.js`, `frontend/src/index.css` |
| Frontend build | CRACO + react-scripts (CRA 5, webpack) | 7.1.0 / 5.0.1 | Alias `@`, dev server, production build | `frontend/package.json`, `frontend/craco.config.js` |
| Frontend chart | recharts | 3.6.0 | Grafik dashboard | `frontend/package.json`, `frontend/src/pages/DashboardPage.jsx` |
| Frontend ikon | lucide-react | 0.516.0 | Ikon seluruh halaman | `frontend/package.json`, ±30 file `src` |
| Frontend notifikasi | sonner | 2.0.3 | Toast sukses/gagal | `frontend/package.json`, halaman + `components/ui/sonner.jsx` |
| Backend | FastAPI | 0.110.1 | HTTP API, routing, validasi, dependency injection | `backend/requirements.txt`, `backend/server.py` |
| Backend runtime | uvicorn | 0.25.0 | ASGI server | `backend/requirements.txt` |
| Database | PostgreSQL 15+ (via asyncpg + adapter `pg_mongo`) | asyncpg ≥ 0.29 | Penyimpanan utama (dokumen JSONB, UUID string) | `backend/requirements.txt`, `backend/core.py`, `backend/pg_mongo.py` |
| Validasi backend | Pydantic | ≥2.6.4 | Model `*In` per endpoint | `backend/requirements.txt`, semua `routers/*.py` |
| Auth token | PyJWT (HS256) | ≥2.10.1 | JWT access (12 jam) + refresh (7 hari) | `backend/requirements.txt`, `backend/core.py:91-99` |
| Password | bcrypt | 4.1.3 | Hash + verifikasi password | `backend/requirements.txt`, `backend/core.py:80-88` |
| Email validation | email-validator | ≥2.2.0 | Validasi `EmailStr` (login, user) | `backend/requirements.txt`, `routers/auth.py`, `routers/portal.py` |
| Upload parsing | python-multipart | ≥0.0.9 | `UploadFile`/`Form` (dokumen, bukti) | `backend/requirements.txt`, `routers/students.py`, `routers/portal.py` |
| HTTP keluar | requests | ≥2.31.0 | Provider WhatsApp + legacy storage eksternal | `backend/requirements.txt`, `routers/whatsapp.py`, `core.py` |
| Ekspor laporan | openpyxl / reportlab | ≥3.1.0 / ≥4.0.0 | Ekspor XLSX / PDF laporan | `backend/requirements.txt`, `routers/dashboard.py:499-560` |
| Env config | python-dotenv | ≥1.0.1 | Load `backend/.env` | `backend/requirements.txt`, `backend/server.py:1-5` |
| Testing backend | pytest + pytest-xdist | ≥8.0.0 / ≥3.6.0 | Suite API; 2 worker `loadscope` | `backend/requirements.txt`, `backend/pytest.ini`, `backend/tests/test_lpk_mvp.py` |
| Penyimpanan file | Custom `LocalDocumentStorage` (stdlib: `pathlib`, `os.replace`, `re`) | — (kode sendiri) | Binary dokumen di filesystem server | `backend/document_storage.py` |
| Runtime/infra | Proses uvicorn + static build frontend; tanpa Dockerfile di repo | — | Operasi lokal/server | Tidak ada `Dockerfile`; `.gitignore` mengabaikan `.env`, `backend/storage/` |


**Dependency yang tercatat di manifest tetapi TIDAK ditemukan import/pemakaiannya di kode** (sehingga tidak diklaim sebagai library aktif dan tidak masuk katalog): `boto3`, `requests-oauthlib`, `passlib`, `python-jose`, `cryptography`, `tzdata`, `pandas`, `numpy`, `jq`, `typer`, `black`, `isort`, `flake8`, `mypy` (backend); `@tanstack/react-query`, `swr`, `zod`, `@hookform/resolvers`, `framer-motion`, `dayjs`, `date-fns`, `cmdk`, `embla-carousel-react`, `vaul`, `next-themes`, `input-otp`, `react-day-picker`, `react-resizable-panels`, sebagian besar `@radix-ui/*`, `react-hook-form` (hanya dipakai file generated `components/ui/form.jsx` yang tidak diimpor halaman aplikasi). Pengecualian: `react-hook-form` tetap tercantum di tabel frontend sebagai "tersedia, tidak dipakai alur aplikasi".

---

## 3. Frontend Technology

**Framework & fondasi**

| Library | Versi | Digunakan Untuk | Contoh Penggunaan | Masalah yang Diselesaikan |
|---|---|---|---|---|
| react + react-dom | 19.0.0 | Komponen UI, 2 shell (staff `AppLayout`, siswa `PortalLayout`) | `src/App.js`, `src/pages/*`, `src/pages/portal/*` | Satu codebase untuk operasional internal dan layanan mandiri siswa tanpa aplikasi terpisah |
| react-router-dom | 7.15.0 | Routing + guard per modul/portal | `Guard mod="keuangan"`, `PortalGuard`, rute `/portal/*` di `src/App.js` | Navigasi terproteksi per peran; URL langsung ke halaman terlarang ditolak di UI |
| axios | 1.18.0 | Satu klien API: baseURL dari env, injeksi Bearer, redirect 401, `errMsg()` | `src/lib/api.js`; `fileUrl()` untuk preview owner | Menghindari fetch manual berulang; satu titik handling auth/error di seluruh app |
| @craco/craco + react-scripts | 7.1.0 / 5.0.1 | Alias `@→src`, dev server, build produksi | `craco.config.js`, script `start/build/test` | Import absolut konsisten; build teroptimasi tanpa eject CRA |
| tailwindcss (+ animate) | 3.4.17 / 1.0.7 | Utility styling + token desain (radius, chart colors) | `tailwind.config.js`, `src/index.css`, class di semua halaman | Konsistensi visual tanpa CSS file per halaman |
| useApi (custom hook) | kode sendiri | Fetch GET standar + `reload()` | `src/hooks/useApi.js`, dipakai semua halaman portal & staff | Menghindari boilerplate loading/error/refetch di tiap halaman |
| AuthContext (custom) | kode sendiri | Sesi user + matriks izin modul `MODULES` + owner bypass | `src/context/AuthContext.jsx:6-45`, `can(mod)` | Tombol/halaman disesuaikan peran sejak render pertama |

**UI & utilitas terbukti dipakai**

| Library | Versi | Digunakan Untuk | Contoh Penggunaan | Masalah yang Diselesaikan |
|---|---|---|---|---|
| lucide-react | 0.516.0 | Ikon | Sidebar, header, semua halaman | Ikon vektor konsisten tanpa aset gambar |
| sonner | 2.0.3 | Toast feedback | `toast.success/error` pasca simpan/upload | Feedback aksi tanpa dialog blocking |
| recharts | 3.6.0 | Grafik dashboard (`BarChart`, `ResponsiveContainer`) | `src/pages/DashboardPage.jsx` | Visualisasi operasional tanpa library chart berat di halaman lain |
| @radix-ui/react-dialog, popover (+ sonner) | 1.1.11 | Dialog & popover aksesibel (dipakai app) | `components/common.jsx`, `ReceiptDialog.jsx`, `layout/Header.jsx` | Dialog/notifikasi yang fokus-trap & aksesibel |
| lib/format.js (custom) | kode sendiri | `rupiah()`, `fmtDate`, `STATUS_LABELS`, `downloadCSV()` | Semua halaman list/laporan | Format id-ID + label status konsisten; ekspor CSV tanpa dependency |

**Pola yang terlihat:** form aplikasi dikelola manual (`useState` + validasi backend sebagai source of truth), bukan `react-hook-form`/`zod` di alur aplikasi. Data diambil langsung via `useApi`/axios per halaman (tanpa cache layer `react-query`/`swr`). Preview dokumen portal memakai Blob dari response + `URL.createObjectURL` dengan MIME asli response (`PortalPages.jsx`, fungsi `openPreview`) — perbaikan yang membuat PDF tampil di viewer browser, bukan raw text.

---

## 4. Backend Technology

| Library | Versi | Digunakan Untuk | Contoh Penggunaan | Masalah yang Diselesaikan |
|---|---|---|---|---|
| FastAPI | 0.110.1 | Routing (`APIRouter` per domain), DI (`Depends`), error `HTTPException` | 12 router di `server.py:27`, ±161 handler | Struktur API modular per domain bisnis |
| uvicorn | 0.25.0 | Menjalankan ASGI app | Runtime `server:app` | Server async produksi/dev yang sederhana |
| asyncpg | ≥ 0.29 | Akses PostgreSQL async lewat adapter `pg_mongo`; `pg_mongo.DuplicateKeyError` untuk idempotency race | `core.py`, `pg_mongo.py`, `finance.py`, `hr.py` | I/O database non-blocking; konflik konkurensi dipetakan ke respons deterministik |
| pydantic | ≥2.6.4 | Skema `*In` (Login, Payment, Payroll, Expense, Interview, dsb.) | Semua router | Validasi input terpusat + pesan error konsisten |
| PyJWT | ≥2.10.1 | Encode/decode JWT HS256 | `core.py:91-120` | Token stateless tanpa session store |
| bcrypt | 4.1.3 | Hash (`gensalt`) & `checkpw` | `core.py:80-88`, `routers/auth.py`, `routers/portal.py` | Password tidak pernah tersimpan plain-text |
| email-validator | ≥2.2.0 | `EmailStr` pada login & user | `routers/auth.py:12`, `routers/portal.py:15` | Menolak email malformed sejak validasi |
| python-multipart | ≥0.0.9 | `UploadFile`/`Form` | Upload dokumen & bukti | Upload file multipart terstandar |
| requests | ≥2.31.0 | HTTP ke provider WhatsApp (Cloud API) | `routers/whatsapp.py` ("hanya `requests`, sudah vendored") | Tanpa SDK provider; adapter mudah diganti |
| openpyxl / reportlab | ≥3.1.0 / ≥4.0.0 | Ekspor laporan XLSX (`Workbook`) / PDF (`SimpleDocTemplate`, kop LPK) | `routers/dashboard.py:499-560` | Laporan siap cetak/kirim tanpa tool eksternal |
| python-dotenv | ≥1.0.1 | Memuat `backend/.env` | `server.py:1-5` | Konfigurasi env per lingkungan |

**Arsitektur API:** satu `FastAPI` + `APIRouter(prefix="/api")`; 12 router domain (`auth, students, academics, finance, hr, jobs, dashboard, whatsapp, portal, collections, candidate_followups, departures`); `CORSMiddleware` (origins dari `CORS_ORIGINS`); startup `server.py:40-118` membuat index, seed admin/demo (dengan guard), seed template WA, dan menyiapkan direktori storage lokal. Relasi antar entity memakai string `id` UUID (`new_id()`), bukan DBRef — join dilakukan di kode (`payment_summary_map`, `enrich`, dsb.).

---

## 5. Database & Data Architecture

- **Teknologi:** PostgreSQL. Koneksi: `PgClient(os.environ["DATABASE_URL"])` (`backend/core.py`). Tiap koleksi disimpan sebagai tabel `(_pk, _seq, doc jsonb)`; `backend/pg_mongo.py` menyediakan API bergaya Motor (find/update/aggregate/index unik) sehingga router tidak menulis SQL manual. Akses async penuh via asyncpg.
- **Model data:** koleksi dokumen JSON dengan `id` UUID string (`new_id()`), `created_at` ISO (`now_iso()`), soft-delete `is_deleted` pada dokumen/file. Tidak ada ODM/migrasi — skema dijaga oleh Pydantic + pola kode; index dibuat idempoten setiap startup.

**Collection yang terbukti dipakai (32):** `users`, `students`, `employees`, `employee_attendances`, `leaves`, `payrolls`, `classes`, `attendance`, `grades`, `exams`, `selections`, `payments`, `transactions`, `accounts`, `expenses`, `reconciliations`, `counters`, `documents`, `files`, `job_orders`, `jobs` (baca fallback legacy di `departures.py:128,228`), `interviews`, `departure_profiles`, `departure_checklist`, `collection_activities`, `candidate_followups`, `notifications`, `whatsapp_templates`, `whatsapp_messages`, `whatsapp_events`, `audit_logs`, `login_attempts`.

**Index strategy (`server.py:42-98`) dan masalah yang diselesaikan:**

| Index | Masalah yang Diselesaikan |
|---|---|
| `users.email` unique; `users.id` unique; `users.student_id` unique+sparse | Satu email & satu akun per siswa; sparse agar user non-siswa tanpa `student_id` tidak saling bertabrakan |
| `attendance (class_id, student_id, tanggal)` unique | Absensi ganda kelas/tanggal yang sama mustahil tersimpan |
| `employee_attendances (employee_id, tanggal)` unique | Satu status harian per karyawan; dasar hitung payroll konsisten |
| `payrolls (periode, employee_id)` unique | Satu payroll per karyawan per periode — anti slip ganda |
| `uniq_linked_tx` partial unique `(ref_type, ref_id)` utk payroll/expense | Satu transaksi kas per payroll/expense — klik "bayar" dua kali tidak menggandakan kas |
| `uniq_payment_idem` partial unique `idem_key` | Retry pembayaran dengan kunci sama kembali ke record existing (+ self-heal transaksi hilang) |
| `uniq_collection_idem`, `uniq_candidate_idem`, `uniq_wa_idem` | Aksi penagihan/follow-up/pesan WA idempoten |
| `uniq_notif_dedupe` (`dedupe_key`) | Notifikasi turunan tidak duplikat meski sync berjalan berulang |
| `uniq_departure_student` (`departure_profiles.student_id`) | Satu profil keberangkatan per siswa |
| `whatsapp_templates.key` unique; `whatsapp_events.provider_event_id` unique | Template tunggal per key; event provider tidak diproses dua kali |
| Index non-unik (`students.status`, `transactions.tanggal`, `attendance.tanggal`, `leaves.status`, dsb.) | Filter periode/status pada dashboard & laporan tetap cepat |

**Mekanisme integritas lain:** snapshot payroll (`snapshot` + `komponen` + `provenance` dibekukan per periode — perubahan master tidak merambat ke slip lama); transaksi terhubung (`ref_type/ref_id` payment/payroll/expense); nomor berurut via `counters` (`SLIP-YYYYMM-xxxx`, `EXP-...`, kwitansi); histori status (`status_history` siswa, `history` expense); overlap cuti ditolak 409; lifespan: transaksi payroll/expense dibuat hanya dari status yang sah (`disetujui`).

---

## 6. Authentication & Authorization

**Cara login (staff):** `POST /api/auth/login` (`routers/auth.py:33`) — rate-limit 5x salah/IP+email lalu kunci 15 menit (429), verifikasi bcrypt, tolak akun nonaktif (403), terbitkan access JWT 12 jam + refresh 7 hari, set cookie `HttpOnly; Secure; SameSite=None`, catat `last_login`. Frontend menyimpan token di `localStorage (lpk_token)` dan mengirim `Authorization: Bearer`; backend juga menerima cookie (`get_current_user`, `core.py:123-131`).

**Portal siswa:** login terpisah `POST /api/student/auth/login` (hanya role `student`, rate-limit sama), `get_current_student` mengambil `student_id` dari JWT — **tidak pernah dari parameter frontend**; `must_change_password=true` memaksa ganti password awal (403 sampai diganti); ada varian lenient untuk `/me`.

| Security Mechanism | Implementasi | Masalah yang Diselesaikan |
|---|---|---|
| Hash password | bcrypt + `password_hash` (hash tak pernah dikembalikan: `public_user`) | Bocornya DB tidak membocorkan password |
| Token + expiry | JWT HS256, klaim `type: access/refresh`, cek user `aktif` tiap request | Sesi kedaluwarsa & akun nonaktif langsung ditolak |
| RBAC backend | `require_roles(*roles)` + **owner bypass** (`core.py:134-139`); matriks per router (mis. `PAYROLL_APPROVE=require_roles("owner")`, `EXP_APPROVE=require_roles("finance")`, `DEP_FINAL=require_roles("owner")`) | Peran tanpa hak (mis. siswa memanggil verify staf) mendapat 403 — terbukti diuji |
| `deny_student` | Penolak eksplisit role student di endpoint internal (`core.py:142-146`) | Portal siswa tak bisa menyentuh endpoint staf meski punya token valid |
| Student scoping | Semua endpoint `/student/*` memfilter `student_id == ctx.sid`; cross-student → 404 | Siswa A tak bisa baca/unduh dokumen/absensi/nilai siswa B |
| Guard frontend | `MODULES` + `can(mod)` (`AuthContext.jsx`), `Guard`/`PortalGuard` (`App.js`) | UI menyesuaikan peran; bukan pengganti otorisasi backend |
| Proteksi data gaji | `list_employees` menghapus `gaji_pokok/tunjangan/honor/nik` untuk role di luar owner/hr/admin/finance (`hr.py:58-60`); search pembayaran hanya untuk `FIN_VISIBLE` | Guru/staff tak mengintip data kompensasi |
| Provisioning deterministik | Konflik race akun siswa → 409 (bukan 400/500) via pre-check + `DuplicateKeyError` mapping (`auth.py:91-119`) | Double-submit pembuatan akun tidak menghasilkan error acak |
| Threshold approval | Expense ≥ Rp1.000.000 wajib Owner (`finance.py:545-546`) | Pengeluaran besar tak bisa lolos oleh finance saja |

**Frontend Guard vs Backend Authorization:** guard frontend (navigasi/tombol) adalah UX; keputusan keamanan ada di backend (`Depends(require_roles...)` di tiap handler). Keduanya ada dan konsisten (matriks `MODULES` frontend mencerminkan matriks router backend).

---

## 7. Document Storage & File Handling

Implementasi aktual: `backend/document_storage.py` + `core.save_upload()` + endpoint di `routers/students.py` & `routers/portal.py`.

- **Upload:** multipart (`jenis` + `file`) → ekstensi diekstrak aman → allowlist `{pdf, jpg, jpeg, png, webp}` (selain itu 400) → tolak file kosong → tolak > 10MB (400) → **content-type kanonis dari ekstensi** (tidak percaya header client) → id file UUID → key `dokumen|bukti/<scope>/<uuid>.<ext>`.
- **Atomic write:** tulis ke `<nama>.tmp` lalu `os.replace` (atomik satu filesystem); metadata `db.files` ditulis setelah binary sukses; bila metadata gagal, binary dihapus. Hasil: tidak ada metadata palsu untuk file yang tidak tersimpan (terverifikasi: upload gagal → jumlah dokumen tak berubah).
- **Metadata (`db.files` + `documents`):** `file_id` (= UUID), `storage_path` (key relatif — bukan path absolut), `original_filename`, `content_type`, `size`, `tanggal_upload`, `uploaded_by`, plus status verifikasi (`pending_verification/verified/rejected/tersedia/belum`) beserta `verified_by/at`, `verification_note`, `rejected_reason` (wajib saat reject).
- **Anti-traversal:** key relatif wajib; `..`/absolut ditolak; komponen direktori disanitasi; nama file harus `<uuid>.<ext>`; containment check `root in parents`.
- **Re-upload:** pola existing — record lama jenis sama di-soft-delete, record baru `pending_verification` (status verified tidak diwariskan), binary lama dibersihkan setelah sukses.
- **Preview/download:** `GET /api/files/{file_id}` (staf, token + `deny_student`) dan `GET /api/student/documents/{doc_id}/download` (siswa, own-scope) — keduanya `Content-Disposition: inline` + MIME kanonis, tanpa `/static` publik, tanpa expose path. Portal memakai Blob dengan MIME asli response sehingga PDF terbuka di viewer browser. Metadata tanpa binary → 404 jujur / label "File belum tersedia".
- **Konfigurasi:** `DOCUMENT_STORAGE_PATH` atau default `backend/storage/documents/` (dibuat saat startup; di-`.gitignore`, tidak ikut git; bukan `/tmp`/ephemeral).
- **Verifikasi tetap staf-side:** endpoint verify/reject hanya role staf (`WRITE`); siswa mendapat 403; alasan reject wajib dan terlihat oleh siswa untuk re-upload.

Masalah yang diselesaikan: file selamat dari restart; tak bergantung storage eksternal/credential; tak bisa diakses via URL publik; traversal mustahil; metadata–binary selalu konsisten; isolasi dokumen per siswa; review manusia tetap memegang keputusan.

---

## 8. Audit & Data Integrity

- **Audit trail** (`log_audit`, `core.py:150-155` → `audit_logs`): setiap aksi penting mencatat `entity`, `entity_id`, `action`, actor (`user_id/name/role`), `before`/`after`, `alasan`, `timestamp`. Terpakai di user, student, payment, transaction, expense, payroll, leave, document, interview, departure, WA. endpoint `GET /api/audit-logs` (role admin/finance/hr); dashboard menampilkan 8 aktivitas terbaru.
- **Idempotency + healing:** payment `idem_key` (duplikat → kembalikan existing + pulihkan transaksi hilang, flag `duplicate/healed`); expense/payroll pay idempoten via `uniq_linked_tx` (`already_paid`); collection/follow-up/WA `idem_key`; notifikasi `dedupe_key`; event WA `provider_event_id` unik.
- **Snapshot & provenance:** payroll membekukan `snapshot` (nama/tipe/jabatan/gaji/tunjangan/tarif/model) + `komponen` (base, tunjangan prorata hari aktif, honor = tarif × pertemuan aktual, potongan alfa, lembur/bonus ber-reason, potongan ber-`source_ref` allowlist) + `provenance` (actor + timestamp tiap komponen). Koreksi draft wajib `alasan` dan tercatat before/after penuh.
- **Status machine terkunci:** expense `draft→diajukan→disetujui→dibayar` (edit hanya draft + alasan; bayar hanya disetujui); leave `menunggu→disetujui/ditolak` (tolak wajib alasan; setuju menandai absensi `cuti`); payroll `draft→disetujui→dibayar` (approve owner-only; bayar finance-only; bersih ≤ 0 ditolak); departure `NOT_READY/READY/BLOCKED` murni derived ( Courtney `compute_readiness` tanpa tulis) + `final_decision` owner-only.
- **Alasan wajib (accountability):** update/hapus payment, koreksi payroll, tolak leave/expense/dokumen, rekonsiliasi berselisih — semua menuntut alasan yang masuk audit.

---

## 9. Testing & Quality Assurance

- **Framework:** pytest + pytest-xdist; `backend/pytest.ini` mematok `-n 2 --dist loadscope` (deterministik, anti-race antar worker). File suite: `backend/tests/test_lpk_mvp.py` — **tercatat 233 metode `def test_`** (dihitung statis dari source; bukan klaim hasil run).
- **Cakupan yang terlihat dari nama/struktur suite** (tidak menjalankan test baru untuk dokumen ini): auth & provisioning (termasuk race 409), RBAC per modul, students/seleksi/status-history, attendance, grades/exams, payments (idempotency, kwitansi, arrears), finance (rekonsiliasi, expense threshold), HR (attendance, leave overlap, payroll snapshot/provenance/konkurensi), documents (checklist 13, upload-download, verify/reject), portal (auth, isolasi cross-student, dokumen), collections, candidate follow-ups, departures (readiness, exception, final), job/matching/interview, WhatsApp (template, idempotency, consent, retry), notifications, search, reports.
- **Pola QA yang dipakai proyek:** BUILD (backend+frontend+tests) → QA discovery per area → corrective → re-verification; modul yang lolos dinyatakan STABLE/FROZEN (tidak boleh diubah tanpa alasan).
- **Frontend:** tidak ditemukan file test (`*.test.*` nihil di `src`); verifikasi berupa `npm run build` (`craco build`) yang wajib hijau — terkonfirmasi lolos pada fase-fase terakhir.
- **Test persistence & keamanan** yang dipraktikkan: restart backend lalu preview ulang; matriks 403/404 (tanpa token, lintas siswa, siswa ke endpoint staf).

---

## 10. System Architecture

### Level 1 — Business

```text
Calon Siswa → Pendaftaran → Seleksi → Pelatihan (kelas/absensi/nilai/ujian)
   → Pembayaran/Koleksi → Matching Job Order → Interview → Pemberkasan/Dokumen
   → Departure (checklist 6 syarat + readiness) → Berangkat/Alumni
        ║                         ║
   SDM (karyawan/guru, absensi, cuti, payroll)    Keuangan (kas, expense approval, rekonsiliasi)
        ║                         ║
   Notifikasi turunan ══ Audit trail ══ Student Portal (profil, akademik, keuangan, dokumen, keberangkatan)
```

### Level 2 — Application

```text
Browser: React SPA — shell Staff (17 rute) + shell Portal (7 rute)
   ↓ axios (Bearer/cookie, errMsg, fileUrl) → /api/*
FastAPI: 12 APIRouter domain; Depends(get_current_user / require_roles / get_current_student)
   ↓ domain logic di router + helper core.py (aggregasi, snapshot, readiness, notifikasi)
PostgreSQL (JSONB via `pg_mongo`; UUID string; index unik/parsial)
LocalDocumentStorage (binary) + db.files/documents (metadata)
Keluar: WhatsApp Cloud API via requests (E1, template+antrean)
```

### Level 3 — Security & Integrity

```text
Authentication (bcrypt, JWT 12j/7h, rate-limit, must-change-password)
 → Authorization (RBAC backend + guard frontend + deny_student + student scoping)
 → Validation (Pydantic, allowlist enum, overlap/range check)
 → Audit (actor, before/after, reason, timestamp)
 → Snapshot/Provenance (payroll, expense history, status_history)
 → Idempotency (idem_key, uniq index, dedupe_key, already_paid)
 → Storage protection (no public path, traversal guard, atomic write)
```

---

## 11. Feature Highlights

### 11.1 Payroll Snapshot & Workflow (HR → Owner → Finance)

**Masalah:** Gaji dihitung dari data master yang terus berubah; tanpa snapshot, slip bulan lalu ikut berubah. Persetujuan dan pembayaran tercampur sehingga kas bisa tercatat ganda.
**Solusi:** Hitung → draft (snapshot beku) → approve (owner-only) → pay (finance-only) → transaksi kas terhubung.
**Cara kerja:** `POST /payrolls/calculate` (mendukung `preview` tanpa tulis) menghitung prorata hari aktif kalender, potongan alfa, lembur/bonus ber-reason, potongan ber-`source_ref`; melewatkan karyawan yang sudah punya slip periode itu (skip, bukan 500). Koreksi draft wajib alasan dan mengaudit before/after penuh.
**Teknologi:** `routers/hr.py:345-763`, `pg_mongo`, `DuplicateKeyError`, `counters` (nomor slip), `log_audit`.
**Nilai operasional:** Slip historis konsisten; segregasi tugas (HR hitung, owner setujui, finance bayar); double-pay mustahil.
**Bukti:** `hr.py` (`_calc_one`, `_active_window`, `calculate_payrolls`, `approve_payroll`, `pay_payroll`).

### 11.2 Honor Guru B1 + Suggest Meetings

**Masalah:** Honor guru berbasis pertemuan mudah dikarang tanpa evidence kehadiran.
**Solusi:** Model honor wajib mengisi jumlah pertemuan aktual; sistem memberi *saran* eviden (distinct tanggal×kelas dari absensi siswa) yang eksplisit bertanda `unverified_presence` — saran, bukan keputusan.
**Cara kerja:** `GET /payrolls/suggest-meetings` read-only; kalkulasi menolak guru honor tanpa input pertemuan (400).
**Teknologi:** `hr.py:560-585`, koleksi `attendance` + `classes`.
**Nilai:** Honor berbasis klaim terverifikasi manusia + jejak provenance (`meetings.note/actor/at`).
**Bukti:** `hr.py:560-585`, `SOURCE_TYPES`, provenance payroll.

### 11.3 Payment Idempotency + Kwitansi

**Masalah:** Double-klik / retry jaringan menciptakan pembayaran & transaksi kas ganda.
**Solusi:** `idem_key` unik parsial + resolusi duplikat yang mengembalikan record existing dan *menyembuhkan* transaksi yang hilang.
**Cara kerja:** `POST /payments` → cek `idem_key` → insert dengan tangkapan `DuplicateKeyError` → transaksi `ref_type=payment` → kwitansi bernomor (`next_receipt_no`), `sisa_setelah` dihitung → event WA `payment_received` (best-effort, gagal kirim tak menggagalkan bayar).
**Teknologi:** `finance.py:238-300`, index `uniq_payment_idem`, `counters`.
**Nilai:** Bayar aman di jaringan buruk; kas selalu rekonsiliasi 1:1 dengan payment.
**Bukti:** `finance.py:238-300`.

### 11.4 RBAC & Backend Authorization

**Masalah:** Tombol disembunyikan di UI tetapi API tetap terbuka; peran mengintip data di luar haknya.
**Solusi:** Setiap handler mengikat `require_roles(...)`; owner bypass eksplisit; `deny_student` untuk endpoint internal; penyaringan field gaji; scoping guru ke kelasnya.
**Teknologi:** `core.py:134-146`, matriks per router, `AuthContext.MODULES` (cermin frontend).
**Nilai:** 403 terbukti untuk peran tak berhak; keamanan tak bergantung pada UI.
**Bukti:** `core.py`, `hr.py:53-63`, `dashboard.py:269-303`.

### 11.5 Absensi + Cuti Terintegrasi

**Masalah:** Cuti disetujui di kertas, absensi tetap alfa → potong gaji salah; pengajuan ganda bertabrakan.
**Solusi:** Pengajuan cuti cek overlap (409); persetujuan otomatis menandai rentang tanggal sebagai `cuti` di absensi; tolak wajib alasan.
**Teknologi:** `hr.py:278-342` (`_find_overlap`, `_mark_cuti_range`), index unik `(employee_id, tanggal)`.
**Nilai:** Satu sumber kebenaran kehadiran untuk payroll.
**Bukti:** `hr.py:299-342`.

### 11.6 Document Verification (Upload → Pending → Verified/Rejected)

**Masalah:** Dokumen syarat (KTP, ijazah, paspor, visa…) tercecer; status "ada" diklaim tanpa bukti; penolakan tanpa alasan.
**Solusi:** 13 jenis dokumen terkontrol (`DOC_TYPES`); upload selalu `pending_verification`; verifikasi/reject staf-side dengan aktor+timestamp; reject wajib alasan; re-upload mereset ke pending.
**Teknologi:** `students.py` (upload/verify/reject), `core.doc_progress` (lengkap = tersedia/verified), audit `document`.
**Nilai:** Checklist kelengkapan jujur; setiap keputusan tertelusur.
**Bukti:** `students.py:272-368`, `core.py:263-266`.

### 11.7 Local Document Storage

**Masalah:** Ketergantungan object-storage eksternal + credential; file di `/tmp`/browser hilang saat restart; URL publik berisiko.
**Solusi:** Abstraksi `DocumentStorage` + implementasi `LocalDocumentStorage`: binary di filesystem server persisten, metadata di PostgreSQL.
**Teknologi:** `document_storage.py` (allowlist ekstensi, MIME kanonis, 10MB, atomic tmp+rename, traversal guard), `core.save_upload()`, `.gitignore: backend/storage/`.
**Nilai:** Tanpa credential eksternal; selamat dari restart; siap diganti object-storage tanpa mengubah bisnis.
**Bukti:** `document_storage.py`, `core.py:194-231`, `server.py:109-113`.

### 11.8 Student Portal Document Workflow

**Masalah:** Siswa bolak-balik menanyakan status berkas; staf memverifikasi berkas yang salah milik.
**Solusi:** Siswa upload/preview/re-upload **miliknya sendiri** (sid dari JWT), melihat label status ramah + alasan penolakan; verifikasi tetap milik staf (403 terbukti).
**Teknologi:** `portal.py:227-312` (`GET /student/documents`, `POST /student/documents`, `GET .../download`), `PortalPages.jsx:PortalDocuments` (Blob+MIME asli, revoke terjadwal).
**Nilai:** Mandiri tanpa mengorbankan isolasi; preview PDF tampil di viewer browser.
**Bukti:** `portal.py:245-312`, `PortalPages.jsx:102-165`.

### 11.9 Collection & Candidate Follow-up (dengan WhatsApp E1)

**Masalah:** Tunggakan dan prospek ditagih manual tanpa jejak; pesan terkirim ganda; nomor tanpa consent ikut dikirimi.
**Solusi:** Aktivitas tercatat + snapshot sisa saat pencatatan; kirim WA via template bervariabel; `idem_key` + antrean + retry (maks 3) + consent check.
**Teknologi:** `collections.py`, `candidate_followups.py`, `whatsapp.py` (`queue_message`, `attempt_send`, `dispatch_event`, template `payment_due`/`payment_received`/`followup_calon`, webhook terverifikasi HMAC).
**Nilai:** Penagihan manusiawi terukur; tidak ada spam ganda; pemisahan prospek (`calon_siswa`) dari siswa aktif.
**Bukti:** `collections.py:1-110`, `whatsapp.py:165-191,227-319`.

### 11.10 Departure Readiness

**Masalah:** Keberangkatan diputuskan dari ingatan; syarat kedaluwarsa lolos; tunggakan tak terlihat.
**Solusi:** 6 syarat (paspor/COE/visa/medical/tiket/kontrak) + `compute_readiness` derived read-only: `BLOCKED` bila ada blocker (termasuk dokumen expired & keputusan final), `READY` hanya bila semua verified + keputusan READY, tunggakan sebagai warning. Final decision owner-only; exception tercatat.
**Teknologi:** `departures.py:27-36,138-187`, profil unik per siswa, audit keputusan.
**Nilai:** Keputusan berangkat berbasis bukti, bukan perasaan.
**Bukti:** `departures.py`.

### 11.11 Job Order → Matching → Interview (transisi status otomatis)

**Masalah:** Penempatan manual; kandidat tak memenuhi syarat lolos; status siswa lupa diperbarui.
**Solusi:** Skor matching (usia, jenis kelamin, JLPT) + rata-rata nilai, terurut; jadwal interview menggeser status ke `matching`; lulus interview menggeser ke `pemberkasan` + history — semua beraudit.
**Teknologi:** `jobs.py:70-126`, `JLPT_ORDER`, `grade_average`.
**Nilai:** Penempatan cepat, adil, tertelusur.
**Bukti:** `jobs.py:70-126`.

### 11.12 Expense Approval Bertingkat

**Masalah:** Pengeluaran besar disetujui sepihak; edit pasca-approve mengubah sejarah.
**Solusi:** Alur `draft→diajukan→disetujui→dibayar`; nominal ≥ Rp1.000.000 wajib Owner; edit hanya draft + alasan + histori; bayar idempoten.
**Teknologi:** `finance.py:397-603`, `EXPENSE_OWNER_THRESHOLD`, `history`, `uniq_linked_tx`.
**Nilai:** Kontrol kas berlapis tanpa birokrasi untuk nominal kecil.
**Bukti:** `finance.py:469-603`.

### 11.13 Dashboard, Notifikasi Turunan, Search, Laporan

**Masalah:** Pimpinan butuh potret harian; pengingat kedaluwarsa/tunggakan tercecer; data tersebar.
**Solusi:** Dashboard agregat (siswa, keuangan, operasional, pending approvals, aktivitas audit) dengan filter periode dan penyajian berbasis peran; notifikasi diturunkan dari event (dokumen expired, tunggakan, dsb.) dengan `dedupe_key`; search global (siswa/karyawan/job) dengan scoping peran; laporan + ekspor CSV/XLSX/PDF.
**Teknologi:** `dashboard.py` (agregasi, `_sync_notifications`, `_notif_scope`, export), `notifications` collection.
**Nilai:** Satu layar komando; pengingat otomatis tanpa spam ganda.
**Bukti:** `dashboard.py:172-311,312-593`.

### 11.14 Student Portal (layanan mandiri)

**Masalah:** Siswa bergantung pada staf untuk info jadwal, nilai, tagihan, dokumen, keberangkatan.
**Solusi:** Portal terpisah (`/portal/*`): profil, akademik (kelas/kehadiran/nilai/ujian), keuangan (tagihan & kwitansi), dokumen (11.8), notifikasi milik sendiri, keberangkatan read-only, pengaturan (ganti password wajib awal, consent WA).
**Teknologi:** `portal.py` (22 handler), `PortalLayout`, `PortalPages.jsx`, `PortalDashboard.jsx`.
**Nilai:** Beban staf turun; transparansi naik; isolasi data ketat.
**Bukti:** `portal.py`, `App.js:42-50`.

---

## 12. Feature → Problem Matrix

| Fitur | Masalah yang Diselesaikan | Mekanisme Teknis | Dampak |
|---|---|---|---|
| Payroll snapshot | Master berubah merusak slip lama | Snapshot + komponen + provenance beku per periode | Slip historis konsisten |
| Honor B1 aktual | Klaim pertemuan tanpa bukti | Input pertemuan wajib + saran evidence bertanda unverified | Honor terbukti & beraudit |
| Payment idempotency | Retry menciptakan bayar ganda | `idem_key` unik + heal transaksi | Kas 1:1 dengan payment |
| RBAC backend | UI disembunyikan tapi API terbuka | `require_roles` + `deny_student` per handler | 403 untuk peran tak berhak |
| Cuti↔absensi | Cuti kertas vs alfa sistem | Overlap 409 + tandai `cuti` otomatis | Payroll berbasis kehadiran benar |
| Doc verification | Status "ada" tanpa bukti | pending→verified/rejected + alasan wajib | Checklist jujur & tertelusur |
| Local storage | Dependensi eksternal; file hilang | Filesystem server + metadata; atomic write | Persisten tanpa credential |
| Portal documents | Tanya status berulang; salah milik | sid dari JWT; verify staf-side | Mandiri + terisolasi |
| Collection/follow-up WA | Tagih manual tanpa jejak; spam ganda | Aktivitas + template + idem + consent | Terukur, tanpa spam |
| Departure readiness | Berangkat dari ingatan | Derived READY/BLOCKED + expiry check | Keputusan berbasis bukti |
| Matching→interview | Kandidat tak layak lolos | Skor usia/JLPT + transisi status otomatis | Penempatan adil & tercatat |
| Expense threshold | Pengeluaran besar sepihak | ≥Rp1jt wajib Owner; histori edit | Kontrol kas berlapis |
| Notifikasi dedupe | Pengingat ganda | `dedupe_key` unik | Tanpa spam |
| Rekonsiliasi kas | Selisih kas tanpa penjelasan | Selisih wajib alasan + audit | Kas terekonsiliasi |

---

## 13. Library Catalog

### Core Framework

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| react / react-dom | 19.0.0 | Frontend | Komponen & render SPA | `src/` keseluruhan | Satu codebase dua shell (staff + siswa) |
| react-router-dom | 7.15.0 | Frontend | Routing + guard | `src/App.js` | Akses halaman sesuai peran |
| FastAPI | 0.110.1 | Backend | Routing, DI, error model | `server.py`, 12 router | API modular per domain |
| uvicorn | 0.25.0 | Runtime | ASGI server | Runtime `server:app` | Menjalankan backend async |
| @craco/craco + react-scripts | 7.1.0 / 5.0.1 | Build | Alias `@`, dev server, build | `craco.config.js`, scripts | Build konsisten tanpa eject |

### Database

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| asyncpg | ≥ 0.29 | Database | Driver PostgreSQL async (dipakai `pg_mongo`) | `pg_mongo.py`, `core.py` | I/O non-blocking untuk API konkurensi |

### Authentication/Security

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| PyJWT | ≥2.10.1 | Auth | JWT HS256 access/refresh | `core.py:91-120` | Sesi stateless + expiry |
| bcrypt | 4.1.3 | Auth | Hash/verifikasi password | `core.py`, `auth.py`, `portal.py` | Password tak tersimpan plain-text |
| email-validator | ≥2.2.0 | Validasi | `EmailStr` | `auth.py`, `portal.py` | Menolak email malformed |

### API/HTTP/Validation

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| axios | 1.18.0 | HTTP client | Instance API + interceptor | `lib/api.js` | Satu titik auth/error handling |
| pydantic | ≥2.6.4 | Validasi | Model `*In` | Semua router | Input tervalidasi sebelum logika |
| python-multipart | ≥0.0.9 | Upload | `UploadFile`/`Form` | `students.py`, `portal.py` | Upload file terstandar |
| requests | ≥2.31.0 | HTTP keluar | Provider WA | `whatsapp.py` | Tanpa SDK vendor |
| python-dotenv | ≥1.0.1 | Konfigurasi | Load `.env` | `server.py` | Konfigurasi per lingkungan |

### File/Document/Export

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| (custom) LocalDocumentStorage | — | Storage | Binary di filesystem server | `document_storage.py` | Persisten tanpa credential eksternal |
| openpyxl | ≥3.1.0 | Export | XLSX laporan | `dashboard.py:499` | Laporan spreadsheet langsung dari sistem |
| reportlab | ≥4.0.0 | Export | PDF laporan berkop | `dashboard.py:533` | Laporan cetak resmi |

### Frontend UI/Utilities

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| tailwindcss / animate | 3.4.17 / 1.0.7 | Styling | Utility + token desain | `tailwind.config.js`, seluruh UI | Konsistensi visual cepat |
| lucide-react | 0.516.0 | Ikon | Ikon vektor | ±30 file | Tanpa aset gambar |
| sonner | 2.0.3 | Feedback | Toast | Halaman + `ui/sonner.jsx` | Feedback non-blocking |
| @radix-ui/react-dialog, popover | 1.1.11 | Primitif UI | Dialog, popover, toaster | `common.jsx`, `ReceiptDialog`, `Header` | Aksesibilitas bawaan |
| recharts | 3.6.0 | Chart | Grafik dashboard | `DashboardPage.jsx` | Visualisasi tanpa beban global |
| react-hook-form | 7.56.2 | Form | **Hanya** file generated `ui/form.jsx` (tidak diimpor halaman) | `components/ui/form.jsx` | Tersedia; alur aplikasi memakai form manual + validasi backend |

### Testing

| Library | Version | Category | Function | Where Used | Why It Matters |
|---|---|---|---|---|---|
| pytest | ≥8.0.0 | Testing | Suite API (233 metode tercatat) | `backend/tests/test_lpk_mvp.py` | Regresi & kontrak API terjaga |
| pytest-xdist | ≥3.6.0 | Testing | Paralel 2 worker `loadscope` | `backend/pytest.ini` | Suite cepat tanpa race antar worker |

**Tidak dimasukkan sebagai library aktif** (tidak ditemukan import di kode aplikasi): `boto3`, `requests-oauthlib`, `passlib`, `python-jose`, `cryptography`, `tzdata`, `pandas`, `numpy`, `jq`, `typer`, tooling `black/isort/flake8/mypy`, serta `@tanstack/react-query`, `swr`, `zod` (+resolvers), `framer-motion`, `dayjs`, `date-fns`, dan mayoritas paket `@radix-ui/*`, `cmdk`, `embla`, `vaul`, `next-themes`, `input-otp`, `react-day-picker`, `react-resizable-panels` (hanya hidup di file `ui/` generated yang tidak dipakai halaman).

---

## 14. Custom Engineering vs Third-Party Libraries

**Disediakan pihak ketiga:** web framework & validasi (FastAPI/Pydantic), driver DB (asyncpg), HTTP client (axios/requests), auth primitif (JWT/bcrypt), UI primitif (Tailwind/Radix/lucide/sonner/recharts), testing & build (pytest/CRACO).

**Direkayasa sendiri (nilai inti proyek):**

| Custom Engineering | Bukti | Mengapa bukan sekadar gabungan library |
|---|---|---|
| Kalkulasi + snapshot + provenance payroll (prorata, honor B1, alfa, reason/source_ref) | `hr.py:345-763` | Aturan bisnis penggajian LPK yang utuh |
| Abstraksi `DocumentStorage` + implementasi lokal (atomic, traversal guard, MIME kanonis) | `document_storage.py`, `core.save_upload` | Storage aman tanpa vendor |
| Workflow verifikasi dokumen + portal siswa terisolasi | `students.py`, `portal.py`, `PortalPages.jsx` | Keputusan manusia + isolasi JWT |
| Idempotency & healing pembayaran/transaksi | `finance.py:238-300`, index unik | Anti-ganda + pulih dari kegagalan parsial |
| Readiness keberangkatan derived + keputusan owner-only | `departures.py:138-187` | Keputusan berbasis bukti |
| Matching kandidat + transisi status otomatis beraudit | `jobs.py:70-126` | Rekrutmen adil & tercatat |
| Approval expense bertingkat + histori | `finance.py:397-603` | Kontrol kas proporsional |
| Cuti↔absensi terhubung + overlap guard | `hr.py:278-342` | Satu kebenaran kehadiran |
| Collection/follow-up + dispatcher WA E1 (template, idem, consent, retry) | `collections.py`, `candidate_followups.py`, `whatsapp.py` | Penagihan & prospek terukur |
| Audit trail universal + notifikasi dedupe + search ter-scoping | `core.log_audit`, `dashboard.py` | Akuntabilitas ujung-ke-ujung |

---

## 15. Technical Highlights

1. **Snapshot payroll** — slip dibekukan per periode (`hr.py:522-532`); mencegah master yang berubah merusak histori; bukti: field `snapshot` + status `draft→disetujui→dibayar`.
2. **Idempotency berlapis** — `idem_key` + unique index parsial + handler `DuplicateKeyError` di payment/payroll/expense/WA/collection/follow-up; mencegah double-submit & race.
3. **RBAC ganda** — backend `require_roles` + frontend `MODULES`; `deny_student` menutup celah token siswa ke endpoint staf.
4. **Isolasi data siswa** — `student_id` dari JWT di semua `/student/*`; cross-access 404; gaji disaring per peran.
5. **Atomic file write** — `tmp + os.replace`; metadata menyusul; gagal di tengah = tanpa sisa (`core.py:215-230`).
6. **Storage abstraction** — `DocumentStorage` ABC; ganti ke object storage kelak tanpa menyentuh bisnis.
7. **Derived readiness** — `compute_readiness` tanpa tulis; satu source of truth; expiry dokumen ikut dihitung.
8. **Audit before/after + reason wajib** — semua mutasi sensitif menuntut alasan yang tersimpan.
9. **Suggest-meetings jujur** — evidence bertanda `unverified_presence`; sistem menyarankan, manusia memutuskan.
10. **Ekspor mandiri** — XLSX (openpyxl) + PDF berkop (reportlab) langsung dari backend laporan.

---

## 16. Penjelasan Sederhana untuk Stakeholder

- **Login berlapis + peran** dipakai agar HR mengurus gaji, finance memegang kas, guru hanya melihat kelasnya, dan siswa hanya melihat datanya sendiri — bukan karena tidak percaya, tetapi agar kesalahan dan penyalahgunaan tertutup secara sistem.
- **Snapshot payroll** dipakai agar slip gaji bulan lalu tidak berubah walau data karyawan diperbarui bulan ini — seperti fotokopi arsip yang tidak ikut berubah.
- **Idempotency pembayaran** dipakai agar klik dua kali atau internet putus tidak menagih siswa dua kali dan tidak menggandakan kas.
- **Verifikasi dokumen staf-side** dipakai agar yang menentukan sah/tidaknya berkas adalah petugas berwenang, bukan pengunggah — siswa cukup upload dan memantau status.
- **Local document storage** dipakai agar file tersimpan di server milik LPK, tetap ada setelah restart, dan hanya bisa dibuka oleh yang berhak — bukan lewat link publik.
- **Readiness keberangkatan** dipakai agar keputusan memberangkatkan diambil dari daftar syarat yang terverifikasi (termasuk masa berlaku dokumen), bukan dari ingatan.
- **Audit trail** dipakai agar setiap perubahan penting tercatat siapa, kapan, dari apa menjadi apa, dan mengapa — siap diaudit kapan pun.
- **WhatsApp terjadwal + consent** dipakai agar tagihan dan kabar pembayaran terkirim otomatis namun tetap sopan (ada izin, tanpa spam ganda).
- **Portal siswa** dipakai agar siswa mengecek sendiri jadwal, nilai, tagihan, dan dokumen — staf fokus pada verifikasi, bukan menjawab pertanyaan berulang.

---

## 17. Limitations & Trade-offs

- **Local vs object storage:** dipilih filesystem server (persisten, tanpa credential). Trade-off: backup database dan backup direktori `backend/storage/` adalah dua pekerjaan berbeda — keduanya harus dijadwalkan; replikasi multi-server butuh storage bersama (abstraksi `DocumentStorage` disiapkan untuk migrasi ini).
- **Tanpa migrasi skema formal:** evolusi skema dijaga oleh kode + index idempoten startup. Trade-off: perubahan field butuh kehati-hatian backward-compat (pola yang dipakai: field opsional + default).
- **Relasi di kode, bukan JOIN DB:** referensi via UUID string + agregasi di Python. Trade-off: fleksibel skema, tetapi query lintas entity berat ditangani manual (limit `to_list` hingga 5000-10000).
- **WhatsApp best-effort:** kegagalan kirim dicatat di antrean + retry, tidak menggagalkan transaksi bisnis. Trade-off: status pesan eventual-consistent; pengiriman riil bergantung konfigurasi env (`WA_ENABLED`, token, provider).
- **Preview browser-native:** PDF/gambar mengandalkan viewer browser via MIME kanonis. Trade-off: pengalaman mengikuti kemampuan browser, bukan viewer kustom.
- **Lingkungan operasi:** repository tidak menyertakan Dockerfile/CI; asumsi runtime adalah server lokal (uvicorn + build statis frontend). Trade-off: deployment direproduksi manual per server.

---

## 18. Repository Evidence / Reference Files

**Backend:** `backend/server.py` (app, 12 router, index, seed) · `backend/core.py` (auth, RBAC, audit, upload, agregasi) · `backend/document_storage.py` (storage) · `backend/routers/{auth,students,academics,finance,hr,jobs,dashboard,whatsapp,portal,collections,candidate_followups,departures}.py` (±161 handler) · `backend/seed.py` + `seed_*.py` (data awal/demo) · `backend/tests/test_lpk_mvp.py` (233 metode test tercatat) · `backend/pytest.ini` · `backend/requirements.txt` · `backend/.env` (**tidak didokumentasikan isinya**).

**Frontend:** `frontend/package.json` · `frontend/craco.config.js` · `frontend/tailwind.config.js` · `frontend/src/App.js` (rute + guard) · `frontend/src/lib/{api,format}.js` · `frontend/src/hooks/useApi.js` · `frontend/src/context/AuthContext.jsx` (matriks peran) · `frontend/src/pages/*` (17 rute staff) · `frontend/src/pages/portal/*` + `components/portal/*` (portal siswa) · `frontend/src/components/{common,PaymentDialog,ReceiptDialog,StudentForm,PayrollTab,LeaveTab,HrAttendanceTab,CollectionDialogs,CandidateDialogs,DepartureDialogs,layout/*,student/*,ui/*}.jsx`.

**Repo-level:** `.gitignore` (mengabaikan `.env`, `backend/storage/`, build artifacts) · `README.md` (placeholder — bukan sumber).
