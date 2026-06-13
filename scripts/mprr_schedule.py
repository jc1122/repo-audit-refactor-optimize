"""Continuous saturating scheduler. Pure state machine; the caller injects
dispatch (start) and completion. The disjoint-lock invariant is enforced here.
"""
from __future__ import annotations

from typing import Any


class SaturatingScheduler:
    def __init__(self, items: list[Any], ceiling: int) -> None:
        if ceiling < 1:
            raise ValueError("ceiling must be >= 1")
        # deterministic order: by id
        self._pending: list[Any] = sorted(items, key=lambda it: it.id)
        self._ceiling = ceiling
        self._locked: set[str] = set()
        self._running: dict[str, Any] = {}

    def dispatchable(self) -> list[Any]:
        """Items startable right now: pool has room and files are disjoint from
        current locks AND from each other within this batch."""
        out: list[Any] = []
        locked = set(self._locked)
        for it in self._pending:
            if len(self._running) + len(out) >= self._ceiling:
                break
            if not (set(it.files) & locked):
                out.append(it)
                locked |= set(it.files)
        return out

    def start(self, item: Any) -> None:
        self._pending.remove(item)
        self._running[item.id] = item
        self._locked |= set(item.files)

    def complete(self, item_id: str) -> None:
        item = self._running.pop(item_id)
        # safe: the invariant guarantees no other running item holds these files
        self._locked -= set(item.files)

    def done(self) -> bool:
        return not self._pending and not self._running
