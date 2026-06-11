from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mod = importlib.import_module("scripts.run_diagnosis_wave")


def _write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _assert_status(payload: dict[str, dict[str, object]], lane: str, exit_code: int, status: str) -> None:
    assert payload[lane]["exit"] == exit_code
    assert payload[lane]["status"] == status


def _make_fake_leaf_with_findings(
    path: Path,
    file_name: str,
    findings_obj,
    exit_code: int,
    *,
    has_exclude_arg: bool = True,
    write_argv: bool = False,
) -> None:
    body = (
        "import argparse\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"RESULT = {json.dumps(findings_obj)}\n"
        "\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--root')\n"
        "parser.add_argument('--out-dir')\n"
        "parser.add_argument('--source-prefix', action='append', default=[])\n"
    )
    if has_exclude_arg:
        body += "parser.add_argument('--exclude-prefix', action='append', default=[])\n"
    if write_argv:
        body += "parser.add_argument('--rev')\n"
    body += "args, _ = parser.parse_known_args()\n"
    body += (
        f"Path(args.out_dir).mkdir(parents=True, exist_ok=True)\n"
        f"Path(args.out_dir + '/{file_name}').write_text(json.dumps(RESULT), encoding='utf-8')\n"
    )
    if write_argv:
        body += (
            "Path(args.out_dir + '/argv.json').write_text("
            "json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        )
    body += f"raise SystemExit({exit_code})\n"
    _write_script(path, body)


def _prepare_repo_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("repo\n", encoding="utf-8")
    (root / "SKILL.md").write_text("name: x\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("x\n", encoding="utf-8")
    (root / "references").mkdir()
    (root / "agents").mkdir()
    (root / "scripts").mkdir()


def test_selected_lanes_disjoint_out_dirs_merge_findings(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    security = skills_root / "security-audit" / "scripts" / "security_audit.py"
    dependency = (
        skills_root / "dependency-audit" / "scripts" / "dependency_audit.py"
    )
    _make_fake_leaf_with_findings(
        security,
        "security_findings.json",
        [
            {
                "path": "src/security.py",
                "location": {"path": "ignored/path", "symbol": "security_symbol"},
                "metric": 7,
            }
        ],
        0,
    )
    _make_fake_leaf_with_findings(
        dependency,
        "dependency_findings.json",
        {"findings": [{"leaf": "dep-leaf", "location": {"path": "src/dep.py", "symbol": "dep"}}]},
        1,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--skills-root",
                str(skills_root),
                "--lanes",
                "security,dependency",
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    findings = json.loads((out_dir / "wave_findings.json").read_text(encoding="utf-8"))

    assert (out_dir / "security").is_dir()
    assert (out_dir / "dependency").is_dir()
    assert (out_dir / "security") != (out_dir / "dependency")

    _assert_status(summary, "security", 0, "ok")
    _assert_status(summary, "dependency", 1, "findings")
    assert summary["security"]["findings"] == 1
    assert summary["dependency"]["findings"] == 1
    assert {
        "leaf": "security",
        "path": "src/security.py",
        "symbol": "security_symbol",
        "metric": "7",
    } in findings
    assert {
        "leaf": "dep-leaf",
        "path": "src/dep.py",
        "symbol": "dep",
        "metric": "",
    } in findings
    assert len(findings) == 2


def test_fake_leaf_exit_two_records_wave_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skills_root = tmp_path / "skills"
    security = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(
        security,
        "security_findings.json",
        [{"path": "bad.py", "location": {"symbol": "bad"}, "metric": "x"}],
        2,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--skills-root",
                str(skills_root),
                "--lanes",
                "security",
            ]
        )
        == 1
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    findings = json.loads((out_dir / "wave_findings.json").read_text(encoding="utf-8"))
    _assert_status(summary, "security", 2, "error")
    assert findings == [
        {"leaf": "security", "path": "bad.py", "symbol": "bad", "metric": "x"},
    ]


def test_docs_living_docs_fallback_scope_no_excludes_flag(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)
    docs_root = repo / "docs"
    (docs_root / "audits").mkdir(parents=True)
    (docs_root / "dogfood").mkdir(parents=True)
    (docs_root / "plans").mkdir(parents=True)
    (docs_root / "superpowers").mkdir(parents=True)
    (docs_root / "guide").mkdir(parents=True)

    skills_root = tmp_path / "skills"
    docs_leaf = (
        skills_root / "docs-consistency-audit" / "scripts" / "docs_consistency_audit.py"
    )
    _make_fake_leaf_with_findings(
        docs_leaf,
        "docs_findings.json",
        [],
        0,
        has_exclude_arg=False,
        write_argv=True,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--skills-root",
                str(skills_root),
                "--lanes",
                "docs",
            ]
        )
        == 0
    )
    argv = json.loads((out_dir / "docs" / "argv.json").read_text(encoding="utf-8"))
    source_prefixes = [
        argv[i + 1]
        for i, value in enumerate(argv)
        if value == "--source-prefix" and i + 1 < len(argv)
    ]
    assert "docs" not in source_prefixes
    assert "docs/audits" not in source_prefixes
    assert "docs/dogfood" not in source_prefixes
    assert "docs/plans" not in source_prefixes
    assert "docs/superpowers" not in source_prefixes
    assert "--exclude-prefix" not in argv
    assert "docs/guide" in source_prefixes


def test_docs_living_docs_supporting_excludes_add_superpowers(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)
    docs_root = repo / "docs"
    (docs_root / "audits").mkdir(parents=True)
    (docs_root / "dogfood").mkdir(parents=True)
    (docs_root / "plans").mkdir(parents=True)
    (docs_root / "superpowers").mkdir(parents=True)

    skills_root = tmp_path / "skills"
    docs_leaf = (
        skills_root / "docs-consistency-audit" / "scripts" / "docs_consistency_audit.py"
    )
    _make_fake_leaf_with_findings(
        docs_leaf,
        "docs_findings.json",
        [],
        0,
        has_exclude_arg=True,
        write_argv=True,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--skills-root",
                str(skills_root),
                "--lanes",
                "docs",
            ]
        )
        == 0
    )
    argv = json.loads((out_dir / "docs" / "argv.json").read_text(encoding="utf-8"))
    source_prefixes = [
        argv[i + 1]
        for i, value in enumerate(argv)
        if value == "--source-prefix" and i + 1 < len(argv)
    ]
    exclude_prefixes = [
        argv[i + 1]
        for i, value in enumerate(argv)
        if value == "--exclude-prefix" and i + 1 < len(argv)
    ]
    assert "docs" in source_prefixes
    assert "--source-prefix" in argv
    assert "docs/audits" in exclude_prefixes
    assert "docs/dogfood" in exclude_prefixes
    assert "docs/plans" in exclude_prefixes
    assert "docs/superpowers" in exclude_prefixes
