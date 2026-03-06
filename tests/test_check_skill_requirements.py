from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


checker = importlib.import_module("scripts.check_skill_requirements")


def write_skill(root: Path, name: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\n",
        encoding="utf-8",
    )


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


MANIFEST_PATH = REPO_ROOT / "scripts" / "skill_bootstrap_manifest.json"


@pytest.fixture
def sample_manifest() -> dict:
    """Load the production manifest and inject a test-only public skill entry."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["skills"]["public-helper"] = {
        "priority": "preferred",
        "source_type": "public",
        "install_source": {
            "method": "skills_cli",
            "package": "acme/skills@public-helper",
        },
        "manual_fallback": "Use fallback helper manually.",
        "restart_required_if_installed": True,
    }
    return manifest


@pytest.fixture
def python_pytest_repo(tmp_path: Path) -> Path:
    """Create a minimal Python+pytest repository and return its root path."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("pass\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return repo


def test_scan_repo_profile_detects_languages_and_surfaces(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "benches").mkdir()
    (repo / "native").mkdir()
    (repo / "rustlib" / "src").mkdir(parents=True)
    (repo / "asm").mkdir()

    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "benches" / "bench_hot.py").write_text("def bench_hot(): pass\n", encoding="utf-8")
    (repo / "native" / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (repo / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
    (repo / "rustlib" / "Cargo.toml").write_text("[package]\nname='r'\nversion='0.1.0'\n", encoding="utf-8")
    (repo / "rustlib" / "src" / "lib.rs").write_text("pub fn hi() {}\n", encoding="utf-8")
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    profile = checker.scan_repo_profile(repo)

    assert profile["languages"] == ["assembly", "c", "python", "rust"]
    assert profile["test_systems"] == ["cargo", "cmake", "pytest"]
    assert profile["benchmark_surfaces"] == ["python-benchmarks"]
    assert profile["has_deterministic_test_surface"] is True
    assert profile["has_deterministic_perf_surface"] is True


def test_resolve_skill_roots_orders_usable_and_advisory_roots(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    orchestrator_home = tmp_path / "orchestrator-home"
    orchestrator_skills = orchestrator_home / "skills"
    bundled = orchestrator_home / "vendor_imports" / "skills" / "skills"
    agents = tmp_path / ".agents" / "skills"
    repo_local = repo / ".agents" / "skills"
    extra = tmp_path / "extra-skills"
    foreign = tmp_path / "foreign-skills"

    for root in [orchestrator_skills, bundled, agents, repo_local, extra, foreign]:
        write_skill(root, "demo-skill")

    roots = checker.resolve_skill_roots(
        repo_root=repo,
        extra_roots=[extra],
        foreign_roots=[foreign],
        env={"AGENT_SKILLS_HOME": str(orchestrator_home), "HOME": str(tmp_path)},
    )

    assert [item["path"] for item in roots["usable_roots"]] == [
        str(orchestrator_skills),
        str(bundled),
        str(agents),
        str(repo_local),
        str(extra),
    ]
    assert [item["path"] for item in roots["advisory_roots"]] == [str(foreign)]


def test_resolve_skill_roots_codex_home_backward_compat(tmp_path: Path):
    """CODEX_HOME still works as a fallback when AGENT_SKILLS_HOME is unset."""
    repo = tmp_path / "repo"
    repo.mkdir()

    codex_home = tmp_path / "codex-compat-home"
    codex_skills = codex_home / "skills"
    write_skill(codex_skills, "demo-skill")

    roots = checker.resolve_skill_roots(
        repo_root=repo,
        env={"CODEX_HOME": str(codex_home), "HOME": str(tmp_path)},
    )

    assert any(item["path"] == str(codex_skills) for item in roots["usable_roots"])


def test_python_repo_uses_tqa_triage_fallback_when_pipeline_missing(
    tmp_path: Path,
    sample_manifest: dict,
    python_pytest_repo: Path,
):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "test-quality-assurance")
    write_skill(skills_root, "test-redundancy-triage")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    test_lane = report["lanes"]["test-python"]
    assert test_lane["state"] == "degraded"
    assert test_lane["selected_skills"] == [
        "test-quality-assurance",
        "test-redundancy-triage",
    ]
    assert report["skills"]["test-audit-pipeline"]["state"] == "manual_only"


def test_missing_public_skill_generates_exact_install_command(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "run-artifacts",
        env={"HOME": str(tmp_path)},
        required_skill_names=["public-helper"],
    )
    checker.write_bootstrap_outputs(report, tmp_path / "run-artifacts")

    install_plan = (tmp_path / "run-artifacts" / "bootstrap" / "install_plan.md").read_text(
        encoding="utf-8"
    )
    assert "npx skills add acme/skills@public-helper -g -y" in install_plan
    assert report["skills"]["public-helper"]["state"] == "installable_now"


def test_assembly_repo_activates_code_health_lane(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    (repo / "asm").mkdir(parents=True)
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "m15-anti-pattern")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "code-health-assembly" in report["summary"]["active_lanes"]
    assert report["lanes"]["code-health-assembly"]["state"] == "full"
    assert report["lanes"]["code-health-assembly"]["selected_skills"] == ["m15-anti-pattern"]


def test_missing_local_skill_without_source_mapping_is_manual_only(
    tmp_path: Path,
    sample_manifest: dict,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        required_skill_names=["m15-anti-pattern"],
    )

    assert report["skills"]["m15-anti-pattern"]["state"] == "manual_only"


def test_malformed_override_file_hard_fails(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    bad_override = tmp_path / "bad-override.json"
    bad_override.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError):
        checker.build_bootstrap_report(
            repo_root=repo,
            manifest_path=manifest_path,
            out_dir=tmp_path / "out",
            env={"HOME": str(tmp_path)},
            user_override_path=bad_override,
        )


def test_bad_optional_override_entry_is_ignored(tmp_path: Path, sample_manifest: dict, python_pytest_repo: Path):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    user_override = tmp_path / "override.json"
    user_override.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "unknown-skill": {
                        "source_type": "public",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        user_override_path=user_override,
        required_skill_names=["public-helper"],
    )

    assert "unknown-skill" not in report["skills"]
    assert report["warnings"]


def test_bad_active_optional_override_entry_is_ignored(tmp_path: Path, sample_manifest: dict, python_pytest_repo: Path):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    user_override = tmp_path / "override.json"
    user_override.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "hypothesis-testing": {
                        "restart_required_if_installed": "yes"
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        user_override_path=user_override,
    )

    assert report["skills"]["hypothesis-testing"]["restart_required_if_installed"] is True
    assert any("hypothesis-testing" in warning for warning in report["warnings"])


def test_bad_blocking_override_entry_hard_fails(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    (repo / "benches").mkdir(parents=True)
    (repo / "benches" / "bench_hot.py").write_text("def bench_hot(): pass\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    user_override = tmp_path / "override.json"
    user_override.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "perf-benchmark": {
                        "restart_required_if_installed": "yes"
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid override entry for required skill: perf-benchmark"):
        checker.build_bootstrap_report(
            repo_root=repo,
            manifest_path=manifest_path,
            out_dir=tmp_path / "out",
            env={"HOME": str(tmp_path)},
            user_override_path=user_override,
        )


def test_perf_focused_repo_without_benchmark_surfaces_is_blocked(
    tmp_path: Path,
    sample_manifest: dict,
):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "module.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    perf_lane = report["lanes"]["performance"]
    assert perf_lane["state"] == "blocked"
    assert report["summary"]["stop_before_discovery"] is True
    assert report["skills"]["perf-benchmark"]["state"] == "blocking_missing"


def test_main_cli_roundtrip(tmp_path: Path, sample_manifest: dict, python_pytest_repo: Path):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    out_dir = tmp_path / "out"
    ret = checker.main([
        "--repo", str(repo),
        "--manifest", str(manifest_path),
        "--out-dir", str(out_dir),
    ])
    assert ret == 0
    assert (out_dir / "bootstrap" / "bootstrap_report.json").exists()
    assert (out_dir / "bootstrap" / "bootstrap_report.md").exists()
    assert (out_dir / "bootstrap" / "install_plan.md").exists()


def test_load_dependency_manifest_malformed_json(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        checker.load_dependency_manifest(bad)


def test_load_dependency_manifest_missing_keys(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"skills": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        checker.load_dependency_manifest(bad)


def test_test_lane_full_with_optional(tmp_path: Path, sample_manifest: dict, python_pytest_repo: Path):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "test-audit-pipeline")
    write_skill(skills_root, "hypothesis-testing")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["test-python"]
    assert lane["state"] == "full"
    assert "test-audit-pipeline" in lane["selected_skills"]
    assert "hypothesis-testing" in lane["selected_skills"]


def test_test_lane_manual_when_nothing_available(tmp_path: Path, sample_manifest: dict, python_pytest_repo: Path):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["lanes"]["test-python"]["state"] == "manual"
    assert report["lanes"]["test-python"]["selected_skills"] == []


def test_performance_lane_full_and_degraded(tmp_path: Path, sample_manifest: dict):

    for install_fallback, expected_state in [(True, "full"), (False, "degraded")]:
        repo = tmp_path / f"repo-{expected_state}"
        (repo / "benches").mkdir(parents=True)
        (repo / "benches" / "bench_hot.py").write_text("pass\n", encoding="utf-8")

        manifest_path = tmp_path / f"manifest-{expected_state}.json"
        write_manifest(manifest_path, sample_manifest)

        skills_root = tmp_path / f".agents-{expected_state}" / "skills"
        write_skill(skills_root, "perf-benchmark")
        write_skill(skills_root, "verification-before-completion")
        if install_fallback:
            write_skill(skills_root, "m10-performance")

        report = checker.build_bootstrap_report(
            repo_root=repo,
            manifest_path=manifest_path,
            out_dir=tmp_path / f"out-{expected_state}",
            env={"HOME": str(tmp_path)},
            extra_roots=[skills_root.parent],
        )

        assert report["lanes"]["performance"]["state"] == expected_state


def test_performance_lane_manual_with_test_surface_no_benchmarks(
    tmp_path: Path,
    sample_manifest: dict,
    python_pytest_repo: Path,
):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["lanes"]["performance"]["state"] == "manual"
    assert any("No benchmark surface" in w for w in report["warnings"])


def test_scan_repo_profile_empty_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    profile = checker.scan_repo_profile(repo)

    assert profile["languages"] == []
    assert profile["test_systems"] == []
    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_test_surface"] is False
    assert profile["has_deterministic_perf_surface"] is False


def test_advisory_only_skill_state(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "asm").mkdir()
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    foreign = tmp_path / "foreign-skills"
    write_skill(foreign, "m15-anti-pattern")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        foreign_roots=[foreign],
    )

    assert report["skills"]["m15-anti-pattern"]["state"] == "advisory_only"
    assert report["skills"]["m15-anti-pattern"]["root_kind"] == "foreign"


def test_repo_level_override_applies(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    (repo / "asm").mkdir(parents=True)
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    repo_override = tmp_path / "repo-override.json"
    repo_override.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "m15-anti-pattern": {
                        "manual_fallback": "Custom fallback from repo override.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        repo_override_path=repo_override,
    )

    assert report["skills"]["m15-anti-pattern"]["manual_fallback"] == "Custom fallback from repo override."


def test_pyproject_toml_detects_pytest(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = '-v'\n",
        encoding="utf-8",
    )

    profile = checker.scan_repo_profile(repo)

    assert "python" in profile["languages"]
    assert "pytest" in profile["test_systems"]


def test_makefile_detects_make(tmp_path: Path):
    for makefile_name in ("Makefile", "GNUmakefile"):
        repo = tmp_path / f"repo-{makefile_name}"
        repo.mkdir()
        (repo / makefile_name).write_text("all:\n\techo ok\n", encoding="utf-8")

        profile = checker.scan_repo_profile(repo)

        assert "make" in profile["test_systems"], f"{makefile_name} should detect make"


def test_meson_build_detects_meson(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "meson.build").write_text("project('demo', 'c')\n", encoding="utf-8")

    profile = checker.scan_repo_profile(repo)

    assert "meson" in profile["test_systems"]


def test_bootstrap_lane_full(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "find-skills")
    write_skill(skills_root, "skill-installer")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["bootstrap"]
    assert lane["state"] == "full"
    assert "find-skills" in lane["selected_skills"]
    assert "skill-installer" in lane["selected_skills"]


def test_orchestration_lane_full_with_optional(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "verification-before-completion")
    write_skill(skills_root, "dispatching-parallel-agents")
    write_skill(skills_root, "subagent-driven-development")
    write_skill(skills_root, "perf-benchmark")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["orchestration"]
    assert lane["state"] == "full"
    assert "verification-before-completion" in lane["selected_skills"]
    assert "dispatching-parallel-agents" in lane["selected_skills"]
    assert "subagent-driven-development" in lane["selected_skills"]


def test_code_health_python_full_with_optional(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "m15-anti-pattern")
    write_skill(skills_root, "refactoring")
    write_skill(skills_root, "python-code-quality")
    write_skill(skills_root, "python-code-style")
    write_skill(skills_root, "dignified-code-simplifier")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["code-health-python"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == [
        "m15-anti-pattern",
        "refactoring",
        "python-code-quality",
        "python-code-style",
        "dignified-code-simplifier",
    ]


def test_markdown_report_structure(tmp_path: Path, sample_manifest: dict, python_pytest_repo: Path):
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    md = checker._markdown_report(report)

    assert "# Bootstrap Report" in md
    assert "## Lane States" in md
    assert "## Skill States" in md
    for lane_name, lane in report["lanes"].items():
        assert f"`{lane_name}`: `{lane['state']}`" in md


def test_install_plan_no_candidates(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )
    checker.write_bootstrap_outputs(report, tmp_path / "out")

    install_plan = (tmp_path / "out" / "bootstrap" / "install_plan.md").read_text(
        encoding="utf-8",
    )
    assert "No public install candidates" in install_plan


def test_matches_when_unknown_key_is_fail_closed(tmp_path: Path, sample_manifest: dict):
    """Unknown condition keys with expected=True should fail-close, not silently activate."""
    # Add a lane with an unknown condition key
    sample_manifest["lanes"]["impossible-lane"] = {
        "when": {"nonexistent_thing": True},
        "lane_type": "code_health",
        "preferred": ["m15-anti-pattern"],
        "manual_fallback": "Manual.",
        "blocking": False,
    }

    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    # The lane should NOT be activated since the condition cannot be satisfied
    assert "impossible-lane" not in report["summary"]["active_lanes"]


def test_require_skill_unknown_name_raises(tmp_path: Path, sample_manifest: dict):
    """--require-skill with a name not in the manifest should raise ValueError."""
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    with pytest.raises(ValueError, match="not defined in the manifest"):
        checker.build_bootstrap_report(
            repo_root=repo,
            manifest_path=manifest_path,
            out_dir=tmp_path / "out",
            env={"HOME": str(tmp_path)},
            required_skill_names=["totally-unknown-skill"],
        )


def test_scan_repo_profile_no_false_positive_from_parent_dir(tmp_path: Path):
    """Repo inside a 'benches' directory should not produce false-positive benchmark surfaces."""
    # Create the repo inside a parent dir named "benches"
    benches_dir = tmp_path / "benches"
    repo = benches_dir / "myproject"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    profile = checker.scan_repo_profile(repo)

    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_perf_surface"] is False


def test_code_health_c_lane_activation(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "m15-anti-pattern")
    write_skill(skills_root, "refactoring")
    write_skill(skills_root, "cpp-coding-standards")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "code-health-c" in report["summary"]["active_lanes"]
    assert report["lanes"]["code-health-c"]["state"] == "full"


def test_code_health_rust_lane_activation(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "Cargo.toml").write_text("[package]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    (repo / "src" / "lib.rs").write_text("pub fn hello() {}\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "m15-anti-pattern")
    write_skill(skills_root, "refactoring")
    write_skill(skills_root, "rust-best-practices")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "code-health-rust" in report["summary"]["active_lanes"]
    assert report["lanes"]["code-health-rust"]["state"] == "full"


def test_optional_install_candidate_does_not_force_restart_summary(
    tmp_path: Path,
    sample_manifest: dict,
    python_pytest_repo: Path,
):
    repo = python_pytest_repo

    sample_manifest["skills"]["hypothesis-testing"] = {
        **sample_manifest["skills"]["hypothesis-testing"],
        "source_type": "public",
        "install_source": {
            "method": "skills_cli",
            "package": "acme/skills@hypothesis-testing",
        },
    }

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["skills"]["hypothesis-testing"]["state"] == "installable_now"
    assert report["summary"]["restart_required"] is False


def test_public_skill_without_supported_install_command_is_manual_only(
    tmp_path: Path,
    sample_manifest: dict,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    sample_manifest["skills"]["public-helper"] = {
        "priority": "preferred",
        "source_type": "public",
        "install_source": {
            "method": "unknown",
            "package": "acme/skills@public-helper",
        },
        "manual_fallback": "Use fallback helper manually.",
        "restart_required_if_installed": True,
    }

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        required_skill_names=["public-helper"],
    )

    assert report["skills"]["public-helper"]["state"] == "manual_only"
    assert report["install_candidates"] == []


def test_main_cli_reports_validation_errors_cleanly(
    tmp_path: Path,
    sample_manifest: dict,
    capsys: pytest.CaptureFixture[str],
):
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    bad_override = tmp_path / "bad-override.json"
    bad_override.write_text("{not-json", encoding="utf-8")

    ret = checker.main(
        [
            "--repo", str(repo),
            "--manifest", str(manifest_path),
            "--out-dir", str(tmp_path / "out"),
            "--user-override", str(bad_override),
        ]
    )
    captured = capsys.readouterr()

    assert ret == 2
    assert "Malformed user override file" in captured.err
    assert "Traceback" not in captured.err


def test_build_bootstrap_report_rejects_missing_repo(tmp_path: Path, sample_manifest: dict):
    repo = tmp_path / "missing-repo"

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    with pytest.raises(ValueError, match="Repository root does not exist"):
        checker.build_bootstrap_report(
            repo_root=repo,
            manifest_path=manifest_path,
            out_dir=tmp_path / "out",
            env={"HOME": str(tmp_path)},
        )


def test_main_cli_reports_missing_manifest_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    repo = tmp_path / "repo"
    repo.mkdir()

    ret = checker.main(
        [
            "--repo", str(repo),
            "--manifest", str(tmp_path / "missing-manifest.json"),
            "--out-dir", str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()

    assert ret == 2
    assert "No such file or directory" in captured.err
    assert "Traceback" not in captured.err


def test_markdown_report_restart_label_matches_summary_semantics(
    tmp_path: Path,
    sample_manifest: dict,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    sample_manifest["skills"]["public-helper"] = {
        "priority": "preferred",
        "source_type": "public",
        "install_source": {
            "method": "skills_cli",
            "package": "acme/skills@public-helper",
        },
        "manual_fallback": "Use fallback helper manually.",
        "restart_required_if_installed": True,
    }

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        required_skill_names=["public-helper"],
    )
    md = checker._markdown_report(report)

    assert "Restart required before using strict installs" in md


def test_cpp_files_detect_c_language(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    profile = checker.scan_repo_profile(repo)

    assert "c" in profile["languages"]


def test_extract_skill_name_missing_name(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\ndescription: test skill\n---\n", encoding="utf-8")

    result = checker._extract_skill_name(skill_file)

    assert result is None


def test_extract_skill_name_unreadable_file(tmp_path: Path):
    nonexistent = tmp_path / "does-not-exist" / "SKILL.md"

    result = checker._extract_skill_name(nonexistent)

    assert result is None


def test_manifest_skill_missing_required_field(tmp_path: Path, sample_manifest: dict):
    sample_manifest["skills"]["m15-anti-pattern"].pop("priority")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    repo = tmp_path / "repo"
    (repo / "asm").mkdir(parents=True)
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    with pytest.raises(ValueError):
        checker.build_bootstrap_report(
            repo_root=repo,
            manifest_path=manifest_path,
            out_dir=tmp_path / "out",
            env={"HOME": str(tmp_path)},
        )


def test_native_benchmarks_surface_detection(tmp_path: Path):
    """A C file with 'bench' in its name triggers the native-benchmarks surface."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "bench_fft.c").write_text("int main(void){return 0;}\n", encoding="utf-8")

    profile = checker.scan_repo_profile(repo)

    assert "c" in profile["languages"]
    assert "native-benchmarks" in profile["benchmark_surfaces"]
    assert profile["has_deterministic_perf_surface"] is True


def test_cargo_benches_surface_detection(tmp_path: Path):
    """An .rs file inside a 'benches/' directory triggers the cargo-benches surface."""
    repo = tmp_path / "repo"
    (repo / "benches").mkdir(parents=True)
    (repo / "Cargo.toml").write_text("[package]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    (repo / "benches" / "my_bench.rs").write_text("fn main(){}\n", encoding="utf-8")

    profile = checker.scan_repo_profile(repo)

    assert "rust" in profile["languages"]
    assert "cargo-benches" in profile["benchmark_surfaces"]
    assert profile["has_deterministic_perf_surface"] is True


def test_unknown_lane_type_falls_back_with_warning(tmp_path: Path, sample_manifest: dict):
    """An unknown lane_type should use the orchestration evaluator and emit a warning."""
    sample_manifest["lanes"]["futuristic-lane"] = {
        "when": {"python": True},
        "lane_type": "quantum_computing",
        "preferred": [],
        "manual_fallback": "Use quantum manually.",
        "blocking": False,
    }

    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "futuristic-lane" in report["summary"]["active_lanes"]
    lane = report["lanes"]["futuristic-lane"]
    assert any("Unknown lane type" in w for w in lane["warnings"])
