"""Operator CLI.

uv run python -m app.cli create-superadmin --email you@x.com --name "You" [--role SUPERADMIN]
uv run python -m app.cli seed-configs        # insert missing platform configs/plans (never overwrites)
uv run python -m app.cli run-cron            # run the daily cron once
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys

from sqlalchemy import text

from app.core.db import get_sessionmaker
from app.core.security import hash_password


async def create_superadmin(email: str, name: str, role: str) -> None:
    password = secrets.token_urlsafe(18)
    async with get_sessionmaker()() as s, s.begin():
        exists = (await s.execute(text("SELECT 1 FROM platform_admins WHERE email = :e"), {"e": email.lower()})).first()
        if exists:
            print(f"admin {email} already exists", file=sys.stderr)
            raise SystemExit(1)
        await s.execute(
            text(
                "INSERT INTO platform_admins (email, password_hash, full_name, role, must_change_password) "
                "VALUES (:e, :h, :n, :r, true)"
            ),
            {"e": email.lower(), "h": await hash_password(password), "n": name, "r": role},
        )
    print(f"Created {role} {email}\nOne-time password: {password}\n(MFA setup is required at first sign-in.)")


async def seed_configs() -> None:
    from app.seeds import PLANS, SEED_EFFECTIVE_FROM, config_rows

    added = 0
    async with get_sessionmaker()() as s, s.begin():
        for p in PLANS:
            await s.execute(
                text(
                    "INSERT INTO platform_subscription_plans (plan_code, name, monthly_price_inr, annual_price_inr, "
                    "max_internal_seats, max_external_collaborators, max_storage_gb, enabled_modules) VALUES "
                    "(:c, :n, CAST(:m AS numeric), CAST(:a AS numeric), :s, :x, :g, CAST(:e AS jsonb)) "
                    "ON CONFLICT (plan_code) DO NOTHING"
                ),
                {
                    "c": p["plan_code"],
                    "n": p["name"],
                    "m": p["monthly_price_inr"],
                    "a": p["annual_price_inr"],
                    "s": p["max_internal_seats"],
                    "x": p["max_external_collaborators"],
                    "g": p["max_storage_gb"],
                    "e": json.dumps(p["enabled_modules"]),
                },  # fmt: skip
            )
        for row in config_rows():
            cid = (
                await s.execute(
                    text(
                        "INSERT INTO platform_global_configs (config_category, config_key, display_name, payload) "
                        "VALUES (:c, :k, :n, CAST(:p AS jsonb)) ON CONFLICT DO NOTHING RETURNING id"
                    ),
                    {"c": row["category"], "k": row["key"], "n": row["name"], "p": json.dumps(row["payload"])},
                )
            ).scalar()
            if cid:
                added += 1
                await s.execute(
                    text(
                        "INSERT INTO platform_global_config_versions (config_id, version, payload, effective_from, "
                        "change_reason) VALUES (:i, 1, CAST(:p AS jsonb), :ef, 'Initial seed')"
                    ),
                    {"i": cid, "p": json.dumps(row["payload"]), "ef": SEED_EFFECTIVE_FROM},
                )
    print(f"seed-configs: {added} new config rows")


async def run_cron() -> None:
    from app.modules.platform.service import run_daily_cron

    async with get_sessionmaker()() as s, s.begin():
        result = await run_daily_cron(s)
    print(result.model_dump_json(indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-superadmin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", default="SUPERADMIN", choices=["SUPERADMIN", "SUPPORT_ADMIN", "BILLING_ADMIN"])
    sub.add_parser("seed-configs")
    sub.add_parser("run-cron")
    args = parser.parse_args(argv)
    if args.cmd == "create-superadmin":
        asyncio.run(create_superadmin(args.email, args.name, args.role))
    elif args.cmd == "seed-configs":
        asyncio.run(seed_configs())
    else:
        asyncio.run(run_cron())


if __name__ == "__main__":
    main()
