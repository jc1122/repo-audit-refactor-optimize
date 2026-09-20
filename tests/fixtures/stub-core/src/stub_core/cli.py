"""Stub repo-audit CLI for installer/launcher tests. Not a check engine."""
import argparse
import json
import sys
from pathlib import Path


def build_parser():
    p = argparse.ArgumentParser(prog="repo-audit")
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("doctor")
    d.add_argument("--checks", default="")
    s = sub.add_parser("scan")
    s.add_argument("--root", default="")
    s.add_argument("--out-dir", default="")
    s.add_argument("--checks", default="")
    s.add_argument("--list-checks", action="store_true")
    c = sub.add_parser("compare")
    c.add_argument("--baseline", default="")
    c.add_argument("--current", default="")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "doctor":
        print(json.dumps({"missing": 0, "checks": []}))
        return 0
    if args.cmd == "scan" and args.list_checks:
        print(json.dumps({"version": "0.0.1-stub", "checks": [{"id": "stub"}]}))
        return 0
    if args.cmd == "scan":
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "run.json").write_text(json.dumps({"status": "findings", "counts": {"active": 1}}))
        (out / "findings.json").write_text(json.dumps([{"id": "stub-1", "leaf": "stub"}]))
        (out / "report.md").write_text("# stub report\n")
        print(json.dumps({"status": "ok", "run": "findings", "active": 1}))
        return 1
    if args.cmd == "compare":
        print(json.dumps({"status": "ok", "new": [], "fixed": []}))
        return 0
    print(json.dumps({"status": "error", "message": "unknown command"}))
    return 2


if __name__ == "__main__":
    sys.exit(main())
