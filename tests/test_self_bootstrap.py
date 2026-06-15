"""Self-bootstrap: git-source install command emission, dedup, install plan."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from scripts import _lane_resolve as lr
from scripts import _skill_probe as sp
from scripts._bootstrap_report import (
    _build_summary,
    _markdown_install_plan,
    build_bootstrap_report,
)

GIT_ENTRY = {
    "source_type": "user-local",
    "source": "repo-audit-skills",
    "install_source": {
        "method": "git",
        "url": "https://github.com/jc1122/repo-audit-skills.git",
        "tag": "v0.8.0",
        "install": ["node", "bin/install-repo-audit-skills.js", "--dest", "{dest}", "--force"],
    },
}


def test_git_source_emits_clone_and_install_command():
    cmd = sp._install_command_for_skill(GIT_ENTRY)
    assert cmd is not None
    assert "git clone --depth 1 -b v0.8.0" in cmd
    assert "https://github.com/jc1122/repo-audit-skills.git" in cmd
    assert "node bin/install-repo-audit-skills.js --dest {dest} --force" in cmd


def test_non_git_user_local_without_source_is_not_installable():
    entry = {"source_type": "user-local", "install_source": None}
    assert sp._install_command_for_skill(entry) is None


def test_public_skills_cli_branch_still_works():
    entry = {
        "source_type": "public",
        "install_source": {"method": "skills_cli", "package": "foo"},
    }
    assert sp._install_command_for_skill(entry) == "npx skills add foo -g -y"


def test_build_merged_skills_resolves_git_source_to_installable_now():
    manifest = {
        "skills": {
            "complexity-audit": {
                "priority": "preferred", "source_type": "user-local",
                "install_source": None, "manual_fallback": "x",
                "restart_required_if_installed": True, "source": "repo-audit-skills",
            },
        },
        "lanes": {},
        "sources": {
            "repo-audit-skills": {
                "kind": "git",
                "url": "https://github.com/jc1122/repo-audit-skills.git",
                "tag": "v0.8.0",
                "install": ["node", "bin/install-repo-audit-skills.js", "--dest", "{dest}", "--force"],
            }
        },
    }
    merged = lr._build_merged_skills({"complexity-audit"}, manifest, {}, {}, {})
    entry = merged["complexity-audit"]
    assert entry["state"] == "installable_now"
    assert entry["source"] == "repo-audit-skills"
    assert entry["install_source"]["method"] == "git"


def _missing_family_manifest():
    def leaf(src):
        return {
            "priority": "preferred", "source_type": "user-local", "install_source": None,
            "manual_fallback": "x", "restart_required_if_installed": True, "source": src,
        }
    return {
        "skills": {
            "complexity-audit": leaf("repo-audit-skills"),
            "security-audit": leaf("repo-audit-skills"),
            "perf-benchmark": leaf("perf-benchmark-skill"),
        },
        "lanes": {},
        "sources": {
            "repo-audit-skills": {"kind": "git",
                "url": "https://github.com/jc1122/repo-audit-skills.git",
                "tag": "v0.8.0", "install": ["node", "x.js", "--dest", "{dest}"]},
            "perf-benchmark-skill": {"kind": "git",
                "url": "https://github.com/jc1122/perf-benchmark-skill.git",
                "tag": "v0.6.0", "install": ["bash", "bootstrap/install-perf.sh", "{dest}"]},
        },
    }


def test_install_candidates_deduped_one_per_source():
    m = _missing_family_manifest()
    merged = lr._build_merged_skills(set(m["skills"]), m, {}, {}, {})
    candidates = lr._build_install_candidates(merged)
    names = sorted(c["name"] for c in candidates)
    assert names == ["perf-benchmark-skill", "repo-audit-skills"]  # 3 skills -> 2 cmds


def test_summary_restart_required_when_blocking_git_skill_missing():
    # Regression: after dedup, a git candidate's name is the SOURCE id, not a
    # skill name. _build_summary must match strict skills via the candidate's
    # `covers` list, else restart_required is wrongly False for a missing
    # blocking git-sourced skill.
    m = _missing_family_manifest()
    merged = lr._build_merged_skills(set(m["skills"]), m, {}, {}, {})
    candidates = lr._build_install_candidates(merged)
    summary = _build_summary(
        lanes={}, active_lanes=[], install_candidates=candidates,
        strict_skills={"perf-benchmark"},
    )
    assert summary["restart_required"] is True
    perf = next(c for c in candidates if c["name"] == "perf-benchmark-skill")
    assert "perf-benchmark" in perf["covers"]


def test_from_scratch_install_plan_lists_both_sources(tmp_path):
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n")
    empty_home = tmp_path / "home"
    empty_home.mkdir()
    env = {"HOME": str(empty_home), "AGENT_SKILLS_HOME": str(empty_home / ".codex"),
           "CODEX_HOME": str(empty_home / ".codex")}
    report = build_bootstrap_report(
        repo_root=repo,
        out_dir=tmp_path / "out",
        manifest_path=Path(__file__).resolve().parents[1] / "scripts" / "skill_bootstrap_manifest.json",
        extra_roots=[], foreign_roots=[],
        user_override_path=None, repo_override_path=None, env=env,
    )
    plan = _markdown_install_plan(report)
    assert "repo-audit-skills" in plan and "perf-benchmark-skill" in plan
    assert "git clone --depth 1 -b v0.8.0" in plan
    assert "git clone --depth 1 -b v0.6.0" in plan
    assert "{dest}" in plan  # documented placeholder present


def test_installer_dry_run_lists_repo_b_and_sources():
    script = Path(__file__).resolve().parents[1] / "bootstrap" / "install.sh"
    out = subprocess.run(
        ["bash", str(script), "--dry-run", "--dest", "/tmp/does-not-matter"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    text = out.stdout
    assert "repo-audit-refactor-optimize" in text       # installs repo-B first
    assert "repo-audit-skills" in text                   # then source repos
    assert "perf-benchmark-skill" in text
    assert "v0.8.0" in text and "v0.6.0" in text         # pinned tags from manifest


def test_install_loop_runs_against_file_url_source(tmp_path):
    # Build a tiny "source" git repo with an installer that drops a skill dir.
    src = tmp_path / "srcrepo"
    src.mkdir()
    (src / "install.sh").write_text(
        '#!/usr/bin/env bash\nset -e\nmkdir -p "$1/demo-skill"\n'
        'printf "name: demo-skill\\nversion: 1.0.0\\n" > "$1/demo-skill/SKILL.md"\n',
        encoding="utf-8",
    )
    subprocess.check_call(["git", "init", "-q", str(src)])
    subprocess.check_call(["git", "-C", str(src), "add", "-A"])
    subprocess.check_call(["git", "-C", str(src), "-c", "user.email=t@t",
                           "-c", "user.name=t", "commit", "-q", "-m", "init"])
    subprocess.check_call(["git", "-C", str(src), "tag", "v1.0.0"])

    dest = tmp_path / "skills"
    dest.mkdir()
    # Mirror install.sh's source loop directly (no network, file:// clone).
    sources = {"demo": {"url": f"file://{src}", "tag": "v1.0.0",
                        "install": ["bash", "install.sh", str(dest)]}}
    for sid, s in sources.items():
        tmp = tempfile.mkdtemp()
        subprocess.check_call(["git", "clone", "--depth", "1", "-b", s["tag"], s["url"], tmp])
        subprocess.check_call(s["install"], cwd=tmp)
    assert (dest / "demo-skill" / "SKILL.md").is_file()


@pytest.mark.skipif(os.environ.get("RUN_NETWORK_E2E") != "1",
                    reason="network e2e is opt-in (set RUN_NETWORK_E2E=1)")
def test_installer_real_network_into_temp_dest(tmp_path):
    script = Path(__file__).resolve().parents[1] / "bootstrap" / "install.sh"
    dest = tmp_path / "skills"
    rc = subprocess.run(["bash", str(script), "--dest", str(dest)],
                        capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
    assert (dest / "repo-audit-refactor-optimize" / "SKILL.md").is_file()
    assert (dest / "complexity-audit" / "SKILL.md").is_file()
    assert (dest / "perf-benchmark" / "SKILL.md").is_file()
