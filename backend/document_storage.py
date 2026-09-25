"""Abstraksi penyimpanan file dokumen (server-local).

Keputusan arsitektur: binary dokumen disimpan di filesystem milik SERVER
aplikasi (bukan laptop user, bukan browser, bukan MongoDB binary), sedangkan
database hanya menyimpan metadata. Tidak memakai EMERGENT_LLM_KEY maupun
credential/service eksternal apa pun.

    business logic (routers/students.py, routers/portal.py)
        -> DocumentStorage (abstraksi)
            -> LocalDocumentStorage (implementasi terpilih)

Masa depan: object storage dapat dipasang sebagai implementasi baru
DocumentStorage tanpa mengubah business logic verifikasi dokumen.

Lokasi: DOCUMENT_STORAGE_PATH (env) atau <backend>/storage/documents.
Direktori storage runtime wajib di-gitignore; file upload tidak ikut git.
"""
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# Ekstensi yang diizinkan untuk dokumen siswa + pemetaan content-type kanonis.
# Content-type TIDAK dipercaya dari client; ditentukan dari ekstensi.
ALLOWED_DOC_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}
EXT_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_-]")


def storage_root() -> Path:
    """Root direktori storage; dibuat bila belum ada (persistent, bukan /tmp)."""
    configured = (os.environ.get("DOCUMENT_STORAGE_PATH") or "").strip()
    root = Path(configured).expanduser() if configured else Path(__file__).parent / "storage" / "documents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_component(value: str) -> str:
    """Bersihkan komponen path dari input agar tidak bisa directory traversal."""
    return _SAFE_COMPONENT.sub("", value or "")[:64]


def extension_of(filename: str) -> str:
    name = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


class DocumentStorage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> int:
        """Simpan binary pada key; kembalikan ukuran byte. Atomic bila memungkinkan."""

    @abstractmethod
    def open(self, key: str) -> Tuple[bytes, None]:
        """Baca binary pada key; raise FileNotFoundError bila tidak ada."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Hapus key; True bila terhapus, False bila memang tidak ada."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Cek keberadaan key tanpa membaca isinya."""


class LocalDocumentStorage(DocumentStorage):
    """Implementasi filesystem lokal server. Key selalu relatif terhadap root
    (mis. 'documents/<student_id>/<file_id>.pdf'); path absolut / '..'
    ditolak agar tidak bisa keluar dari root."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or storage_root()

    def _resolve(self, key: str) -> Path:
        raw_key = (key or "").replace("\\", "/")
        if raw_key.startswith("/") or not raw_key.strip("/"):
            raise ValueError("Storage key tidak valid")
        k = raw_key.strip("/")
        if ".." in k.split("/"):
            raise ValueError("Storage key tidak valid")
        raw = k.split("/")
        parts = [sanitize_component(p) for p in raw[:-1]]
        last = raw[-1]
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,8}", last):
            raise ValueError("Storage key tidak valid")
        parts.append(last.lower())
        if any(not p for p in parts):
            raise ValueError("Storage key tidak valid")
        full = self.root.joinpath(*parts).resolve()
        if full != self.root.resolve() and self.root.resolve() not in full.parents:
            raise ValueError("Storage key di luar root")
        return full

    def save(self, key: str, data: bytes) -> int:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, target)  # atomic pada filesystem yang sama
        return len(data)

    def open(self, key: str) -> Tuple[bytes, None]:
        target = self._resolve(key)
        if not target.is_file():
            raise FileNotFoundError(f"File tidak ditemukan: {key}")
        with open(target, "rb") as f:
            return f.read(), None

    def delete(self, key: str) -> bool:
        try:
            target = self._resolve(key)
        except ValueError:
            return False
        try:
            target.unlink()
            return True
        except FileNotFoundError:
            return False

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except ValueError:
            return False


storage: DocumentStorage = LocalDocumentStorage()
