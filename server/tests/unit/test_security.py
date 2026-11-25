import uuid

import pytest

from app.core import security as sec
from app.core.errors import TokenExpiredError, UnauthenticatedError, ValidationFailedError


def test_password_policy():
    sec.check_password_policy("Correct-Horse-9", "a@b.com")
    for bad in ("short", "1234567890", "qwertyuiop", "x" * 129):
        with pytest.raises(ValidationFailedError):
            sec.check_password_policy(bad, "a@b.com")
    with pytest.raises(ValidationFailedError):
        sec.check_password_policy("someone@example.com", "someone@example.com")


def test_password_hash_roundtrip():
    h = sec.hash_password_sync("Correct-Horse-9")
    assert h.startswith("$argon2id$")
    assert sec.verify_password_sync(h, "Correct-Horse-9")
    assert not sec.verify_password_sync(h, "wrong")
    assert not sec.verify_password_sync(None, "x")


def test_access_token_roundtrip_and_audience_isolation():
    uid, sid = uuid.uuid4(), uuid.uuid4()
    token, ttl = sec.create_access_token(user_id=uid, session_id=sid, email="a@b.com", mfa=True)
    claims = sec.decode_access_token(token)
    assert claims.sub == uid and claims.sid == sid and claims.mfa and ttl == 900
    with pytest.raises(UnauthenticatedError):
        sec.decode_admin_access_token(token)
    admin_token, _ = sec.create_admin_access_token(admin_id=uid, session_id=sid, email="x", role="SUPERADMIN")
    with pytest.raises(UnauthenticatedError):
        sec.decode_access_token(admin_token)


def test_mfa_token_is_not_an_access_token():
    t = sec.create_mfa_token(user_id=uuid.uuid4(), remember=False)
    with pytest.raises(UnauthenticatedError):
        sec.decode_access_token(t)
    assert sec.decode_mfa_token(t)["typ"] == "mfa"


def test_expired_token():
    token, _ = sec.create_access_token(
        user_id=uuid.uuid4(), session_id=uuid.uuid4(), email="", mfa=False, ttl_seconds=-5
    )
    with pytest.raises(TokenExpiredError):
        sec.decode_access_token(token)


def test_refresh_tokens_are_random_and_hashed():
    a, b = sec.new_refresh_token(), sec.new_refresh_token()
    assert a != b and len(a) >= 43
    assert sec.hash_token(a) != a and len(sec.hash_token(a)) == 64


def test_totp_and_fernet():
    secret = sec.new_totp_secret()
    assert sec.verify_totp(secret, sec.current_totp(secret))
    assert not sec.verify_totp(secret, "000000x")
    enc = sec.encrypt_secret(secret)
    assert enc != secret and sec.decrypt_secret(enc) == secret


def test_codes():
    code = sec.new_numeric_code()
    assert len(code) == 6 and code.isdigit()
    assert sec.hash_code("EMAIL_VERIFY", "A@b.com", code) == sec.hash_code("EMAIL_VERIFY", "a@b.com", code)
    assert sec.hash_code("PASSWORD_RESET", "a@b.com", code) != sec.hash_code("EMAIL_VERIFY", "a@b.com", code)
    rc = sec.new_recovery_codes()
    assert len(rc) == 10 and len(set(rc)) == 10
    assert sec.normalize_recovery_code(rc[0].replace("-", "").upper()) == rc[0]


def test_csv_safe_neutralises_formulas_not_numbers():
    from app.core.security import csv_safe

    assert csv_safe('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    assert csv_safe("-12.50") == "-12.50"
    assert csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert csv_safe(5) == 5


def test_totp_code_cannot_be_replayed():
    from types import SimpleNamespace

    from app.core.security import accept_totp, current_totp, encrypt_secret, new_totp_secret

    secret = new_totp_secret()
    holder = SimpleNamespace(mfa_secret=encrypt_secret(secret), mfa_last_step=None)
    code = current_totp(secret)
    assert accept_totp(holder, code) is True
    assert accept_totp(holder, code) is False
