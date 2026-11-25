"""Pure folder rules: name validation and move-cycle detection."""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable
from typing import TypeVar

K = TypeVar("K", bound=Hashable)
_BAD = re.compile(r"[/\\\x00-\x1f]")


def validate_folder_name(name: str | None) -> str | None:
    """Trimmed name, or None when it is empty, too long, '.'/'..' or contains slashes/control chars."""
    if name is None:
        return None
    n = name.strip()
    if not n or len(n) > 200 or n in (".", "..") or _BAD.search(n):
        return None
    return n


def would_create_cycle[K: Hashable](folder_id: K, new_parent_id: K | None, parent_of: Callable[[K], K | None]) -> bool:
    """True when moving ``folder_id`` under ``new_parent_id`` makes it its own ancestor."""
    cur, hops = new_parent_id, 0
    while cur is not None and hops < 10_000:
        if cur == folder_id:
            return True
        cur, hops = parent_of(cur), hops + 1
    return False
