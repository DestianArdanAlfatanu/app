# Sistem LPK Jepang

FastAPI backend (`backend/`) + React frontend (`frontend/`). Database: PostgreSQL.

## Prasyarat

- Python 3.11
- Node 20 + Yarn 1.x
- PostgreSQL 15+ (unique index memakai `NULLS NOT DISTINCT`)

## Setup backend

```bash
createdb lpk
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # production cukup requirements.txt
cp .env.example .env   # isi DATABASE_URL, JWT_SECRET (openssl rand -hex 32), ADMIN_PASSWORD
.venv/bin/uvicorn server:app --port 8001 --reload
```

Saat startup, tabel + index dibuat otomatis dan akun owner pertama dibuat dari `ADMIN_EMAIL` / `ADMIN_PASSWORD`
(sekali saja; password yang sudah diganti owner tidak ditimpa saat restart). Server menolak start bila `JWT_SECRET`
kurang dari 32 karakter atau `CORS_ORIGINS` berisi `*`.

**Mode demo (dev saja):** tambahkan `LPK_DEMO=1` di `backend/.env` dan `REACT_APP_DEMO=1` di `frontend/.env` untuk
seed data demo (akun `*@lpk.id` / `password123`), tombol akun demo di halaman login, dan dokumentasi API di `/docs`.
Jangan aktifkan di production.

## Setup frontend

```bash
cd frontend
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env   # tambah REACT_APP_DEMO=1 untuk dev
yarn install
yarn start   # http://localhost:3000
```

## Database

`backend/pg_mongo.py` menyimpan tiap koleksi sebagai tabel PostgreSQL `(_pk, _seq, doc jsonb)` dan menyediakan
API bergaya Motor (`find`, `update_one`, `aggregate`, unique index → `DuplicateKeyError`), jadi router tidak perlu
SQL manual. Unique index dibuat sebagai unique expression index PostgreSQL; query di-prefilter via index GIN `jsonb_path_ops`.

Pindah data dari MongoDB lama: `pip install pymongo` lalu
`MONGO_URL=mongodb://... MONGO_DB=lpk .venv/bin/python migrate_mongo_to_pg.py`.

## Tests

Test HTTP menembak backend yang sedang jalan di `REACT_APP_BACKEND_URL` (default `http://localhost:8001`)
dengan data demo (`LPK_DEMO=1`, `ADMIN_PASSWORD=owner123`):

```bash
cd backend && .venv/bin/pytest tests
```

Test `TestWA` mengharapkan backend dengan `WA_ENABLED=true WA_DRY_RUN=true WA_APP_SECRET=test-secret-123 WA_VERIFY_TOKEN=test-verify`;
test lain mengharapkan WA nonaktif.

## Catatan keamanan production

- Jalankan di balik HTTPS; API memakai token `Authorization: Bearer` (tanpa cookie), token berlaku 12 jam dan
  dicabut saat logout, ganti/reset password, perubahan role, atau akun dinonaktifkan.
- File unggahan hanya PDF/JPG/PNG/WEBP; disimpan di `backend/storage/` (atau `DOCUMENT_STORAGE_PATH`) — backup folder ini.
- Jangan set `LPK_DEMO` / `REACT_APP_DEMO` di production.
