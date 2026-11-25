"""Pytest plugin: env for tests, one Postgres database per stream (``TEST_DATABASE_URL``), migrations once
per session, ASGI client, email outbox.

Each stream uses its own DB: ``TEST_DATABASE_URL=postgresql+asyncpg://inaiflow_owner:inaiflow_owner@localhost:5432/inaiflow_test_s2 uv run pytest``.
``TEST_DB_REUSE=1`` skips drop/create (faster local reruns; migrations still upgrade to head).
Tests never truncate: factories create unique users/orgs, so tests are independent and order-free.
"""

from __future__ import annotations

import os
import random
import tempfile

DEFAULT_TEST_URL = "postgresql+asyncpg://inaiflow_owner:inaiflow_owner@localhost:5432/inaiflow_test_s1"
TEST_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_URL,
        "DATABASE_URL_MIGRATIONS": TEST_URL,
        "DB_NULLPOOL": "1",
        "ARGON2_TIME_COST": "1",
        "ARGON2_MEMORY_KIB": "8192",
        "STORAGE_PROVIDER": "local",
        "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="inaiflow-storage-"),
        "EMAIL_PROVIDER": "console",
        "TAX_GATEWAY": "mock",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "CORS_ORIGINS": "",
        "TRUST_PROXY_HEADERS": "0",
    }
)

import asyncio  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from pathlib import Path  # noqa: E402
from urllib.parse import urlsplit, urlunsplit  # noqa: E402

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

SERVER_DIR = Path(__file__).resolve().parent.parent


async def _recreate_database(url: str) -> None:
    parts = urlsplit(url.replace("+asyncpg", ""))
    name = parts.path.lstrip("/")
    admin_url = urlunsplit(parts._replace(path="/postgres"))
    conn = await asyncpg.connect(admin_url)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_DIR / "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def database() -> str:
    if os.environ.get("TEST_DB_REUSE") != "1":
        asyncio.run(_recreate_database(TEST_URL))
    _migrate()
    return TEST_URL


@pytest.fixture(scope="session")
def app(database: str):  # noqa: ANN201
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client_ip() -> str:
    """A unique IP per test so IP-based rate limits never leak between tests."""
    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


@pytest.fixture
async def client(app, client_ip: str) -> AsyncIterator[httpx.AsyncClient]:  # noqa: ANN001
    transport = httpx.ASGITransport(app=app, client=(client_ip, 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def outbox():  # noqa: ANN201
    from app.adapters.email import ConsoleEmail, get_email

    email = get_email()
    assert isinstance(email, ConsoleEmail)
    email.outbox.clear()
    return email


@pytest.fixture
async def owner(client: httpx.AsyncClient):  # noqa: ANN001,ANN201
    """A verified user who owns a freshly created org (via the real POST /organizations)."""
    from tests import factories

    return await factories.org_with_owner(client)
