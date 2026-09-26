"""PostgreSQL-backed document store exposing the subset of the Motor (MongoDB) API used by this app.

Each collection is a table ``(_pk text primary key, _seq bigserial, doc jsonb)``. Queries are pushed
down to SQL where cheap (JSONB containment / range prefilter, backed by a GIN index) and then evaluated
exactly with a Python implementation of Mongo query semantics, so behaviour matches Mongo for every
operator the routers use. Unique indexes become PostgreSQL unique expression indexes and violations
raise ``DuplicateKeyError`` like pymongo does.
"""
import asyncio
import datetime
import decimal
import json
import re
import uuid
import zlib
from copy import deepcopy
from typing import Dict, List, Optional

import asyncpg


class DuplicateKeyError(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}


class OperationFailure(Exception):
    pass


# ---------- JSON ----------
def _json_default(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    if isinstance(o, uuid.UUID):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _dumps(v) -> str:
    return json.dumps(v, default=_json_default)


# ---------- Query matching (Mongo semantics) ----------
_MISSING = object()


def _path_values(doc, path: str) -> list:
    parts = path.split(".")

    def walk(cur, i):
        if i == len(parts):
            return [cur]
        p = parts[i]
        if isinstance(cur, dict):
            return walk(cur[p], i + 1) if p in cur else [_MISSING]
        if isinstance(cur, list):
            if p.isdigit():
                idx = int(p)
                return walk(cur[idx], i + 1) if idx < len(cur) else [_MISSING]
            out = []
            for el in cur:
                if isinstance(el, (dict, list)):
                    out.extend(v for v in walk(el, i) if v is not _MISSING)
            return out or [_MISSING]
        return [_MISSING]

    return walk(doc, 0)


def _get(doc, path: str):
    cur = doc
    for p in path.split("."):
        if isinstance(cur, dict):
            if p not in cur:
                return _MISSING
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            return _MISSING
    return cur


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _eq(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_num(a) and _is_num(b):
        return a == b
    if type(a) is not type(b):
        return False
    return a == b


def _candidates(values):
    for v in values:
        yield v
        if isinstance(v, list):
            yield from v


def _match_eq(values, target) -> bool:
    if target is None:
        return any(v is _MISSING or v is None for v in _candidates(values))
    return any(v is not _MISSING and _eq(v, target) for v in _candidates(values))


def _type_rank(v) -> int:
    if v is _MISSING or v is None:
        return 1
    if _is_num(v):
        return 2
    if isinstance(v, str):
        return 3
    if isinstance(v, dict):
        return 4
    if isinstance(v, list):
        return 5
    if isinstance(v, bool):
        return 8
    return 9


def _cmp_ok(v, target, op) -> bool:
    if v is _MISSING or _type_rank(v) != _type_rank(target) or isinstance(v, (dict, list)):
        return False
    if v is None:
        return op in ("$gte", "$lte")
    if op == "$gt":
        return v > target
    if op == "$gte":
        return v >= target
    if op == "$lt":
        return v < target
    return v <= target


def _regex_flags(options: str) -> int:
    flags = 0
    for ch in options or "":
        flags |= {"i": re.I, "m": re.M, "s": re.S, "x": re.X}.get(ch, 0)
    return flags


def _is_operator_dict(v) -> bool:
    return isinstance(v, dict) and bool(v) and all(isinstance(k, str) and k.startswith("$") for k in v)


def _match_field(values, cond) -> bool:
    if not _is_operator_dict(cond):
        if isinstance(cond, re.Pattern):
            return any(isinstance(v, str) and cond.search(v) for v in _candidates(values))
        return _match_eq(values, cond)
    for op, arg in cond.items():
        if op == "$eq":
            ok = _match_eq(values, arg)
        elif op == "$ne":
            ok = not _match_eq(values, arg)
        elif op == "$in":
            ok = any(_match_eq(values, a) for a in arg)
        elif op == "$nin":
            ok = not any(_match_eq(values, a) for a in arg)
        elif op in ("$gt", "$gte", "$lt", "$lte"):
            ok = any(_cmp_ok(v, arg, op) for v in _candidates(values))
        elif op == "$exists":
            present = any(v is not _MISSING for v in values)
            ok = present if arg else not present
        elif op == "$regex":
            pattern = arg if isinstance(arg, re.Pattern) else re.compile(arg, _regex_flags(cond.get("$options", "")))
            ok = any(isinstance(v, str) and pattern.search(v) for v in _candidates(values))
        elif op == "$options":
            continue
        elif op == "$not":
            ok = not _match_field(values, arg)
        elif op == "$size":
            ok = any(isinstance(v, list) and len(v) == arg for v in values)
        elif op == "$all":
            ok = all(_match_eq(values, a) for a in arg)
        elif op == "$elemMatch":
            ok = any(isinstance(v, list) and any(
                (_matches(el, arg) if isinstance(el, dict) and not _is_operator_dict(arg) else _match_field([el], arg))
                for el in v) for v in values)
        else:
            raise OperationFailure(f"Unsupported query operator {op}")
        if not ok:
            return False
    return True


def _matches(doc: dict, flt: Optional[dict]) -> bool:
    if not flt:
        return True
    for key, cond in flt.items():
        if key == "$and":
            if not all(_matches(doc, c) for c in cond):
                return False
        elif key == "$or":
            if not any(_matches(doc, c) for c in cond):
                return False
        elif key == "$nor":
            if any(_matches(doc, c) for c in cond):
                return False
        elif key.startswith("$"):
            raise OperationFailure(f"Unsupported top-level operator {key}")
        elif not _match_field(_path_values(doc, key), cond):
            return False
    return True


# ---------- SQL prefilter (superset of the real match; Python makes the final decision) ----------
def _pushable_scalar(v) -> bool:
    return isinstance(v, (str, bool, int, float)) and v is not None


def _prefilter(flt: Optional[dict], params: list) -> List[str]:
    clauses: List[str] = []
    if not flt:
        return clauses

    def contain(key, v):
        params.append({key: v})
        a = len(params)
        params.append({key: [v]})
        return f"(doc @> ${a} OR doc @> ${a + 1})"

    for key, cond in flt.items():
        if key == "$and":
            for c in cond:
                clauses.extend(_prefilter(c, params))
            continue
        if key.startswith("$") or "." in key:
            continue
        if _pushable_scalar(cond):
            clauses.append(contain(key, cond))
        elif _is_operator_dict(cond):
            if "$eq" in cond and _pushable_scalar(cond["$eq"]):
                clauses.append(contain(key, cond["$eq"]))
            if "$in" in cond and cond["$in"] and all(_pushable_scalar(x) for x in cond["$in"]):
                clauses.append("(" + " OR ".join(contain(key, x) for x in cond["$in"]) + ")")
            elif "$in" in cond and not cond["$in"]:
                clauses.append("FALSE")
            for op, sql_op in (("$gt", ">"), ("$gte", ">="), ("$lt", "<"), ("$lte", "<=")):
                if op in cond and isinstance(cond[op], str):
                    params.append(key)
                    params.append(cond[op])
                    k, v = len(params) - 1, len(params)
                    clauses.append(f"(jsonb_typeof(doc->${k}) IS DISTINCT FROM 'string' "
                                   f"OR (doc->>${k}) COLLATE \"C\" {sql_op} ${v}::text COLLATE \"C\")")
            if cond.get("$exists") is True:
                params.append(key)
                clauses.append(f"(doc ? ${len(params)})")
    return clauses


# ---------- Updates ----------
def _set_path(doc, path: str, value):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(p)]
        else:
            if not isinstance(cur.get(p), (dict, list)):
                cur[p] = {}
            cur = cur[p]
    last = parts[-1]
    if isinstance(cur, list):
        idx = int(last)
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = value
    else:
        cur[last] = value


def _unset_path(doc, path: str):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _each(arg):
    if isinstance(arg, dict) and "$each" in arg:
        return list(arg["$each"])
    return [arg]


def _apply_update(doc: dict, update: dict, inserting: bool = False) -> dict:
    if not any(k.startswith("$") for k in update):
        new = deepcopy(update)
        if "_id" in doc:
            new["_id"] = doc["_id"]
        return new
    doc = deepcopy(doc)
    for op, fields in update.items():
        for path, arg in fields.items():
            if op == "$set":
                _set_path(doc, path, deepcopy(arg))
            elif op == "$setOnInsert":
                if inserting:
                    _set_path(doc, path, deepcopy(arg))
            elif op == "$unset":
                _unset_path(doc, path)
            elif op == "$inc":
                cur = _get(doc, path)
                _set_path(doc, path, (0 if cur is _MISSING or cur is None else cur) + arg)
            elif op in ("$max", "$min"):
                cur = _get(doc, path)
                if cur is _MISSING or (arg > cur if op == "$max" else arg < cur):
                    _set_path(doc, path, arg)
            elif op in ("$push", "$addToSet"):
                cur = _get(doc, path)
                lst = [] if cur is _MISSING or cur is None else list(cur)
                for item in _each(arg):
                    if op == "$push" or not any(_eq(x, item) for x in lst):
                        lst.append(deepcopy(item))
                _set_path(doc, path, lst)
            elif op == "$pull":
                cur = _get(doc, path)
                if isinstance(cur, list):
                    if _is_operator_dict(arg):
                        keep = [x for x in cur if not _match_field([x], arg)]
                    elif isinstance(arg, dict):
                        keep = [x for x in cur if not (isinstance(x, dict) and _matches(x, arg))]
                    else:
                        keep = [x for x in cur if not _eq(x, arg)]
                    _set_path(doc, path, keep)
            elif op == "$pullAll":
                cur = _get(doc, path)
                if isinstance(cur, list):
                    _set_path(doc, path, [x for x in cur if not any(_eq(x, a) for a in arg)])
            else:
                raise OperationFailure(f"Unsupported update operator {op}")
    return doc


def _upsert_seed(flt: Optional[dict]) -> dict:
    doc: dict = {}
    for k, v in (flt or {}).items():
        if k == "$and":
            for c in v:
                doc.update(_upsert_seed(c))
        elif not k.startswith("$"):
            if _is_operator_dict(v):
                if "$eq" in v:
                    _set_path(doc, k, deepcopy(v["$eq"]))
            else:
                _set_path(doc, k, deepcopy(v))
    return doc


# ---------- Projection / sort ----------
def _project(doc: dict, projection) -> dict:
    if not projection:
        return doc
    if isinstance(projection, (list, tuple)):
        projection = {k: 1 for k in projection}
    include_id = bool(projection.get("_id", 1))
    fields = {k: v for k, v in projection.items() if k != "_id"}
    inclusive = any(bool(v) for v in fields.values())
    if inclusive:
        out: dict = {}
        for k, v in fields.items():
            if not v:
                continue
            val = _get(doc, k)
            if val is not _MISSING:
                _set_path(out, k, val)
        if include_id and "_id" in doc:
            out["_id"] = doc["_id"]
        return out
    out = deepcopy(doc)
    for k in fields:
        _unset_path(out, k)
    if not include_id:
        out.pop("_id", None)
    return out


def _sort_key(v):
    rank = _type_rank(v)
    if rank in (2, 3, 8):
        return (rank, v)
    if rank in (4, 5):
        return (rank, _dumps(v))
    return (rank, 0)


def _normalize_sort(key_or_list, direction=None):
    if isinstance(key_or_list, str):
        return [(key_or_list, direction if direction is not None else 1)]
    if isinstance(key_or_list, dict):
        return list(key_or_list.items())
    return [(k, d) for k, d in key_or_list]


def _sort_docs(docs: list, spec) -> list:
    for key, direction in reversed(spec):
        docs.sort(key=lambda d: _sort_key(_get(d, key)), reverse=(direction == -1 or direction == "desc"))
    return docs


# ---------- Aggregation ----------
def _eval_expr(doc, expr):
    if isinstance(expr, str) and expr.startswith("$"):
        v = _get(doc, expr[1:])
        return None if v is _MISSING else v
    if isinstance(expr, dict):
        if len(expr) == 1 and next(iter(expr)).startswith("$"):
            op, arg = next(iter(expr.items()))
            args = [_eval_expr(doc, a) for a in (arg if isinstance(arg, list) else [arg])]
            if op in ("$substr", "$substrBytes", "$substrCP"):
                s = "" if args[0] is None else str(args[0])
                start, length = int(args[1]), int(args[2])
                return s[start:] if length < 0 else s[start:start + length]
            if op == "$toLower":
                return (args[0] or "").lower()
            if op == "$toUpper":
                return (args[0] or "").upper()
            if op == "$ifNull":
                return next((a for a in args if a is not None), None)
            if op == "$add":
                return sum(a for a in args if _is_num(a))
            if op == "$subtract":
                return args[0] - args[1]
            if op == "$multiply":
                out = 1
                for a in args:
                    out *= a
                return out
            if op == "$literal":
                return arg
            raise OperationFailure(f"Unsupported expression operator {op}")
        return {k: _eval_expr(doc, v) for k, v in expr.items()}
    return expr


def _group(docs: list, spec: dict) -> list:
    id_expr = spec.get("_id")
    accs = {k: v for k, v in spec.items() if k != "_id"}
    groups: Dict[str, dict] = {}
    for d in docs:
        gid = _eval_expr(d, id_expr)
        gkey = _dumps(gid)
        g = groups.get(gkey)
        if g is None:
            g = groups[gkey] = {"_id": gid, "_acc": {k: [] for k in accs}}
        for name, acc in accs.items():
            op, arg = next(iter(acc.items()))
            g["_acc"][name].append(_eval_expr(d, arg))
    out = []
    for g in groups.values():
        row = {"_id": g["_id"]}
        for name, acc in accs.items():
            op = next(iter(acc))
            vals = g["_acc"][name]
            if op == "$sum":
                row[name] = sum(v for v in vals if _is_num(v))
            elif op == "$avg":
                nums = [v for v in vals if _is_num(v)]
                row[name] = sum(nums) / len(nums) if nums else None
            elif op in ("$max", "$min"):
                present = [v for v in vals if v is not None]
                row[name] = (max if op == "$max" else min)(present, key=_sort_key) if present else None
            elif op == "$first":
                row[name] = vals[0] if vals else None
            elif op == "$last":
                row[name] = vals[-1] if vals else None
            elif op == "$push":
                row[name] = vals
            elif op == "$addToSet":
                uniq = []
                for v in vals:
                    if not any(_eq(v, u) for u in uniq):
                        uniq.append(v)
                row[name] = uniq
            elif op == "$count":
                row[name] = len(vals)
            else:
                raise OperationFailure(f"Unsupported accumulator {op}")
        out.append(row)
    return out


def _run_pipeline(docs: list, pipeline: list) -> list:
    for stage in pipeline:
        (op, arg), = stage.items()
        if op == "$match":
            docs = [d for d in docs if _matches(d, arg)]
        elif op == "$group":
            docs = _group(docs, arg)
        elif op == "$sort":
            docs = _sort_docs(docs, list(arg.items()))
        elif op == "$limit":
            docs = docs[:arg]
        elif op == "$skip":
            docs = docs[arg:]
        elif op == "$count":
            docs = [{arg: len(docs)}] if docs else []
        elif op == "$project":
            computed = {k: v for k, v in arg.items() if not isinstance(v, (int, bool))}
            plain = {k: v for k, v in arg.items() if isinstance(v, (int, bool))}
            new_docs = []
            for d in docs:
                nd = _project(d, plain) if plain else ({} if computed else d)
                for k, v in computed.items():
                    nd[k] = _eval_expr(d, v)
                new_docs.append(nd)
            docs = new_docs
        elif op == "$unwind":
            path = (arg["path"] if isinstance(arg, dict) else arg)[1:]
            new_docs = []
            for d in docs:
                v = _get(d, path)
                if isinstance(v, list):
                    for el in v:
                        nd = deepcopy(d)
                        _set_path(nd, path, el)
                        new_docs.append(nd)
            docs = new_docs
        else:
            raise OperationFailure(f"Unsupported pipeline stage {op}")
    return docs


# ---------- Results ----------
class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id
        self.acknowledged = True


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids
        self.acknowledged = True


class UpdateResult:
    def __init__(self, matched_count, modified_count, upserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id
        self.acknowledged = True


class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count
        self.acknowledged = True


# ---------- Cursor ----------
class Cursor:
    def __init__(self, coll: "Collection", flt, projection):
        self._coll = coll
        self._filter = flt or {}
        self._projection = projection
        self._sort = None
        self._skip = 0
        self._limit = 0

    def sort(self, key_or_list, direction=None):
        self._sort = _normalize_sort(key_or_list, direction)
        return self

    def skip(self, n: int):
        self._skip = n
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    async def _execute(self) -> list:
        docs = [d for _, d in await self._coll._fetch(self._filter)]
        if self._sort:
            docs = _sort_docs(docs, self._sort)
        if self._skip:
            docs = docs[self._skip:]
        if self._limit:
            docs = docs[:self._limit]
        return [_project(d, self._projection) for d in docs]

    async def to_list(self, length: Optional[int] = None) -> list:
        docs = await self._execute()
        return docs[:length] if length else docs

    def __aiter__(self):
        async def gen():
            for d in await self._execute():
                yield d
        return gen()


class AggregateCursor:
    def __init__(self, coll: "Collection", pipeline: list):
        self._coll = coll
        self._pipeline = pipeline

    async def _execute(self) -> list:
        pipeline = list(self._pipeline)
        pre = pipeline.pop(0)["$match"] if pipeline and "$match" in pipeline[0] else {}
        docs = [d for _, d in await self._coll._fetch(pre)]
        return _run_pipeline(docs, pipeline)

    async def to_list(self, length: Optional[int] = None) -> list:
        docs = await self._execute()
        return docs[:length] if length else docs

    def __aiter__(self):
        async def gen():
            for d in await self._execute():
                yield d
        return gen()


# ---------- Collection ----------
def _qi(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _ql(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _field_sql(field: str) -> str:
    if "." in field:
        return "(doc #>> " + _ql("{" + ",".join(field.split(".")) + "}") + ")"
    return f"(doc ->> {_ql(field)})"


def _partial_sql(expr: dict) -> str:
    parts = []
    for field, cond in expr.items():
        f = _field_sql(field)
        if _is_operator_dict(cond):
            for op, arg in cond.items():
                if op == "$exists":
                    parts.append(f"doc ? {_ql(field)}" if arg else f"NOT (doc ? {_ql(field)})")
                elif op == "$in":
                    parts.append(f"{f} IN (" + ", ".join(_ql(a) for a in arg) + ")")
                elif op == "$eq":
                    parts.append(f"{f} = {_ql(arg)}")
                elif op == "$type" and arg == "string":
                    parts.append(f"jsonb_typeof(doc->{_ql(field)}) = 'string'")
                else:
                    raise OperationFailure(f"Unsupported partialFilterExpression operator {op}")
        else:
            parts.append(f"{f} = {_ql(cond)}")
    return " AND ".join(parts)


class Collection:
    def __init__(self, database: "Database", name: str):
        self._db = database
        self.name = name
        self._t = _qi(name)

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        return self._db[f"{self.name}.{item}"]

    async def _con(self):
        return await self._db._client._acquire(self.name)

    def _lock_key(self) -> int:
        return zlib.crc32(("upsert:" + self.name).encode()) - 2 ** 31

    async def _fetch(self, flt, con=None, for_update=False):
        params: list = []
        clauses = _prefilter(flt, params)
        sql = f"SELECT _pk, doc FROM {self._t}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY _seq"
        if for_update:
            sql += " FOR UPDATE"
        if con is None:
            async with await self._con() as c:
                rows = await c.fetch(sql, *params)
        else:
            rows = await con.fetch(sql, *params)
        return [(r["_pk"], r["doc"]) for r in rows if _matches(r["doc"], flt)]

    # --- reads ---
    def find(self, filter=None, projection=None, *args, sort=None, skip=0, limit=0, **kwargs):
        cur = Cursor(self, filter, projection)
        if sort:
            cur.sort(sort)
        if skip:
            cur.skip(skip)
        if limit:
            cur.limit(limit)
        return cur

    async def find_one(self, filter=None, projection=None, *args, sort=None, **kwargs):
        if filter is not None and not isinstance(filter, dict):
            filter = {"_id": filter}
        rows = await self.find(filter, projection, sort=sort).limit(1).to_list(1)
        return rows[0] if rows else None

    async def count_documents(self, filter=None, **kwargs) -> int:
        if not filter:
            async with await self._con() as c:
                return await c.fetchval(f"SELECT count(*) FROM {self._t}")
        return len(await self._fetch(filter))

    async def estimated_document_count(self, **kwargs) -> int:
        return await self.count_documents({})

    async def distinct(self, key: str, filter=None, **kwargs) -> list:
        out: list = []
        for _, d in await self._fetch(filter or {}):
            for v in _candidates(_path_values(d, key)):
                if v is not _MISSING and not isinstance(v, list) and not any(_eq(v, o) for o in out):
                    out.append(v)
        return out

    def aggregate(self, pipeline: list, *args, **kwargs):
        return AggregateCursor(self, pipeline)

    # --- writes ---
    @staticmethod
    def _dup(e: asyncpg.UniqueViolationError) -> DuplicateKeyError:
        detail = getattr(e, "detail", "") or ""
        cname = getattr(e, "constraint_name", "") or ""
        return DuplicateKeyError(f"E11000 duplicate key error index: {cname} {detail}",
                                 {"index": cname, "errmsg": detail, "code": 11000})

    @staticmethod
    def _split_pk(doc: dict):
        return str(doc["_id"]) if "_id" in doc else str(uuid.uuid4())

    async def insert_one(self, document: dict, *args, **kwargs) -> InsertOneResult:
        pk = self._split_pk(document)
        try:
            async with await self._con() as c:
                await c.execute(f"INSERT INTO {self._t} (_pk, doc) VALUES ($1, $2)", pk, document)
        except asyncpg.UniqueViolationError as e:
            raise self._dup(e) from None
        return InsertOneResult(document.get("_id", pk))

    async def insert_many(self, documents: list, *args, **kwargs) -> InsertManyResult:
        documents = list(documents)
        if not documents:
            raise OperationFailure("documents must be a non-empty list")
        pks = [self._split_pk(d) for d in documents]
        try:
            async with await self._con() as c:
                async with c.transaction():
                    await c.executemany(f"INSERT INTO {self._t} (_pk, doc) VALUES ($1, $2)", list(zip(pks, documents)))
        except asyncpg.UniqueViolationError as e:
            raise self._dup(e) from None
        return InsertManyResult([d.get("_id", pk) for d, pk in zip(documents, pks)])

    async def _update(self, flt, update, upsert: bool, many: bool, return_doc: Optional[str] = None,
                      projection=None, sort=None):
        """Core read-modify-write inside a transaction with row locks (atomic per document)."""
        try:
            async with await self._con() as c:
                async with c.transaction():
                    if upsert:
                        await c.execute("SELECT pg_advisory_xact_lock($1)", self._lock_key())
                    rows = await self._fetch(flt, con=c, for_update=True)
                    if sort and rows:
                        order = _sort_docs([d for _, d in rows], _normalize_sort(sort))
                        rows = [next(r for r in rows if r[1] is d) for d in order]
                    if not many:
                        rows = rows[:1]
                    if not rows:
                        if not upsert:
                            return UpdateResult(0, 0), None, None
                        new = _apply_update(_upsert_seed(flt), update, inserting=True)
                        pk = self._split_pk(new)
                        await c.execute(f"INSERT INTO {self._t} (_pk, doc) VALUES ($1, $2)", pk, new)
                        return UpdateResult(0, 0, new.get("_id", pk)), None, new
                    modified = 0
                    before = after = None
                    for pk, doc in rows:
                        new = _apply_update(doc, update)
                        if new != doc:
                            await c.execute(f"UPDATE {self._t} SET doc = $2 WHERE _pk = $1", pk, new)
                            modified += 1
                        if before is None:
                            before, after = doc, new
                    return UpdateResult(len(rows), modified), before, after
        except asyncpg.UniqueViolationError as e:
            raise self._dup(e) from None

    async def update_one(self, filter, update, upsert=False, **kwargs) -> UpdateResult:
        res, _, _ = await self._update(filter, update, upsert, many=False, sort=kwargs.get("sort"))
        return res

    async def update_many(self, filter, update, upsert=False, **kwargs) -> UpdateResult:
        res, _, _ = await self._update(filter, update, upsert, many=True)
        return res

    async def replace_one(self, filter, replacement, upsert=False, **kwargs) -> UpdateResult:
        res, _, _ = await self._update(filter, replacement, upsert, many=False)
        return res

    async def find_one_and_update(self, filter, update, projection=None, sort=None, upsert=False,
                                  return_document=False, **kwargs):
        _, before, after = await self._update(filter, update, upsert, many=False, sort=sort)
        doc = after if return_document else before
        return _project(doc, projection) if doc is not None else None

    async def find_one_and_replace(self, filter, replacement, projection=None, sort=None, upsert=False,
                                   return_document=False, **kwargs):
        return await self.find_one_and_update(filter, replacement, projection, sort, upsert, return_document)

    async def _delete(self, flt, many: bool) -> list:
        async with await self._con() as c:
            async with c.transaction():
                rows = await self._fetch(flt, con=c, for_update=True)
                if not many:
                    rows = rows[:1]
                if rows:
                    await c.execute(f"DELETE FROM {self._t} WHERE _pk = ANY($1::text[])", [pk for pk, _ in rows])
                return rows

    async def delete_one(self, filter, **kwargs) -> DeleteResult:
        return DeleteResult(len(await self._delete(filter, many=False)))

    async def delete_many(self, filter, **kwargs) -> DeleteResult:
        return DeleteResult(len(await self._delete(filter, many=True)))

    async def find_one_and_delete(self, filter, projection=None, **kwargs):
        rows = await self._delete(filter, many=False)
        return _project(rows[0][1], projection) if rows else None

    # --- indexes ---
    def _index_name(self, name: str) -> str:
        full = f"{self.name}__{name}"
        if len(full) > 63:
            full = full[:54] + "_" + format(zlib.crc32(full.encode()), "08x")
        return full

    async def create_index(self, keys, unique=False, sparse=False, partialFilterExpression=None, name=None, **kwargs):
        spec = _normalize_sort(keys)
        name = name or "_".join(f"{k}_{d}" for k, d in spec)
        if not unique:
            # Non-unique indexes are served by the per-table GIN index on doc (see _ensure_table).
            return name
        exprs = ", ".join(_field_sql(k) for k, _ in spec)
        where = []
        if sparse:
            where += [f"(doc ? {_ql(k)} AND jsonb_typeof(doc->{_ql(k)}) <> 'null')" for k, _ in spec]
        if partialFilterExpression:
            where.append(_partial_sql(partialFilterExpression))
        nulls = " NULLS NOT DISTINCT" if not where else ""
        sql = (f"CREATE UNIQUE INDEX IF NOT EXISTS {_qi(self._index_name(name))} ON {self._t} ({exprs}){nulls}"
               + (" WHERE " + " AND ".join(where) if where else ""))
        async with await self._con() as c:
            await c.execute(sql)
        return name

    async def create_indexes(self, indexes, **kwargs):
        return [await self.create_index(i.document["key"], **{k: v for k, v in i.document.items() if k != "key"})
                for i in indexes]

    async def drop_index(self, name: str, **kwargs):
        async with await self._con() as c:
            await c.execute(f"DROP INDEX IF EXISTS {_qi(self._index_name(name))}")

    async def drop(self):
        async with await self._con() as c:
            await c.execute(f"DROP TABLE IF EXISTS {self._t}")
        self._db._client._ready.discard(self.name)


class Database:
    def __init__(self, client: "PgClient", name: str):
        self._client = client
        self.name = name

    def __getattr__(self, item) -> Collection:
        if item.startswith("_"):
            raise AttributeError(item)
        return Collection(self, item)

    def __getitem__(self, item) -> Collection:
        return Collection(self, item)

    def get_collection(self, name: str) -> Collection:
        return Collection(self, name)

    async def list_collection_names(self) -> List[str]:
        async with await self._client._acquire(None) as c:
            rows = await c.fetch("SELECT table_name FROM information_schema.tables "
                                 "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'")
        return sorted(r["table_name"] for r in rows)

    async def drop_collection(self, name: str):
        await Collection(self, name).drop()


class _Acquire:
    """``async with await client._acquire(coll)`` -> pooled connection with the collection table ensured."""

    def __init__(self, pool: asyncpg.Pool):
        self._ctx = pool.acquire()

    async def __aenter__(self):
        return await self._ctx.__aenter__()

    async def __aexit__(self, *exc):
        return await self._ctx.__aexit__(*exc)


class PgClient:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 20):
        self._dsn = dsn
        self._min, self._max = min_size, max_size
        self._pool: Optional[asyncpg.Pool] = None
        self._loop = None
        self._ready: set = set()

    def __getitem__(self, name: str) -> Database:
        return Database(self, name)

    def get_database(self, name: str) -> Database:
        return Database(self, name)

    @staticmethod
    async def _init_conn(con):
        await con.set_type_codec("jsonb", encoder=_dumps, decoder=json.loads, schema="pg_catalog")

    async def _get_pool(self) -> asyncpg.Pool:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            # Pools and locks are bound to an event loop; rebuild when used from a new loop (tests, scripts).
            self._loop = loop
            self._pool = None
            self._pool_lock = asyncio.Lock()
            self._table_lock = asyncio.Lock()
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:
                    self._pool = await asyncpg.create_pool(self._dsn, min_size=self._min, max_size=self._max,
                                                           init=self._init_conn)
        return self._pool

    async def _acquire(self, collection: Optional[str]) -> _Acquire:
        pool = await self._get_pool()
        if collection and collection not in self._ready:
            async with self._table_lock:
                if collection not in self._ready:
                    t = _qi(collection)
                    async with pool.acquire() as c:
                        await c.execute("SELECT pg_advisory_lock(424242)")
                        try:
                            await c.execute(f"CREATE TABLE IF NOT EXISTS {t} ("
                                            "_pk text PRIMARY KEY, _seq bigserial, doc jsonb NOT NULL)")
                            await c.execute(f"CREATE INDEX IF NOT EXISTS {_qi(collection[:55] + '__doc_gin')} "
                                            f"ON {t} USING gin (doc jsonb_path_ops)")
                        finally:
                            await c.execute("SELECT pg_advisory_unlock(424242)")
                    self._ready.add(collection)
        return _Acquire(pool)

    async def aclose(self):
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def close(self):
        """Motor-compatible sync close: schedules pool shutdown on the running loop."""
        if self._pool is None:
            return
        try:
            asyncio.get_running_loop().create_task(self.aclose())
        except RuntimeError:
            asyncio.run(self.aclose())
