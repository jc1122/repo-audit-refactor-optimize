"""Merge integration: enforce the disjoint-file invariant at merge time.

A textual conflict during merge is structurally impossible under the scheduler
invariant, so it is treated as a hard error (partitioner/worker bug), not a
normal merge conflict to resolve.
"""

from __future__ import annotations

import subprocess  # nosec B404 — fixed git argv, no shell
from pathlib import Path
from collections.abc import Iterable


class InvariantViolation(RuntimeError):
    """Raised when a merge that must be conflict-free reports a conflict."""


def assert_scope(
    declared_files: Iterable[str], diff_files: Iterable[str]
) -> tuple[bool, list[str]]:
    extra = sorted(set(diff_files) - set(declared_files))
    return (not extra, [f"worker touched undeclared file: {p}" for p in extra])


def merge_clean(repo: str, branch: str) -> None:
    """Merge `branch` into the current branch; raise InvariantViolation on conflict."""
    proc = subprocess.run(  # nosec B603,B607 — fixed git argv, no shell
        ["git", "merge", "--no-ff", "--no-edit", branch],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=repo,  # nosec B603,B607
            capture_output=True,
            text=True,
        )
        raise InvariantViolation(
            f"merge of {branch} conflicted (disjoint-file invariant violated): "
            f"{proc.stdout.strip()} {proc.stderr.strip()}"
        )


_ENGINE_DIR = Path(__file__).resolve().parent  # the engine repo's scripts/ dir


def _git_toplevel(path: Path | str) -> str | None:
    """Return the git toplevel for *path*, or None if it cannot be resolved."""
    try:
        proc = subprocess.run(  # nosec B603,B607 — fixed git argv, no shell
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def self_guard(repo: str, diff_files: Iterable[str]) -> tuple[bool, list[str]]:
    """Refuse to auto-merge edits to the engine's own ``scripts/*.py`` when the
    target resolves to the engine's own repo (or the target is unresolvable —
    fail closed). Defense-in-depth against the in-place / self-modification topology.
    """
    engine_root = _git_toplevel(_ENGINE_DIR)
    if engine_root is None:
        return True, []  # cannot identify the engine repo; nothing to protect
    target_root = _git_toplevel(Path(repo))
    if target_root is not None and target_root != engine_root:
        return True, []  # clearly a different repo
    offenders = sorted(
        f for f in diff_files if f.startswith("scripts/") and f.endswith(".py")
    )
    if offenders:
        return False, [
            f"self-engine modification requires human review: {f}" for f in offenders
        ]
    return True, []
