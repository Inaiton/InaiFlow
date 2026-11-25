"""GST IRP e-invoice / e-way bill gateway behind ``TaxGatewayProvider``.

``MockTaxGateway`` (default) returns deterministic IRN/ack/QR/EWB numbers derived from the input so tests are
stable. ``SandboxIRP`` is a skeleton for a real GSP; it raises ``NotImplementedError`` until credentials and
the GSP client are wired (deferred item 1 of the plan).
"""

from __future__ import annotations

import abc
import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class IrnResult:
    irn: str
    ack_no: str
    ack_date: datetime
    signed_qr: str
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EwayResult:
    eway_bill_no: str
    valid_until: datetime
    raw: dict[str, Any]


class TaxGatewayProvider(abc.ABC):
    name = "abstract"

    @abc.abstractmethod
    async def generate_irn(self, payload: dict[str, Any]) -> IrnResult:
        """``payload`` follows the NIC e-invoice schema (SellerDtls, BuyerDtls, DocDtls{No,Dt}, ItemList...)."""

    @abc.abstractmethod
    async def cancel_irn(self, irn: str, reason_code: str, remarks: str) -> dict[str, Any]: ...

    @abc.abstractmethod
    async def generate_eway_bill(self, payload: dict[str, Any]) -> EwayResult: ...

    async def health(self) -> str:
        return "ok"


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class MockTaxGateway(TaxGatewayProvider):
    name = "mock"

    async def generate_irn(self, payload: dict[str, Any]) -> IrnResult:
        seller = (payload.get("SellerDtls") or {}).get("Gstin", "")
        doc = payload.get("DocDtls") or {}
        irn = hashlib.sha256(
            f"{seller}|{doc.get('Typ', 'INV')}|{doc.get('No', '')}|{doc.get('Dt', '')}".encode()
        ).hexdigest()
        ack_no = str(int(irn[:12], 16))[:15].rjust(15, "1")
        ack_date = datetime(2025, 4, 1, tzinfo=UTC) + timedelta(seconds=int(irn[12:18], 16) % 86400)
        qr = base64.b64encode(
            json.dumps({"Irn": irn, "AckNo": ack_no, "SellerGstin": seller, "DocNo": doc.get("No")}).encode()
        ).decode()
        return IrnResult(irn, ack_no, ack_date, qr, {"mock": True, "Irn": irn, "AckNo": ack_no})

    async def cancel_irn(self, irn: str, reason_code: str, remarks: str) -> dict[str, Any]:
        return {"Irn": irn, "CancelDate": datetime.now(UTC).isoformat(), "mock": True}

    async def generate_eway_bill(self, payload: dict[str, Any]) -> EwayResult:
        d = _digest(payload)
        number = str(int(d[:14], 16))[:12].rjust(12, "1")
        km = int(payload.get("distance_km") or payload.get("Distance") or 100)
        days = max(1, -(-km // 200))  # 1 day per 200 km (rounded up)
        return EwayResult(number, datetime.now(UTC) + timedelta(days=days), {"mock": True, "EwbNo": number})


class SandboxIRP(TaxGatewayProvider):
    name = "sandbox"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id, self.client_secret = client_id, client_secret

    def _require_creds(self) -> None:
        if not (self.client_id and self.client_secret):
            raise NotImplementedError("SandboxIRP needs GSP_CLIENT_ID/GSP_CLIENT_SECRET")
        raise NotImplementedError("SandboxIRP GSP integration is deferred (plan §4 item 1)")

    async def generate_irn(self, payload: dict[str, Any]) -> IrnResult:
        self._require_creds()
        raise AssertionError  # pragma: no cover

    async def cancel_irn(self, irn: str, reason_code: str, remarks: str) -> dict[str, Any]:
        self._require_creds()
        raise AssertionError  # pragma: no cover

    async def generate_eway_bill(self, payload: dict[str, Any]) -> EwayResult:
        self._require_creds()
        raise AssertionError  # pragma: no cover

    async def health(self) -> str:
        return "unconfigured" if not (self.client_id and self.client_secret) else "not_implemented"


@lru_cache
def get_tax_gateway() -> TaxGatewayProvider:
    s = get_settings()
    if s.TAX_GATEWAY == "sandbox":
        return SandboxIRP(s.GSP_CLIENT_ID, s.GSP_CLIENT_SECRET)
    return MockTaxGateway()
