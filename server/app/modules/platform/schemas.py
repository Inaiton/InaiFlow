from __future__ import annotations

from app.core.schemas import OutModel


class HealthOut(OutModel):
    status: str
    version: str
    db: str


class StateOut(OutModel):
    code: str
    name: str


class PermissionKeyOut(OutModel):
    key: str
    label: str
    description: str


class PermissionModuleOut(OutModel):
    module: str
    label: str
    keys: list[PermissionKeyOut]


class CronResultOut(OutModel):
    orgs_processed: int
    folders_created: int
    instruments_updated: int
    invitations_expired: int
    memberships_expired: int
