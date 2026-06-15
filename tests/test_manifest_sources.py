"""Guard: every user-local family skill resolves to a declared git source."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "skill_bootstrap_manifest.json"
# External (non-family) skills: installed from elsewhere, not our repos.
EXTERNAL = {"find-skills", "skill-installer"}


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_sources_are_well_formed():
    sources = _manifest()["sources"]
    assert sources, "manifest must declare git sources"
    for name, src in sources.items():
        assert src.get("kind") == "git", f"{name} must be kind=git"
        assert src.get("url", "").startswith("https://"), f"{name} needs an https url"
        # strict vX.Y.Z so the tag is safe to interpolate into a shell command
        assert re.fullmatch(r"v\d+\.\d+\.\d+", src.get("tag", "")), (
            f"{name} needs a vX.Y.Z tag"
        )
        assert isinstance(src.get("install"), list) and src["install"], (
            f"{name} needs a non-empty install array"
        )


def test_every_family_skill_has_a_resolvable_source():
    m = _manifest()
    sources = m["sources"]
    undefined = []
    for name, cfg in m["skills"].items():
        if cfg.get("source_type") != "user-local":
            continue
        if cfg.get("always_available") or name in EXTERNAL:
            continue
        src = cfg.get("source")
        if src not in sources:
            undefined.append((name, src))
    assert not undefined, f"family skills missing a valid source: {undefined}"
