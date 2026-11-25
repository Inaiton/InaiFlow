"""Application settings (pydantic-settings). Read once via ``get_settings()``."""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-insecure-secret-change-me-0123456789abcdef"  # noqa: S105 - dev default only
DEV_ADMIN_SECRET = "dev-insecure-admin-secret-change-me-0123456789"  # noqa: S105
DEV_CRON_SECRET = "dev-cron-secret"  # noqa: S105
# Valid Fernet key (32 url-safe base64 bytes) for development only.
DEV_FERNET_KEY = base64.urlsafe_b64encode(b"inaiflow-dev-mfa-key-not-secret!").decode()

_DEFAULT_SECRETS = {DEV_SECRET, DEV_ADMIN_SECRET, DEV_CRON_SECRET, DEV_FERNET_KEY}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://inaiflow_owner:inaiflow_owner@localhost:5432/inaiflow_dev"
    DATABASE_URL_MIGRATIONS: str | None = None
    DB_NULLPOOL: bool = False
    DB_POOL_SIZE: int = 5

    JWT_SECRET: str = DEV_SECRET
    ADMIN_JWT_SECRET: str = DEV_ADMIN_SECRET
    MFA_ENCRYPTION_KEY: str = DEV_FERNET_KEY
    CRON_SECRET: str = DEV_CRON_SECRET

    ACCESS_TOKEN_TTL_SECONDS: int = 15 * 60
    MFA_TOKEN_TTL_SECONDS: int = 5 * 60
    REFRESH_TTL_DAYS: int = 14
    REFRESH_TTL_REMEMBER_DAYS: int = 30
    COOKIE_SECURE: bool | None = None  # None -> secure unless development/test

    # argon2id cost (production values per plan; tests may lower them)
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_KIB: int = 64 * 1024
    ARGON2_PARALLELISM: int = 1

    CORS_ORIGINS: str = ""
    PUBLIC_USER_WEB_URL: str = "http://localhost:3000"
    PUBLIC_ADMIN_WEB_URL: str = "http://localhost:3001"
    PUBLIC_API_URL: str = ""  # optional absolute base for links the API generates (local storage URLs)

    STORAGE_PROVIDER: Literal["supabase", "local"] = "local"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    STORAGE_BUCKET: str = "inaiflow-private"
    LOCAL_STORAGE_DIR: str = Field(
        default_factory=lambda: os.path.join(os.path.dirname(__file__), "..", "..", ".local-storage")
    )

    EMAIL_PROVIDER: Literal["console", "resend"] = "console"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "InaiFlow <no-reply@inaiflow.local>"

    TAX_GATEWAY: Literal["mock", "sandbox"] = "mock"
    GSP_CLIENT_ID: str = ""
    GSP_CLIENT_SECRET: str = ""

    ADMIN_IP_ALLOWLIST: str = ""
    TRUST_PROXY_HEADERS: bool = False  # trust X-Forwarded-For (always on for Vercel)

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    VERCEL: str = ""

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cookie_secure(self) -> bool:
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.APP_ENV == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def admin_ip_allowlist(self) -> list[str]:
        return [c.strip() for c in self.ADMIN_IP_ALLOWLIST.split(",") if c.strip()]

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def trust_proxy_headers(self) -> bool:
        return self.TRUST_PROXY_HEADERS or bool(self.VERCEL)

    @property
    def use_nullpool(self) -> bool:
        return self.DB_NULLPOOL or bool(self.VERCEL)

    @model_validator(mode="after")
    def _refuse_weak_production(self) -> Settings:
        if not self.is_production:
            return self
        problems: list[str] = []
        for name in ("JWT_SECRET", "ADMIN_JWT_SECRET", "CRON_SECRET", "MFA_ENCRYPTION_KEY"):
            value = getattr(self, name)
            if value in _DEFAULT_SECRETS or len(value.encode()) < 32:
                problems.append(f"{name} must be a non-default secret of at least 32 bytes")
        if self.JWT_SECRET == self.ADMIN_JWT_SECRET:
            problems.append("JWT_SECRET and ADMIN_JWT_SECRET must differ")
        if self.EMAIL_PROVIDER != "resend" or not self.RESEND_API_KEY:
            problems.append("EMAIL_PROVIDER=resend with RESEND_API_KEY is required (console email logs OTP codes)")
        if self.STORAGE_PROVIDER == "local":
            problems.append("STORAGE_PROVIDER=local is not allowed in production")
        if self.STORAGE_PROVIDER == "supabase" and not (self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY):
            problems.append("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for supabase storage")
        try:
            from cryptography.fernet import Fernet

            Fernet(self.MFA_ENCRYPTION_KEY.encode())
        except Exception:
            problems.append("MFA_ENCRYPTION_KEY must be a valid Fernet key")
        if problems:
            raise ValueError("Refusing to start in production: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
