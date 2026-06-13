"""Merge integration: enforce the disjoint-file invariant at merge time.

A textual conflict during merge is structurally impossible under the scheduler
invariant, so it is treated as a hard error (partitioner/worker bug), not a
normal merge conflict to resolve.
"""
from __future__ import annotations

import subprocess  # nosec B404 — fixed git argv, no shell
from typing import Iterable


class InvariantViolation(RuntimeError):
    """Raised when a merge that must be conflict-free reports a conflict."""


def assert_scope(declared_files: Iterable[str], diff_files: Iterable[str]) -> tuple[bool, list[str]]:
    extra = sorted(set(diff_files) - set(declared_files))
    return (not extra, [f"worker touched undeclared file: {p}" for p in extra])


def merge_clean(repo: str, branch: str) -> None:
    """Merge `branch` into the current branch; raise InvariantViolation on conflict."""
    proc = subprocess.run(  # nosec B603,B607 — fixed git argv, no shell
        ["git", "merge", "--no-ff", "--no-edit", branch],
        cwd=repo, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], cwd=repo,  # nosec B603,B607
                       capture_output=True, text=True)
        raise InvariantViolation(
            f"merge of {branch} conflicted (disjoint-file invariant violated): "
            f"{proc.stdout.strip()} {proc.stderr.strip()}"
        )
