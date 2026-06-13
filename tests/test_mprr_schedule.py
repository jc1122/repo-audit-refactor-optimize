"""Tests for scripts/mprr_schedule.py — the saturating scheduler invariant."""
from __future__ import annotations
import importlib, random, sys
from dataclasses import dataclass
from pathlib import Path
from hypothesis import given, settings, strategies as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sched = importlib.import_module("scripts.mprr_schedule")


@dataclass(frozen=True)
class _It:
    id: str
    files: tuple[str, ...]


def _items(specs):
    return [_It(str(i), tuple(sorted(set(fs)))) for i, fs in enumerate(specs)]


def test_dispatchable_never_co_locks_shared_files():
    s = sched.SaturatingScheduler(_items([["x"], ["x", "y"], ["z"]]), ceiling=4)
    batch = s.dispatchable()
    seen: set[str] = set()
    for it in batch:
        assert not (set(it.files) & seen)
        seen |= set(it.files)


def test_respects_ceiling():
    s = sched.SaturatingScheduler(_items([["a"], ["b"], ["c"]]), ceiling=2)
    assert len(s.dispatchable()) == 2


def test_completing_releases_locks_for_blocked_item():
    s = sched.SaturatingScheduler(_items([["x"], ["x"]]), ceiling=4)
    first = s.dispatchable()
    assert len(first) == 1           # second shares "x", blocked
    s.start(first[0])
    assert s.dispatchable() == []    # still blocked while first runs
    s.complete(first[0].id)
    assert len(s.dispatchable()) == 1  # now free


@settings(max_examples=200)
@given(specs=st.lists(st.lists(st.sampled_from("abcd"), min_size=1, max_size=3), max_size=10),
       ceiling=st.integers(min_value=1, max_value=5), seed=st.integers())
def test_invariant_and_liveness_under_random_completion(specs, ceiling, seed):
    rng = random.Random(seed)
    s = sched.SaturatingScheduler(_items(specs), ceiling=ceiling)
    running: dict[str, _It] = {}
    started = 0
    total = len(specs)
    steps = 0
    while not s.done():
        steps += 1
        assert steps < 10_000, "scheduler failed to make progress (liveness)"
        for it in s.dispatchable():
            s.start(it); running[it.id] = it; started += 1
        # INVARIANT: running items are pairwise file-disjoint
        seen: set[str] = set()
        for it in running.values():
            assert not (set(it.files) & seen)
            seen |= set(it.files)
        if running:
            done_id = rng.choice(list(running))
            s.complete(done_id); running.pop(done_id)
    assert started == total  # every item eventually ran
