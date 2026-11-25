"""Pure-ASGI middleware: request id + logging context, security headers, no-store for JSON."""

from __future__ import annotations

import contextvars
import logging
import secrets
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
log = logging.getLogger("inaiflow.request")

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-site"),
]


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(isinstance(f, RequestIdFilter) for h in root.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode()[:64]
        rid = incoming if incoming and incoming.replace("-", "").isalnum() else secrets.token_hex(8)
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status: dict[str, Any] = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = list(message.get("headers") or [])
                names = {k.lower() for k, _ in headers}
                headers.append((b"x-request-id", rid.encode()))
                for k, v in SECURITY_HEADERS:
                    if k not in names:
                        headers.append((k, v))
                ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if b"application/json" in ctype and b"cache-control" not in names:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info(
                "%s %s -> %s in %.1fms",
                scope.get("method"),
                scope.get("path"),
                status["code"],
                (time.perf_counter() - started) * 1000,
            )
            request_id_var.reset(token)
