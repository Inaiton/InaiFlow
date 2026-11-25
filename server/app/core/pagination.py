"""List conventions: ``?limit=50&offset=0`` (limit 1..200) -> ``{items, total, limit, offset}``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class PageParams:
    limit: int = 50
    offset: int = 0


def page_params(limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0) -> PageParams:
    return PageParams(limit, offset)


Paging = Annotated[PageParams, Depends(page_params)]


async def paginate(db: AsyncSession, stmt: Select[Any], params: PageParams) -> tuple[list[Any], int]:
    """Run ``stmt`` with limit/offset and a COUNT(*) over the same filters. Returns (rows, total)."""
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(stmt.limit(params.limit).offset(params.offset))).all()
    return list(rows), int(total)
