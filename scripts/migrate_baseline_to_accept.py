#!/usr/bin/env python3
"""Convert a flat {leaf,path,symbol,metric} baseline into a `.repo-audit/accept.json`.

Identity-preserving and count-neutral: every baseline row becomes a report-stage
`finding` acceptance with the same 4-tuple identity. Reasons default to a pointer at
the frozen ledger and may be overridden per identity.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

_acc = importlib.import_module("scripts._accept" if __package__ else "_accept")

_DEFAULT_REASON = "migrated accepted residual — see the repo's frozen ledger"


def build_policy(
    rows: list[dict[str, str]],
    reasons: dict[tuple[str, str, str, str], str],
) -> dict:
    accept = []
    for r in rows:
        match = {"kind": "finding", "leaf": r.get("leaf", ""),
                 "path": r.get("path", ""), "symbol": r.get("symbol", ""),
                 "metric": r.get("metric", "")}
        ident = _acc.identity_of(match)
        accept.append({"match": match, "reason": reasons.get(ident, _DEFAULT_REASON),
                       "applies": ["report"]})
    return {"version": 1, "accept": accept}


def _parse_args(argv=None):
    ap = argparse.ArgumentParser(description="baseline.json -> .repo-audit/accept.json")
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    rows = json.loads(args.baseline.read_text(encoding="utf-8"))
    payload = build_policy(rows, reasons={})
    _acc._parse_policy(payload)  # fail closed if the result is somehow invalid
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "entries": len(payload["accept"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
