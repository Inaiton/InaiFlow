import pytest

from app.core.permissions import (
    ALL_PERMISSION_KEYS,
    at_least,
    effective_level,
    effective_permissions,
    impersonation_permissions,
    max_level,
    resolve_resource_level,
    validate_permission_map,
)


def test_catalog_has_all_27_keys():
    assert len(ALL_PERMISSION_KEYS) == 27
    assert "accounts.vouchers" in ALL_PERMISSION_KEYS
    assert "organization.billing" in ALL_PERMISSION_KEYS
    assert "documents.iso_approval" in ALL_PERMISSION_KEYS


@pytest.mark.parametrize(
    ("have", "need", "ok"),
    [
        ("NONE", "READ", False),
        ("READ", "READ", True),
        ("WRITE", "READ", True),
        ("READ", "WRITE", False),
        ("FULL", "WRITE", True),
        ("WRITE", "FULL", False),
        ("NONE", "NONE", True),
    ],
)
def test_level_ordering(have, need, ok):
    assert at_least(have, need) is ok


def test_effective_permissions_fills_missing_with_none_and_drops_unknown():
    perms = effective_permissions({"accounts.vouchers": "WRITE", "bogus.key": "FULL"}, is_owner=False)
    assert perms["accounts.vouchers"] == "WRITE"
    assert perms["accounts.reports"] == "NONE"
    assert "bogus.key" not in perms
    assert set(perms) == set(ALL_PERMISSION_KEYS)


def test_invalid_level_values_are_treated_as_none():
    perms = effective_permissions({"accounts.vouchers": "ADMIN"}, is_owner=False)
    assert perms["accounts.vouchers"] == "NONE"


def test_owner_is_always_full():
    perms = effective_permissions({"accounts.vouchers": "NONE"}, is_owner=True)
    assert set(perms.values()) == {"FULL"}
    assert effective_level({}, "operations.workflows", is_owner=True) == "FULL"


def test_effective_level_missing_key_is_none():
    assert effective_level({}, "operations.workflows", is_owner=False) == "NONE"


def test_resource_user_override_beats_role_override():
    assert resolve_resource_level("READ", user_override="NONE", role_override="FULL", is_owner=False) == "NONE"
    assert resolve_resource_level("NONE", user_override="WRITE", role_override=None, is_owner=False) == "WRITE"


def test_resource_role_override_replaces_module_level_both_directions():
    assert resolve_resource_level("FULL", user_override=None, role_override="READ", is_owner=False) == "READ"
    assert resolve_resource_level("NONE", user_override=None, role_override="READ", is_owner=False) == "READ"


def test_resource_without_override_uses_module_level():
    assert resolve_resource_level("WRITE", user_override=None, role_override=None, is_owner=False) == "WRITE"


def test_resource_owner_always_full():
    assert resolve_resource_level("NONE", user_override="NONE", role_override="NONE", is_owner=True) == "FULL"


def test_impersonation_modes():
    ro = impersonation_permissions("READ_ONLY")
    assert set(ro.values()) == {"READ"}
    full = impersonation_permissions("FULL_SUPPORT")
    assert full["accounts.vouchers"] == "FULL"
    for key in ("organization.billing", "organization.roles_rbac", "organization.members"):
        assert full[key] == "READ"


def test_validate_permission_map():
    assert validate_permission_map({"accounts.vouchers": "READ"}) == {"accounts.vouchers": "READ"}
    with pytest.raises(ValueError):
        validate_permission_map({"nope": "READ"})
    with pytest.raises(ValueError):
        validate_permission_map({"accounts.vouchers": "SUPER"})


def test_max_level():
    assert max_level(["READ", "NONE", "WRITE"]) == "WRITE"
    assert max_level([]) == "NONE"
