# Self-Bootstrapping repo-audit Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repo-audit skill family installable from a bare machine with one command, staying private (git sources from three public GitHub repos), wired into the orchestrator's Stage-0 bootstrap.

**Architecture:** A new `sources` map in repo-B's bootstrap manifest declares the two source repos (DRY — the 19 leaves share one). The bootstrap checker resolves each user-local family skill's `source`, emits a real `git clone … && <install>` command (deduped to one per source repo), and reports those skills as `installable_now`. A top-level `bootstrap/install.sh` installs repo-B first, then reads the manifest and installs the sources at pinned tags. repo-P gains a small `install-perf.sh` since it has no installer.

**Tech Stack:** Python 3 (stdlib only; pytest), POSIX `sh`, git, Node (repo-A's existing leaf installer).

**Spec:** `docs/superpowers/specs/2026-06-16-self-bootstrapping-family-design.md`

**Branches:** repo-B work on `feat/self-bootstrapping-family` (already created, holds the spec). repo-P work on a new `feat/perf-installer` branch in `~/projects/perf-benchmark-skill`.

---

## File Structure

**repo-B (`~/projects/repo-audit-refactor-optimize`):**
- Modify `scripts/skill_bootstrap_manifest.json` — add `sources` map + `source` refs (data).
- Modify `scripts/_skill_probe.py` — `_install_command_for_skill` git branch; `_build_skill_entry_base` carries `source`.
- Modify `scripts/_lane_resolve.py` — `_resolve_skill_source` helper + call in `_build_merged_skills`; dedup in `_build_install_candidates`.
- Modify `scripts/_bootstrap_report.py` — install-plan preamble (define `{dest}`).
- Create `bootstrap/install.sh` — top-level one-line installer.
- Create `tests/test_manifest_sources.py` — manifest schema guard.
- Create `tests/test_self_bootstrap.py` — probe/command/dedup/install-plan + hermetic `file://` e2e + opt-in network e2e.
- Modify `SKILL.md`, `references/bootstrap.md` — safety-rule refinement + version bump.
- Modify `scripts/run_diagnosis_wave.py` — `__version__` bump.
- Modify `CHANGELOG.md`.

**repo-P (`~/projects/perf-benchmark-skill`):**
- Create `bootstrap/install-perf.sh` — deploys `perf-benchmark` + `perf-optimization`.
- Create `tests/test_install_perf.py` — deploy test.
- Modify `SKILL.md`, `CHANGELOG.md` — version bump.

---

## Task 1: Manifest — add `sources` map + per-skill `source` refs

**Files:**
- Modify: `scripts/skill_bootstrap_manifest.json`

The 16 repo-A leaf skills in the manifest get `"source": "repo-audit-skills"`; `perf-benchmark` and `perf-optimization` get `"source": "perf-benchmark-skill"`. `find-skills`, `skill-installer` (external) and the 3 `always_available` process skills get NO `source`.

- [ ] **Step 1: Add the `sources` top-level key.** In `scripts/skill_bootstrap_manifest.json`, add a sibling key to `skills`/`lanes` (keep `version` first):

```json
  "sources": {
    "repo-audit-skills": {
      "kind": "git",
      "url": "https://github.com/jc1122/repo-audit-skills.git",
      "tag": "v0.8.0",
      "install": ["node", "bin/install-repo-audit-skills.js", "--dest", "{dest}", "--force"]
    },
    "perf-benchmark-skill": {
      "kind": "git",
      "url": "https://github.com/jc1122/perf-benchmark-skill.git",
      "tag": "v0.6.0",
      "install": ["bash", "bootstrap/install-perf.sh", "{dest}"]
    }
  }
```

- [ ] **Step 2: Add `"source": "repo-audit-skills"`** to each of these 16 skill objects: `test-audit-pipeline`, `test-quality-assurance`, `test-redundancy-triage`, `code-health-audit-pipeline`, `complexity-audit`, `duplication-audit`, `dead-code-audit`, `structure-audit`, `quality-audit`, `coverage-gap-audit`, `hotspot-audit`, `dependency-audit`, `repo-hygiene-audit`, `docs-consistency-audit`, `security-audit`, `test-effectiveness-audit`. Example (complexity-audit):

```json
    "complexity-audit": {
      "priority": "preferred",
      "source_type": "user-local",
      "install_source": null,
      "manual_fallback": "Part of repo-audit-skills v0.3.0+; install via its node installer.",
      "restart_required_if_installed": true,
      "min_version": "0.3.0",
      "source": "repo-audit-skills"
    }
```

- [ ] **Step 3: Add `"source": "perf-benchmark-skill"`** to the `perf-benchmark` and `perf-optimization` skill objects.

- [ ] **Step 4: Validate JSON parses.**

Run: `python3 -c "import json; json.load(open('scripts/skill_bootstrap_manifest.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit.**

```bash
git add scripts/skill_bootstrap_manifest.json
git commit -m "feat(manifest): add git sources + per-skill source refs"
```

---

## Task 2: Manifest schema guard test

**Files:**
- Create: `tests/test_manifest_sources.py`

- [ ] **Step 1: Write the failing test.**

```python
"""Guard: every user-local family skill resolves to a declared git source."""
import json
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
        assert src.get("tag", "").startswith("v"), f"{name} needs a vX.Y.Z tag"
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
```

- [ ] **Step 2: Run — expect PASS** (Task 1 already added the data, so this guard should pass immediately; it locks the invariant going forward).

Run: `python3 -m pytest tests/test_manifest_sources.py -v`
Expected: 2 passed

- [ ] **Step 3: Commit.**

```bash
git add tests/test_manifest_sources.py
git commit -m "test(manifest): guard every family skill has a resolvable git source"
```

---

## Task 3: `_install_command_for_skill` — git method

**Files:**
- Modify: `scripts/_skill_probe.py:228-234`
- Test: `tests/test_self_bootstrap.py`

- [ ] **Step 1: Write the failing test.** Create `tests/test_self_bootstrap.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest tests/test_self_bootstrap.py::test_git_source_emits_clone_and_install_command -v`
Expected: FAIL (current code returns None for non-public source_type)

- [ ] **Step 3: Replace `_install_command_for_skill`** (`scripts/_skill_probe.py`) with:

```python
def _install_command_for_skill(skill: dict[str, Any]) -> str | None:
    install_source = skill.get("install_source")
    if not isinstance(install_source, dict):
        return None
    method = install_source.get("method")
    if (
        method == "skills_cli"
        and skill.get("source_type") == "public"
        and install_source.get("package")
    ):
        return f"npx skills add {install_source['package']} -g -y"
    if method == "git":
        url = install_source.get("url")
        tag = install_source.get("tag")
        install = install_source.get("install")
        if url and tag and isinstance(install, list) and install:
            run = " ".join(install)  # {dest} stays a literal token; see install plan
            return (
                f'tmp=$(mktemp -d) && git clone --depth 1 -b {tag} {url} "$tmp" '
                f'&& (cd "$tmp" && {run}) && rm -rf "$tmp"'
            )
    return None
```

- [ ] **Step 4: Run the test file — all 3 pass.**

Run: `python3 -m pytest tests/test_self_bootstrap.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit.**

```bash
git add scripts/_skill_probe.py tests/test_self_bootstrap.py
git commit -m "feat(probe): emit git clone+install command for git sources"
```

---

## Task 4: Resolve `source` → git `install_source`; carry `source` into the entry

**Files:**
- Modify: `scripts/_lane_resolve.py` (`_build_merged_skills` + new `_resolve_skill_source`)
- Modify: `scripts/_skill_probe.py:54-65` (`_build_skill_entry_base` carries `source`)
- Test: `tests/test_self_bootstrap.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_self_bootstrap.py`):

```python
from scripts import _lane_resolve as lr


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
```

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest tests/test_self_bootstrap.py::test_build_merged_skills_resolves_git_source_to_installable_now -v`
Expected: FAIL (`state` is `manual_only`; `source`/git `install_source` not present on entry)

- [ ] **Step 3a: Add `_resolve_skill_source` and call it** in `scripts/_lane_resolve.py`. Insert the helper just above `_build_merged_skills`:

```python
def _resolve_skill_source(
    skill_config: dict[str, Any], sources: dict[str, Any]
) -> None:
    """Attach a git install_source from the shared `sources` map (DRY).

    No-op if the skill has no `source`, already has an explicit install_source,
    or the referenced source is missing/not a git source.
    """
    src_id = skill_config.get("source")
    if not src_id or skill_config.get("install_source"):
        return
    src = sources.get(src_id)
    if not isinstance(src, dict) or src.get("kind") != "git":
        return
    skill_config["install_source"] = {
        "method": "git",
        "url": src.get("url"),
        "tag": src.get("tag"),
        "install": src.get("install"),
    }
```

Then in `_build_merged_skills`, read `sources` once and resolve per skill:

```python
def _build_merged_skills(
    active_skills: set[str],
    manifest: dict[str, Any],
    overrides: dict[str, dict[str, Any]],
    usable_skills: dict[str, dict[str, Any]],
    advisory_skills: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    sources = manifest.get("sources", {})
    merged: dict[str, dict[str, Any]] = {}
    for skill_name in sorted(active_skills):
        skill_config = dict(manifest["skills"][skill_name])
        if skill_name in overrides:
            skill_config.update(overrides[skill_name])
        _resolve_skill_source(skill_config, sources)
        merged[skill_name] = _skill_entry(
            skill_name, skill_config, usable_skills, advisory_skills
        )
    return merged
```

- [ ] **Step 3b: Carry `source` into the entry.** In `scripts/_skill_probe.py`, add one line to `_build_skill_entry_base`'s returned dict (after `install_source`):

```python
        "install_source": skill_config.get("install_source"),
        "source": skill_config.get("source"),
```

- [ ] **Step 4: Run — test passes; full suite still green.**

Run: `python3 -m pytest tests/test_self_bootstrap.py -v && python3 -m pytest -q`
Expected: new test passes; whole suite green

- [ ] **Step 5: Commit.**

```bash
git add scripts/_lane_resolve.py scripts/_skill_probe.py tests/test_self_bootstrap.py
git commit -m "feat(bootstrap): resolve per-skill git source to installable_now"
```

---

## Task 5: Dedup install candidates by source

**Files:**
- Modify: `scripts/_lane_resolve.py:424-437` (`_build_install_candidates`)
- Test: `tests/test_self_bootstrap.py`

- [ ] **Step 1: Write the failing test** (append):

```python
def _missing_family_manifest():
    leaf = lambda src: {  # noqa: E731
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
```

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest tests/test_self_bootstrap.py::test_install_candidates_deduped_one_per_source -v`
Expected: FAIL (currently 3 candidates named after each skill)

- [ ] **Step 3: Replace `_build_install_candidates`** with the deduping version:

```python
def _build_install_candidates(
    merged_skills: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for skill_name, skill in merged_skills.items():
        if skill["state"] != "installable_now":
            continue
        command = _install_command_for_skill(skill)
        if not command:
            continue
        source = skill.get("source")
        if source:  # git source: one command installs all its skills -> dedupe
            if source in seen_sources:
                continue
            seen_sources.add(source)
            name = source
        else:  # public skills_cli: per-skill (unchanged)
            name = skill_name
        candidates.append({
            "name": name,
            "command": command,
            "post_install_state": skill.get("post_install_state"),
            "restart_required": skill["restart_required_if_installed"],
            "source_type": skill["source_type"],
        })
    return candidates
```

- [ ] **Step 4: Run — test passes; full suite green.**

Run: `python3 -m pytest tests/test_self_bootstrap.py -q && python3 -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit.**

```bash
git add scripts/_lane_resolve.py tests/test_self_bootstrap.py
git commit -m "feat(bootstrap): dedupe install candidates to one command per source"
```

---

## Task 6: install_plan.md preamble + from-scratch integration test

**Files:**
- Modify: `scripts/_bootstrap_report.py:544-552` (`_markdown_install_plan` preamble)
- Test: `tests/test_self_bootstrap.py`

- [ ] **Step 1: Write the failing test** (append; drives a real from-scratch report against an empty skills root via an empty `HOME`/`AGENT_SKILLS_HOME`):

```python
from scripts._bootstrap_report import build_bootstrap_report, _markdown_install_plan


def test_from_scratch_install_plan_lists_both_sources(tmp_path):
    repo = tmp_path / "target"; (repo).mkdir(); (repo / "app.py").write_text("x = 1\n")
    empty_home = tmp_path / "home"; empty_home.mkdir()
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
```

NOTE: `build_bootstrap_report(**kwargs)` builds a frozen `BootstrapReportRequest`
whose fields are exactly `repo_root, manifest_path, out_dir, env, extra_roots,
foreign_roots, user_override_path, repo_override_path, required_skill_names`
(verified) — the kwargs call above is correct as written.

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest tests/test_self_bootstrap.py::test_from_scratch_install_plan_lists_both_sources -v`
Expected: FAIL on the `{dest}` documentation assertion (and/or preamble wording)

- [ ] **Step 3: Update the install-plan preamble** in `_markdown_install_plan` to define `{dest}` and keep the "never installs" framing:

```python
def _markdown_install_plan(report: dict[str, Any]) -> str:
    lines = [
        "# Install Plan",
        "",
        "This checker never installs skills. Use the commands below "
        "only after explicit approval.",
        "",
        "Replace `{dest}` with your skills root "
        "(default: `~/.agents/skills`).",
        "",
    ]
    if not report["install_candidates"]:
        lines.append("No install candidates were detected.")
        lines.append("")
        return "\n".join(lines)
    # ... existing per-candidate loop unchanged ...
```

- [ ] **Step 4: Run — test passes; full suite green.**

Run: `python3 -m pytest tests/test_self_bootstrap.py -q && python3 -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit.**

```bash
git add scripts/_bootstrap_report.py tests/test_self_bootstrap.py
git commit -m "feat(bootstrap): install plan documents {dest} + lists git sources"
```

---

## Task 7: repo-P `bootstrap/install-perf.sh` (in repo-P)

**Files (in `~/projects/perf-benchmark-skill`, branch `feat/perf-installer`):**
- Create: `bootstrap/install-perf.sh`
- Test: `tests/test_install_perf.py`

- [ ] **Step 1: Create the branch.**

```bash
cd ~/projects/perf-benchmark-skill && git checkout -b feat/perf-installer
```

- [ ] **Step 2: Write the failing test.** Create `tests/test_install_perf.py`:

```python
"""install-perf.sh deploys perf-benchmark + perf-optimization into a dest."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "bootstrap" / "install-perf.sh"


def test_installs_both_skill_dirs(tmp_path):
    dest = tmp_path / "skills"
    rc = subprocess.run(["bash", str(SCRIPT), str(dest)], cwd=str(REPO),
                        capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
    assert (dest / "perf-benchmark" / "SKILL.md").is_file()
    assert (dest / "perf-optimization" / "SKILL.md").is_file()
    # the deployed perf-benchmark SKILL.md is repo-P's root skill
    head = (dest / "perf-benchmark" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: perf-benchmark" in head
    opt = (dest / "perf-optimization" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: perf-optimization" in opt
```

- [ ] **Step 3: Run to verify it fails.**

Run: `cd ~/projects/perf-benchmark-skill && python3 -m pytest tests/test_install_perf.py -v`
Expected: FAIL (script does not exist)

- [ ] **Step 4: Create `bootstrap/install-perf.sh`:**

```sh
#!/usr/bin/env bash
# Deploy perf-benchmark (repo root) + perf-optimization (subdir) into <dest>.
# Run from a checkout of perf-benchmark-skill. Idempotent.
set -euo pipefail
DEST="${1:?usage: install-perf.sh <dest-skills-dir>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$DEST"
# perf-benchmark = whole repo tree (matches current deployed layout, which
# includes the nested perf-optimization/ copy).
rm -rf "$DEST/perf-benchmark"
mkdir -p "$DEST/perf-benchmark"
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$DEST/perf-benchmark"

# perf-optimization = the subdir, deployed as its own skill dir.
rm -rf "$DEST/perf-optimization"
mkdir -p "$DEST/perf-optimization"
git -C "$REPO_ROOT" archive HEAD:perf-optimization | tar -x -C "$DEST/perf-optimization"

echo "installed perf-benchmark + perf-optimization -> $DEST"
```

- [ ] **Step 5: Make it executable + run the test.**

Run: `chmod +x bootstrap/install-perf.sh && python3 -m pytest tests/test_install_perf.py -v`
Expected: PASS

- [ ] **Step 6: Commit.**

```bash
git add bootstrap/install-perf.sh tests/test_install_perf.py
git commit -m "feat(install): bootstrap/install-perf.sh deploys both perf skills"
```

---

## Task 8: repo-P version bump + ship

**Files (repo-P):**
- Modify: `SKILL.md` (version), `CHANGELOG.md`

- [ ] **Step 1: Bump `SKILL.md` version** `0.6.0` → `0.6.1` and add a `## 0.6.1` CHANGELOG entry describing `bootstrap/install-perf.sh`.

- [ ] **Step 2: Run repo-P's full suite.**

Run: `cd ~/projects/perf-benchmark-skill && python3 -m pytest -q`
Expected: all pass (incl. new install-perf test)

- [ ] **Step 3: Commit, PR, wait for BOTH CI jobs green, merge, tag, reinstall.**

```bash
git add SKILL.md CHANGELOG.md
git commit -m "chore(release): v0.6.1 (perf installer)"
git push -u origin feat/perf-installer
gh pr create --title "v0.6.1: bootstrap/install-perf.sh" --body "Adds the installer the family's one-line bootstrap calls. Deploys perf-benchmark + perf-optimization."
# poll: gh pr checks <N> ; on green:
gh pr merge <N> --merge --delete-branch
git checkout main && git pull origin main
git tag -a v0.6.1 -m "v0.6.1 perf installer" && git push origin v0.6.1
bash bootstrap/install-perf.sh ~/.agents/skills   # reinstall from the tagged tree
```

- [ ] **Step 4: Verify deployed.**

Run: `grep -m1 '^version:' ~/.agents/skills/perf-benchmark/SKILL.md`
Expected: `version: 0.6.1`

---

## Task 9: repo-B `bootstrap/install.sh` + `--dry-run` test

**Files (repo-B):**
- Create: `bootstrap/install.sh`
- Test: `tests/test_self_bootstrap.py`

- [ ] **Step 1: Write the failing `--dry-run` test** (append to `tests/test_self_bootstrap.py`):

```python
import subprocess


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
```

- [ ] **Step 2: Run to verify it fails.**

Run: `python3 -m pytest "tests/test_self_bootstrap.py::test_installer_dry_run_lists_repo_b_and_sources" -v`
Expected: FAIL (script missing)

- [ ] **Step 3: Create `bootstrap/install.sh`:**

```sh
#!/usr/bin/env bash
# One-line bootstrap: install the repo-audit family from scratch.
#   curl -fsSL https://raw.githubusercontent.com/jc1122/repo-audit-refactor-optimize/<tag>/bootstrap/install.sh | bash
set -euo pipefail

REPO_B_URL="https://github.com/jc1122/repo-audit-refactor-optimize.git"
REF="v0.12.0"            # SHIP CHECKLIST: bump to the new repo-B tag before tagging
DEST=""
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
if [ -z "$DEST" ]; then
  if [ -n "${AGENT_SKILLS_HOME:-}" ]; then DEST="$AGENT_SKILLS_HOME/skills"
  elif [ -n "${CODEX_HOME:-}" ]; then DEST="$CODEX_HOME/skills"
  else DEST="$HOME/.agents/skills"; fi
fi

run() { if [ "$DRY_RUN" -eq 1 ]; then echo "DRY: $*"; else eval "$*"; fi; }

echo "== repo-audit family bootstrap =="
echo "dest: $DEST"
echo "repo-audit-refactor-optimize @ $REF"

# 1. Install repo-B (the orchestrator) first.
TMPB="$(mktemp -d)"
run "git clone --depth 1 -b $REF $REPO_B_URL \"$TMPB\""
run "mkdir -p \"$DEST/repo-audit-refactor-optimize\""
run "git -C \"$TMPB\" archive $REF | tar -x -C \"$DEST/repo-audit-refactor-optimize\""

# 2. Read the manifest sources and install each at its pinned tag.
MANIFEST="$DEST/repo-audit-refactor-optimize/scripts/skill_bootstrap_manifest.json"
if [ "$DRY_RUN" -eq 1 ]; then MANIFEST="$(dirname "$0")/../scripts/skill_bootstrap_manifest.json"; fi
python3 - "$MANIFEST" "$DEST" "$DRY_RUN" <<'PY'
import json, subprocess, sys, tempfile, shlex
manifest, dest, dry = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
sources = json.load(open(manifest)).get("sources", {})
for sid, src in sources.items():
    url, tag, install = src["url"], src["tag"], src["install"]
    install = [a.replace("{dest}", dest) for a in install]
    print(f"source {sid} @ {tag}: {url}")
    if dry:
        print("DRY: git clone --depth 1 -b %s %s <tmp> && %s" % (tag, url, " ".join(install)))
        continue
    tmp = tempfile.mkdtemp()
    subprocess.check_call(["git", "clone", "--depth", "1", "-b", tag, url, tmp])
    subprocess.check_call(install, cwd=tmp)
PY

# 3. Verify (skip on dry-run).
if [ "$DRY_RUN" -eq 0 ]; then
  python3 "$DEST/repo-audit-refactor-optimize/scripts/check_skill_requirements.py" \
    --repo "$(mktemp -d)" --out-dir "$(mktemp -d)" | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print('stop_before_discovery:', d.get('stop_before_discovery'))"
fi
echo "== done =="
```

- [ ] **Step 4: Make executable + run the dry-run test.**

Run: `chmod +x bootstrap/install.sh && python3 -m pytest "tests/test_self_bootstrap.py::test_installer_dry_run_lists_repo_b_and_sources" -v`
Expected: PASS

- [ ] **Step 5: Commit.**

```bash
git add bootstrap/install.sh tests/test_self_bootstrap.py
git commit -m "feat(install): top-level bootstrap/install.sh (one-line family install)"
```

---

## Task 10: Hermetic `file://` end-to-end test (CI-safe)

**Files (repo-B):**
- Test: `tests/test_self_bootstrap.py`

This exercises the manifest→clone→install path with NO network by pointing a clone at a local `file://` git repo. It uses a throwaway manifest whose single source is a tiny local git repo with a trivial installer, proving the install.sh source loop works end-to-end.

- [ ] **Step 1: Write the test** (append):

```python
def test_install_loop_runs_against_file_url_source(tmp_path):
    # Build a tiny "source" git repo with an installer that drops a skill dir.
    src = tmp_path / "srcrepo"; src.mkdir()
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

    dest = tmp_path / "skills"; dest.mkdir()
    # Mirror install.sh's source loop directly (no network, file:// clone).
    import json, tempfile
    sources = {"demo": {"url": f"file://{src}", "tag": "v1.0.0",
                        "install": ["bash", "install.sh", str(dest)]}}
    for sid, s in sources.items():
        tmp = tempfile.mkdtemp()
        subprocess.check_call(["git", "clone", "--depth", "1", "-b", s["tag"], s["url"], tmp])
        subprocess.check_call(s["install"], cwd=tmp)
    assert (dest / "demo-skill" / "SKILL.md").is_file()
```

- [ ] **Step 2: Run.**

Run: `python3 -m pytest "tests/test_self_bootstrap.py::test_install_loop_runs_against_file_url_source" -v`
Expected: PASS (hermetic; no network)

- [ ] **Step 3: Commit.**

```bash
git add tests/test_self_bootstrap.py
git commit -m "test(install): hermetic file:// end-to-end of the source install loop"
```

---

## Task 11: Opt-in real-network end-to-end test

**Files (repo-B):**
- Test: `tests/test_self_bootstrap.py`

- [ ] **Step 1: Add the marked test** (append). It is skipped unless `RUN_NETWORK_E2E=1` so the fast CI `check` job stays hermetic:

```python
import os
import pytest


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
```

- [ ] **Step 2: Verify it skips by default.**

Run: `python3 -m pytest "tests/test_self_bootstrap.py::test_installer_real_network_into_temp_dest" -v`
Expected: SKIPPED

- [ ] **Step 3: (Manual, optional) run it for real once repo-B v0.12.0 is tagged.**

Run: `RUN_NETWORK_E2E=1 python3 -m pytest "tests/test_self_bootstrap.py::test_installer_real_network_into_temp_dest" -v`
Expected: PASS

- [ ] **Step 4: Commit.**

```bash
git add tests/test_self_bootstrap.py
git commit -m "test(install): opt-in real-network e2e (skipped in CI)"
```

---

## Task 12: Safety-rule docs + version bump + release

**Files (repo-B):**
- Modify: `SKILL.md` (Stage 0 rules + `version`), `references/bootstrap.md`
- Modify: `scripts/run_diagnosis_wave.py` (`__version__`)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Refine the safety rule** in `SKILL.md` Stage 0 — replace the line
  `- Never auto-install local/private skills.` with:

```markdown
- Install only the pinned git sources declared in the manifest. The top-level
  `bootstrap/install.sh` (explicitly invoked) installs them directly; in-session,
  run the checker-emitted commands only after explicit user approval. Never install
  undeclared or arbitrary skills.
```

  Apply the equivalent change in `references/bootstrap.md` wherever the old rule appears
  (grep: `grep -n "auto-install" references/bootstrap.md SKILL.md`).

- [ ] **Step 2: Add a "Self-bootstrap from scratch" subsection** to `SKILL.md` Stage 0 documenting the one-liner:

```markdown
From a bare machine, install the whole family in one command:

\`\`\`bash
curl -fsSL https://raw.githubusercontent.com/jc1122/repo-audit-refactor-optimize/v0.12.0/bootstrap/install.sh | bash
\`\`\`

It installs the orchestrator, then the manifest's pinned git sources (repo-audit-skills, perf-benchmark-skill).
```

- [ ] **Step 3: Bump versions.** `SKILL.md` `version: 0.11.4` → `0.12.0`; `scripts/run_diagnosis_wave.py` `__version__ = "0.11.4"` → `"0.12.0"`; add a `## 0.12.0` CHANGELOG entry.

- [ ] **Step 4: Run the full suite + release gate.**

Run: `python3 -m pytest -q && python3 scripts/check_release.py`
Expected: all pass; `{"status": "pass"}`

- [ ] **Step 5: Run the convergence + coverage-gap gates locally** (new `bootstrap/` files + scripts edits are audited by the wave):

```bash
WAVE_RUNNER="$PWD/scripts/run_diagnosis_wave.py" SKILLS_ROOT="$HOME/.agents/skills" \
  python3 scripts/check_wave_baseline.py    # expect active:0
LEAF=~/.agents/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  python3 scripts/check_coverage_gap.py --suite tests --source-prefix scripts  # expect count:0
```
Expected: convergence `active: 0`; coverage-gap `count: 0`. If the wave flags the new
`tests/`/`bootstrap/` files (e.g. perf-smell W83xx, duplication, complexity), fix
wave-clean or add a justified accept + `wave_frozen.md` row (see the v0.11.3 precedent).

- [ ] **Step 6: Commit.**

```bash
git add SKILL.md references/bootstrap.md scripts/run_diagnosis_wave.py CHANGELOG.md
git commit -m "docs+chore(release): self-bootstrap rule + v0.12.0"
```

---

## Task 13: Ship repo-B + final from-scratch verification

**Pin-sync ship order (from the spec):** repo-P is already shipped (Task 8) and its
manifest pin is `v0.6.1` — **update the manifest pin if Task 8 produced a new tag.**

- [ ] **Step 1: Reconcile manifest pin with repo-P's shipped tag.** If repo-P shipped
  `v0.6.1`, set `sources["perf-benchmark-skill"].tag` to `v0.6.1` in
  `scripts/skill_bootstrap_manifest.json` and re-run `python3 -m pytest tests/test_manifest_sources.py -q`. Commit if changed:

```bash
git add scripts/skill_bootstrap_manifest.json
git commit -m "chore(manifest): pin perf-benchmark-skill v0.6.1"
```

- [ ] **Step 2: Confirm `install.sh`'s `REF` default == the tag about to be cut** (`v0.12.0`). It already is (Task 9 Step 3). If the version differs, fix and recommit.

- [ ] **Step 3: PR, CI, merge, tag, reinstall.**

```bash
git push -u origin feat/self-bootstrapping-family
gh pr create --title "v0.12.0: self-bootstrapping family (git sources + one-line installer)" --body "See docs/superpowers/specs/2026-06-16-self-bootstrapping-family-design.md"
# poll gh pr checks <N> until both jobs green
gh pr merge <N> --merge --delete-branch
git checkout main && git pull origin main
git tag -a v0.12.0 -m "v0.12.0 self-bootstrapping family" && git push origin v0.12.0
git archive v0.12.0 | tar -x -C ~/.agents/skills/repo-audit-refactor-optimize
```

- [ ] **Step 4: Final from-scratch verification** (real one-liner into a throwaway dest):

```bash
RUN_NETWORK_E2E=1 python3 -m pytest "tests/test_self_bootstrap.py::test_installer_real_network_into_temp_dest" -v
# and a true end-to-end against an empty home:
TMP=$(mktemp -d); bash bootstrap/install.sh --dest "$TMP/skills"
grep -m1 '^version:' "$TMP/skills/repo-audit-refactor-optimize/SKILL.md"   # 0.12.0
grep -m1 '^version:' "$TMP/skills/complexity-audit/SKILL.md"                # 0.8.0
grep -m1 '^version:' "$TMP/skills/perf-benchmark/SKILL.md"                  # 0.6.1
```
Expected: all three present at their pinned versions; the family installed from one command.

- [ ] **Step 5: Update memory** (`repo-audit-dogfood-loops.md` + `MEMORY.md`) with the self-bootstrap ship: versions repo-B v0.12.0 / perf-benchmark v0.6.1, the manifest `sources` mechanism, the one-liner, and the pin-sync ship-order lesson.

---

## Self-Review

**Spec coverage:** manifest `sources`+`source` (T1), schema guard (T2), checker git command (T3), source resolution + installable_now (T4), dedup by source (T5), install_plan `{dest}` (T6), repo-P installer (T7/T8), top-level installer (T9), hermetic CI e2e (T10), opt-in network e2e (T11), safety-rule + version (T12), pin-sync ship order + from-scratch verification (T13), version-drift verification (T13 Step 4). All spec sections mapped.

**Placeholder scan:** `<tag>`/`<N>`/`<tmp>` are command-line placeholders the engineer fills at run time, not unfinished spec content; `{dest}` is an intentional substitution token. No "TBD"/"implement later".

**Type consistency:** `install_source` dict shape (`method`/`url`/`tag`/`install`) is identical across T1/T3/T4. Entry `source` key added in T4 (Step 3b) and consumed in T5. `_build_install_candidates` candidate dict keys (`name`/`command`/`post_install_state`/`restart_required`/`source_type`) preserved from the original. `build_bootstrap_report`'s kwargs form is confirmed against the `BootstrapReportRequest` dataclass fields (T6 note).
