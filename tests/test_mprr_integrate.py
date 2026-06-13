"""Tests for scripts/mprr_integrate.py."""
from __future__ import annotations
import importlib, subprocess, sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
integ = importlib.import_module("scripts.mprr_integrate")


def test_assert_scope_accepts_subset():
    ok, reasons = integ.assert_scope(["a.py", "b.py"], ["a.py"])
    assert ok and reasons == []


def test_assert_scope_rejects_undeclared_file():
    ok, reasons = integ.assert_scope(["a.py"], ["a.py", "rogue.py"])
    assert not ok and any("rogue.py" in r for r in reasons)


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def _init_repo(tmp_path):
    repo = tmp_path / "r"; repo.mkdir()
    _git(repo, "init", "-q", "-b", "master"); _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (repo / "base.py").write_text("x = 1\n")
    _git(repo, "add", "."); _git(repo, "commit", "-qm", "base")
    return repo


def test_merge_clean_merges_disjoint_branch(tmp_path):
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-qb", "w1")
    (repo / "a.py").write_text("a = 1\n"); _git(repo, "add", "."); _git(repo, "commit", "-qm", "a")
    _git(repo, "checkout", "-q", "master")
    integ.merge_clean(str(repo), "w1")          # disjoint -> clean
    assert (repo / "a.py").exists()


def test_merge_clean_raises_on_conflict(tmp_path):
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-qb", "w1")
    (repo / "base.py").write_text("x = 2\n"); _git(repo, "add", "."); _git(repo, "commit", "-qm", "w1")
    _git(repo, "checkout", "-q", "master")
    (repo / "base.py").write_text("x = 3\n"); _git(repo, "add", "."); _git(repo, "commit", "-qm", "main")
    with pytest.raises(integ.InvariantViolation):
        integ.merge_clean(str(repo), "w1")      # overlapping edit -> must raise
