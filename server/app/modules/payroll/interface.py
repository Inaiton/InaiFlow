"""Public API of the payroll module (binding signatures, plan §3.6). S3 extends this file."""

from __future__ import annotations

from app.modules.payroll.seeding import seed_org_payroll

__all__ = ["seed_org_payroll"]
