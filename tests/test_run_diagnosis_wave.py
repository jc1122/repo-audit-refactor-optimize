from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mod = importlib.import_module("scripts.run_diagnosis_wave")


# ── helpers ─────────────────────────────────────────────────────────────


def _write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _assert_status(
    payload: dict[str, dict[str, object]], lane: str, exit_code: int, status: str
) -> None:
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
        body += "parser.add_argument('--config')\n"
        body += "parser.add_argument('--baseline-rev')\n"
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


def _make_registry(tmp_path: Path, entries: list[dict]) -> Path:
    """Write a temporary lane registry and return its path."""
    reg_path = tmp_path / "wave_lanes.json"
    reg_path.write_text(
        json.dumps({"lanes": entries}, indent=2), encoding="utf-8"
    )
    return reg_path


# ── existing tests (legacy LANES fallback) ──────────────────────────────


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


def test_fake_leaf_exit_two_with_findings_records_findings_status(tmp_path: Path) -> None:
    """A lane that exits 2 but produced findings is reported as 'findings', not 'error'."""
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
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    findings = json.loads((out_dir / "wave_findings.json").read_text(encoding="utf-8"))
    _assert_status(summary, "security", 2, "findings")
    assert findings == [
        {"leaf": "security", "path": "bad.py", "symbol": "bad", "metric": "x"},
    ]


def test_fake_leaf_exit_two_no_findings_is_error(tmp_path: Path) -> None:
    """Exit 2 without parsed findings remains an error (true tool failure)."""
    repo = tmp_path / "repo"
    skills_root = tmp_path / "skills"
    security = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(
        security,
        "security_findings.json",
        [],
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
    assert findings == []


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


def test_hotspot_config_is_forwarded_to_hotspot_lane(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)
    config = repo / "scripts" / "hotspot_config.json"
    config.write_text('{"coupling_allow_pairs": []}\n', encoding="utf-8")

    skills_root = tmp_path / "skills"
    hotspot = skills_root / "hotspot-audit" / "scripts" / "hotspot_audit.py"
    _make_fake_leaf_with_findings(
        hotspot,
        "hotspot_findings.json",
        [],
        0,
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
                "hotspot",
                "--rev",
                "abc123",
                "--hotspot-config",
                str(config),
            ]
        )
        == 0
    )

    argv = json.loads((out_dir / "hotspot" / "argv.json").read_text(encoding="utf-8"))
    assert "--rev" in argv
    assert argv[argv.index("--rev") + 1] == "abc123"
    assert "--config" in argv
    assert argv[argv.index("--config") + 1] == str(config)


def test_security_config_is_forwarded_to_security_lane(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)
    config = repo / "scripts" / "security_config.json"
    config.write_text('{"trusted_subprocess": {"enabled": true}}\n', encoding="utf-8")

    skills_root = tmp_path / "skills"
    security = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(
        security,
        "security_findings.json",
        [],
        0,
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
                "security",
                "--security-config",
                str(config),
            ]
        )
        == 0
    )

    argv = json.loads((out_dir / "security" / "argv.json").read_text(encoding="utf-8"))
    assert "--config" in argv
    assert argv[argv.index("--config") + 1] == str(config)


# ── new tests: registry, parallel, exec, growth, timings ────────────────


def test_load_lanes_returns_ordered_dict_from_registry(tmp_path: Path) -> None:
    registry = _make_registry(
        tmp_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
            {"name": "exec", "script": "exec-audit/scripts/exec_audit.py", "languages": ["*"]},
            {"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]},
        ],
    )
    lanes = mod.load_lanes(registry)
    assert list(lanes.keys()) == ["hygiene", "exec", "growth"]
    assert lanes["hygiene"] == "repo-hygiene-audit/scripts/repo_hygiene_audit.py"
    assert lanes["exec"] == "exec-audit/scripts/exec_audit.py"
    assert lanes["growth"] == "growth-audit/scripts/growth_audit.py"


def test_registry_drives_lane_selection_and_order(tmp_path: Path) -> None:
    """Lanes are selected and ordered per the registry, not the --lanes CSV order."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    hyg = skills_root / "repo-hygiene-audit" / "scripts" / "repo_hygiene_audit.py"
    sec = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(hyg, "hygiene_findings.json", [], 0)
    _make_fake_leaf_with_findings(
        sec,
        "security_findings.json",
        [{"path": "s.py", "location": {"symbol": "s"}, "metric": "1"}],
        0,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "security", "script": "security-audit/scripts/security_audit.py", "languages": ["python"]},
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    # Request lanes in reverse registry order; they must still execute and
    # appear in the summary in *registry* order (security first, hygiene second).
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "hygiene,security",
                "--registry", str(registry),
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    assert list(summary.keys()) == ["security", "hygiene"]


def test_wave_timings_is_emitted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    sec = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(
        sec,
        "security_findings.json",
        [{"path": "t.py", "location": {"symbol": "t"}, "metric": "2"}],
        0,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "security", "script": "security-audit/scripts/security_audit.py", "languages": ["python"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "security",
                "--registry", str(registry),
            ]
        )
        == 0
    )

    timings = json.loads((out_dir / "wave_timings.json").read_text(encoding="utf-8"))
    assert "security" in timings
    assert "start" in timings["security"]
    assert "end" in timings["security"]
    assert "elapsed" in timings["security"]
    assert isinstance(timings["security"]["elapsed"], (int, float))
    assert timings["security"]["elapsed"] >= 0


def test_parallel_execution_lanes_run_concurrently(tmp_path: Path) -> None:
    """Two slow-ish fake leaves must finish faster than sequential would."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    leaf_a = skills_root / "a-audit" / "scripts" / "a_audit.py"
    leaf_b = skills_root / "b-audit" / "scripts" / "b_audit.py"

    # Each leaf sleeps 0.3 s — sequential would be >= 0.6 s, parallel < 0.55 s.
    slow_body = (
        "import argparse, json, sys, time\n"
        "from pathlib import Path\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--root')\n"
        "p.add_argument('--out-dir')\n"
        "args, _ = p.parse_known_args()\n"
        "Path(args.out_dir).mkdir(parents=True, exist_ok=True)\n"
        "time.sleep(0.3)\n"
        "Path(args.out_dir + '/f.json').write_text('[]', encoding='utf-8')\n"
        "raise SystemExit(0)\n"
    )
    _write_script(leaf_a, slow_body)
    _write_script(leaf_b, slow_body)

    registry = _make_registry(
        tmp_path,
        [
            {"name": "a", "script": "a-audit/scripts/a_audit.py", "languages": ["*"]},
            {"name": "b", "script": "b-audit/scripts/b_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    t0 = __import__("time").time()
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "a,b",
                "--registry", str(registry),
            ]
        )
        == 0
    )
    elapsed = __import__("time").time() - t0
    assert elapsed < 0.55, f"parallel expected but took {elapsed:.2f}s"


def test_exec_lane_no_extra_args(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    exec_leaf = skills_root / "exec-audit" / "scripts" / "exec_audit.py"
    _make_fake_leaf_with_findings(
        exec_leaf,
        "exec_findings.json",
        [],
        0,
        write_argv=True,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "exec", "script": "exec-audit/scripts/exec_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "exec",
                "--registry", str(registry),
            ]
        )
        == 0
    )

    argv = json.loads((out_dir / "exec" / "argv.json").read_text(encoding="utf-8"))
    # exec lane must NOT receive any extra flags beyond --root and --out-dir
    assert "--source-prefix" not in argv
    assert "--rev" not in argv
    assert "--baseline-rev" not in argv
    assert "--config" not in argv
    assert "--coverage-json" not in argv


def test_growth_lane_skipped_without_rev(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf,
        "growth_findings.json",
        [],
        0,
        write_argv=True,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "growth",
                "--registry", str(registry),
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "growth", 0, "skipped")
    assert summary["growth"]["findings"] == 0
    # growth leaf directory should NOT have been created (never ran)
    assert not (out_dir / "growth").exists()


def test_growth_lane_with_rev_passes_baseline_rev(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf,
        "growth_findings.json",
        [],
        0,
        write_argv=True,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "growth",
                "--registry", str(registry),
                "--rev", "abc123",
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "growth", 0, "ok")

    argv = json.loads((out_dir / "growth" / "argv.json").read_text(encoding="utf-8"))
    assert "--baseline-rev" in argv
    assert argv[argv.index("--baseline-rev") + 1] == "abc123"
    assert "--rev" not in argv  # growth must not receive bare --rev
    assert "--config" not in argv  # no growth config supplied


def test_growth_autodetect_config_from_repo(tmp_path: Path) -> None:
    """When repo/scripts/growth_allowances.json exists, --config is auto-forwarded."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)
    config = repo / "scripts" / "growth_allowances.json"
    config.write_text('{"allowances": []}\n', encoding="utf-8")

    skills_root = tmp_path / "skills"
    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf,
        "growth_findings.json",
        [],
        0,
        write_argv=True,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "growth",
                "--registry", str(registry),
                "--rev", "abc123",
            ]
        )
        == 0
    )

    argv = json.loads((out_dir / "growth" / "argv.json").read_text(encoding="utf-8"))
    assert "--baseline-rev" in argv
    assert argv[argv.index("--baseline-rev") + 1] == "abc123"
    assert "--config" in argv
    assert argv[argv.index("--config") + 1] == str(config)


def test_unknown_lane_in_registry_detected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry = _make_registry(
        tmp_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--lanes", "nonexistent",
            "--registry", str(registry),
        ]
    )
    assert exit_code == 2


def test_missing_leaf_in_registry_sets_error_status(tmp_path: Path) -> None:
    """When a registry entry points to a non-existent script, record error."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    # Do NOT create the leaf script

    registry = _make_registry(
        tmp_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "hygiene",
                "--registry", str(registry),
            ]
        )
        == 1
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "hygiene", 2, "error")
    assert summary["hygiene"]["findings"] == 0


def test_registry_preserves_lane_order_in_summary_and_findings(tmp_path: Path) -> None:
    """Deterministic byte-identical summary/findings order per registry."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    hygiene = skills_root / "repo-hygiene-audit" / "scripts" / "repo_hygiene_audit.py"
    exec_leaf = skills_root / "exec-audit" / "scripts" / "exec_audit.py"

    _make_fake_leaf_with_findings(
        hygiene,
        "hygiene_findings.json",
        [{"path": "h.py", "location": {"symbol": "h"}, "metric": "1"}],
        0,
    )
    _make_fake_leaf_with_findings(
        exec_leaf,
        "exec_findings.json",
        [{"path": "e.py", "location": {"symbol": "e"}, "metric": "2"}],
        0,
    )

    registry = _make_registry(
        tmp_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
            {"name": "exec", "script": "exec-audit/scripts/exec_audit.py", "languages": ["*"]},
        ],
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "hygiene,exec",
                "--registry", str(registry),
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    findings = json.loads((out_dir / "wave_findings.json").read_text(encoding="utf-8"))

    # Summary keys in registry order
    assert list(summary.keys()) == ["hygiene", "exec"]

    # Findings in registry order: hygiene first, exec second
    assert len(findings) == 2
    assert findings[0]["path"] == "h.py"
    assert findings[1]["path"] == "e.py"


# ── default-registry tests: exec and growth known without --registry ─────


def test_exec_lane_recognized_from_default_registry(tmp_path: Path) -> None:
    """exec lane is known without --registry when wave_lanes.json exists."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    exec_leaf = skills_root / "exec-audit" / "scripts" / "exec_audit.py"
    _make_fake_leaf_with_findings(
        exec_leaf,
        "exec_findings.json",
        [],
        0,
        write_argv=True,
    )

    out_dir = tmp_path / "wave"
    # No --registry flag; must resolve from the committed scripts/wave_lanes.json
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "exec",
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "exec", 0, "ok")

    argv = json.loads((out_dir / "exec" / "argv.json").read_text(encoding="utf-8"))
    # exec lane must NOT receive any extra flags beyond --root and --out-dir
    assert "--source-prefix" not in argv
    assert "--rev" not in argv
    assert "--baseline-rev" not in argv
    assert "--config" not in argv


def test_growth_lane_recognized_from_default_registry(tmp_path: Path) -> None:
    """growth lane is known without --registry when wave_lanes.json exists."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf,
        "growth_findings.json",
        [],
        0,
        write_argv=True,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "growth",
                "--rev", "abc123",
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "growth", 0, "ok")

    argv = json.loads((out_dir / "growth" / "argv.json").read_text(encoding="utf-8"))
    assert "--baseline-rev" in argv
    assert argv[argv.index("--baseline-rev") + 1] == "abc123"
    assert "--rev" not in argv  # growth must not receive bare --rev
    assert "--config" not in argv  # no growth config supplied


def test_growth_lane_skipped_without_rev_default_registry(tmp_path: Path) -> None:
    """growth is skipped without --rev using the default registry."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf,
        "growth_findings.json",
        [],
        0,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "growth",
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "growth", 0, "skipped")
    assert summary["growth"]["findings"] == 0
    assert not (out_dir / "growth").exists()


def test_unknown_lane_in_default_registry_detected(tmp_path: Path) -> None:
    """Unknown lane with default registry exits 2."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)
    skills_root = tmp_path / "skills"
    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--lanes", "nonexistent",
        ]
    )
    assert exit_code == 2


def test_wave_timings_emitted_with_default_registry(tmp_path: Path) -> None:
    """wave_timings.json is emitted when using the default registry."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    sec = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(
        sec,
        "security_findings.json",
        [{"path": "t.py", "location": {"symbol": "t"}, "metric": "2"}],
        0,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "security",
            ]
        )
        == 0
    )

    timings = json.loads((out_dir / "wave_timings.json").read_text(encoding="utf-8"))
    assert "security" in timings
    assert "start" in timings["security"]
    assert "end" in timings["security"]
    assert "elapsed" in timings["security"]
    assert isinstance(timings["security"]["elapsed"], (int, float))
    assert timings["security"]["elapsed"] >= 0


def test_default_registry_preserves_lane_order(tmp_path: Path) -> None:
    """Summary and findings order matches the default registry order."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    hygiene = skills_root / "repo-hygiene-audit" / "scripts" / "repo_hygiene_audit.py"
    exec_leaf = skills_root / "exec-audit" / "scripts" / "exec_audit.py"

    _make_fake_leaf_with_findings(
        hygiene,
        "hygiene_findings.json",
        [{"path": "h.py", "location": {"symbol": "h"}, "metric": "1"}],
        0,
    )
    _make_fake_leaf_with_findings(
        exec_leaf,
        "exec_findings.json",
        [{"path": "e.py", "location": {"symbol": "e"}, "metric": "2"}],
        0,
    )

    out_dir = tmp_path / "wave"
    assert (
        mod.main(
            [
                "--repo", str(repo),
                "--out-dir", str(out_dir),
                "--skills-root", str(skills_root),
                "--lanes", "exec,hygiene",
            ]
        )
        == 0
    )

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    findings = json.loads((out_dir / "wave_findings.json").read_text(encoding="utf-8"))

    # Default registry order: hygiene before exec
    assert list(summary.keys()) == ["hygiene", "exec"]
    assert len(findings) == 2
    assert findings[0]["path"] == "h.py"
    assert findings[1]["path"] == "e.py"


import importlib
wave = importlib.import_module("scripts.run_diagnosis_wave")


def test_effective_excludes_defaults_to_tests_and_fixtures():
    assert wave._effective_excludes(source_prefixes=[], exclude_prefixes=[]) == ["tests", "fixtures"]


def test_effective_excludes_explicit_source_prefix_disables_default():
    assert wave._effective_excludes(source_prefixes=["scripts"], exclude_prefixes=[]) == []


def test_effective_excludes_explicit_excludes_win():
    assert wave._effective_excludes(source_prefixes=[], exclude_prefixes=["vendor"]) == ["vendor"]


def test_audit_scope_args_emits_excludes_when_supported():
    args = wave._audit_scope_args(["scripts"], ["tests", "fixtures"], supports_exclude=True)
    assert args == ["--source-prefix", "scripts",
                    "--exclude-prefix", "tests", "--exclude-prefix", "fixtures"]


def test_audit_scope_args_drops_excludes_when_unsupported():
    args = wave._audit_scope_args([], ["tests"], supports_exclude=False)
    assert args == []


# ── Task 4: _resolve_accept / _apply_accept ──────────────────────────────


def test_resolve_accept_auto_discovers_repo_file(tmp_path: Path):
    (tmp_path / ".repo-audit").mkdir()
    (tmp_path / ".repo-audit" / "accept.json").write_text(json.dumps(
        {"version": 1, "accept": [
            {"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "r"}]}),
        encoding="utf-8")
    policy = wave._resolve_accept(tmp_path, accept=None, baseline=None)
    assert len(policy.entries) == 1


def test_resolve_accept_merges_baseline_rows(tmp_path: Path):
    base = tmp_path / "b.json"
    base.write_text(json.dumps([
        {"leaf": "c", "path": "p", "symbol": "<module>", "metric": "mi"}]), encoding="utf-8")
    policy = wave._resolve_accept(tmp_path, accept=None, baseline=base)
    assert policy.entries[0].kind == "finding"
    assert policy.entries[0].applies == frozenset({"report"})


def test_apply_accept_writes_accepted_sidecar(tmp_path: Path):
    findings = [{"leaf": "c", "path": "scripts/a.py", "symbol": "<module>", "metric": "mi"},
                {"leaf": "c", "path": "scripts/b.py", "symbol": "f", "metric": "x"}]
    acc = importlib.import_module("scripts._accept")
    policy = acc.AcceptPolicy([acc._parse_entry(
        {"match": {"kind": "finding", "leaf": "c", "path": "scripts/a.py",
                   "symbol": "<module>", "metric": "mi"}, "reason": "ok"}, 0)])
    active = wave._apply_accept(policy, findings, tmp_path)
    assert [f["path"] for f in active] == ["scripts/b.py"]
    sidecar = json.loads((tmp_path / "wave_findings.accepted.json").read_text())
    assert sidecar["accepted"][0]["accept_reason"] == "ok"
    assert (tmp_path / "wave_findings.suppressed.json").exists()  # back-compat


def test_perf_smell_lane_is_registered():
    lanes = wave.load_lanes(wave._DEFAULT_REGISTRY)
    assert "perf-smell" in lanes
    assert lanes["perf-smell"].endswith("perf-smell-audit/scripts/perf_smell_audit.py")
