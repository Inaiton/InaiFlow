"""Identical local copies of contract models owned by other modules (used only while those modules do not
export them from their ``interface.py``; identical JSON schemas merge into one OpenAPI component)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel


class BomComponent(InModel):
    raw_item_id: uuid.UUID
    qty_per_unit: DecimalStr
    scrap_pct: DecimalStr


class StockItemIn(InModel):
    target_type: str | None = None
    name: str
    sku_code: str | None = None
    stock_group_id: uuid.UUID | None = None
    uom_primary: str | None = None
    uom_alternate: str | None = None
    uom_conversion_factor: DecimalStr | None = None
    valuation_method: str | None = None
    hsn_sac_code: str | None = None
    gst_rate: DecimalStr | None = None
    opening_qty: DecimalStr | None = None
    opening_rate: DecimalStr | None = None
    reorder_level: DecimalStr | None = None
    diagram_storage_key: str | None = None
    custom_fields: Any | None = None
    bom_components: list[BomComponent] | None = None


class KpiOut(OutModel):
    key: str
    label: str
    value: DecimalStr
    change_pct: DecimalStr | None


class InvitationOut(OutModel):
    id: uuid.UUID
    email: str
    role_id: uuid.UUID
    role_name: str
    status: str
    access_expires_at: datetime | None
    expires_at: datetime
    created_by_name: str | None
    created_at: datetime
