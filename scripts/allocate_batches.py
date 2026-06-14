"""Batch allocator (L-5a).

Guarantees every ACTIVE repo at least one batch (defeats starvation), then
routes surplus batches to the best trailing per-repo yield mined from
``iteration_kpis.jsonl``. Stdlib only; advisory and deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence


def trailing_yield(repo: str, kpis: Sequence[Mapping]) -> int:
    """Sum of rows closed for ``repo`` across the supplied kpi records.

    Per-record closed = rows_before[repo] - rows_after[repo] (missing -> 0).
    """
    total = 0
    for rec in kpis:
        before = rec.get("rows_before", {}).get(repo, 0)
        after = rec.get("rows_after", {}).get(repo, 0)
        total += before - after
    return total


def allocate(
    active_repos: Sequence[str],
    kpis: Sequence[Mapping],
    surplus: int,
    cap: int = 6,
) -> dict[str, int]:
    """Allocate batches to active repos.

    Every active repo starts at the guaranteed minimum of 1. Surplus batches
    are distributed one at a time to the active repo with the highest trailing
    yield that is still below ``cap`` (ties broken stably by ``active_repos``
    order). Stops when all repos are at ``cap``. Never exceeds ``cap``.
    """
    alloc: dict[str, int] = {repo: 1 for repo in active_repos}
    yields = {repo: trailing_yield(repo, kpis) for repo in active_repos}

    for _ in range(max(surplus, 0)):
        below_cap = [repo for repo in active_repos if alloc[repo] < cap]
        if not below_cap:
            break
        # Highest trailing yield wins; ties resolved by active_repos order
        # (stable: max over the ordered list returns the first max).
        winner = max(below_cap, key=lambda repo: yields[repo])
        alloc[winner] += 1

    return alloc


def rationale(
    active_repos: Sequence[str],
    kpis: Sequence[Mapping],
    alloc: Mapping[str, int],
) -> str:
    """Return a single-line rationale naming the surplus winner and its yield."""
    yields = {repo: trailing_yield(repo, kpis) for repo in active_repos}
    if active_repos:
        winner = max(active_repos, key=lambda repo: yields[repo])
    else:
        winner = "(none)"
    yields_str = ",".join(f"{repo}:{yields[repo]}" for repo in active_repos)
    return (
        f"L-5a: every active repo >=1; surplus -> {winner} "
        f"(trailing yield {yields.get(winner, 0)} rows, best of {{{yields_str}}})"
    )


def _load_kpis(path: str) -> list[Mapping]:
    records: list[Mapping] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Allocate batches: guaranteed minimum per active repo + "
            "best trailing-yield surplus routing (L-5a)."
        )
    )
    parser.add_argument(
        "--kpi-file",
        help="Path to iteration_kpis.jsonl (one JSON object per line).",
    )
    parser.add_argument(
        "--active",
        required=True,
        help="Comma-separated list of active repos.",
    )
    parser.add_argument(
        "--surplus", type=int, required=True, help="Surplus batches to distribute."
    )
    parser.add_argument(
        "--cap", type=int, default=6, help="Max batches per repo (default 6)."
    )
    args = parser.parse_args(argv)

    active = [r.strip() for r in args.active.split(",") if r.strip()]
    kpis = _load_kpis(args.kpi_file) if args.kpi_file else []
    alloc = allocate(active, kpis, args.surplus, args.cap)

    print(json.dumps(alloc))
    print(rationale(active, kpis, alloc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
