"""Synchronous, pymongo-style facade over pg_mongo for scripts and tests (``MongoClient(...)["lpk"].users.find_one``)."""
import asyncio
import inspect
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

from pg_mongo import AggregateCursor, Cursor, DuplicateKeyError, PgClient  # noqa: F401

load_dotenv(Path(__file__).parent / ".env")

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True, name="pg_mongo_sync").start()


def _run(coro):
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()


class SyncCursor:
    def __init__(self, cursor):
        self._c = cursor

    def sort(self, *a, **k):
        self._c.sort(*a, **k)
        return self

    def skip(self, n):
        self._c.skip(n)
        return self

    def limit(self, n):
        self._c.limit(n)
        return self

    def to_list(self, length=None):
        return _run(self._c.to_list(length))

    def __iter__(self):
        return iter(self.to_list())


class SyncCollection:
    def __init__(self, coll):
        self._c = coll

    def __getattr__(self, name):
        attr = getattr(self._c, name)
        if not callable(attr):
            return attr

        def call(*a, **k):
            res = attr(*a, **k)
            if inspect.isawaitable(res):
                return _run(res)
            if isinstance(res, (Cursor, AggregateCursor)):
                return SyncCursor(res)
            return res
        return call


class SyncDatabase:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return SyncCollection(self._db[name])

    def __getitem__(self, name):
        return SyncCollection(self._db[name])

    def list_collection_names(self):
        return _run(self._db.list_collection_names())


class MongoClient:
    """Accepts (and ignores) a Mongo URI for drop-in compatibility; connects via DATABASE_URL."""

    def __init__(self, *_args, **_kwargs):
        self._client = PgClient(os.environ["DATABASE_URL"], max_size=5)

    def __getitem__(self, name):
        return SyncDatabase(self._client[name])

    def close(self):
        _run(self._client.aclose())
