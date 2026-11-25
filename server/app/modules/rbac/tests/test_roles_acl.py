from app.core.db import get_sessionmaker, set_tenant_scope
from app.core.deps import acl_list_filter, assert_resource_access, filter_accessible, resource_level
from app.core.errors import NotFoundError, PermissionDeniedError
from tests import factories as f

API = f.API


async def test_role_crud(client, owner):
    h = owner.headers
    roles = (await client.get(f"{API}/organization/roles", headers=h)).json()
    assert len(roles) == 6 and next(r for r in roles if r["role_code"] == "ORG_OWNER")["member_count"] == 1
    body = {
        "role_code": "STORE_KEEPER",
        "role_name": "Store Keeper",
        "permissions": {"accounts.inventory_masters": "WRITE"},
    }
    r = await client.post(f"{API}/organization/roles", json=body, headers=h)
    assert r.status_code == 201 and r.json()["permissions"]["accounts.inventory_masters"] == "WRITE"
    assert r.json()["permissions"]["accounts.vouchers"] == "NONE" and len(r.json()["permissions"]) == 27
    assert (await client.post(f"{API}/organization/roles", json=body, headers=h)).status_code == 409
    bad = {**body, "role_code": "X_BAD", "permissions": {"accounts.nope": "READ"}}
    assert (await client.post(f"{API}/organization/roles", json=bad, headers=h)).status_code == 400
    reserved = {**body, "role_code": "ADMIN"}
    assert (await client.post(f"{API}/organization/roles", json=reserved, headers=h)).status_code == 400
    rid = r.json()["id"]
    up = await client.patch(
        f"{API}/organization/roles/{rid}", json={"permissions": {"accounts.reports": "READ"}}, headers=h
    )
    assert (
        up.json()["permissions"]["accounts.reports"] == "READ"
        and up.json()["permissions"]["accounts.inventory_masters"] == "WRITE"
    )
    owner_role = next(x for x in roles if x["role_code"] == "ORG_OWNER")["id"]
    assert (
        await client.patch(f"{API}/organization/roles/{owner_role}", json={"role_name": "x"}, headers=h)
    ).status_code == 409
    admin_role = next(x for x in roles if x["role_code"] == "ADMIN")["id"]
    assert (await client.delete(f"{API}/organization/roles/{admin_role}", headers=h)).status_code == 409
    member = await f.add_member(owner.org_id, "STORE_KEEPER")
    assert (await client.delete(f"{API}/organization/roles/{rid}", headers=h)).status_code == 409
    ctx = (await client.get(f"{API}/org/context", headers=member.headers)).json()
    assert ctx["permissions"]["accounts.reports"] == "READ"
    await client.delete(f"{API}/organization/members/{member.membership_id}", headers=h)
    assert (await client.delete(f"{API}/organization/roles/{rid}", headers=h)).status_code == 204


async def test_acl_put_list_delete(client, owner):
    h = owner.headers
    folder = (await f.sql("SELECT id FROM doc_folders WHERE org_id=:o AND system_kind='MASTER_SOP'", o=owner.org_id))[
        0
    ][0]
    godown = (await f.sql("SELECT id FROM godowns WHERE org_id=:o AND system_code='SCRAP'", o=owner.org_id))[0][0]
    op_role = await f.role_id(owner.org_id, "OPERATOR")
    r = await client.put(f"{API}/organization/acl", json={"subject_type": "ROLE", "subject_id": str(op_role), "resource_type": "DOC_FOLDER",
                                                         "resource_id": str(folder), "access_level": "READ"}, headers=h)  # fmt: skip
    assert r.status_code == 200 and r.json()["subject_name"] == "Shop-floor Operator"
    r2 = await client.put(f"{API}/organization/acl", json={"subject_type": "ROLE", "subject_id": str(op_role), "resource_type": "DOC_FOLDER",
                                                          "resource_id": str(folder), "access_level": "NONE"}, headers=h)  # fmt: skip
    assert r2.json()["id"] == r.json()["id"] and r2.json()["access_level"] == "NONE"
    g = await client.put(f"{API}/organization/acl", json={"subject_type": "ROLE", "subject_id": str(op_role), "resource_type": "GODOWN",
                                                         "resource_id": str(godown), "access_level": "WRITE"}, headers=h)  # fmt: skip
    assert g.json()["resource_name"] == "Scrap Yard"
    other = await f.org_with_owner(client)
    foreign = (await f.sql("SELECT id FROM doc_folders WHERE org_id=:o LIMIT 1", o=other.org_id))[0][0]
    nf = await client.put(f"{API}/organization/acl", json={"subject_type": "ROLE", "subject_id": str(op_role), "resource_type": "DOC_FOLDER",
                                                          "resource_id": str(foreign), "access_level": "READ"}, headers=h)  # fmt: skip
    assert nf.status_code == 404
    listed = (await client.get(f"{API}/organization/acl", params={"resource_type": "GODOWN"}, headers=h)).json()
    assert [x["id"] for x in listed] == [g.json()["id"]]
    assert (await client.delete(f"{API}/organization/acl/{g.json()['id']}", headers=h)).status_code == 204


async def _ctx(client, actor):
    """Build the TenantContext the API would build (via the real dependency)."""
    from starlette.requests import Request

    from app.core.deps import get_principal, get_tenant_context

    scope = {"type": "http", "method": "GET", "path": "/", "headers": [(k.lower().encode(), v.encode()) for k, v in actor.headers.items()],
             "client": ("10.0.0.1", 1)}  # fmt: skip
    req = Request(scope)
    async with get_sessionmaker()() as s:
        principal = await get_principal(req, s)
        return await get_tenant_context(req, principal, s)


async def test_acl_semantics_user_beats_role_and_owner_full(client, owner):
    oid = owner.org_id
    folders = [
        r[0]
        for r in await f.sql(
            "SELECT id FROM doc_folders WHERE org_id=:o AND system_kind LIKE 'MASTER_%' ORDER BY name", o=oid
        )
    ]
    a, b, c = folders[:3]
    op = await f.add_member(oid, "OPERATOR")  # documents.explorer READ
    op_role = await f.role_id(oid, "OPERATOR")
    await f.sql("INSERT INTO resource_acl (org_id, subject_type, subject_id, resource_type, resource_id, access_level) VALUES "
                "(:o,'ROLE',:r,'DOC_FOLDER',:a,'NONE'), (:o,'ROLE',:r,'DOC_FOLDER',:b,'NONE'), (:o,'USER',:u,'DOC_FOLDER',:b,'FULL'), "
                "(:o,'ROLE',:r,'DOC_FOLDER',:c,'WRITE')", o=oid, r=op_role, u=op.user_id, a=a, b=b, c=c)  # fmt: skip
    ctx = await _ctx(client, op)
    owner_ctx = await _ctx(client, owner)
    async with get_sessionmaker()() as s, s.begin():
        await set_tenant_scope(s, oid, op.user_id)
        key = "documents.explorer"
        assert await resource_level(ctx, s, "DOC_FOLDER", a, key) == "NONE"  # role override lowers
        assert await resource_level(ctx, s, "DOC_FOLDER", b, key) == "FULL"  # user beats role
        assert await resource_level(ctx, s, "DOC_FOLDER", c, key) == "WRITE"  # role raises
        assert await resource_level(ctx, s, "DOC_FOLDER", folders[3], key) == "READ"  # module level
        assert await resource_level(owner_ctx, s, "DOC_FOLDER", a, key) == "FULL"
        try:
            await assert_resource_access(ctx, s, "DOC_FOLDER", a, key)
            raise AssertionError("expected NOT_FOUND")
        except NotFoundError:
            pass
        try:
            await assert_resource_access(ctx, s, "DOC_FOLDER", folders[3], key, "WRITE")
            raise AssertionError("expected PERMISSION_DENIED")
        except PermissionDeniedError:
            pass
        assert set(await filter_accessible(ctx, s, "DOC_FOLDER", folders, key)) == set(folders) - {a}
        flt = await acl_list_filter(ctx, s, "DOC_FOLDER", key)
        assert not flt.visible(a) and flt.visible(b) and flt.visible(folders[3])
        from sqlalchemy import text

        visible = await s.execute(text("SELECT id FROM doc_folders").columns())
        assert len(visible.all()) >= 4


async def test_require_with_acl_resource_admits_grant_holders(client, owner):
    import httpx
    from fastapi import APIRouter, Depends

    from app.core.deps import require
    from app.main import create_app

    router = APIRouter()

    @router.get("/acl-probe")
    async def probe(ctx=Depends(require("documents.templates", "READ", acl_resource="DOC_FOLDER"))):  # noqa: ANN001,B008
        return {"ok": True}

    app = create_app()
    app.include_router(router, prefix="/api/v1")
    op = await f.add_member(owner.org_id, "OPERATOR")  # documents.templates NONE
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/acl-probe", headers=op.headers)).status_code == 403
        folder = (await f.sql("SELECT id FROM doc_folders WHERE org_id=:o LIMIT 1", o=owner.org_id))[0][0]
        await f.sql("INSERT INTO resource_acl (org_id, subject_type, subject_id, resource_type, resource_id, access_level) "
                    "VALUES (:o,'USER',:u,'DOC_FOLDER',:f,'READ')", o=owner.org_id, u=op.user_id, f=folder)  # fmt: skip
        assert (await c.get("/api/v1/acl-probe", headers=op.headers)).status_code == 200


async def test_admin_cannot_raise_own_role_permissions(client, owner):
    admin = await f.add_member(owner.org_id, "ADMIN")
    roles = (await client.get(f"{API}/organization/roles", headers=admin.headers)).json()
    admin_role = next(x for x in roles if x["role_code"] == "ADMIN")["id"]
    r = await client.patch(f"{API}/organization/roles/{admin_role}", json={"permissions": {"organization.billing": "FULL"}},
                           headers=admin.headers)  # fmt: skip
    assert r.status_code == 403
    r = await client.patch(f"{API}/organization/roles/{admin_role}", json={"permissions": {"organization.billing": "FULL"}},
                           headers=owner.headers)  # fmt: skip
    assert r.status_code == 200
