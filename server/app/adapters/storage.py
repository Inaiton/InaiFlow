"""Object storage behind ``StorageProvider`` (Supabase Storage in prod, local files in dev/test).

Keys: ``org/{org_id}/{yyyy}/{mm}/{uuid}/{sanitized_name}`` (use ``build_org_key``) or
``users/{user_id}/{purpose}/{uuid}/{name}`` for personal files. Never expose public URLs: issue short-lived
signed URLs only after RBAC checks.
"""

from __future__ import annotations

import abc
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.core.errors import FileTooLargeError, InternalError, UnsupportedMediaError
from app.core.security import decode_signed_payload, encode_signed_payload

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DOWNLOAD_TTL = timedelta(minutes=5)
UPLOAD_TTL = timedelta(minutes=15)

DOCUMENT_MIME_ALLOWLIST = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/heic",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/plain",
    }
)
IMAGE_MIME_ALLOWLIST = frozenset({"image/png", "image/jpeg", "image/webp"})


@dataclass(frozen=True, slots=True)
class UploadTicket:
    upload_url: str
    method: str
    headers: dict[str, str]
    storage_key: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SignedUrl:
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    size: int
    content_type: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def sanitize_name(name: str, max_len: int = 120) -> str:
    base = Path(name or "file").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "file"
    if len(cleaned) > max_len:
        stem, dot, ext = cleaned.rpartition(".")
        cleaned = (stem[: max_len - len(ext) - 1] + "." + ext) if dot and len(ext) < 10 else cleaned[:max_len]
    return cleaned


def build_org_key(org_id: uuid.UUID, file_name: str, on: date | None = None) -> str:
    d = on or datetime.now(UTC).date()
    return f"org/{org_id}/{d.year:04d}/{d.month:02d}/{uuid.uuid4()}/{sanitize_name(file_name)}"


def build_user_key(user_id: uuid.UUID, purpose: str, file_name: str) -> str:
    return f"users/{user_id}/{purpose.lower()}/{uuid.uuid4()}/{sanitize_name(file_name)}"


def validate_upload(content_type: str, size_bytes: int, allow: frozenset[str] = DOCUMENT_MIME_ALLOWLIST,
                    max_bytes: int = MAX_UPLOAD_BYTES) -> None:  # fmt: skip
    if size_bytes <= 0 or size_bytes > max_bytes:
        raise FileTooLargeError(details={"max_bytes": max_bytes})
    if content_type.split(";")[0].strip().lower() not in allow:
        raise UnsupportedMediaError(details={"allowed": sorted(allow)})


class StorageProvider(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def create_upload_ticket(
        self, key: str, content_type: str, size: int, expires: timedelta = UPLOAD_TTL
    ) -> UploadTicket: ...

    @abc.abstractmethod
    async def create_download_url(
        self, key: str, expires: timedelta = DOWNLOAD_TTL, filename: str | None = None
    ) -> SignedUrl: ...

    @abc.abstractmethod
    async def head(self, key: str) -> ObjectInfo | None: ...

    @abc.abstractmethod
    async def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    @abc.abstractmethod
    async def get_bytes(self, key: str) -> bytes: ...

    @abc.abstractmethod
    async def delete(self, key: str) -> None: ...

    async def health(self) -> str:
        return "ok"


# ---------------------------------------------------------------- local (dev/test only)
class LocalStorage(StorageProvider):
    """Files under ``LOCAL_STORAGE_DIR``; URLs point at the dev-only ``/api/v1/storage/local/{token}`` routes."""

    name = "local"

    def __init__(self, root: str | Path, base_url: str = "") -> None:
        self.root = Path(root).resolve()
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise InternalError("invalid storage key")
        return p

    def _url(self, token: str) -> str:
        return f"{self.base_url}/api/v1/storage/local/{token}"

    async def create_upload_ticket(self, key, content_type, size, expires=UPLOAD_TTL):  # type: ignore[override]
        token = encode_signed_payload(
            {"op": "put", "key": key, "ct": content_type, "max": size},
            ttl_seconds=int(expires.total_seconds()),
            purpose="storage",
        )
        return UploadTicket(self._url(token), "PUT", {"Content-Type": content_type}, key,
                            datetime.now(UTC) + expires)  # fmt: skip

    async def create_download_url(self, key, expires=DOWNLOAD_TTL, filename=None):  # type: ignore[override]
        token = encode_signed_payload(
            {"op": "get", "key": key, "fn": filename}, ttl_seconds=int(expires.total_seconds()), purpose="storage"
        )
        return SignedUrl(self._url(token), datetime.now(UTC) + expires)

    def verify_token(self, token: str, op: str) -> dict:
        payload = decode_signed_payload(token, purpose="storage")
        if payload.get("op") != op:
            raise InternalError("invalid storage token")
        return payload

    async def head(self, key: str) -> ObjectInfo | None:
        p = self._path(key)
        if not p.is_file():
            return None
        meta = p.with_name(p.name + ".ctype")
        return ObjectInfo(p.stat().st_size, meta.read_text() if meta.exists() else None)

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        p.with_name(p.name + ".ctype").write_text(content_type or "application/octet-stream")

    async def get_bytes(self, key: str) -> bytes:
        p = self._path(key)
        if not p.is_file():
            raise FileNotFoundError(key)
        return p.read_bytes()

    async def delete(self, key: str) -> None:
        p = self._path(key)
        p.unlink(missing_ok=True)
        p.with_name(p.name + ".ctype").unlink(missing_ok=True)


# ---------------------------------------------------------------- Supabase Storage REST
class SupabaseStorage(StorageProvider):
    name = "supabase"

    def __init__(self, url: str, service_key: str, bucket: str, client: httpx.AsyncClient | None = None) -> None:
        self.base = url.rstrip("/") + "/storage/v1"
        self.bucket = bucket
        self.headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        self._client = client

    def _client_or_new(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=20)

    async def _request(self, method: str, path: str, **kw: object) -> httpx.Response:
        client = self._client_or_new()
        try:
            resp = await client.request(
                method, self.base + path, headers={**self.headers, **kw.pop("headers", {})}, **kw
            )  # type: ignore[arg-type]
        finally:
            if self._client is None:
                await client.aclose()
        return resp

    @staticmethod
    def _q(key: str) -> str:
        return quote(key, safe="/")

    async def create_upload_ticket(self, key, content_type, size, expires=UPLOAD_TTL):  # type: ignore[override]
        resp = await self._request("POST", f"/object/upload/sign/{self.bucket}/{self._q(key)}")
        if resp.status_code >= 400:
            raise InternalError("storage: could not create upload URL")
        url = resp.json()["url"]
        # Supabase signed upload URLs are valid for 2 hours; we advertise our shorter TTL.
        return UploadTicket(self.base + url, "PUT", {"Content-Type": content_type, "x-upsert": "false"}, key,
                            datetime.now(UTC) + expires)  # fmt: skip

    async def create_download_url(self, key, expires=DOWNLOAD_TTL, filename=None):  # type: ignore[override]
        resp = await self._request(
            "POST", f"/object/sign/{self.bucket}/{self._q(key)}", json={"expiresIn": int(expires.total_seconds())}
        )
        if resp.status_code >= 400:
            raise InternalError("storage: could not create download URL")
        url = self.base + resp.json()["signedURL"]
        if filename:
            url += ("&" if "?" in url else "?") + "download=" + quote(filename)
        return SignedUrl(url, datetime.now(UTC) + expires)

    async def head(self, key: str) -> ObjectInfo | None:
        resp = await self._request("GET", f"/object/info/{self.bucket}/{self._q(key)}")
        if resp.status_code == 404 or resp.status_code == 400:
            return None
        if resp.status_code >= 400:
            raise InternalError("storage: head failed")
        data = resp.json()
        size = data.get("size") or (data.get("metadata") or {}).get("size") or 0
        ctype = data.get("content_type") or (data.get("metadata") or {}).get("mimetype")
        return ObjectInfo(int(size), ctype)

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        resp = await self._request(
            "POST", f"/object/{self.bucket}/{self._q(key)}", content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )  # fmt: skip
        if resp.status_code >= 400:
            raise InternalError("storage: upload failed")

    async def get_bytes(self, key: str) -> bytes:
        resp = await self._request("GET", f"/object/authenticated/{self.bucket}/{self._q(key)}")
        if resp.status_code == 404:
            raise FileNotFoundError(key)
        if resp.status_code >= 400:
            raise InternalError("storage: download failed")
        return resp.content

    async def delete(self, key: str) -> None:
        resp = await self._request("DELETE", f"/object/{self.bucket}", json={"prefixes": [key]})
        if resp.status_code >= 400 and resp.status_code != 404:
            raise InternalError("storage: delete failed")

    async def health(self) -> str:
        try:
            resp = await self._request("GET", f"/bucket/{self.bucket}")
            return "ok" if resp.status_code < 400 else f"error:{resp.status_code}"
        except httpx.HTTPError:
            return "unreachable"


@lru_cache
def get_storage() -> StorageProvider:
    s = get_settings()
    if s.STORAGE_PROVIDER == "supabase":
        return SupabaseStorage(s.SUPABASE_URL, s.SUPABASE_SERVICE_ROLE_KEY, s.STORAGE_BUCKET)
    return LocalStorage(s.LOCAL_STORAGE_DIR, s.PUBLIC_API_URL)
