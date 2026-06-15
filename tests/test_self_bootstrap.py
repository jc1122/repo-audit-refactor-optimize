"""Self-bootstrap: git-source install command emission, dedup, install plan."""
import json
from pathlib import Path

from scripts import _skill_probe as sp

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
