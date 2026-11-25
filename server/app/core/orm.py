"""Column helpers shared by every ``models.py`` (keep the migration and models in lock-step)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

TZ = TIMESTAMP(timezone=True)
MONEY = Numeric(18, 4)
RATE = Numeric(7, 4)


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )


def fk(target: str, *, nullable: bool = True, ondelete: str | None = None, index: bool = True) -> Any:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


def uuid_col(*, nullable: bool = True, index: bool = False) -> Any:
    return mapped_column(UUID(as_uuid=True), nullable=nullable, index=index)


def ts_now() -> Mapped[datetime]:
    return mapped_column(TZ, nullable=False, server_default=func.now())


def ts(*, nullable: bool = True) -> Any:
    return mapped_column(TZ, nullable=nullable)


def money(*, nullable: bool = False, default: str | None = "0") -> Mapped[Decimal]:
    if default is None:
        return mapped_column(MONEY, nullable=nullable)
    return mapped_column(MONEY, nullable=nullable, server_default=text(default))


def flag(default: bool = False) -> Mapped[bool]:
    return mapped_column(Boolean, nullable=False, server_default=text("true" if default else "false"))


def string(length: int, *, nullable: bool = True, default: str | None = None, **kw: Any) -> Any:
    if default is not None:
        return mapped_column(String(length), nullable=nullable, server_default=text(f"'{default}'"), **kw)
    return mapped_column(String(length), nullable=nullable, **kw)


def textcol(*, nullable: bool = True) -> Any:
    return mapped_column(Text, nullable=nullable)


def jsonb(*, nullable: bool = True, default: str | None = None) -> Any:
    if default is not None:
        return mapped_column(JSONB, nullable=nullable, server_default=text(f"'{default}'::jsonb"))
    return mapped_column(JSONB, nullable=nullable)


def integer(*, nullable: bool = False, default: int | None = None) -> Any:
    if default is not None:
        return mapped_column(Integer, nullable=nullable, server_default=text(str(default)))
    return mapped_column(Integer, nullable=nullable)


def inet() -> Any:
    return mapped_column(INET, nullable=True)
