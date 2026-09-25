"""WhatsApp integration (Phase E1).

Architecture: WhatsAppService -> ProviderAdapter -> Concrete provider.
Business logic never touches provider SDKs directly (only `requests`, already vendored).
"""
import hashlib
import hmac
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from core import db, require_roles, new_id, now_iso, clean, log_audit, today_str

router = APIRouter()

WA_READ = require_roles("admin", "finance", "hr")
WA_SEND = require_roles("finance")
WA_ADMIN = require_roles("owner")

STATUS_ORDER = {"queued": 0, "sending": 1, "sent": 2, "delivered": 3, "read": 4}
TERMINAL = ("read", "skipped_no_consent")
RETRYABLE_TERMINAL = ("failed",)
MAX_ATTEMPTS = 3


# ---------- config ----------
def wa_config(public_only: bool = False) -> dict:
    enabled = os.environ.get("WA_ENABLED", "false").lower() == "true"
    dry = os.environ.get("WA_DRY_RUN", "true").lower() != "false"
    cfg = {"provider": os.environ.get("WA_PROVIDER", "cloud_api"),
           "enabled": enabled, "dry_run": dry,
           "sender_id": os.environ.get("WA_SENDER_ID", ""),
           "api_url": os.environ.get("WA_API_URL", "https://graph.facebook.com/v21.0"),
           "default_language": os.environ.get("WA_LANGUAGE", "id"),
           "webhook_configured": bool(os.environ.get("WA_VERIFY_TOKEN"))}
    if not public_only:
        cfg["token_configured"] = bool(os.environ.get("WA_TOKEN"))
        cfg["app_secret_configured"] = bool(os.environ.get("WA_APP_SECRET"))
    return cfg


def mask_phone(phone: str) -> str:
    p = phone or ""
    if len(p) <= 7:
        return "****"
    return f"{p[:5]}****{p[-3:]}"


# ---------- phone ----------
def normalize_phone(raw: str) -> Optional[str]:
    """Kembalikan MSISDN 628xxxxxxxxxx atau None bila invalid. Non-destruktif terhadap source."""
    if not raw:
        return None
    d = re.sub(r"\D", "", str(raw))
    if d.startswith("0"):
        d = "62" + d[1:]
    elif d.startswith("+"):
        d = d[1:]
    if d.startswith("62") and d[2:3] == "0":
        d = "62" + d[3:]
    if re.fullmatch(r"628\d{8,12}", d or ""):
        return d
    return None


# ---------- provider adapters ----------
class ProviderResult(Dict[str, Any]):
    pass


class ProviderAdapter:
    name = "base"

    def send(self, to: str, body: str, template_name: Optional[str], language: str) -> ProviderResult:
        raise NotImplementedError

    def verify_signature(self, raw_body: bytes, signature: str) -> bool:
        raise NotImplementedError

    def parse_webhook(self, payload: dict) -> List[dict]:
        return []


class CloudApiAdapter(ProviderAdapter):
    name = "cloud_api"

    def send(self, to: str, body: str, template_name: Optional[str], language: str) -> ProviderResult:
        token = os.environ.get("WA_TOKEN", "")
        sender = os.environ.get("WA_SENDER_ID", "")
        base = os.environ.get("WA_API_URL", "https://graph.facebook.com/v21.0").rstrip("/")
        if not token or not sender:
            return {"ok": False, "retryable": False, "error": "Kredensial provider belum dikonfigurasi"}
        try:
            payload: Dict[str, Any] = {"messaging_product": "whatsapp", "to": to, "type": "text",
                                       "text": {"body": body, "preview_url": False}}
            if template_name:
                payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
                           "template": {"name": template_name, "language": {"code": language}}}
            r = requests.post(f"{base}/{sender}/messages", headers={"Authorization": f"Bearer {token}"},
                              json=payload, timeout=15)
            data = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {}
            if r.status_code >= 400:
                err = (data.get("error") or {}).get("message", f"HTTP {r.status_code}")
                return {"ok": False, "retryable": r.status_code >= 500 or r.status_code == 429, "error": err}
            msgs = data.get("messages") or [{}]
            return {"ok": True, "provider_msg_id": msgs[0].get("id")}
        except requests.Timeout:
            return {"ok": False, "retryable": True, "error": "Timeout provider"}
        except requests.RequestException as e:
            return {"ok": False, "retryable": True, "error": f"Provider error: {e}"}

    def verify_signature(self, raw_body: bytes, signature: str) -> bool:
        secret = os.environ.get("WA_APP_SECRET", "")
        if not secret or not signature:
            return False
        sig = signature[7:] if signature.startswith("sha256=") else signature
        expect = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expect, sig)

    def parse_webhook(self, payload: dict) -> List[dict]:
        out = []
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                val = change.get("value") or {}
                for st in val.get("statuses") or []:
                    out.append({"provider_event_id": f"{st.get('id')}:{st.get('status')}:{st.get('timestamp')}",
                                "message_id": st.get("id"), "status": st.get("status"),
                                "timestamp": st.get("timestamp"), "recipient": st.get("recipient_id")})
        return out


class FakeAdapter(ProviderAdapter):
    """Adapter uji (WA_PROVIDER=fake_success|fake_fail|fake_timeout). Tanpa HTTP keluar."""

    def __init__(self, mode: str):
        self.name = f"fake_{mode}"
        self.mode = mode

    def send(self, to: str, body: str, template_name: Optional[str], language: str) -> ProviderResult:
        if self.mode == "success":
            return {"ok": True, "provider_msg_id": f"fake-{new_id()[:8]}"}
        if self.mode == "timeout":
            return {"ok": False, "retryable": True, "error": "Timeout provider (fake)"}
        return {"ok": False, "retryable": False, "error": "Provider menolak pesan (fake)"}

    def verify_signature(self, raw_body: bytes, signature: str) -> bool:
        return signature == "fake-valid"


def get_adapter() -> ProviderAdapter:
    mode = os.environ.get("WA_PROVIDER", "cloud_api")
    if mode.startswith("fake_"):
        return FakeAdapter(mode[len("fake_"):])
    return CloudApiAdapter()


# ---------- templates ----------
TEMPLATE_VARS: Dict[str, List[str]] = {
    "payment_due": ["nama", "jumlah", "jatuh_tempo", "cara_bayar"],
    "payment_received": ["nama", "jumlah", "tanggal", "nomor_kwitansi"],
    "document_expiry": ["nama", "jenis_dokumen", "tanggal"],
    "interview_reminder": ["nama", "perusahaan", "posisi", "tanggal"],
    "followup_calon": ["nama", "nama_lpk", "tanggal_follow_up"],
}

DEFAULT_TEMPLATES = [
    {"key": "payment_due", "provider_name": "", "language": "id", "category": "UTILITY",
     "body": "Halo {{nama}}, tagihan LPK sebesar {{jumlah}} jatuh tempo {{jatuh_tempo}}. {{cara_bayar}}"},
    {"key": "payment_received", "language": "id", "category": "UTILITY",
     "body": "Halo {{nama}}, pembayaran {{jumlah}} pada {{tanggal}} telah diterima. Kwitansi: {{nomor_kwitansi}}."},
    {"key": "document_expiry", "language": "id", "category": "UTILITY",
     "body": "Halo {{nama}}, dokumen {{jenis_dokumen}} perlu perhatian sebelum {{tanggal}}. Mohon segera dilengkapi."},
    {"key": "interview_reminder", "language": "id", "category": "UTILITY",
     "body": "Halo {{nama}}, pengingat interview di {{perusahaan}} ({{posisi}}) pada {{tanggal}}. Harap hadir tepat waktu."},
    {"key": "followup_calon", "language": "id", "category": "UTILITY",
     "body": "Halo {{nama}}, ini {{nama_lpk}}. Menindaklanjuti ketertarikan Anda mengikuti program kami. {{tanggal_follow_up}}"},
]


async def seed_templates():
    for t in DEFAULT_TEMPLATES:
        if not await db.whatsapp_templates.find_one({"key": t["key"]}):
            await db.whatsapp_templates.insert_one(
                {"id": new_id(), **t, "variables": TEMPLATE_VARS[t["key"]],
                 "active": True, "version": 1, "created_at": now_iso(), "updated_at": now_iso()})


async def get_template(key: str) -> Optional[dict]:
    return await db.whatsapp_templates.find_one({"key": key, "active": True}, {"_id": 0})


def render_template(body: str, allowed: List[str], variables: dict) -> str:
    missing = [v for v in re.findall(r"\{\{(\w+)\}\}", body) if v not in allowed]
    if missing:
        raise HTTPException(status_code=400, detail=f"Variabel template tidak dikenal: {', '.join(missing)}")
    out = body
    for v in allowed:
        if v not in variables or variables[v] in (None, ""):
            raise HTTPException(status_code=400, detail=f"Variabel '{v}' wajib diisi")
        out = out.replace("{{" + v + "}}", str(variables[v]))
    return out


# ---------- service ----------
async def _resolve_recipient(student: dict, recipient: str) -> dict:
    """Kembalikan {phone, consent, name} atau raise 400 dengan alasan jelas."""
    if recipient == "siswa":
        phone = student.get("wa_student_phone") or normalize_phone(student.get("no_hp"))
        return {"phone": phone, "consent": bool(student.get("wa_student_opt_in", False)),
                "name": student.get("nama_lengkap", "")}
    if recipient == "wali":
        if not student.get("no_hp_orang_tua") or not student.get("nama_orang_tua"):
            raise HTTPException(status_code=400, detail="Data wali belum lengkap")
        phone = student.get("wa_guardian_phone") or normalize_phone(student.get("no_hp_orang_tua"))
        return {"phone": phone, "consent": bool(student.get("wa_guardian_opt_in", False)),
                "name": student.get("nama_orang_tua", "")}
    raise HTTPException(status_code=400, detail="Recipient tidak valid")


async def queue_message(template_key: str, student_id: str, recipient: str, idem_suffix: str,
                        variables: dict, created_by: Optional[dict] = None,
                        allow_skipped: bool = True) -> dict:
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    tpl = await get_template(template_key)
    if not tpl:
        raise HTTPException(status_code=400, detail="Template tidak aktif")
    rcpt = await _resolve_recipient(student, recipient)
    if not rcpt["phone"]:
        return {"skipped": True, "status": "failed", "fail_reason": "invalid_number",
                "template_key": template_key, "student_id": student_id, "recipient_role": recipient}
    if not rcpt["consent"]:
        if not allow_skipped:
            raise HTTPException(status_code=400, detail="Consent WhatsApp belum diberikan")
        return {"skipped": True, "status": "skipped_no_consent",
                "template_key": template_key, "student_id": student_id, "recipient_role": recipient}
    body = render_template(tpl["body"], tpl.get("variables") or TEMPLATE_VARS.get(template_key, []), variables)
    key = f"wa:{template_key}:v{tpl['version']}:{student_id}:{recipient}:{idem_suffix}"
    doc = {"id": new_id(), "idempotency_key": key, "template_key": template_key, "template_version": tpl["version"],
           "body_snapshot": body, "variables": variables, "recipient_role": recipient, "student_id": student_id,
           "student_nama": student.get("nama_lengkap", ""), "recipient_name": rcpt["name"], "phone": rcpt["phone"],
           "status": "queued", "provider": get_adapter().name if wa_config()["enabled"] else "disabled",
           "provider_msg_id": None, "fail_reason": None, "retryable": False, "attempts": 0,
           "next_retry_at": None, "sent_at": None, "retry_of": None,
           "created_by": (created_by or {}).get("name"), "created_at": now_iso(), "updated_at": now_iso(),
           "dry_run": False}
    try:
        await db.whatsapp_messages.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.whatsapp_messages.find_one({"idempotency_key": key}, {"_id": 0})
        if existing:
            return {**clean(existing), "duplicate": True}
        raise
    return clean(doc)


async def attempt_send(msg_id: str, actor: Optional[dict] = None) -> dict:
    msg = await db.whatsapp_messages.find_one({"id": msg_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Pesan tidak ditemukan")
    if msg["status"] not in ("queued", "failed"):
        return clean(msg)
    cfg = wa_config()
    await db.whatsapp_messages.update_one({"id": msg_id}, {"$set": {"status": "sending", "updated_at": now_iso()}})
    if cfg["dry_run"] or not cfg["enabled"]:
        await db.whatsapp_messages.update_one({"id": msg_id}, {"$set": {"status": "sent", "sent_at": now_iso(),
            "provider": "dry_run" if cfg["dry_run"] else "disabled", "dry_run": True, "updated_at": now_iso()}})
        await log_audit("wa_message", msg_id, "send_dry_run" if cfg["dry_run"] else "send_skipped_disabled",
                        actor or {"id": "system", "name": "system", "role": "system"},
                        {"status": msg["status"]}, {"status": "sent"})
        return clean(await db.whatsapp_messages.find_one({"id": msg_id}, {"_id": 0}))
    adapter = get_adapter()
    res = adapter.send(msg["phone"], msg["body_snapshot"], None, cfg["default_language"])
    attempts = msg.get("attempts", 0) + 1
    if res.get("ok"):
        await db.whatsapp_messages.update_one({"id": msg_id}, {"$set": {"status": "sent", "sent_at": now_iso(),
            "provider": adapter.name, "provider_msg_id": res.get("provider_msg_id"), "attempts": attempts,
            "fail_reason": None, "retryable": False, "updated_at": now_iso()}})
    else:
        retryable = bool(res.get("retryable")) and attempts < MAX_ATTEMPTS
        await db.whatsapp_messages.update_one({"id": msg_id}, {"$set": {"status": "failed",
            "fail_reason": res.get("error", "unknown"), "retryable": retryable, "attempts": attempts,
            "next_retry_at": (datetime.now(timezone.utc) + timedelta(minutes=5 * attempts)).isoformat()
            if retryable else None, "updated_at": now_iso()}})
    await log_audit("wa_message", msg_id, "send", actor or {"id": "system", "name": "system", "role": "system"},
                    {"status": msg["status"]}, {"status": (await db.whatsapp_messages.find_one({"id": msg_id}, {"_id": 0}))["status"]})
    return clean(await db.whatsapp_messages.find_one({"id": msg_id}, {"_id": 0}))


async def dispatch_event(template_key: str, student_id: str, idem_suffix: str, variables: dict,
                         recipients: List[str]) -> list:
    """Dipanggil dari notification sync / business hooks. Aman diulang (idempoten)."""
    cfg = wa_config()
    if not cfg["enabled"]:
        return []
    out = []
    for rcpt in recipients:
        try:
            msg = await queue_message(template_key, student_id, rcpt, idem_suffix, variables)
            if not msg.get("duplicate") and msg["status"] == "queued":
                msg = await attempt_send(msg["id"])
            out.append(msg)
        except HTTPException:
            continue
    # retry opportunity: gagal retryable yang jatuh tempo
    due = await db.whatsapp_messages.find(
        {"status": "failed", "retryable": True,
         "next_retry_at": {"$lte": datetime.now(timezone.utc).isoformat()}}, {"_id": 0, "id": 1}).to_list(20)
    for d in due:
        try:
            await attempt_send(d["id"])
        except HTTPException:
            continue
    return out


# ---------- API ----------
class TemplateIn(BaseModel):
    key: str
    provider_name: Optional[str] = ""
    language: Optional[str] = "id"
    category: Optional[str] = "UTILITY"
    body: str
    active: Optional[bool] = True


class ManualSendIn(BaseModel):
    student_id: str
    recipient: str = "siswa"
    template_key: str
    variables: Optional[Dict[str, Any]] = None
    payment_id: Optional[str] = None


def _public_msg(m: dict) -> dict:
    m = clean(m)
    m["phone"] = mask_phone(m.get("phone", ""))
    return m


@router.get("/wa/status")
async def wa_status(user: dict = Depends(require_roles("owner", "admin"))):
    return wa_config(public_only=user["role"] != "owner")


@router.post("/wa/test-connection")
async def wa_test_connection(user: dict = Depends(require_roles("owner"))):
    cfg = wa_config()
    if not cfg["enabled"]:
        return {"ok": False, "mode": "disabled", "detail": "WA_ENABLED=false — tidak ada HTTP keluar"}
    if cfg["dry_run"]:
        return {"ok": True, "mode": "dry_run", "detail": "Dry-run aktif — tidak ada HTTP keluar"}
    return {"ok": True, "mode": cfg["provider"], "detail": "Konfigurasi tersedia (tanpa mengirim pesan)"}


@router.get("/wa/templates")
async def wa_templates(user: dict = Depends(require_roles("owner", "finance"))):
    return await db.whatsapp_templates.find({}, {"_id": 0}).sort("key", 1).to_list(100)


@router.post("/wa/templates")
async def wa_template_create(body: TemplateIn, user: dict = Depends(require_roles("owner"))):
    if await db.whatsapp_templates.find_one({"key": body.key}):
        raise HTTPException(status_code=400, detail="Template key sudah ada")
    if body.key not in TEMPLATE_VARS:
        raise HTTPException(status_code=400, detail="Template key tidak dikenal")
    doc = {"id": new_id(), "key": body.key, "provider_name": body.provider_name or "",
           "language": body.language or "id", "category": body.category or "UTILITY", "body": body.body,
           "variables": TEMPLATE_VARS[body.key], "active": body.active, "version": 1,
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.whatsapp_templates.insert_one(doc)
    await log_audit("wa_template", doc["id"], "create", user, None, {"key": body.key})
    return clean(doc)


@router.put("/wa/templates/{key}")
async def wa_template_update(key: str, body: TemplateIn, user: dict = Depends(require_roles("owner"))):
    tpl = await db.whatsapp_templates.find_one({"key": key})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan")
    upd: Dict[str, Any] = {"provider_name": body.provider_name or "", "language": body.language or "id",
                           "category": body.category or "UTILITY", "active": body.active, "updated_at": now_iso()}
    if body.body != tpl["body"]:
        upd["body"] = body.body
        upd["version"] = tpl["version"] + 1
    await db.whatsapp_templates.update_one({"key": key}, {"$set": upd})
    await log_audit("wa_template", tpl["id"], "update", user, {"version": tpl["version"]}, {"version": upd.get("version", tpl["version"])})
    return clean(await db.whatsapp_templates.find_one({"key": key}, {"_id": 0}))


@router.get("/wa/messages")
async def wa_messages(status: Optional[str] = None, student_id: Optional[str] = None,
                      dari: Optional[str] = None, user: dict = Depends(require_roles("admin", "finance", "hr"))):
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if student_id:
        q["student_id"] = student_id
    if dari:
        q["created_at"] = {"$gte": dari}
    rows = await db.whatsapp_messages.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [_public_msg(r) for r in rows]


async def _manual_variables(template_key: str, student_id: str, payment_id: Optional[str], extra: dict) -> dict:
    if template_key == "payment_received":
        pay = None
        if payment_id:
            pay = await db.payments.find_one({"id": payment_id, "student_id": student_id}, {"_id": 0})
            if not pay:
                raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
        else:
            pay = await db.payments.find_one({"student_id": student_id}, {"_id": 0}, sort=[("tanggal", -1)])
            if not pay:
                raise HTTPException(status_code=400, detail="Belum ada pembayaran untuk siswa ini")
        s = await db.students.find_one({"id": student_id}, {"_id": 0, "nama_lengkap": 1})
        return {"nama": s["nama_lengkap"], "jumlah": f"Rp{pay['nominal']:,.0f}".replace(",", "."),
                "tanggal": pay["tanggal"], "nomor_kwitansi": pay.get("no_kwitansi", "-")}
    if template_key == "payment_due":
        from core import payment_summary_map, fee_total
        s = await db.students.find_one({"id": student_id}, {"_id": 0})
        pay = await payment_summary_map([student_id])
        total, bayar = fee_total(s), pay.get(student_id, {}).get("bayar", 0)
        return {"nama": s["nama_lengkap"], "jumlah": f"Rp{max(total - bayar, 0):,.0f}".replace(",", "."),
                "jatuh_tempo": s.get("jatuh_tempo") or "-", "cara_bayar": extra.get("cara_bayar", "Transfer/QRIS LPK")}
    if template_key == "followup_calon":
        s = await db.students.find_one({"id": student_id}, {"_id": 0, "nama_lengkap": 1})
        if not s:
            raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
        tgl = (extra.get("tanggal_follow_up") or "").strip()
        return {"nama": s["nama_lengkap"], "nama_lpk": "LPK",
                "tanggal_follow_up": f"Kami hubungi kembali pada {tgl}." if tgl else
                "Mohon kabari waktu yang cocok untuk dihubungi kembali."}
    allowed = TEMPLATE_VARS.get(template_key, [])
    if any(v not in allowed for v in (extra or {})):
        raise HTTPException(status_code=400, detail="Variabel tidak dikenal untuk template ini")
    return {v: extra.get(v, "") for v in allowed}


@router.post("/wa/messages")
async def wa_manual_send(body: ManualSendIn, user: dict = Depends(require_roles("finance"))):
    if not wa_config()["enabled"]:
        raise HTTPException(status_code=400, detail="WhatsApp belum diaktifkan")
    variables = await _manual_variables(body.template_key, body.student_id, body.payment_id, body.variables or {})
    msg = await queue_message(body.template_key, body.student_id, body.recipient,
                              f"manual:{new_id()}", variables, created_by=user, allow_skipped=False)
    if msg.get("skipped"):
        raise HTTPException(status_code=400, detail="Nomor WhatsApp penerima tidak valid")
    if not msg.get("duplicate") and msg["status"] == "queued":
        msg = await attempt_send(msg["id"], user)
    await log_audit("wa_message", msg["id"], "manual_send", user, None,
                    {"template": body.template_key, "student_id": body.student_id, "recipient": body.recipient})
    return _public_msg(msg)


@router.post("/wa/messages/{msg_id}/retry")
async def wa_retry(msg_id: str, user: dict = Depends(require_roles("finance"))):
    orig = await db.whatsapp_messages.find_one({"id": msg_id}, {"_id": 0})
    if not orig:
        raise HTTPException(status_code=404, detail="Pesan tidak ditemukan")
    if orig["status"] != "failed" or not orig.get("retryable"):
        raise HTTPException(status_code=400, detail="Hanya pesan gagal yang retryable yang dapat diulang")
    student = await db.students.find_one({"id": orig["student_id"]}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    rcpt = await _resolve_recipient(student, orig["recipient_role"])
    if not rcpt["phone"] or not rcpt["consent"]:
        raise HTTPException(status_code=400, detail="Kontak/consent tidak valid")
    tpl = await db.whatsapp_templates.find_one({"key": orig["template_key"], "active": True}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=400, detail="Template tidak aktif")
    key = f"{orig['idempotency_key']}:retry{orig.get('attempts', 0) + 1}"
    retry_vars = orig.get("variables") or {v: _var_from_body(orig.get("body_snapshot", ""), tpl["body"], v)
                                           for v in (tpl.get("variables") or [])}
    doc = {"id": new_id(), "idempotency_key": key, "template_key": tpl["key"], "template_version": tpl["version"],
           "body_snapshot": render_template(tpl["body"], tpl.get("variables") or [], retry_vars),
           "recipient_role": orig["recipient_role"], "student_id": orig["student_id"],
           "student_nama": orig.get("student_nama", ""), "recipient_name": rcpt["name"], "phone": rcpt["phone"],
           "status": "queued", "provider": get_adapter().name, "provider_msg_id": None, "fail_reason": None,
           "retryable": False, "attempts": 0, "next_retry_at": None, "sent_at": None, "retry_of": orig["id"],
           "created_by": user["name"], "created_at": now_iso(), "updated_at": now_iso(), "dry_run": False}
    try:
        await db.whatsapp_messages.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.whatsapp_messages.find_one({"idempotency_key": key}, {"_id": 0})
        return {**_public_msg(existing), "duplicate": True}
    await log_audit("wa_message", doc["id"], "retry", user, {"retry_of": orig["id"]}, {"status": "queued"})
    return _public_msg(await attempt_send(doc["id"], user))


def _var_from_body(rendered: str, template: str, var: str) -> str:
    import re as _re
    parts = template.split("{{" + var + "}}")
    if len(parts) != 2:
        return ""
    pre, post = parts
    start = rendered.find(pre) + len(pre) if pre else 0
    end = rendered.find(post, start) if post else len(rendered)
    return rendered[start:end] if start >= 0 and end >= start else ""


# ---------- webhook (Cloud API) ----------
@router.get("/wa/webhook")
async def wa_webhook_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge", "")
    if mode == "subscribe" and token and token == os.environ.get("WA_VERIFY_TOKEN", ""):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verifikasi webhook gagal")


@router.post("/wa/webhook")
async def wa_webhook(request: Request):
    raw = await request.body()
    adapter = get_adapter()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if isinstance(adapter, CloudApiAdapter) and not adapter.verify_signature(raw, sig):
        raise HTTPException(status_code=403, detail="Signature webhook tidak valid")
    import json as _json
    try:
        payload = _json.loads(raw.decode() or "{}")
    except Exception:
        return {"ok": True, "ignored": True}
    for ev in adapter.parse_webhook(payload):
        try:
            await db.whatsapp_events.insert_one({"id": new_id(), "provider_event_id": ev["provider_event_id"],
                                                 "message_id": ev.get("message_id"), "type": ev.get("status"),
                                                 "created_at": now_iso()})
        except DuplicateKeyError:
            continue
        msg = await db.whatsapp_messages.find_one(
            {"$or": [{"provider_msg_id": ev.get("message_id")}]}, {"_id": 0})
        if not msg:
            continue
        rank = STATUS_ORDER.get(ev.get("status"), -1)
        cur = STATUS_ORDER.get(msg["status"], -1)
        if ev.get("status") == "failed":
            if msg["status"] in ("sending", "sent", "queued"):
                await db.whatsapp_messages.update_one({"id": msg["id"]}, {"$set": {"status": "failed",
                    "fail_reason": "provider", "retryable": True,
                    "next_retry_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                    "updated_at": now_iso()}})
        elif rank > cur and ev.get("status") in STATUS_ORDER:
            await db.whatsapp_messages.update_one({"id": msg["id"]}, {"$set": {"status": ev["status"],
                                                                               "updated_at": now_iso()}})
    return {"ok": True}
