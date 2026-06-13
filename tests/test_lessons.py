import json
import scripts.synthesize_packets as sp


def test_scope_matched_binding_lessons_injected_capped():
    lessons = [
        {"id": "L1", "tier": "binding", "scope": "worktree-setup",
         "text": "run npm ci in fresh worktrees", "command": "npm ci"},
        {"id": "L2", "tier": "candidate", "scope": "worktree-setup",
         "text": "candidate not yet proven", "command": ""},
        {"id": "L3", "tier": "binding", "scope": "release",
         "text": "changelog date must match commit date", "command": ""},
    ]
    packet = {"scope": "worktree-setup", "files": ["a.py"]}
    out = sp.inject_lessons(packet, lessons, cap=5)
    ids = [lz["id"] for lz in out["lessons"]]
    assert ids == ["L1"]            # only binding + scope match; candidate L2 excluded


def test_escalation_flag_after_three_fires():
    lesson = {"id": "L1", "tier": "binding", "fires": 3,
              "escalated": False, "scope": "worktree-setup"}
    assert sp.needs_automation(lesson) is True
    assert sp.needs_automation({**lesson, "fires": 2}) is False
