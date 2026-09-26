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
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # isi DATABASE_URL & JWT_SECRET
.venv/bin/uvicorn server:app --port 8001 --reload
```

Saat startup, tabel + index dibuat otomatis dan data demo di-seed (matikan dengan `LPK_DISABLE_STARTUP_DEMO_SEED=1`).
Login owner default: `owner@lpk.id` / `owner123` (dari `ADMIN_EMAIL` / `ADMIN_PASSWORD`).

## Setup frontend

```bash
cd frontend
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
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

Test HTTP menembak backend yang sedang jalan di `REACT_APP_BACKEND_URL` (default `http://localhost:8001`):

```bash
cd backend && .venv/bin/pytest tests
```

Test `TestWA` mengharapkan backend dengan `WA_ENABLED=true WA_DRY_RUN=true WA_APP_SECRET=test-secret-123 WA_VERIFY_TOKEN=test-verify`;
test lain mengharapkan WA nonaktif.
