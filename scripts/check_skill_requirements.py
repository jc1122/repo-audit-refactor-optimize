from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path


def _ensure_scripts_importable() -> None:
    """Ensure ``import scripts.*`` resolves when running as a standalone file."""
    if importlib.util.find_spec("scripts"):
        return
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))


_RE_EXPORT_MODULES = (
    "scripts._skill_probe",
    "scripts._lane_resolve",
    "scripts._bootstrap_report",
)


_ensure_scripts_importable()
_BOOTSTRAP_REPORT = importlib.import_module("scripts._bootstrap_report")
_build_bootstrap_report = _BOOTSTRAP_REPORT.build_bootstrap_report
_write_bootstrap_outputs = _BOOTSTRAP_REPORT.write_bootstrap_outputs

for _module_name in _RE_EXPORT_MODULES:
    _module = importlib.import_module(_module_name)
    for _name in dir(_module):
        if _name.startswith("__"):
            continue
        globals()[_name] = getattr(_module, _name)
    del _name
del _module
del _module_name
del _ensure_scripts_importable
del _RE_EXPORT_MODULES


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check metaskill bootstrap requirements."
    )
    parser.add_argument(
        "--repo", required=True, type=Path, help="Repository root to scan."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("skill_bootstrap_manifest.json"),
        help="Dependency manifest path.",
    )
    parser.add_argument(
        "--out-dir", required=True, type=Path, help="Output directory root."
    )
    parser.add_argument("--extra-root", action="append", default=[], type=Path)
    parser.add_argument("--foreign-root", action="append", default=[], type=Path)
    parser.add_argument("--user-override", type=Path)
    parser.add_argument("--repo-override", type=Path)
    parser.add_argument("--require-skill", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = _build_bootstrap_report(
            repo_root=args.repo,
            manifest_path=args.manifest,
            out_dir=args.out_dir,
            extra_roots=args.extra_root,
            foreign_roots=args.foreign_root,
            user_override_path=args.user_override,
            repo_override_path=args.repo_override,
            required_skill_names=args.require_skill,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    _write_bootstrap_outputs(report, args.out_dir)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
