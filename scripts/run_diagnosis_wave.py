#!/usr/bin/env python3
"""Thin compatibility wrapper: delegate diagnosis to the ``repo-audit`` CLI.

The v0.x wave runner (lane registry, skill discovery, baseline suppression)
was retired in 1.0.0. Detection now lives in the ``repo-audit`` command from
the ``repo-audit-checks`` package. This script maps the surviving arguments
and execs the real CLI, so recent invocations keep working for one migration
release. New callers should invoke ``repo-audit scan`` directly.

Forwarded: --root/--repo, --out-dir, --checks/--lanes, --preset,
--accept, --coverage-json, --source-prefix, --rev.
Retired (exit 2 with a migration pointer, never silent): --baseline,
--registry, --skills-root, --exclude-prefix, --security-config,
--hotspot-config.

Exit status is propagated unchanged (0 clean, 1 findings, 2 incomplete/error).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

__version__ = "1.0.0"

_RETIRED = (
    "baseline",
    "registry",
    "skills_root",
    "exclude_prefix",
    "security_config",
    "hotspot_config",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deprecated wrapper for `repo-audit scan`.",
    )
    parser.add_argument("--repo", help="Target repository (alias for --root).")
    parser.add_argument("--root", help="Target repository root.")
    parser.add_argument("--out-dir", help="Output directory for the run record.")
    parser.add_argument(
        "--lanes",
        help="Deprecated: comma-separated lane names, passed through as --checks.",
    )
    parser.add_argument("--checks", help="Comma-separated check ids for repo-audit.")
    parser.add_argument("--accept", help="Acceptance file handed to repo-audit.")
    parser.add_argument("--preset", help="Check preset handed to repo-audit.")
    parser.add_argument(
        "--coverage-json",
        action="append",
        default=[],
        help="Coverage.py JSON handed to repo-audit (repeatable).",
    )
    parser.add_argument(
        "--source-prefix",
        action="append",
        default=[],
        help="Source scope handed to repo-audit (repeatable).",
    )
    parser.add_argument("--rev", help="Revision handed to repo-audit.")
    for retired in _RETIRED:
        parser.add_argument(
            f"--{retired.replace('_', '-')}",
            help=f"REMOVED in 1.0.0 (see references/MIGRATION.md).",
        )
    parser.add_argument(
        "--list-checks", action="store_true", help="List available checks and exit."
    )
    parser.add_argument("--version", action="store_true", help="Print version.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    for retired in _RETIRED:
        if getattr(args, retired):
            flag = f"--{retired.replace('_', '-')}"
            print(
                f"error: {flag} was removed in 1.0.0 and has no equivalent "
                f"in `repo-audit scan` (--baseline: convert to "
                f".repo-audit/accept.json; --registry/--skills-root: the CLI "
                f"owns its registry; --exclude-prefix/--security-config/"
                f"--hotspot-config: dropped; see references/MIGRATION.md).",
                file=sys.stderr,
            )
            return 2
    if args.list_checks:
        extras = [
            name
            for name in (
                "root", "repo", "out_dir", "checks", "lanes", "accept",
                "preset", "rev",
            )
            if getattr(args, name)
        ] + (["--coverage-json"] if args.coverage_json else []) + (
            ["--source-prefix"] if args.source_prefix else []
        )
        if extras:
            print(
                "error: --list-checks takes no other scan options "
                f"(got: {', '.join(sorted(extras))}).",
                file=sys.stderr,
            )
            return 2
    # Prefer the launcher shipped next to this wrapper: inside an installed
    # skill it resolves the install-time venv without activation or PATH.
    # The launcher itself exits 2 with a clean message when nothing resolves.
    sibling = Path(__file__).resolve().parent / "repo-audit"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        cli = str(sibling)
    else:
        cli = shutil.which("repo-audit")
    if cli is None:
        print(
            "error: `repo-audit` CLI not found. Install repo-audit-checks "
            "(see bootstrap/install.sh --help).",
            file=sys.stderr,
        )
        return 2
    cmd = [cli, "scan"]
    if args.list_checks:
        cmd.append("--list-checks")
    else:
        root = args.root or args.repo
        if root:
            cmd += ["--root", root]
        if args.out_dir:
            cmd += ["--out-dir", args.out_dir]
        checks = args.checks or args.lanes
        if checks:
            cmd += ["--checks", checks]
        if args.accept:
            cmd += ["--accept", args.accept]
        if args.preset:
            cmd += ["--preset", args.preset]
        for cov in args.coverage_json:
            cmd += ["--coverage-json", cov]
        for prefix in args.source_prefix:
            cmd += ["--source-prefix", prefix]
        if args.rev:
            cmd += ["--rev", args.rev]
    if args.lanes:
        print(
            "warning: --lanes is deprecated, treating values as --checks.",
            file=sys.stderr,
        )
    print(
        "warning: run_diagnosis_wave.py is a deprecated thin wrapper; "
        "use `repo-audit scan` directly.",
        file=sys.stderr,
    )
    proc = subprocess.run(cmd)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
