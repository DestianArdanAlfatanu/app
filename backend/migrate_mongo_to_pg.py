"""One-off copy of an existing MongoDB database into PostgreSQL.

Usage (needs `pip install pymongo` temporarily):
    MONGO_URL=mongodb://host:27017 MONGO_DB=lpk python migrate_mongo_to_pg.py

Start the API once first so unique indexes exist; rows are copied verbatim (ObjectId _id values become strings).
"""
import asyncio
import os
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from pg_mongo import PgClient

load_dotenv(Path(__file__).parent / ".env")


def _plain(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


async def main():
    src = MongoClient(os.environ["MONGO_URL"])[os.environ.get("MONGO_DB", "lpk")]
    pg = PgClient(os.environ["DATABASE_URL"])
    dst = pg[os.environ.get("DB_NAME", "lpk")]
    for name in sorted(src.list_collection_names()):
        docs = []
        for d in src[name].find({}):
            d = _plain(d)
            if name != "counters":
                d.pop("_id", None)
            docs.append(d)
        await dst[name].delete_many({})
        if docs:
            await dst[name].insert_many(docs)
        print(f"{name}: {len(docs)}")
    await pg.aclose()


if __name__ == "__main__":
    asyncio.run(main())
