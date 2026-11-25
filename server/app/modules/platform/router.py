from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.adapters.storage import sanitize_name
from app.core.deps import DB, require_cron
from app.modules.platform import service
from app.modules.platform.schemas import CronResultOut, HealthOut, PermissionModuleOut, StateOut

router = APIRouter(tags=["platform"])


@router.get("/health", response_model=HealthOut)
async def health(db: DB) -> HealthOut:
    return await service.health(db)


@router.get("/meta/states", response_model=list[StateOut])
async def states(db: DB) -> list[StateOut]:
    return await service.states(db)


@router.get("/meta/permission-keys", response_model=list[PermissionModuleOut])
async def permission_keys() -> list[PermissionModuleOut]:
    return service.permission_keys()


@router.get("/internal/cron/daily", response_model=CronResultOut)
async def cron_daily(_: Annotated[None, Depends(require_cron())], db: DB) -> CronResultOut:
    return await service.run_daily_cron(db)


@router.put("/storage/local/{token}", status_code=status.HTTP_204_NO_CONTENT, tags=["storage"])
async def local_put(token: str, request: Request) -> Response:
    """Raw request body = file bytes (same as a Supabase signed upload URL)."""
    await service.local_put(token, await request.body(), request.headers.get("content-type"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/storage/local/{token}", tags=["storage"], response_class=Response)
async def local_get(token: str) -> Response:
    data, ctype, filename = await service.local_get(token)
    headers = {"Content-Disposition": f'attachment; filename="{sanitize_name(filename)}"'} if filename else {}
    return Response(content=data, media_type=ctype, headers=headers)
