from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schemas import InModel, OutModel

Level = Literal["NONE", "READ", "WRITE", "FULL"]
SubjectType = Literal["ROLE", "USER"]
ResourceType = Literal["STOCK_ITEM", "PERIOD_RUN", "DOC_FOLDER", "GODOWN"]


class RoleOut(OutModel):
    id: uuid.UUID
    role_code: str
    role_name: str
    is_system_role: bool
    is_external_collaborator: bool
    permissions: dict[str, Level]
    member_count: int


class RoleIn(InModel):
    role_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,49}$")
    role_name: str = Field(min_length=1, max_length=100)
    is_external_collaborator: bool = False
    permissions: dict[str, Level]


class RoleUpdateIn(InModel):
    role_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_external_collaborator: bool | None = None
    permissions: dict[str, Level] | None = None


class AclOut(OutModel):
    id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    subject_name: str
    resource_type: str
    resource_id: uuid.UUID
    resource_name: str
    access_level: Level
    created_at: datetime


class AclIn(InModel):
    subject_type: SubjectType
    subject_id: uuid.UUID
    resource_type: ResourceType
    resource_id: uuid.UUID
    access_level: Level
