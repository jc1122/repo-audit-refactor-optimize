"""Tests for scripts/mprr_partition.py."""
from __future__ import annotations
import importlib, sys
from dataclasses import dataclass
from pathlib import Path
from hypothesis import given, strategies as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
part = importlib.import_module("scripts.mprr_partition")


@dataclass(frozen=True)
class _It:
    id: str
    files: tuple[str, ...]


def test_shared_file_conflicts():
    assert part.conflicts(_It("a", ("x.py",)), _It("b", ("x.py", "y.py")))

def test_disjoint_files_do_not_conflict():
    assert not part.conflicts(_It("a", ("x.py",)), _It("b", ("y.py",)))

def test_eligible_iff_disjoint_from_locks():
    it = _It("a", ("x.py", "y.py"))
    assert part.eligible(it, set())
    assert part.eligible(it, {"z.py"})
    assert not part.eligible(it, {"y.py"})


@given(st.lists(st.lists(st.sampled_from("abcde"), min_size=1, max_size=3), max_size=8))
def test_eligible_matches_conflicts_against_a_single_running_item(file_lists):
    items = [_It(str(i), tuple(set(fs))) for i, fs in enumerate(file_lists)]
    for a in items:
        for b in items:
            locked = set(b.files)
            # a is eligible against b's locks iff a and b do not conflict
            assert part.eligible(a, locked) == (not part.conflicts(a, b))
