from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_checker_module():
    return importlib.import_module("scripts.check_skill_requirements")


def write_skill(root: Path, name: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\n",
        encoding="utf-8",
    )


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.fixture
def sample_manifest() -> dict:
    return {
        "version": 1,
        "skills": {
            "find-skills": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Use raw npx skills find.",
                "restart_required_if_installed": False,
            },
            "skill-installer": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Use raw npx skills add.",
                "restart_required_if_installed": False,
            },
            "test-audit-pipeline": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Use manual test audit.",
                "restart_required_if_installed": True,
            },
            "test-quality-assurance": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Audit test quality manually.",
                "restart_required_if_installed": True,
            },
            "test-redundancy-triage": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Review redundant tests manually.",
                "restart_required_if_installed": True,
            },
            "hypothesis-testing": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Use example-based invariant checks.",
                "restart_required_if_installed": True,
            },
            "m15-anti-pattern": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Review anti-patterns manually.",
                "restart_required_if_installed": True,
            },
            "refactoring": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Refactor conservatively without the skill.",
                "restart_required_if_installed": True,
            },
            "python-code-quality": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Review linting and typing manually.",
                "restart_required_if_installed": True,
            },
            "python-code-style": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Review style manually.",
                "restart_required_if_installed": True,
            },
            "dignified-code-simplifier": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Simplify Python manually.",
                "restart_required_if_installed": True,
            },
            "cpp-coding-standards": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Apply C/C++ review manually.",
                "restart_required_if_installed": True,
            },
            "rust-best-practices": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Review Rust manually.",
                "restart_required_if_installed": True,
            },
            "perf-benchmark": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Use manual benchmark discipline.",
                "restart_required_if_installed": True,
            },
            "m10-performance": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Optimize from profiling evidence manually.",
                "restart_required_if_installed": True,
            },
            "performance-testing": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Use service-level performance checks manually.",
                "restart_required_if_installed": True,
            },
            "dispatching-parallel-agents": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Run lanes sequentially.",
                "restart_required_if_installed": True,
            },
            "subagent-driven-development": {
                "priority": "optional",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Execute batches sequentially in one agent.",
                "restart_required_if_installed": True,
            },
            "verification-before-completion": {
                "priority": "preferred",
                "source_type": "user-local",
                "install_source": None,
                "manual_fallback": "Manually rerun verification before closing.",
                "restart_required_if_installed": True,
            },
            "public-helper": {
                "priority": "preferred",
                "source_type": "public",
                "install_source": {
                    "method": "skills_cli",
                    "package": "acme/skills@public-helper",
                },
                "manual_fallback": "Use fallback helper manually.",
                "restart_required_if_installed": True,
            },
        },
        "lanes": {
            "bootstrap": {
                "always": True,
                "lane_type": "bootstrap",
                "preferred": ["find-skills", "skill-installer"],
                "fallback": [],
                "manual_fallback": "Use raw Skills CLI commands.",
                "blocking": False,
            },
            "test-python": {
                "when": {"python": True, "pytest": True},
                "lane_type": "test",
                "preferred": ["test-audit-pipeline"],
                "fallback": ["test-quality-assurance", "test-redundancy-triage"],
                "optional": ["hypothesis-testing"],
                "manual_fallback": "Run a manual deterministic test audit.",
                "blocking": False,
            },
            "code-health-python": {
                "when": {"python": True},
                "lane_type": "code_health",
                "preferred": [
                    "m15-anti-pattern",
                    "refactoring",
                    "python-code-quality",
                    "python-code-style",
                ],
                "optional": ["dignified-code-simplifier"],
                "manual_fallback": "Review Python code health manually.",
                "blocking": False,
            },
            "code-health-c": {
                "when": {"c": True},
                "lane_type": "code_health",
                "preferred": ["m15-anti-pattern", "refactoring", "cpp-coding-standards"],
                "manual_fallback": "Review C code health manually.",
                "blocking": False,
            },
            "code-health-rust": {
                "when": {"rust": True},
                "lane_type": "code_health",
                "preferred": ["m15-anti-pattern", "refactoring", "rust-best-practices"],
                "manual_fallback": "Review Rust code health manually.",
                "blocking": False,
            },
            "code-health-assembly": {
                "when": {"assembly": True},
                "lane_type": "code_health",
                "preferred": ["m15-anti-pattern"],
                "manual_fallback": "Review assembly-adjacent code health manually.",
                "blocking": False,
            },
            "performance": {
                "always": True,
                "lane_type": "performance",
                "preferred": ["perf-benchmark"],
                "fallback": ["m10-performance"],
                "optional": ["performance-testing"],
                "manual_fallback": "Use deterministic manual performance review.",
                "blocking": True,
            },
            "orchestration": {
                "always": True,
                "lane_type": "orchestration",
                "preferred": ["verification-before-completion"],
                "optional": [
                    "dispatching-parallel-agents",
                    "subagent-driven-development",
                ],
                "manual_fallback": "Run verification manually and execute sequentially.",
                "blocking": False,
            },
        },
    }


def test_scan_repo_profile_detects_languages_and_surfaces(tmp_path: Path):
    checker = load_checker_module()
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
    checker = load_checker_module()
    repo = tmp_path / "repo"
    repo.mkdir()

    codex_home = tmp_path / "codex-home"
    codex_skills = codex_home / "skills"
    bundled = codex_home / "vendor_imports" / "skills" / "skills"
    agents = tmp_path / ".agents" / "skills"
    repo_local = repo / ".agents" / "skills"
    extra = tmp_path / "extra-skills"
    foreign = tmp_path / "foreign-skills"

    for root in [codex_skills, bundled, agents, repo_local, extra, foreign]:
        write_skill(root, "demo-skill")

    roots = checker.resolve_skill_roots(
        repo_root=repo,
        extra_roots=[extra],
        foreign_roots=[foreign],
        env={"CODEX_HOME": str(codex_home), "HOME": str(tmp_path)},
    )

    assert [item["path"] for item in roots["usable_roots"]] == [
        str(codex_skills),
        str(bundled),
        str(agents),
        str(repo_local),
        str(extra),
    ]
    assert [item["path"] for item in roots["advisory_roots"]] == [str(foreign)]


def test_python_repo_uses_tqa_triage_fallback_when_pipeline_missing(
    tmp_path: Path,
    sample_manifest: dict,
):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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
    checker = load_checker_module()
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
    checker = load_checker_module()
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
    checker = load_checker_module()
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
    checker = load_checker_module()
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


def test_bad_optional_override_entry_is_ignored(tmp_path: Path, sample_manifest: dict):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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


def test_bad_active_optional_override_entry_is_ignored(tmp_path: Path, sample_manifest: dict):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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
    checker = load_checker_module()
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
    checker = load_checker_module()
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
