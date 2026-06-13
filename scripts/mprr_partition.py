"""File-level conflict model. Pure; duck-types on `.files` (a tuple of paths)."""
from __future__ import annotations

from typing import Any, Iterable


def conflicts(a: Any, b: Any) -> bool:
    """True iff two items share any file (so they may not run concurrently)."""
    return bool(set(a.files) & set(b.files))


def eligible(item: Any, locked_files: Iterable[str]) -> bool:
    """True iff the item's files are disjoint from the currently-locked files."""
    return not (set(item.files) & set(locked_files))
