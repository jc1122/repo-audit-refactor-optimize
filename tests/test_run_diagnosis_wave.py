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


def _write_registry(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"lanes": entries}), encoding="utf-8")


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
        body += (
            "parser.add_argument('--exclude-prefix', action='append', default=[])\n"
        )
    if write_argv:
        body += "parser.add_argument('--rev')\n"
        body += "parser.add_argument('--baseline-rev')\n"
    body += "args, _ = parser.parse_known_args()\n"
    body += (
        f"Path(args.out_dir).mkdir(parents=True, exist_ok=True)\n"
        f"Path(args.out_dir + '/{file_name}').write_text("
        f"json.dumps(RESULT), encoding='utf-8')\n"
    )
    if write_argv:
        body += (
            "Path(args.out_dir + '/argv.json').write_text("
            "json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        )
    body += f"raise SystemExit({exit_code})\n"
    _write_script(path, body)


def _make_fake_lane_leaf(
    skills_root: Path,
    lane_script: str,
    file_name: str,
    findings_obj,
    exit_code: int = 0,
    *,
    write_argv: bool = False,
) -> Path:
    """Create a minimal fake leaf under *skills_root* and return its path."""
    leaf = skills_root / lane_script
    _make_fake_leaf_with_findings(
        leaf, file_name, findings_obj, exit_code, write_argv=write_argv
    )
    return leaf


def _prepare_repo_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("repo\n", encoding="utf-8")
    (root / "SKILL.md").write_text("name: x\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("x\n", encoding="utf-8")
    (root / "references").mkdir()
    (root / "agents").mkdir()
    (root / "scripts").mkdir()


# ── existing tests (unchanged assertions, now parallel-capable) ─────────


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
        {
            "findings": [
                {"leaf": "dep-leaf", "location": {"path": "src/dep.py", "symbol": "dep"}}
            ]
        },
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


# ── new tests: registry-driven behaviour ────────────────────────────────


def test_load_lanes_parses_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "wave_lanes.json"
    _write_registry(
        registry_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
            {"name": "exec", "script": "exec-audit/scripts/exec_audit.py", "languages": ["*"]},
            {"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]},
        ],
    )
    result = mod.load_lanes(registry_path)
    assert list(result.keys()) == ["hygiene", "exec", "growth"]
    assert result["hygiene"] == "repo-hygiene-audit/scripts/repo_hygiene_audit.py"
    assert result["exec"] == "exec-audit/scripts/exec_audit.py"
    assert result["growth"] == "growth-audit/scripts/growth_audit.py"


def test_registry_driven_wave(tmp_path: Path) -> None:
    """Use a temp registry; verify summary and findings order follows registry."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [
            {"name": "alpha", "script": "alpha-audit/scripts/alpha.py", "languages": ["*"]},
            {"name": "beta", "script": "beta-audit/scripts/beta.py", "languages": ["*"]},
        ],
    )

    alpha = skills_root / "alpha-audit" / "scripts" / "alpha.py"
    beta = skills_root / "beta-audit" / "scripts" / "beta.py"
    _make_fake_leaf_with_findings(
        alpha, "alpha_findings.json",
        [{"path": "a.py", "location": {"symbol": "a"}, "metric": 1}], 0,
    )
    _make_fake_leaf_with_findings(
        beta, "beta_findings.json",
        [{"path": "b.py", "location": {"symbol": "b"}, "metric": 2}], 0,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "alpha,beta",
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    findings = json.loads((out_dir / "wave_findings.json").read_text(encoding="utf-8"))
    timings = json.loads((out_dir / "wave_timings.json").read_text(encoding="utf-8"))

    # summary keys preserve registry order
    assert list(summary.keys()) == ["alpha", "beta"]
    _assert_status(summary, "alpha", 0, "ok")
    _assert_status(summary, "beta", 0, "ok")

    # findings order: alpha then beta (registry order)
    assert len(findings) == 2
    assert findings[0]["symbol"] == "a"
    assert findings[1]["symbol"] == "b"

    # timings emitted
    assert "alpha" in timings
    assert "beta" in timings
    assert "elapsed" in timings["alpha"]
    assert "elapsed" in timings["beta"]


def test_exec_lane_no_extra_args(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [{"name": "exec", "script": "exec-audit/scripts/exec_audit.py", "languages": ["*"]}],
    )

    exec_leaf = skills_root / "exec-audit" / "scripts" / "exec_audit.py"
    _make_fake_leaf_with_findings(
        exec_leaf, "exec_findings.json", [], 0, write_argv=True,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "exec",
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "exec", 0, "ok")

    argv = json.loads((out_dir / "exec" / "argv.json").read_text(encoding="utf-8"))
    # exec lane must have no --source-prefix, no --rev, no extra args
    assert "--source-prefix" not in argv
    assert "--rev" not in argv
    assert "--baseline-rev" not in argv
    assert "--config" not in argv
    # only --root and --out-dir (plus any argparse extras)
    assert "--root" in argv


def test_growth_lane_skipped_without_rev(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [{"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]}],
    )

    # Even if the script exists, it should be skipped when no --rev
    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf, "growth_findings.json", [], 0, write_argv=True,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "growth",
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "growth", 0, "skipped")
    assert summary["growth"]["findings"] == 0

    # The growth lane directory should NOT have been created (run_lane was never called)
    assert not (out_dir / "growth").exists()


def test_growth_lane_with_rev_passes_baseline_rev(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [{"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]}],
    )

    growth_leaf = skills_root / "growth-audit" / "scripts" / "growth_audit.py"
    _make_fake_leaf_with_findings(
        growth_leaf, "growth_findings.json", [], 0, write_argv=True,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "growth",
            "--rev", "deadbeef",
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "growth", 0, "ok")

    argv = json.loads((out_dir / "growth" / "argv.json").read_text(encoding="utf-8"))
    assert "--baseline-rev" in argv
    assert argv[argv.index("--baseline-rev") + 1] == "deadbeef"
    assert "--rev" not in argv


def test_unknown_lane_in_registry_reports_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [{"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]}],
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "nonexistent",
        ]
    )
    assert exit_code == 2


def test_wave_timings_is_emitted_for_every_lane(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
            {"name": "security", "script": "security-audit/scripts/security_audit.py", "languages": ["*"]},
        ],
    )

    hygiene_leaf = skills_root / "repo-hygiene-audit" / "scripts" / "repo_hygiene_audit.py"
    security_leaf = skills_root / "security-audit" / "scripts" / "security_audit.py"
    _make_fake_leaf_with_findings(hygiene_leaf, "hygiene_findings.json", [], 0)
    _make_fake_leaf_with_findings(security_leaf, "security_findings.json", [], 0)

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "hygiene,security",
        ]
    )
    assert exit_code == 0

    timings = json.loads((out_dir / "wave_timings.json").read_text(encoding="utf-8"))
    assert "hygiene" in timings
    assert "security" in timings
    for lane in ("hygiene", "security"):
        assert "start" in timings[lane]
        assert "end" in timings[lane]
        assert isinstance(timings[lane]["elapsed"], (int, float))
        assert timings[lane]["elapsed"] >= 0


def test_registry_order_preserved_in_summary_keys(tmp_path: Path) -> None:
    """Even when --lanes reverses registry order, summary keys follow registry order."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [
            {"name": "aaa", "script": "aaa-audit/scripts/aaa.py", "languages": ["*"]},
            {"name": "zzz", "script": "zzz-audit/scripts/zzz.py", "languages": ["*"]},
        ],
    )

    _make_fake_leaf_with_findings(
        skills_root / "aaa-audit" / "scripts" / "aaa.py",
        "aaa_findings.json", [], 0,
    )
    _make_fake_leaf_with_findings(
        skills_root / "zzz-audit" / "scripts" / "zzz.py",
        "zzz_findings.json", [], 0,
    )

    out_dir = tmp_path / "wave"
    # Request lanes in reverse order
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--lanes", "zzz,aaa",
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    # Summary keys must follow registry order: aaa first, then zzz
    assert list(summary.keys()) == ["aaa", "zzz"]


def test_all_lanes_from_registry_when_no_lanes_arg(tmp_path: Path) -> None:
    """When --lanes is omitted, all lanes from the registry run in registry order."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [
            {"name": "one", "script": "one-audit/scripts/one.py", "languages": ["*"]},
            {"name": "two", "script": "two-audit/scripts/two.py", "languages": ["*"]},
        ],
    )

    _make_fake_leaf_with_findings(
        skills_root / "one-audit" / "scripts" / "one.py",
        "one_findings.json", [{"path": "f1.py", "location": {"symbol": "s1"}, "metric": 1}], 0,
    )
    _make_fake_leaf_with_findings(
        skills_root / "two-audit" / "scripts" / "two.py",
        "two_findings.json", [{"path": "f2.py", "location": {"symbol": "s2"}, "metric": 2}], 0,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    assert list(summary.keys()) == ["one", "two"]
    _assert_status(summary, "one", 0, "ok")
    _assert_status(summary, "two", 0, "ok")


def test_missing_leaf_in_registry_records_error(tmp_path: Path) -> None:
    """A lane whose script does not exist records status=error in summary."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [
            {"name": "ghost", "script": "ghost-audit/scripts/ghost.py", "languages": ["*"]},
            {"name": "real", "script": "real-audit/scripts/real.py", "languages": ["*"]},
        ],
    )

    # Only 'real' exists
    _make_fake_leaf_with_findings(
        skills_root / "real-audit" / "scripts" / "real.py",
        "real_findings.json", [], 0,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
        ]
    )
    assert exit_code == 1  # wave_exit becomes 1 on missing leaf

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    assert list(summary.keys()) == ["ghost", "real"]
    _assert_status(summary, "ghost", 2, "error")
    _assert_status(summary, "real", 0, "ok")
    assert summary["ghost"]["findings"] == 0


def test_growth_with_rev_and_missing_leaf_handled(tmp_path: Path) -> None:
    """growth lane with --rev should still run when leaf exists."""
    repo = tmp_path / "repo"
    _prepare_repo_root(repo)

    skills_root = tmp_path / "skills"
    registry_path = tmp_path / "wave_lanes.json"

    _write_registry(
        registry_path,
        [
            {"name": "hygiene", "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py", "languages": ["*"]},
            {"name": "growth", "script": "growth-audit/scripts/growth_audit.py", "languages": ["*"]},
        ],
    )

    _make_fake_leaf_with_findings(
        skills_root / "repo-hygiene-audit" / "scripts" / "repo_hygiene_audit.py",
        "hygiene_findings.json", [], 0,
    )
    _make_fake_leaf_with_findings(
        skills_root / "growth-audit" / "scripts" / "growth_audit.py",
        "growth_findings.json",
        [{"path": "g.py", "location": {"symbol": "g"}, "metric": "growth"}], 0,
    )

    out_dir = tmp_path / "wave"
    exit_code = mod.main(
        [
            "--repo", str(repo),
            "--out-dir", str(out_dir),
            "--skills-root", str(skills_root),
            "--registry", str(registry_path),
            "--rev", "abc123",
        ]
    )
    assert exit_code == 0

    summary = json.loads((out_dir / "wave_summary.json").read_text(encoding="utf-8"))
    _assert_status(summary, "hygiene", 0, "ok")
    _assert_status(summary, "growth", 0, "ok")  # --rev supplied, not skipped
