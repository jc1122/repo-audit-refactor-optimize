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


def write_skill(root: Path, name: str, version: str | None = None) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = f"name: {name}"
    if version is not None:
        frontmatter += f"\nversion: {version}"
    (skill_dir / "SKILL.md").write_text(
        f"---\n{frontmatter}\ndescription: test skill\n---\n",
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
    assert report["skills"]["test-audit-pipeline"]["state"] == "installable_now"


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


def test_missing_local_skill_without_source_mapping_is_manual_only(
    tmp_path: Path,
):
    """A user-local skill that has no source entry in the manifest stays manual_only."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Build a minimal manifest with NO sources map so the skill stays manual_only.
    manifest_no_sources: dict = {
        "version": 2,
        "skills": {
            "complexity-audit": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "install manually",
                "restart_required_if_installed": True,
            },
        },
        "lanes": {},
    }
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest_no_sources)

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        required_skill_names=["complexity-audit"],
    )

    assert report["skills"]["complexity-audit"]["state"] == "manual_only"


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
                    "quality-audit": {
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

    assert report["skills"]["quality-audit"]["restart_required_if_installed"] is True
    assert any("quality-audit" in warning for warning in report["warnings"])


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
    # perf-benchmark has a git source so it is installable_now (not blocking_missing).
    assert report["skills"]["perf-benchmark"]["state"] == "installable_now"


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
    write_skill(skills_root, "test-audit-pipeline", version="0.3.0")
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


def test_performance_lane_full_with_perf_benchmark_and_optimization(
    tmp_path: Path, sample_manifest: dict
):
    repo = tmp_path / "repo"
    (repo / "benches").mkdir(parents=True)
    (repo / "benches" / "bench_hot.py").write_text("pass\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "perf-optimization", version="0.1.0")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        extra_roots=[skills_root.parent],
    )

    lane = report["lanes"]["performance"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["perf-benchmark", "perf-optimization"]
    assert lane["warnings"] == []


def test_performance_lane_degraded_when_only_perf_benchmark_installed(
    tmp_path: Path, sample_manifest: dict
):
    repo = tmp_path / "repo"
    (repo / "benches").mkdir(parents=True)
    (repo / "benches" / "bench_hot.py").write_text("pass\n", encoding="utf-8")

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
        extra_roots=[skills_root.parent],
    )

    lane = report["lanes"]["performance"]
    assert lane["state"] == "degraded"
    assert lane["selected_skills"] == ["perf-benchmark"]
    assert lane["warnings"] == [
        "Optimization skill missing; lane remains benchmark-first."
    ]


def test_performance_lane_synthesizable_with_test_surface_no_benchmarks(
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

    assert report["lanes"]["performance"]["state"] == "synthesizable"
    assert "perf-benchmark" in report["lanes"]["performance"]["selected_skills"]
    assert any("synthesi" in w.lower() for w in report["lanes"]["performance"]["warnings"])


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
    """An always-available process skill resolves usable_now/harness even when only
    a foreign-rooted copy is discovered.

    ``verification-before-completion`` carries ``always_available: true`` in the real
    manifest (G4), so it short-circuits to a harness-guaranteed ``usable_now`` regardless
    of where it is found — it is never downgraded to ``advisory_only`` by a foreign root.
    (The plain advisory_only path for non-always-available skills is unit-tested by
    ``tests/test_skill_probe.py::test_skill_entry_marks_advisory_only_when_only_advisory_discovery``.)
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "asm").mkdir()
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    foreign = tmp_path / "foreign-skills"
    write_skill(foreign, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
        foreign_roots=[foreign],
    )

    assert report["skills"]["verification-before-completion"]["state"] == "usable_now"
    assert report["skills"]["verification-before-completion"]["root_kind"] == "harness"


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
                        "verification-before-completion": {
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

    assert report["skills"]["verification-before-completion"]["manual_fallback"] == "Custom fallback from repo override."


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
    write_skill(skills_root, "code-health-audit-pipeline", version="0.3.0")
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
    assert lane["selected_skills"] == ["code-health-audit-pipeline"]


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


def test_install_plan_no_candidates(tmp_path: Path):
    """When all active skills are installed, the install plan reports no candidates."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Use a minimal manifest with only skills we will install — no sources needed.
    minimal_manifest: dict = {
        "version": 2,
        "skills": {
            "perf-benchmark": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "manual",
                "restart_required_if_installed": True,
            },
            "perf-optimization": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "manual",
                "restart_required_if_installed": True,
            },
            "verification-before-completion": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "manual",
                "restart_required_if_installed": True,
                "always_available": True,
            },
        },
        "lanes": {
            "performance": {
                "always": True,
                "lane_type": "performance",
                "preferred": ["perf-benchmark"],
                "fallback": ["perf-optimization"],
                "manual_fallback": "manual",
                "blocking": True,
            },
            "orchestration": {
                "always": True,
                "lane_type": "orchestration",
                "preferred": ["verification-before-completion"],
                "manual_fallback": "manual",
                "blocking": False,
            },
        },
    }

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, minimal_manifest)

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
    assert report["install_candidates"] == []
    assert "No" in install_plan and "install candidates" in install_plan


def test_matches_when_unknown_key_is_fail_closed(tmp_path: Path, sample_manifest: dict):
    """Unknown condition keys with expected=True should fail-close, not silently activate."""
    # Add a lane with an unknown condition key
    sample_manifest["lanes"]["impossible-lane"] = {
        "when": {"nonexistent_thing": True},
        "lane_type": "code_health",
        "preferred": ["helper-a"],
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


def test_optional_install_candidate_does_not_force_restart_summary(
    tmp_path: Path,
    sample_manifest: dict,
    python_pytest_repo: Path,
):
    repo = python_pytest_repo

    sample_manifest["skills"]["quality-audit"] = {
        **sample_manifest["skills"]["quality-audit"],
        "source_type": "public",
        "install_source": {
            "method": "skills_cli",
            "package": "acme/skills@quality-audit",
        },
    }

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, sample_manifest)

    # Install the strict (blocking) skills so they aren't in install_candidates.
    # The performance lane is blocking=true, so perf-benchmark/perf-optimization
    # are strict skills.  quality-audit is optional — its installable_now state
    # must NOT flip restart_required=True in the summary.
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "perf-optimization")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["skills"]["quality-audit"]["state"] == "installable_now"
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
    # public-helper has no install command; verify it is NOT in install_candidates.
    candidate_names = {c["name"] for c in report["install_candidates"]}
    assert "public-helper" not in candidate_names


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
    sample_manifest["skills"]["complexity-audit"].pop("priority")

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


def _lane_manifest(lane_type: str, *, preferred, fallback=None, optional=None, always=False) -> dict:
    skills = {}
    for name in [*preferred, *(fallback or []), *(optional or [])]:
        skills[name] = {
            "priority": "preferred",
            "source_type": "user-local",
            "install_source": None,
            "manual_fallback": f"Manual fallback for {name}.",
            "restart_required_if_installed": True,
        }
    lane: dict = {
        "lane_type": lane_type,
        "preferred": list(preferred),
        "manual_fallback": "Manual lane fallback.",
        "blocking": False,
    }
    if always:
        lane["always"] = True
    else:
        lane["when"] = {"python": True}
    if fallback is not None:
        lane["fallback"] = list(fallback)
    if optional is not None:
        lane["optional"] = list(optional)
    return {"version": 1, "skills": skills, "lanes": {"lane-under-test": lane}}


def _python_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    return repo


def test_code_health_lane_degrades_to_fallback_leaves(tmp_path: Path):
    repo = _python_repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        _lane_manifest("code_health", preferred=["umbrella-skill"], fallback=["leaf-a", "leaf-b"]),
    )
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "leaf-a")
    write_skill(skills_root, "leaf-b")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "degraded"
    assert lane["selected_skills"] == ["leaf-a", "leaf-b"]
    assert lane["warnings"] == [
        "Preferred code-health umbrella unavailable; using leaf audits directly."
    ]


def test_coverage_lane_full_when_leaf_usable(tmp_path: Path):
    repo = _python_repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _lane_manifest("coverage", preferred=["cov-leaf"]))
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "cov-leaf")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["cov-leaf"]
    assert lane["warnings"] == []


def test_coverage_lane_manual_when_leaf_missing(tmp_path: Path):
    repo = _python_repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _lane_manifest("coverage", preferred=["cov-leaf"]))

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "manual"
    assert lane["selected_skills"] == []


def test_performance_lane_full_with_no_fallback_declared(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "benches").mkdir()
    (repo / "benches" / "bench_hot.py").write_text("def bench_hot(): pass\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _lane_manifest("performance", preferred=["bench-skill"], always=True))
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "bench-skill")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["bench-skill"]
    assert lane["warnings"] == []


EXPECTED_MANIFEST_SKILLS = {
    "find-skills",
    "skill-installer",
    "test-audit-pipeline",
    "test-quality-assurance",
    "test-redundancy-triage",
    "code-health-audit-pipeline",
    "complexity-audit",
    "duplication-audit",
    "dead-code-audit",
    "structure-audit",
    "quality-audit",
    "coverage-gap-audit",
    "perf-benchmark",
    "verification-before-completion",
    "dispatching-parallel-agents",
    "subagent-driven-development",
    "hotspot-audit",
    "dependency-audit",
    "repo-hygiene-audit",
    "docs-consistency-audit",
    "security-audit",
    "test-effectiveness-audit",
    "perf-optimization",
}


EXPECTED_MANIFEST_LANES = {
    "bootstrap",
    "test-python",
    "code-health-python",
    "coverage-python",
    "security",
    "performance",
    "hygiene",
    "orchestration",
}


def test_production_manifest_contains_only_first_party_and_process_skills():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert set(manifest["skills"]) == EXPECTED_MANIFEST_SKILLS
    assert set(manifest["lanes"]) == EXPECTED_MANIFEST_LANES


def test_python_repo_resolves_all_deterministic_lanes_full(tmp_path: Path, python_pytest_repo: Path):
    skills_root = tmp_path / ".agents" / "skills"
    for name in [
        "test-audit-pipeline",
        "code-health-audit-pipeline",
        "coverage-gap-audit",
    ]:
        write_skill(skills_root, name, version="0.3.0")

    report = checker.build_bootstrap_report(
        repo_root=python_pytest_repo,
        manifest_path=MANIFEST_PATH,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["lanes"]["test-python"]["state"] == "full"
    assert report["lanes"]["test-python"]["selected_skills"] == ["test-audit-pipeline"]
    assert report["lanes"]["code-health-python"]["state"] == "full"
    assert report["lanes"]["code-health-python"]["selected_skills"] == ["code-health-audit-pipeline"]
    assert report["lanes"]["coverage-python"]["state"] == "full"
    assert report["lanes"]["coverage-python"]["selected_skills"] == ["coverage-gap-audit"]


def test_code_health_python_degrades_to_leaves_on_production_manifest(
    tmp_path: Path, python_pytest_repo: Path
):
    skills_root = tmp_path / ".agents" / "skills"
    for name in [
        "complexity-audit",
        "duplication-audit",
        "dead-code-audit",
        "structure-audit",
        "quality-audit",
    ]:
        write_skill(skills_root, name, version="0.3.0")

    report = checker.build_bootstrap_report(
        repo_root=python_pytest_repo,
        manifest_path=MANIFEST_PATH,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["code-health-python"]
    assert lane["state"] == "degraded"
    assert lane["selected_skills"] == [
        "complexity-audit",
        "duplication-audit",
        "dead-code-audit",
        "structure-audit",
        "quality-audit",
    ]


def test_non_python_repo_activates_no_code_health_lane(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "asm").mkdir(parents=True)
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=MANIFEST_PATH,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    active = set(report["summary"]["active_lanes"])
    assert "code-health-python" not in active
    assert "coverage-python" not in active
    assert not any(name.startswith("code-health-") and name != "code-health-python" for name in report["lanes"])


# ---------------------------------------------------------------------------
# SP7 B1: min_version-aware skill resolution
# ---------------------------------------------------------------------------


def test_skill_with_old_version_is_stale_installed(tmp_path: Path):
    """Skill at version 1.0.0 < min_version 2.0.0 → stale_installed, lane manual."""
    repo = _python_repo(tmp_path)
    manifest = _lane_manifest("test", preferred=["audit-skill"])
    manifest["skills"]["audit-skill"]["min_version"] = "2.0.0"

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "audit-skill", version="1.0.0")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    skill = report["skills"]["audit-skill"]
    assert skill["state"] == "stale_installed"
    assert skill["found_version"] == "1.0.0"
    assert skill["min_version"] == "2.0.0"
    assert any(
        "audit-skill" in w and "1.0.0" in w and "2.0.0" in w
        for w in report["warnings"]
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "manual"


def test_skill_meeting_min_version_is_usable(tmp_path: Path):
    """Skill at version 2.0.0 ≥ min_version 2.0.0 → usable_now, lane full."""
    repo = _python_repo(tmp_path)
    manifest = _lane_manifest("test", preferred=["audit-skill"])
    manifest["skills"]["audit-skill"]["min_version"] = "2.0.0"

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "audit-skill", version="2.0.0")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    skill = report["skills"]["audit-skill"]
    assert skill["state"] == "usable_now"

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "full"


def test_skill_without_version_frontmatter_is_stale_when_min_version_set(
    tmp_path: Path,
):
    """Skill without version frontmatter + min_version → stale_installed, lane manual."""
    repo = _python_repo(tmp_path)
    manifest = _lane_manifest("test", preferred=["audit-skill"])
    manifest["skills"]["audit-skill"]["min_version"] = "1.0.0"

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "audit-skill")  # no version frontmatter

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    skill = report["skills"]["audit-skill"]
    assert skill["state"] == "stale_installed"
    assert skill["found_version"] == "unknown"
    assert skill["min_version"] == "1.0.0"
    assert any(
        "audit-skill" in w and "unknown" in w
        for w in report["warnings"]
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "manual"


def test_manifest_without_min_version_behaves_as_today(tmp_path: Path):
    """No min_version at all → usable_now, no version fields, lane full."""
    repo = _python_repo(tmp_path)
    manifest = _lane_manifest("test", preferred=["audit-skill"])

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "audit-skill", version="1.0.0")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    skill = report["skills"]["audit-skill"]
    assert skill["state"] == "usable_now"
    assert "min_version" not in skill
    assert "found_version" not in skill

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "full"


# ---------------------------------------------------------------------------
# SP7 B2: advisory unreferenced-skills section
# ---------------------------------------------------------------------------


def test_unreferenced_skill_appears_in_report_and_markdown(tmp_path: Path):
    """An on-disk skill not referenced by the manifest is listed as unreferenced."""
    repo = _python_repo(tmp_path)
    manifest = _lane_manifest("test", preferred=["audit-skill"])

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "audit-skill")
    write_skill(skills_root, "orphan-skill")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["unreferenced_skills"] == ["orphan-skill"]
    assert report["summary"]["stop_before_discovery"] is False

    md = checker._markdown_report(report)
    assert "## Unreferenced Skills (advisory)" in md
    assert "`orphan-skill`" in md
    assert "`audit-skill`" not in md.split("## Unreferenced Skills (advisory)")[-1] \
        if "## Unreferenced Skills (advisory)" in md else True


def test_no_unreferenced_section_when_all_skills_referenced(tmp_path: Path):
    """No orphan skills → unreferenced_skills is empty and markdown omits section."""
    repo = _python_repo(tmp_path)
    manifest = _lane_manifest("test", preferred=["audit-skill"])

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "audit-skill")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["unreferenced_skills"] == []
    assert report["summary"]["stop_before_discovery"] is False

    md = checker._markdown_report(report)
    assert "## Unreferenced Skills (advisory)" not in md


# ---------------------------------------------------------------------------
# SP7 B7: hygiene + security lanes, hotspot/test-effectiveness optionals,
#         min_version pins
# ---------------------------------------------------------------------------

# -- hygiene lane tests ------------------------------------------------------


def test_hygiene_lane_full_with_only_repo_hygiene_audit(
    tmp_path: Path,
):
    """Hygiene lane: full with only repo-hygiene-audit installed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "repo-hygiene-audit", version="0.4.0")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["hygiene"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["repo-hygiene-audit"]


def test_hygiene_lane_selected_skills_grows_with_optionals(
    tmp_path: Path,
):
    """Hygiene lane: selected skills grow to include installed optionals."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "repo-hygiene-audit", version="0.4.0")
    write_skill(skills_root, "dependency-audit", version="0.4.0")
    write_skill(skills_root, "docs-consistency-audit", version="0.4.0")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["hygiene"]
    assert lane["state"] == "full"
    assert "repo-hygiene-audit" in lane["selected_skills"]
    assert "dependency-audit" in lane["selected_skills"]
    assert "docs-consistency-audit" in lane["selected_skills"]
    assert len(lane["selected_skills"]) == 3


# -- security lane tests -----------------------------------------------------


def test_security_lane_manual_on_python_without_security_audit(
    tmp_path: Path,
    python_pytest_repo: Path,
):
    """Security lane is manual on a Python repo without security-audit."""
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["security"]
    assert lane["state"] == "manual"
    assert lane["selected_skills"] == []


def test_security_lane_full_on_python_with_security_audit(
    tmp_path: Path,
    python_pytest_repo: Path,
):
    """Security lane is full on a Python repo with security-audit installed."""
    repo = python_pytest_repo

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "security-audit", version="0.4.0")
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["security"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["security-audit"]


def test_security_lane_not_active_on_non_python_repo(tmp_path: Path):
    """Security lane is NOT activated on a non-Python repo."""
    repo = tmp_path / "repo"
    (repo / "asm").mkdir(parents=True)
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "security" not in report["lanes"]


# -- production manifest shape tests -----------------------------------------


def test_production_manifest_skill_count_is_23():
    """The production manifest has exactly 23 skills (22 existing + perf-optimization)."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert len(manifest["skills"]) == 23
    assert set(manifest["skills"]) == EXPECTED_MANIFEST_SKILLS


def test_production_manifest_lane_count_is_8():
    """The production manifest has exactly 8 lanes (6 existing + hygiene + security)."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert len(manifest["lanes"]) == 8
    assert set(manifest["lanes"]) == EXPECTED_MANIFEST_LANES


def test_production_manifest_code_health_python_optional_is_hotspot_audit():
    """code-health-python lane has optional: [hotspot-audit]."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lane = manifest["lanes"]["code-health-python"]
    assert lane["optional"] == ["hotspot-audit"]


def test_production_manifest_test_python_optional_is_test_effectiveness_audit():
    """test-python lane has optional: [test-effectiveness-audit]."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lane = manifest["lanes"]["test-python"]
    assert lane["optional"] == ["test-effectiveness-audit"]


# -- min_version assertions --------------------------------------------------

_NEW_LEAF_NAMES = [
    "hotspot-audit",
    "dependency-audit",
    "repo-hygiene-audit",
    "docs-consistency-audit",
    "security-audit",
    "test-effectiveness-audit",
]

_EXISTING_REPO_AUDIT_FAMILY = [
    "code-health-audit-pipeline",
    "complexity-audit",
    "duplication-audit",
    "dead-code-audit",
    "structure-audit",
    "quality-audit",
    "coverage-gap-audit",
    "test-audit-pipeline",
]


def test_six_new_leaves_have_min_version_0_4_0():
    """The six new SP7 leaves have min_version == '0.4.0'."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for name in _NEW_LEAF_NAMES:
        assert name in manifest["skills"], f"{name} not in manifest skills"
        skill = manifest["skills"][name]
        assert skill.get("min_version") == "0.4.0", (
            f"{name} min_version={skill.get('min_version')}, expected 0.4.0"
        )


def test_eight_existing_leaves_have_min_version_0_3_0():
    """The eight existing repo-audit-skills family entries have min_version == '0.3.0'."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for name in _EXISTING_REPO_AUDIT_FAMILY:
        assert name in manifest["skills"], f"{name} not in manifest skills"
        skill = manifest["skills"][name]
        assert skill.get("min_version") == "0.3.0", (
            f"{name} min_version={skill.get('min_version')}, expected 0.3.0"
        )


# -- literal lane shape assertions -------------------------------------------


def test_hygiene_lane_shape_literal():
    """The hygiene lane shape matches the pinned spec exactly."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lane = manifest["lanes"]["hygiene"]
    assert lane == {
        "always": True,
        "lane_type": "audit",
        "preferred": ["repo-hygiene-audit"],
        "fallback": [],
        "optional": ["dependency-audit", "docs-consistency-audit"],
        "manual_fallback": (
            "Review repo hygiene manually (tracked artifacts, configs, "
            "release files) when the leaf is unavailable."
        ),
        "blocking": False,
    }


def test_security_lane_shape_literal():
    """The security lane shape matches the pinned spec exactly."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lane = manifest["lanes"]["security"]
    assert lane == {
        "when": {"python": True},
        "lane_type": "audit",
        "preferred": ["security-audit"],
        "fallback": [],
        "manual_fallback": (
            "Perform a manual security review; "
            "the bandit-based leaf is unavailable."
        ),
        "blocking": False,
    }


def test_hygiene_lane_always_active(tmp_path: Path):
    """Hygiene lane is active on any repo (always: true)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "hygiene" in report["lanes"]
    assert "hygiene" in report["summary"]["active_lanes"]


def test_hygiene_lane_degrades_to_manual_when_preferred_missing(
    tmp_path: Path,
):
    """Hygiene lane is manual when repo-hygiene-audit is not installed."""
    repo = tmp_path / "repo"
    repo.mkdir()

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "perf-benchmark")
    write_skill(skills_root, "verification-before-completion")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["hygiene"]
    assert lane["state"] == "manual"
    assert lane["selected_skills"] == []


def test_benchmark_named_tooling_is_not_a_surface(tmp_path: Path):
    """Source/test files that merely mention 'benchmark' are not a benchmark surface."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts" / "graduate_benchmark.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests" / "test_graduate_benchmark.py").write_text("def test_x(): pass\n", encoding="utf-8")
    profile = checker.scan_repo_profile(repo)
    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_perf_surface"] is False


def test_benchmark_utils_at_src_is_not_a_surface(tmp_path: Path):
    """A 'benchmark'-substring utility outside a benchmark dir is not a surface."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "benchmark_utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    profile = checker.scan_repo_profile(repo)
    assert profile["has_deterministic_perf_surface"] is False


def test_real_harness_under_benchmarks_dir_is_a_surface(tmp_path: Path):
    """A graduated harness (bench_*.py under benchmarks/) is still a real surface."""
    repo = tmp_path / "repo"
    (repo / "benchmarks" / "sort").mkdir(parents=True)
    (repo / "benchmarks" / "sort" / "bench_sort.py").write_text("def main(): pass\n", encoding="utf-8")
    profile = checker.scan_repo_profile(repo)
    assert profile["benchmark_surfaces"] == ["python-benchmarks"]
    assert profile["has_deterministic_perf_surface"] is True
