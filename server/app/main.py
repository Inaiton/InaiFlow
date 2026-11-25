"""FastAPI application factory."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute, iter_route_contexts

from app.core.config import get_settings
from app.core.deps import guard_of
from app.core.errors import install_exception_handlers
from app.core.idempotency import install_idempotency_handler
from app.core.middleware import RequestContextMiddleware, configure_logging
from app.modules.identity.router import auth_router, me_router
from app.modules.organization.router import personal_router as org_personal_router
from app.modules.organization.router import router as organization_router
from app.modules.platform.router import router as platform_router
from app.modules.rbac.router import router as rbac_router

API_PREFIX = "/api/v1"

# Routers in registration order. Module streams append theirs here (one line each).
ROUTERS = [
    platform_router,
    auth_router,
    me_router,
    org_personal_router,
    organization_router,
    rbac_router,
]


def _optional_routers() -> list:
    """Routers of streams S2–S5, included when their module provides ``router.py`` with ``router``."""
    import importlib

    found = []
    for name in ("accounts", "taxation", "payroll", "operations", "documents", "superadmin"):
        try:
            mod = importlib.import_module(f"app.modules.{name}.router")
        except ModuleNotFoundError as exc:
            if exc.name != f"app.modules.{name}.router":
                raise
            continue
        for attr in ("router", "routers"):
            value = getattr(mod, attr, None)
            if value is not None:
                found.extend(value if isinstance(value, list | tuple) else [value])
    return found


def route_guard(route: APIRoute) -> tuple[str, str | None, list[str] | None]:
    """(auth, permission, admin_roles) found by walking the route's dependency tree."""
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop(0)
        g = guard_of(dep.call)
        if g:
            return g
        stack.extend(dep.dependencies)
    return "public", None, None


def _annotate_router(router: APIRouter) -> None:
    """Expose guard metadata as ``x-auth`` / ``x-permission`` like the contract."""
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        auth, perm, roles = route_guard(route)
        extra = dict(route.openapi_extra or {})
        extra["x-auth"] = auth
        if perm:
            extra["x-permission"] = perm
        if roles:
            extra["x-admin-roles"] = roles
        route.openapi_extra = extra


def iter_api_routes(app: FastAPI) -> list[tuple[str, set[str], APIRoute]]:
    """Flattened (full path, methods, APIRoute) — FastAPI >= 0.160 keeps included routers nested."""
    out = []
    for rc in iter_route_contexts(app.routes):
        route = rc.original_route
        if isinstance(route, APIRoute) and rc.path:
            out.append((rc.path, set(route.methods or ()), route))
    return out


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.LOG_LEVEL)
    app = FastAPI(
        title="InaiFlow API",
        version=s.APP_VERSION,
        openapi_url="/openapi.json",
        docs_url=None if s.is_production else "/docs",
        redoc_url=None,
    )
    install_exception_handlers(app)
    install_idempotency_handler(app)
    for r in [*ROUTERS, *_optional_routers()]:
        _annotate_router(r)
        app.include_router(r, prefix=API_PREFIX)
    if s.cors_origins and not s.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=s.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
