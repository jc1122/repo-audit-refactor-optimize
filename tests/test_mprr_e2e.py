"""End-to-end: normalize -> partition -> schedule drains with 0 conflicts."""
from __future__ import annotations
import importlib, json, random, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
norm = importlib.import_module("scripts.mprr_normalize")
sched = importlib.import_module("scripts.mprr_schedule")
FIX = REPO_ROOT / "tests" / "fixtures" / "mprr"


def _drain(items, ceiling, seed=0):
    rng = random.Random(seed)
    s = sched.SaturatingScheduler(items, ceiling=ceiling)
    running = {}
    while not s.done():
        for it in s.dispatchable():
            s.start(it); running[it.id] = it
            seen = set()
            for r in running.values():        # invariant holds every tick
                assert not (set(r.files) & seen); seen |= set(r.files)
        if running:
            k = rng.choice(list(running)); s.complete(k); running.pop(k)
    return True


def test_known_redundancy_drains_conflict_free():
    items = norm.normalize(json.loads((FIX / "known_redundancy" / "findings.json").read_text()))
    assert len(items) == 3
    # k3 EXTRACT spans a.py+b.py so it can never co-run with k1 or k2
    assert _drain(items, ceiling=8)


def test_degenerate_all_one_file_serializes():
    items = norm.normalize(json.loads((FIX / "degenerate" / "findings.json").read_text()))
    s = sched.SaturatingScheduler(items, ceiling=8)
    assert len(s.dispatchable()) == 1          # only one may run at a time
    assert _drain(items, ceiling=8)


def test_nonpython_fixture_is_handled():
    items = norm.normalize(json.loads((FIX / "nonpython" / "findings.json").read_text()))
    assert len(items) == 1 and items[0].files == ("app.js",)
    assert _drain(items, ceiling=8)
