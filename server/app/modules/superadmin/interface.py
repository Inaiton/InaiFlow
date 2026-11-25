"""Public API of the superadmin module. S5 extends this file.

Config access is effective-dated and lives in ``platform.interface.get_config`` (re-exported here per plan §3.6).
``write_platform_audit`` is the helper every admin mutation must call.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import to_jsonable
from app.core.context import AdminPrincipal
from app.modules.platform.interface import get_config, list_configs
from app.modules.superadmin.template_tokens import TEMPLATE_TOKENS, TemplateToken


async def write_platform_audit(
    db: AsyncSession, admin: AdminPrincipal | None, action: str, target_type: str, target_id: uuid.UUID | None,
    before: Any = None, after: Any = None,
) -> None:  # fmt: skip
    await db.execute(
        text(
            "INSERT INTO platform_audit_logs (superadmin_id, action, target_type, target_id, before_state, "
            "after_state, ip_address) VALUES (:aid, :action, :tt, :tid, CAST(:b AS jsonb), CAST(:a AS jsonb), "
            "CAST(:ip AS inet))"
        ),
        {
            "aid": admin.admin_id if admin else None,
            "action": action,
            "tt": target_type,
            "tid": target_id,
            "b": None if before is None else json.dumps(to_jsonable(before)),
            "a": None if after is None else json.dumps(to_jsonable(after)),
            "ip": admin.ip if admin and admin.ip else None,
        },  # fmt: skip
    )


#: Report template token catalogue (``TemplateToken(token, label, group, sample)``) — documents should reuse it
#: for ``GET /documents/template-tokens`` so both endpoints stay identical.
__all__ = ["TEMPLATE_TOKENS", "TemplateToken", "get_config", "list_configs", "write_platform_audit"]
