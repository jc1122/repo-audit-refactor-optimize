# scripts/graduate_benchmark.py
"""Graduate a proven synthesized benchmark into the audited repo (on demand).

Copies the harness (*.py) into ``benchmarks/<name>/`` only. The perf trend ledger
is owned entirely by perf-benchmark's ``--baseline-ledger`` (ledger.append_run) — this
script never writes it, so the two never disagree on format.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def graduate(*, harness_dir: Path, repo_root: Path, name: str) -> dict[str, object]:
    harness_dir, repo_root = Path(harness_dir), Path(repo_root)
    dest = repo_root / "benchmarks" / name
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for src in sorted(harness_dir.glob("*.py")):
        shutil.copy2(src, dest / src.name)
        copied.append(src.name)
    return {"benchmark_dir": dest.as_posix(), "copied": copied}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copy a synthesized harness into benchmarks/."
    )
    parser.add_argument("--harness-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    res = graduate(
        harness_dir=args.harness_dir, repo_root=args.repo_root, name=args.name
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
