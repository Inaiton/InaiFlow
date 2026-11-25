"""Pydantic base classes. Name schemas exactly like the contract models (``MemberOut``, ``InvitationIn``...)
so the server's ``/openapi.json`` matches ``docs/api/openapi.json``."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class InModel(BaseModel):
    """Request bodies: unknown fields are rejected (contract has additionalProperties: false)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OutModel(BaseModel):
    """Responses: build from ORM rows/objects."""

    model_config = ConfigDict(from_attributes=True)


class OkOut(OutModel):
    ok: bool


# ---- shared contract models (use these; do not redeclare in modules) ----
class UploadTicket(OutModel):
    upload_url: str
    method: str
    headers: dict[str, str]
    storage_key: str
    expires_at: datetime


class UploadRequest(InModel):
    file_name: str
    content_type: str
    size_bytes: int


class SignedUrlOut(OutModel):
    url: str
    expires_at: datetime


class AuditLogOut(OutModel):
    id: uuid.UUID
    module: str
    action: str
    entity_type: str
    entity_id: uuid.UUID
    actor_type: str
    user_id: uuid.UUID | None
    user_name: str | None
    role_code: str
    before_diff: Any | None
    after_diff: Any | None
    reason: str | None
    ip_address: str | None
    created_at: datetime


class ErrorBody(OutModel):
    code: str
    message: str
    details: Any | None


class Error(OutModel):
    error: ErrorBody
