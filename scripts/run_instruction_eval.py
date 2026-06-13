#!/usr/bin/env python3
"""Advisory behavioral instruction-eval harness (X1.2).

R2 admission
------------
- signal: does the instruction layer (a skill's SKILL.md, in isolation) actually
  steer a model to the right behavior? We measure this by comparing the number of
  findings a pinned model produces — given ONLY the SKILL.md — against the count
  the skill's deterministic pipeline emits on the same fixture.
- sunset: fold into a richer eval suite once more than one skill is covered.

Design constraints
------------------
- ADVISORY ONLY. Drift between model and deterministic baseline produces an
  advisory finding plus a ``candidate``-tier lesson; it NEVER raises and NEVER
  fails the pipeline. LLM nondeterminism must not break a deterministic gate.
- This module is pure and deterministic. It does NOT call any LLM. The real model
  call is driven by the orchestrator, which captures the model's findings to a
  JSON array and hands that path to ``--model-findings``.
- Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def score_eval(
    skill: str,
    expected_rows: int,
    model_findings: list[Any],
    model: str,
) -> dict[str, Any]:
    """Score a single instruction-eval run.

    ``actual_rows`` is the length of the model's findings; ``pass`` is True iff it
    equals the deterministic baseline ``expected_rows``.
    """
    actual_rows = len(model_findings)
    return {
        "skill": skill,
        "model": model,
        "expected_rows": expected_rows,
        "actual_rows": actual_rows,
        "pass": actual_rows == expected_rows,
    }


def advisory_outputs(res: dict[str, Any]) -> dict[str, Any]:
    """Derive advisory outputs from a scored result.

    On pass: both ``finding`` and ``lesson`` are None. On drift: an EVAL advisory
    finding (shared schema) and a ``candidate``-tier lesson. Never raises.
    """
    if res["pass"]:
        return {"finding": None, "lesson": None}

    skill = res["skill"]
    actual = res["actual_rows"]
    expected = res["expected_rows"]

    finding = {
        "signal": "EVAL",
        "leaf": "instruction-eval",
        "skill": skill,
        "model": res["model"],
        "expected_rows": expected,
        "actual_rows": actual,
        "message": (
            f"instruction-eval drift for {skill}: model produced {actual} rows "
            f"vs {expected} expected (advisory)"
        ),
    }
    lesson = {
        "id": f"instruction-eval/{skill}",
        "tier": "candidate",
        "scope": "instruction-eval",
        "text": (
            f"{skill} SKILL.md under-/over-specifies: model produced "
            f"{actual} rows vs {expected} expected"
        ),
        "fires": 1,
        "escalated": False,
    }
    return {"finding": finding, "lesson": lesson}


def _load_expected(raw: str) -> int:
    """Resolve ``--expected`` as either an int literal or a path to a JSON file.

    The JSON file may be ``{"expected_rows": N}`` or a bare integer. Raises
    ValueError on anything else.
    """
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    path = Path(raw)
    if not path.is_file():
        raise ValueError(f"--expected is neither an int nor an existing file: {raw}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, bool):
        raise ValueError(f"expected JSON is not an int payload: {raw}")
    if isinstance(data, int):
        return data
    if isinstance(data, dict) and isinstance(data.get("expected_rows"), int):
        return int(data["expected_rows"])
    raise ValueError(
        f"expected JSON must be an int or {{'expected_rows': int}}: {raw}"
    )


def _load_model_findings(path_str: str) -> list[Any]:
    """Load the orchestrator-captured model findings (a JSON array)."""
    path = Path(path_str)
    if not path.is_file():
        raise ValueError(f"--model-findings file does not exist: {path_str}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"--model-findings must be a JSON array: {path_str}")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_instruction_eval.py",
        description=(
            "Advisory behavioral instruction-eval harness: scores a pinned model's "
            "findings count (captured by the orchestrator) against a skill's "
            "deterministic baseline. Advisory only; never exits nonzero on drift."
        ),
    )
    parser.add_argument("--skill", required=True, help="skill name under eval")
    parser.add_argument(
        "--expected",
        required=True,
        help="expected findings count: an int or a path to a JSON file",
    )
    parser.add_argument(
        "--model-findings",
        required=True,
        help="path to a JSON array of findings the orchestrator captured",
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-8",
        help="pinned model id (default: claude-opus-4-8)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output path for the eval artifact (default: eval_<skill>.json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns 0 on success (including drift); nonzero only on
    malformed inputs. Never calls an LLM."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        expected_rows = _load_expected(args.expected)
        model_findings = _load_model_findings(args.model_findings)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    res = score_eval(
        skill=args.skill,
        expected_rows=expected_rows,
        model_findings=model_findings,
        model=args.model,
    )
    adv = advisory_outputs(res)

    out_path = Path(args.out) if args.out else Path(f"eval_{args.skill}.json")
    artifact = {**res, "advisory": adv}
    out_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(adv, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
