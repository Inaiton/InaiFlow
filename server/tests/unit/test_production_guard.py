import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings

STRONG = {
    "APP_ENV": "production",
    "JWT_SECRET": "u" * 40,
    "ADMIN_JWT_SECRET": "a" * 40,
    "CRON_SECRET": "c" * 40,
    "MFA_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "STORAGE_PROVIDER": "supabase",
    "SUPABASE_URL": "https://x.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "k",
    "EMAIL_PROVIDER": "resend",
    "RESEND_API_KEY": "re_x",
}


def test_production_accepts_strong_config(monkeypatch):
    for k, v in STRONG.items():
        monkeypatch.setenv(k, v)
    Settings()


@pytest.mark.parametrize(
    "override", [{"EMAIL_PROVIDER": "console"}, {"RESEND_API_KEY": ""}, {"STORAGE_PROVIDER": "local"}]
)
def test_production_refuses_unsafe_config(monkeypatch, override):
    for k, v in {**STRONG, **override}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError, match="Refusing to start"):
        Settings()
