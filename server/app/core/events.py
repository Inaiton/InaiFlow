"""Tiny in-process synchronous domain events (same transaction as the publisher).

    @subscribe("operations.run_created")
    async def on_run_created(db, ctx, payload): ...

    await publish(db, ctx, "operations.run_created", {"run_id": ...})

Prefer explicit ``interface.py`` calls for anything the publisher depends on; use events only for optional
side effects. Subscribers register at import time (import them from the module's ``__init__``/router).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[Any, Any, dict[str, Any]], Awaitable[None]]
_handlers: dict[str, list[Handler]] = defaultdict(list)


def subscribe(event: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _handlers[event].append(fn)
        return fn

    return deco


async def publish(db: Any, ctx: Any, event: str, payload: dict[str, Any]) -> None:
    for handler in list(_handlers.get(event, ())):
        await handler(db, ctx, payload)
