"""Tests for scripts/mprr_packets.py."""
from __future__ import annotations
import importlib, sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
pk = importlib.import_module("scripts.mprr_packets")


@dataclass(frozen=True)
class _It:
    id: str; lane: str; signal: str; files: tuple[str, ...]
    remediation_class: str; confidence: str; finding: dict


def _item(**kw):
    base = dict(id="a", lane="dead-code", signal="DELETE", files=("pkg/m.py",),
                remediation_class="mechanical", confidence="high", finding={"suggested_action": "remove f"})
    base.update(kw); return _It(**base)


def test_packet_declares_only_item_files():
    p = pk.remediation_packet(_item(), repo="/r", lessons=[])
    assert p["files"] == ["pkg/m.py"]
    assert p["packet_id"] == "a"
    assert p["token_budget"] <= 8000


def test_refactor_packet_requires_mutation_in_must_run():
    p = pk.remediation_packet(_item(lane="duplication", signal="EXTRACT",
                                    remediation_class="refactor"), repo="/r", lessons=[])
    assert any("mutmut" in c or "mutation" in c for c in p["must_run"])


def test_lessons_capped_at_five():
    p = pk.remediation_packet(_item(), repo="/r", lessons=[f"L{i}" for i in range(9)])
    assert len(p["lessons"]) == 5
