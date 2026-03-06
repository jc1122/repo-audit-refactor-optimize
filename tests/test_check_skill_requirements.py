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
    assert report["skills"]["perf-benchmark"]["state"] == "blocking_missing"


def test_main_cli_roundtrip(tmp_path: Path, sample_manifest: dict):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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
    checker = load_checker_module()
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        checker.load_dependency_manifest(bad)


def test_load_dependency_manifest_missing_keys(tmp_path: Path):
    checker = load_checker_module()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"skills": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        checker.load_dependency_manifest(bad)


def test_test_lane_full_with_optional(tmp_path: Path, sample_manifest: dict):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("pass\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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


def test_test_lane_manual_when_nothing_available(tmp_path: Path, sample_manifest: dict):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("pass\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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
    checker = load_checker_module()

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
):
    checker = load_checker_module()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("pass\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

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
    checker = load_checker_module()
    repo = tmp_path / "repo"
    repo.mkdir()

    profile = checker.scan_repo_profile(repo)

    assert profile["languages"] == []
    assert profile["test_systems"] == []
    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_test_surface"] is False
    assert profile["has_deterministic_perf_surface"] is False
