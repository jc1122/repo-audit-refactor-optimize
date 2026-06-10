# SP5: Deterministic Skillset Rewire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **For the SP5 Opus orchestrator:** workers implement tasks VERBATIM via TDD in isolated worktrees; you own all merges, re-run every gate yourself, and read real output. A worker's "green" is not evidence.

**Goal:** Rewire `repo-audit-refactor-optimize` so its diagnosis lanes run exclusively on the first-party repo-audit-skills v0.3.0 family (code-health umbrella + 5 leaves, coverage-gap-audit, test-audit family), drop all third-party/generic diagnosis and execution skills, and fill the gaps they leave with a schema-native remediation playbook and coverage-gated prioritization — then prove it by dogfooding the rewired orchestrator.

**Architecture:** The orchestrator is manifest-driven: `scripts/skill_bootstrap_manifest.json` declares skills + lanes, `scripts/check_skill_requirements.py` evaluates lanes per `lane_type`, and `references/*.md` carry the operating doctrine. The rewire is therefore: (1) one evaluator refactor (preferred/fallback semantics for code-health + a new `coverage` lane type), (2) a manifest rewrite, (3) reference-doc rewrites including a NEW remediation playbook that replaces the dropped generic execution skills, (4) a SKILL.md rewrite, (5) self-check and bounded dogfood gates.

**Tech Stack:** Python 3 stdlib only (matches existing checker), pytest (48 tests green at baseline), JSON manifest, markdown references. No new dependencies.

**Repo:** `/home/jakub/projects/repo-audit-refactor-optimize` (clean main at baseline; `python3 -m pytest tests/ -q` → `48 passed`).

---

## Design Decisions (locked)

1. **Dropped from the manifest (10 skills, none of them ours):** `m15-anti-pattern`, `refactoring`, `python-code-quality`, `python-code-style`, `dignified-code-simplifier`, `cpp-coding-standards`, `rust-best-practices`, `m10-performance`, `performance-testing`, `hypothesis-testing`.
2. **Added (7 first-party skills, repo-audit-skills v0.3.0):** `code-health-audit-pipeline`, `complexity-audit`, `duplication-audit`, `dead-code-audit`, `structure-audit`, `quality-audit`, `coverage-gap-audit`. All `source_type: user-local`, installed via `node bin/install-repo-audit-skills.js` from `github.com/jc1122/repo-audit-skills`.
3. **Kept (process/infra, not diagnosis content):** `find-skills`, `skill-installer`, `perf-benchmark` (first-party), `verification-before-completion`, `dispatching-parallel-agents`, `subagent-driven-development` (superpowers process scaffolding with documented manual fallbacks — dropping them creates a real gap and adds no determinism).
4. **Gap fills:**
   - *Diagnosis* (was m15-anti-pattern + python-code-quality/style): `code-health-audit-pipeline` preferred; the 5 leaves as the degraded fallback.
   - *Execution guidance* (was refactoring + dignified-code-simplifier): NEW `references/remediation-playbook.md` mapping every finding signal (DELETE/EXTRACT/MERGE/SIMPLIFY/DECOMPOSE/RESTRUCTURE/LINT/FORMAT/TYPE/TEST) to a safe TDD procedure.
   - *Refactor-safety* (was nothing): NEW `coverage-python` lane (coverage-gap-audit) + coverage-gated prioritization: files with TEST findings are never auto-remediated; characterize first.
   - *Non-Python code health* (was cpp-coding-standards/rust-best-practices): honest manual mode. The `code-health-c/rust/assembly` lanes are REMOVED; the activation matrix records the tooling gap explicitly instead of pretending generic skills cover it.
5. **Performance lane:** keep `perf-benchmark` as sole preferred; remove generic fallback/optional. Evaluator change: preferred-usable with **no fallback declared** = `full` (today it would report `degraded` with a misleading warning).
6. **Coverage handoff (umbrella v2 integration):** the test lane's coverage.json artifact feeds both `coverage-gap-audit --coverage-json` and `code-health-audit-pipeline --coverage-json` (artifact-gated leaf registered in repo-audit-skills v0.3.0).
7. Version bump `SKILL.md` 0.1.0 → 0.2.0. Commit locally each task. **Do NOT push, tag, or release** — human reviews.

## File Structure

- Modify: `scripts/check_skill_requirements.py` (evaluators only, ~lines 401–466)
- Modify: `scripts/skill_bootstrap_manifest.json` (full skills/lanes rewrite)
- Modify: `tests/test_check_skill_requirements.py` (new TDD tests + production-manifest assertion updates)
- Rewrite: `references/activation-matrix.md`
- Modify: `references/pipeline.md`, `references/prioritization.md`, `references/bootstrap.md`
- Create: `references/remediation-playbook.md`
- Rewrite lanes + version: `SKILL.md`; touch `README.md`
- Create: `docs/dogfood/2026-06-10-sp5-dogfood-report.md` (T7 evidence)

### Worker wave map (keep the DeepSeek pool saturated; cap 4)

The design is locked in this plan, so doc tasks do NOT wait for code tasks. Dispatch one worker per packet, own worktree each:

- **Wave 1 (3 workers in parallel):** W-A = T1 (evaluators + tests) ∥ W-B = T3 (references rewrite) ∥ W-C = T4 (remediation playbook). Disjoint files.
- **Wave 2 (2 workers in parallel):** W-D = T2 (manifest + manifest tests; requires T1 merged) ∥ W-E = T5 (SKILL.md; requires T3+T4 merged). Disjoint files.
- **Gate (orchestrator, no worker):** T6 bootstrap self-checks. Must pass before Wave 3.
- **Wave 3 (3 workers in parallel):** W-F = T7a (code-health determinism dogfood) ∥ W-G = T7b (coverage handoff dogfood) ∥ W-H = T7c (test-audit-pipeline self-dogfood). All read-only diagnosis with disjoint `/tmp` out-dirs; orchestrator synthesizes T7d (gated backlog + report).
- **Sequential tail:** T8 README/review, then **Phase 2 self-dogfood loop** (one worker per remediation batch, serialized merges).

Merge discipline: the orchestrator owns all merges; after each merge re-run `python3 -m pytest tests/ -q` and read the output. Never merge two workers touching the same file without rebasing the second.

---

### Task 1: Evaluator refactor — preferred/fallback for code-health, new coverage lane type, perf no-fallback full

**Files:**
- Modify: `scripts/check_skill_requirements.py:401-466`
- Test: `tests/test_check_skill_requirements.py` (append; uses existing helpers `write_skill`, `write_manifest` defined at lines 19–29)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_check_skill_requirements.py`):

```python
def _lane_manifest(lane_type: str, *, preferred, fallback=None, optional=None, always=False) -> dict:
    skills = {}
    for name in [*preferred, *(fallback or []), *(optional or [])]:
        skills[name] = {
            "priority": "preferred",
            "source_type": "user-local",
            "install_source": None,
            "manual_fallback": f"Manual fallback for {name}.",
            "restart_required_if_installed": True,
        }
    lane: dict = {
        "lane_type": lane_type,
        "preferred": list(preferred),
        "manual_fallback": "Manual lane fallback.",
        "blocking": False,
    }
    if always:
        lane["always"] = True
    else:
        lane["when"] = {"python": True}
    if fallback is not None:
        lane["fallback"] = list(fallback)
    if optional is not None:
        lane["optional"] = list(optional)
    return {"version": 1, "skills": skills, "lanes": {"lane-under-test": lane}}


def _python_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    return repo


def test_code_health_lane_degrades_to_fallback_leaves(tmp_path: Path):
    repo = _python_repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        _lane_manifest("code_health", preferred=["umbrella-skill"], fallback=["leaf-a", "leaf-b"]),
    )
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "leaf-a")
    write_skill(skills_root, "leaf-b")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "degraded"
    assert lane["selected_skills"] == ["leaf-a", "leaf-b"]
    assert lane["warnings"] == [
        "Preferred code-health umbrella unavailable; using leaf audits directly."
    ]


def test_coverage_lane_full_when_leaf_usable(tmp_path: Path):
    repo = _python_repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _lane_manifest("coverage", preferred=["cov-leaf"]))
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "cov-leaf")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["cov-leaf"]
    assert lane["warnings"] == []


def test_coverage_lane_manual_when_leaf_missing(tmp_path: Path):
    repo = _python_repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _lane_manifest("coverage", preferred=["cov-leaf"]))

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "manual"
    assert lane["selected_skills"] == []


def test_performance_lane_full_with_no_fallback_declared(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "benches").mkdir()
    (repo / "benches" / "bench_hot.py").write_text("def bench_hot(): pass\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _lane_manifest("performance", preferred=["bench-skill"], always=True))
    skills_root = tmp_path / ".agents" / "skills"
    write_skill(skills_root, "bench-skill")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["lane-under-test"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["bench-skill"]
    assert lane["warnings"] == []
```

- [ ] **Step 2: Run the new tests, verify they fail**

Run: `python3 -m pytest tests/test_check_skill_requirements.py -q -k "fallback_leaves or coverage_lane or no_fallback_declared"`
Expected: 4 failed (`degraded` vs `manual` for code-health; unknown-lane-type warning for coverage; `degraded` + warning for performance).

- [ ] **Step 3: Implement.** In `scripts/check_skill_requirements.py`, replace the bodies at lines 401–419 and 422–444, and extend `_LANE_EVALUATORS`:

```python
def _evaluate_preferred_fallback_lane(
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    fallback_warning: str,
) -> tuple[str, list[str], list[str]]:
    preferred = lane.get("preferred", [])
    fallback = lane.get("fallback", [])
    warnings: list[str] = []
    if preferred and _all_usable(preferred, skills):
        selected = list(preferred) + _usable_optionals(lane, skills)
        return "full", selected, warnings
    if fallback and _all_usable(fallback, skills):
        warnings.append(fallback_warning)
        selected = list(fallback) + _usable_optionals(lane, skills)
        return "degraded", selected, warnings
    return "manual", [], warnings


def _evaluate_test_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    return _evaluate_preferred_fallback_lane(
        lane, skills, "Preferred test audit skill unavailable; using fallback pair."
    )


def _evaluate_code_health_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    return _evaluate_preferred_fallback_lane(
        lane, skills, "Preferred code-health umbrella unavailable; using leaf audits directly."
    )


def _evaluate_coverage_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    return _evaluate_preferred_fallback_lane(
        lane, skills, "Preferred coverage skill unavailable; using fallback."
    )


def _evaluate_performance_lane(
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    if not profile["has_deterministic_perf_surface"]:
        if profile["has_deterministic_test_surface"]:
            warnings.append("No benchmark surface detected; performance work remains manual.")
            return "manual", [], warnings
        return "blocked", [], warnings

    if _all_usable(lane.get("preferred", []), skills):
        selected = list(lane.get("preferred", []))
        fallback = lane.get("fallback", [])
        if not fallback:
            selected.extend(_usable_optionals(lane, skills))
            return "full", selected, warnings
        if _all_usable(fallback, skills):
            selected.extend(fallback)
            selected.extend(_usable_optionals(lane, skills))
            return "full", selected, warnings
        warnings.append("Optimization skill missing; lane remains benchmark-first.")
        return "degraded", selected, warnings

    return "manual", [], warnings
```

And in `_LANE_EVALUATORS` add the coverage entry:

```python
_LANE_EVALUATORS = {
    "test": lambda lane, skills, profile: _evaluate_test_lane(lane, skills),
    "code_health": lambda lane, skills, profile: _evaluate_code_health_lane(lane, skills),
    "coverage": lambda lane, skills, profile: _evaluate_coverage_lane(lane, skills),
    "performance": _evaluate_performance_lane,
    "bootstrap": lambda lane, skills, profile: _evaluate_bootstrap_lane(lane, skills),
    "orchestration": lambda lane, skills, profile: _evaluate_orchestration_lane(lane, skills),
}
```

- [ ] **Step 4: Run the full suite, verify green**

Run: `python3 -m pytest tests/ -q`
Expected: `52 passed` (48 baseline + 4 new). The existing test-lane degraded test (asserts the exact "fallback pair" warning string, preserved verbatim) must still pass. The production manifest is untouched in T1, so all existing production-manifest tests still pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/check_skill_requirements.py tests/test_check_skill_requirements.py
git commit -m "feat(checker): preferred/fallback code-health, coverage lane type, perf full without fallback (SP5 T1)"
```

---

### Task 2: Manifest rewrite + production-manifest test updates

**Files:**
- Modify: `scripts/skill_bootstrap_manifest.json` (full rewrite of `skills` and `lanes`)
- Modify: `tests/test_check_skill_requirements.py` (update production-manifest assertions; add guard + lane tests)

- [ ] **Step 1: Write the failing production-manifest tests** (append):

```python
EXPECTED_MANIFEST_SKILLS = {
    "find-skills",
    "skill-installer",
    "test-audit-pipeline",
    "test-quality-assurance",
    "test-redundancy-triage",
    "code-health-audit-pipeline",
    "complexity-audit",
    "duplication-audit",
    "dead-code-audit",
    "structure-audit",
    "quality-audit",
    "coverage-gap-audit",
    "perf-benchmark",
    "verification-before-completion",
    "dispatching-parallel-agents",
    "subagent-driven-development",
}


def test_production_manifest_contains_only_first_party_and_process_skills():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert set(manifest["skills"]) == EXPECTED_MANIFEST_SKILLS
    assert set(manifest["lanes"]) == {
        "bootstrap",
        "test-python",
        "code-health-python",
        "coverage-python",
        "performance",
        "orchestration",
    }


def test_python_repo_resolves_all_deterministic_lanes_full(tmp_path: Path, python_pytest_repo: Path):
    skills_root = tmp_path / ".agents" / "skills"
    for name in [
        "test-audit-pipeline",
        "code-health-audit-pipeline",
        "coverage-gap-audit",
    ]:
        write_skill(skills_root, name)

    report = checker.build_bootstrap_report(
        repo_root=python_pytest_repo,
        manifest_path=MANIFEST_PATH,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert report["lanes"]["test-python"]["state"] == "full"
    assert report["lanes"]["test-python"]["selected_skills"] == ["test-audit-pipeline"]
    assert report["lanes"]["code-health-python"]["state"] == "full"
    assert report["lanes"]["code-health-python"]["selected_skills"] == ["code-health-audit-pipeline"]
    assert report["lanes"]["coverage-python"]["state"] == "full"
    assert report["lanes"]["coverage-python"]["selected_skills"] == ["coverage-gap-audit"]


def test_code_health_python_degrades_to_leaves_on_production_manifest(
    tmp_path: Path, python_pytest_repo: Path
):
    skills_root = tmp_path / ".agents" / "skills"
    for name in [
        "complexity-audit",
        "duplication-audit",
        "dead-code-audit",
        "structure-audit",
        "quality-audit",
    ]:
        write_skill(skills_root, name)

    report = checker.build_bootstrap_report(
        repo_root=python_pytest_repo,
        manifest_path=MANIFEST_PATH,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    lane = report["lanes"]["code-health-python"]
    assert lane["state"] == "degraded"
    assert lane["selected_skills"] == [
        "complexity-audit",
        "duplication-audit",
        "dead-code-audit",
        "structure-audit",
        "quality-audit",
    ]


def test_non_python_repo_activates_no_code_health_lane(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "asm").mkdir(parents=True)
    (repo / "asm" / "start.S").write_text(".globl _start\n", encoding="utf-8")

    report = checker.build_bootstrap_report(
        repo_root=repo,
        manifest_path=MANIFEST_PATH,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    active = set(report["summary"]["active_lanes"])
    assert "code-health-python" not in active
    assert "coverage-python" not in active
    assert not any(name.startswith("code-health-") and name != "code-health-python" for name in report["lanes"])
```

- [ ] **Step 2: Run them, verify they fail**

Run: `python3 -m pytest tests/test_check_skill_requirements.py -q -k "production_manifest or deterministic_lanes or degrades_to_leaves_on_production or no_code_health_lane"`
Expected: 4 failed (old manifest still has 19 skills / 8 lanes).

- [ ] **Step 3: Rewrite the manifest.** In `scripts/skill_bootstrap_manifest.json`:
  - **Keep byte-identical** the existing `skills` entries for: `find-skills`, `skill-installer`, `test-audit-pipeline`, `test-quality-assurance`, `test-redundancy-triage`, `perf-benchmark`, `verification-before-completion`, `dispatching-parallel-agents`, `subagent-driven-development`.
  - **Delete** the entries for: `hypothesis-testing`, `m15-anti-pattern`, `refactoring`, `python-code-quality`, `python-code-style`, `dignified-code-simplifier`, `cpp-coding-standards`, `rust-best-practices`, `m10-performance`, `performance-testing`.
  - **Add** these 7 entries verbatim:

```json
"code-health-audit-pipeline": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Install repo-audit-skills v0.3.0+ (github.com/jc1122/repo-audit-skills, `node bin/install-repo-audit-skills.js --dest <skills-root> --force`), or run the five leaf audits directly.",
  "restart_required_if_installed": true
},
"complexity-audit": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Part of repo-audit-skills v0.3.0+; install via its node installer.",
  "restart_required_if_installed": true
},
"duplication-audit": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Part of repo-audit-skills v0.3.0+; install via its node installer.",
  "restart_required_if_installed": true
},
"dead-code-audit": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Part of repo-audit-skills v0.3.0+; install via its node installer.",
  "restart_required_if_installed": true
},
"structure-audit": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Part of repo-audit-skills v0.3.0+; install via its node installer.",
  "restart_required_if_installed": true
},
"quality-audit": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Part of repo-audit-skills v0.3.0+; install via its node installer.",
  "restart_required_if_installed": true
},
"coverage-gap-audit": {
  "priority": "preferred",
  "source_type": "user-local",
  "install_source": null,
  "manual_fallback": "Collect a coverage.py JSON report and assess testedness manually when the leaf is unavailable.",
  "restart_required_if_installed": true
}
```

  - **Replace the entire `lanes` object** with (bootstrap and orchestration stay byte-identical to current; shown for completeness):

```json
"lanes": {
  "bootstrap": {
    "always": true,
    "lane_type": "bootstrap",
    "preferred": ["find-skills", "skill-installer"],
    "fallback": [],
    "manual_fallback": "Use raw Skills CLI commands when helper skills are missing.",
    "blocking": false
  },
  "test-python": {
    "when": {"python": true, "pytest": true},
    "lane_type": "test",
    "preferred": ["test-audit-pipeline"],
    "fallback": ["test-quality-assurance", "test-redundancy-triage"],
    "manual_fallback": "Run a deterministic manual Python test audit when the skill lane is unavailable.",
    "blocking": false
  },
  "code-health-python": {
    "when": {"python": true},
    "lane_type": "code_health",
    "preferred": ["code-health-audit-pipeline"],
    "fallback": ["complexity-audit", "duplication-audit", "dead-code-audit", "structure-audit", "quality-audit"],
    "manual_fallback": "Review Python code health manually and record the tooling gap when the deterministic family is unavailable.",
    "blocking": false
  },
  "coverage-python": {
    "when": {"python": true, "pytest": true},
    "lane_type": "coverage",
    "preferred": ["coverage-gap-audit"],
    "fallback": [],
    "manual_fallback": "Collect coverage.py JSON and assess testedness manually when the leaf is unavailable.",
    "blocking": false
  },
  "performance": {
    "always": true,
    "lane_type": "performance",
    "preferred": ["perf-benchmark"],
    "fallback": [],
    "manual_fallback": "Use manual performance reasoning and stable verification when the preferred skill set is unavailable.",
    "blocking": true
  },
  "orchestration": {
    "always": true,
    "lane_type": "orchestration",
    "preferred": ["verification-before-completion"],
    "optional": ["dispatching-parallel-agents", "subagent-driven-development"],
    "manual_fallback": "Run verification manually and execute batches sequentially when orchestration helpers are missing.",
    "blocking": false
  }
}
```

- [ ] **Step 4: Update stale production-manifest tests.** Run `grep -n "m15-anti-pattern\|refactoring\|python-code-quality\|python-code-style\|cpp-coding-standards\|rust-best-practices\|m10-performance\|performance-testing\|hypothesis-testing\|dignified-code-simplifier\|code-health-c\|code-health-rust\|code-health-assembly" tests/test_check_skill_requirements.py`. For each hit decide:
  - Tests that use **synthetic manifests** (built with `write_manifest` from scratch, not `sample_manifest`/`MANIFEST_PATH`) are functionally fine with any skill name, but rename any literal dropped-skill name (e.g., `m15-anti-pattern` → `helper-a`) so the repo greps clean — DoD item 1 asserts zero references repo-wide.
  - Tests that exercise the **production manifest** (via `sample_manifest` or `MANIFEST_PATH`) and assert removed lanes/skills must be rewritten: delete `test_assembly_repo_activates_code_health_lane` (~line 194) and the code-health-c (~line 841) / code-health-rust (~line 868) full-state tests — `test_non_python_repo_activates_no_code_health_lane` from Step 1 replaces them. Rewrite any performance-lane test that fabricates `m10-performance`/`performance-testing` roots to expect `full` with `["perf-benchmark"]` only.

- [ ] **Step 5: Run the full suite, verify green**

Run: `python3 -m pytest tests/ -q`
Expected: `53 passed` (52 after T1, + 4 new from Step 1, − the 3 deleted lane tests; perf-lane tests are rewritten in place, net 0). If Step 4's grep surfaces additional stale production-manifest tests, the count may differ — record the exact count and the delta arithmetic in the commit message. Zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/skill_bootstrap_manifest.json tests/test_check_skill_requirements.py
git commit -m "feat(manifest): first-party deterministic lanes; drop generic diagnosis skills (SP5 T2)"
```

---

### Task 3: Reference docs rewrite (activation matrix, pipeline, prioritization, bootstrap)

**Files:**
- Rewrite: `references/activation-matrix.md`
- Modify: `references/pipeline.md`, `references/prioritization.md`, `references/bootstrap.md`

- [ ] **Step 1: Replace `references/activation-matrix.md` entirely with:**

```markdown
# Activation Matrix

## Core Rule

Activated diagnosis lanes are independent read-only analyses and should be dispatched in parallel when bootstrap and discovery are complete. All diagnosis lanes run first-party deterministic skills from the repo-audit-skills family; every lane resolves to `full`, `degraded`, `manual`, or `blocked`.

## Test Lane (`test-python`)

- Preferred: `test-audit-pipeline`
- Fallback: `test-quality-assurance` + `test-redundancy-triage`
- Manual fallback: deterministic manual test audit
- Blocking: no

`full` when `test-audit-pipeline` is usable now; `degraded` on the TQA + redundancy pair; `manual` otherwise. The test lane also produces the `coverage.json` artifact consumed by the coverage and code-health lanes (see pipeline.md).

### Non-Python Test Surfaces

No first-party audit stack exists. Perform a deterministic manual test-loop review and record the tooling gap explicitly. Never present Python-lane results as covering non-Python code.

## Code Health Lane (`code-health-python`)

- Preferred: `code-health-audit-pipeline` (runs complexity, duplication, dead-code, structure, and quality leaves, merges and ranks findings, exit 0/1/2)
- Fallback: the five leaf skills invoked directly (`complexity-audit`, `duplication-audit`, `dead-code-audit`, `structure-audit`, `quality-audit`)
- Manual fallback: manual review with the tooling gap recorded
- Blocking: no

`full` when the umbrella is usable; `degraded` when only the leaves are usable (run all five, merge by the shared finding schema); `manual` otherwise. When a `coverage.json` artifact exists, pass it through (`--coverage-json`) so the umbrella's artifact-gated coverage leaf runs too.

### Non-Python Code Health

There is no first-party C, Rust, or assembly code-health lane. This is a recorded tooling gap: review manually, keep changes perf-first and evidence-driven, and say so in the report. Do not substitute generic advice for deterministic findings.

## Coverage Lane (`coverage-python`)

- Preferred: `coverage-gap-audit` (consumes coverage.py JSON, emits TEST findings: untested / under-tested production files)
- Manual fallback: read the coverage report manually
- Blocking: no

This lane is the refactor-safety signal: its TEST findings gate remediation (see prioritization.md). It never runs tests itself; it consumes the test lane's coverage artifact.

## Performance Lane (`performance`)

- Preferred: `perf-benchmark`
- Manual fallback: manual performance reasoning over stable verification
- Blocking: yes (blocked only when the repo has neither a benchmark nor a deterministic test surface)

`full` when `perf-benchmark` is usable and a deterministic benchmark surface exists; `manual` with a warning when only a test surface exists.

## Orchestration Lane (`orchestration`)

- Preferred: `verification-before-completion`
- Optional: `dispatching-parallel-agents`, `subagent-driven-development`
- Manual fallback: sequential batches with manual verification
- Blocking: no

These are process scaffolding, not diagnosis content; their absence degrades convenience, not evidence quality.
```

- [ ] **Step 2: Edit `references/pipeline.md`** — add this section after the existing artifact-layout section (and update any stage list that names the old lanes to the new five: test-python, code-health-python, coverage-python, performance, orchestration):

```markdown
## Coverage Artifact Handoff

The test lane produces a single `coverage.json` (coverage.py JSON format) under its artifact directory. Two consumers depend on it:

1. `coverage-gap-audit --coverage-json <path> --root <repo>` — the coverage lane's TEST findings.
2. `code-health-audit-pipeline ... --coverage-json <path>` — enables the umbrella's artifact-gated coverage leaf (repo-audit-skills v0.3.0+).

Sequencing rule: the coverage and code-health lanes may start before the test lane completes, but their coverage-dependent outputs must be produced (or re-produced) after `coverage.json` exists. If no coverage artifact can be produced, run the code-health lane without `--coverage-json` and mark the coverage lane `manual` in the run summary — never fabricate testedness.
```

- [ ] **Step 3: Edit `references/prioritization.md`** — add this section after "Ranking Dimensions":

```markdown
## Coverage-Gated Actionability

Cross-join every finding with the coverage lane's TEST findings before ranking:

- A finding in a file **with** a TEST finding (untested / under-tested) is **not auto-executable**. Demote it to characterize-first: write behavior/golden tests for the file's current contract, then remediate under that protection. This rule has priority over impact scores.
- A finding in a covered file keeps its computed rank.
- TEST findings themselves rank as test-debt work items (add tests), never as refactor licenses.

This generalizes the Actionability Rule proven in the repo-audit-skills dogfooding runs: advisory findings in untested code are frozen until tests exist.
```

Also update the "Safe Cleanup" / "Structural Refactor" examples to name finding signals: safe cleanup = `LINT`, `FORMAT`, `DELETE` (high-confidence), same-file `MERGE`; structural = `EXTRACT`, `DECOMPOSE`, `RESTRUCTURE`, `SIMPLIFY`, cross-file `MERGE`; and reference `references/remediation-playbook.md` for per-signal procedure.

- [ ] **Step 4: Edit `references/bootstrap.md`** — `grep -n "m15\|refactoring\|python-code-quality\|python-code-style\|cpp-coding\|rust-best\|m10\|performance-testing\|hypothesis\|dignified" references/bootstrap.md` and replace any example using a removed skill with `code-health-audit-pipeline` (user-local example) keeping the surrounding prose intact. Add one line to the user-local source notes: "The repo-audit-skills family installs via `node bin/install-repo-audit-skills.js --dest <skills-root> --force` from github.com/jc1122/repo-audit-skills (v0.3.0+); a session restart is required after install."

- [ ] **Step 5: Verify and commit**

Run: `grep -rn "m15-anti-pattern\|rust-best-practices\|cpp-coding-standards\|m10-performance" references/ && echo STALE || echo CLEAN`
Expected: `CLEAN`

```bash
git add references/activation-matrix.md references/pipeline.md references/prioritization.md references/bootstrap.md
git commit -m "docs(references): first-party deterministic lanes + coverage gating (SP5 T3)"
```

---

### Task 4: New remediation playbook (replaces the dropped execution skills)

**Files:**
- Create: `references/remediation-playbook.md`

- [ ] **Step 1: Create the file with exactly this content:**

```markdown
# Remediation Playbook

Maps every finding signal from the shared code-health finding schema (repo-audit-skills) to a safe execution procedure. This replaces generic refactoring/code-style guidance: the *diagnosis* is deterministic, the *execution* below is the discipline for acting on it.

## Standing Rules

1. **Coverage gate first.** Before touching a file, check the coverage lane's TEST findings. Uncovered file → characterize-first: write behavior/golden tests for the current contract, get them green, then remediate. No exceptions for "obvious" changes.
2. **One signal class per batch.** Never mix mechanical lint fixes with structural moves in one commit; verification cannot attribute regressions.
3. **Ratchet.** Re-run the producing leaf after each batch. Findings may only shrink; growth means stop and investigate before the next batch.
4. **Tests green before and after** every batch, on the smallest sufficient surface first, full relevant suite before closing the batch.
5. **Goldens are contracts.** If a remediation changes observable output and a golden test catches it, investigate and explain; never silently regenerate a golden to make a fix pass.

## Signal Procedures

| Signal | Emitted by | Meaning | Procedure |
|---|---|---|---|
| `LINT` | quality-audit | Lint violation | Fix mechanically in bulk per file. Prefer `ruff check --fix` for auto-fixable codes; review non-auto-fixable ones individually (late-binding/`B023`-class findings are real bug risks — fix deliberately, watch goldens). |
| `FORMAT` | quality-audit | Formatting drift | Apply the formatter (`ruff format`) to the flagged files only. Zero logic review needed; keep the batch purely mechanical. |
| `TYPE` | quality-audit | Type-check error | Fix the annotation or the code, never silence with blanket ignores. A per-line ignore requires an inline reason. |
| `DELETE` | dead-code-audit | Unused code | Confirm reachability (grep for dynamic uses: getattr, registries, entry points, tests). Then delete outright — no commenting out. One module per batch. |
| `MERGE` (same file) | duplication-audit | In-file clone | Extract a local helper only if it nets fewer findings (params, length). If extraction trades one finding for another, keep the clone and justify. |
| `EXTRACT` (cross file) | duplication-audit | Cross-file clone | Only extract into a shared module when the files may legitimately import a common dependency. Vendored/standalone tools must stay self-contained — record a justified freeze instead. |
| `SIMPLIFY` | complexity-audit | High cyclomatic complexity / long function | Reduce branching via early returns, dict dispatch, or guard clauses. If the function is a cohesive linear pipeline (parse → transform → emit), splitting may relocate, not reduce — justify keeping it. |
| `DECOMPOSE` | complexity-audit | Oversized function/module, too many params | Group parameters into a dataclass or split by responsibility. Check the result against the producing leaf before committing: helpers with 5+ params or new clones are regressions. |
| `RESTRUCTURE` | structure-audit | Import cycle / god module | Break cycles by extracting the shared dependency downward (never by inline imports as a permanent fix). For god modules, split by fan-in clusters. Highest-risk class: always characterize-first even in covered files if the public surface is unclear. |
| `TEST` | coverage-gap-audit | Untested / under-tested file | Not a refactor license. Add behavior tests for the file's JSON/stdout/exit-code contract (in-process where coverage tracing requires it) until the file clears the threshold, or record a concrete justification. |

## Batch Protocol

1. Pick the top-ranked batch from the prioritized backlog (one signal class, one or few files).
2. Coverage gate (rule 1). 3. Apply the signal procedure. 4. Run the file/module tests, then the full relevant suite.
5. Re-run the producing leaf; confirm the finding count for the batch scope shrank and nothing new appeared elsewhere.
6. Commit with the signal class and finding count delta in the message. 7. Rebaseline before the next batch.

## Stop Conditions

Stop the execution phase and report instead of continuing when: a batch grows total findings; a golden changes without an explained behavior change; two consecutive batches make no net progress; or remediation requires changing a public contract (needs explicit human approval).
```

- [ ] **Step 2: Commit**

```bash
git add references/remediation-playbook.md
git commit -m "docs(playbook): schema-native remediation procedures replacing generic skills (SP5 T4)"
```

---

### Task 5: SKILL.md rewrite + version bump

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1:** Set frontmatter `version: 0.2.0`. Update the `description:` to: `End-to-end repository diagnosis, remediation, and optimization orchestration built on the deterministic repo-audit-skills family. Use when the agent needs to audit a repository with deterministic code-health, coverage-gap, and test-audit lanes, synthesize a coverage-gated remediation backlog, execute safe refactor batches, benchmark and optimize performance, or run a full repo optimization pipeline from diagnosis through verified completion.`

- [ ] **Step 2:** Replace the three lane sections (`### Test Lane`, `### Code Health Lane`, `### Performance Lane`, lines 84–115) with:

```markdown
### Test Lane

Use:

- `test-audit-pipeline` as the preferred Python audit lane (also produces the `coverage.json` artifact)
- `test-quality-assurance` plus `test-redundancy-triage` as the degraded fallback
- `verification-before-completion` only as the final gate, not as a replacement for diagnosis

For non-Python test ecosystems, perform deterministic test-loop assessment and structural review, and keep the tooling gap explicit.

### Code Health Lane

Use:

- `code-health-audit-pipeline` as the preferred deterministic diagnosis (complexity, duplication, dead-code, structure, quality leaves; merged, ranked findings; exit 0/1/2)
- the five leaf skills directly (`complexity-audit`, `duplication-audit`, `dead-code-audit`, `structure-audit`, `quality-audit`) as the degraded fallback
- pass the test lane's `coverage.json` via `--coverage-json` so the artifact-gated coverage leaf runs

Findings are advisory and deterministic; execution discipline lives in `references/remediation-playbook.md`. Do not start with restructuring. Start with findings, gate on coverage, then remediate in single-signal batches.

For C, Rust, and assembly code health no first-party lane exists: review manually, record the tooling gap, and keep changes perf-first and evidence-driven.

### Coverage Lane

Use:

- `coverage-gap-audit` on the test lane's `coverage.json` to emit TEST findings (untested / under-tested production files)

TEST findings gate the backlog (see `references/prioritization.md`): findings in uncovered files are characterize-first, never auto-executed.

### Performance Lane

Use:

- `perf-benchmark` to establish baselines, hotspot rankings, and benchmark discipline; optimize only after a bottleneck is proven

Treat assembly as a perf-first, evidence-driven lane: profiling evidence and conservative change control over broad structural edits.
```

- [ ] **Step 3:** Add `references/remediation-playbook.md` to both reference lists (the "Keep the top-level flow here..." list near the top and `## Required References` at the bottom), with the loading hint: load it before the Execution stage. In the `## Execution` section, change the first line to: `Execute changes in batches following references/remediation-playbook.md.`

- [ ] **Step 4: Verify no stale skill names remain**

Run: `grep -n "m15-anti-pattern\|refactoring\b\|python-code-quality\|python-code-style\|cpp-coding-standards\|rust-best-practices\|m10-performance\|performance-testing\|hypothesis-testing\|dignified-code-simplifier" SKILL.md && echo STALE || echo CLEAN`
Expected: `CLEAN` (note: the prose word "refactoring" in ordinary sentences is fine; the grep guards the skill-name contexts — review hits manually).

- [ ] **Step 5: Run suite and commit**

Run: `python3 -m pytest tests/ -q` → all pass.

```bash
git add SKILL.md
git commit -m "feat(skill): v0.2.0 — deterministic first-party lanes + remediation playbook (SP5 T5)"
```

---

### Task 6: Bootstrap self-check gates (orchestrator-verified, no worker)

- [ ] **Step 1:** No install needed: run the working-tree checker (it defaults to the working-tree manifest at `scripts/skill_bootstrap_manifest.json`); the repo-audit-skills v0.3.0 family is already installed at the user skills root, which the checker discovers via its standard root search order. From `/home/jakub/projects/repo-audit-refactor-optimize`:

```bash
python3 scripts/check_skill_requirements.py \
  --repo /home/jakub/projects/repo-audit-skills \
  --out-dir /tmp/sp5-selfcheck/repo-audit-skills
```

If a lane unexpectedly reports `manual`, verify discovery with `--extra-root /home/jakub/.claude/skills` before debugging anything else.

Expected in `bootstrap/bootstrap_report.json` — HARD assertions (any divergence → STOP):
- `test-python` full `["test-audit-pipeline"]`
- `code-health-python` full `["code-health-audit-pipeline"]`
- `coverage-python` full `["coverage-gap-audit"]`
- `performance` manual with the no-benchmark-surface warning
- `summary.stop_before_discovery` false

RECORD-ONLY (non-blocking lanes whose state depends on the local environment — do not STOP on these): `bootstrap` is expected `degraded` (find-skills/skill-installer not installed) and `orchestration` is expected `manual` (verified 2026-06-10: `verification-before-completion` is not mirrored into `~/.claude/skills`; only some superpowers skills are). Record both states in the T7 report.

- [ ] **Step 2:** Run the same against this repo itself (`--repo /home/jakub/projects/repo-audit-refactor-optimize`); expect the same lane states. Save both reports; they are T8 evidence.

---

### Task 7: Bounded dogfood — drive the rewired lanes end-to-end (diagnosis only)

**Files:**
- Create: `docs/dogfood/2026-06-10-sp5-dogfood-report.md`

T7a/T7b/T7c are independent read-only packets (Wave 3, one worker each, disjoint out-dirs). `SKILLS=/home/jakub/.claude/skills` throughout. T7d is the orchestrator's synthesis.

- [ ] **T7a (code-health determinism):** run the umbrella twice over the canonical production scope (mirrors `scripts/self_audit.py::_prefixes()` in repo-audit-skills: `shared`, `scripts`, and each `skills/<name>/scripts` — NOT wholesale `skills/`, which would sweep test fixtures into the audit) and diff:

```bash
TARGET=/home/jakub/projects/repo-audit-skills
PREFIXES="--source-prefix shared --source-prefix scripts"
for d in "$TARGET"/skills/*/scripts; do
  PREFIXES="$PREFIXES --source-prefix skills/$(basename "$(dirname "$d")")/scripts"
done
python3 $SKILLS/code-health-audit-pipeline/scripts/code_health_pipeline.py \
  --root "$TARGET" $PREFIXES \
  --out-dir /tmp/sp5-dogfood/code-health-run1
python3 $SKILLS/code-health-audit-pipeline/scripts/code_health_pipeline.py \
  --root "$TARGET" $PREFIXES \
  --out-dir /tmp/sp5-dogfood/code-health-run2
python3 - <<'EOF'
import json
a = json.load(open("/tmp/sp5-dogfood/code-health-run1/code_health_summary.json"))
b = json.load(open("/tmp/sp5-dogfood/code-health-run2/code_health_summary.json"))
a.pop("meta", None); b.pop("meta", None)
assert a == b, "NON-DETERMINISTIC umbrella output"
print("deterministic: OK,", len(a.get("findings", [])), "findings")
EOF
```

Expected: `deterministic: OK` with a finding count > 0. Any assertion failure → STOP.

- [ ] **T7b (coverage handoff into both consumers):**

```bash
cd /home/jakub/projects/repo-audit-skills
.venv/bin/python -m pytest tests/ -q --cov=scripts --cov-report=json:/tmp/sp5-dogfood/coverage.json
python3 $SKILLS/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root /home/jakub/projects/repo-audit-skills \
  --coverage-json /tmp/sp5-dogfood/coverage.json \
  --source-prefix scripts/ \
  --out-dir /tmp/sp5-dogfood/coverage-gap --format json
python3 $SKILLS/code-health-audit-pipeline/scripts/code_health_pipeline.py \
  --root /home/jakub/projects/repo-audit-skills \
  --source-prefix scripts/ \
  --coverage-json /tmp/sp5-dogfood/coverage.json \
  --out-dir /tmp/sp5-dogfood/code-health-cov
```

Expected: the coverage-gap leaf emits TEST findings JSON under `/tmp/sp5-dogfood/coverage-gap/` (advisory exit 0/1, never a crash), and the umbrella run executed the `coverage-gap` leaf (not skipped). Verify mechanically:

```bash
python3 - <<'EOF'
import json
s = json.load(open("/tmp/sp5-dogfood/code-health-cov/code_health_summary.json"))
text = json.dumps(s)
assert "coverage-gap" in text, "coverage-gap leaf absent from umbrella summary"
print("coverage-gap leaf present in umbrella summary: OK")
EOF
```

Capture the summary's per-leaf record for `coverage-gap` (exit code / findings count) as the activation evidence in the report.

- [ ] **T7c (test lane, small target):** run the pipeline against this repo (bounded: one suite, 53 tests):

```bash
python3 $SKILLS/test-audit-pipeline/scripts/audit_pipeline.py \
  --root /home/jakub/projects/repo-audit-refactor-optimize \
  --python python3 \
  --suite tests/test_check_skill_requirements.py \
  --source-prefix scripts/ \
  --out-dir /tmp/sp5-dogfood/test-audit
```

Expected: pipeline completes; `/tmp/sp5-dogfood/test-audit/pipeline_summary.json` carries a supervisor decision; exit code 0/1/2 (2 = error → STOP).

- [ ] **T7d (orchestrator synthesis):** Apply `references/prioritization.md` to the merged findings from T7a–T7c: produce a ranked backlog table (top 10) in which every finding in a file with a TEST finding is marked `characterize-first`. This proves the coverage gate is mechanically applicable.

- [ ] **Step 5:** Write `docs/dogfood/2026-06-10-sp5-dogfood-report.md` recording: lane states from T6, finding counts per lane, the determinism check output, the coverage-leaf activation evidence, the top-10 gated backlog, and exact commands used. Commit:

```bash
git add docs/dogfood/2026-06-10-sp5-dogfood-report.md
git commit -m "docs(dogfood): SP5 rewired-lane diagnosis evidence (SP5 T7)"
```

---

### Task 8: README touch-up + final review

- [ ] **Step 1:** Update `README.md` wherever it names lanes or skills to match the new lane set; add one sentence: the diagnosis lanes require repo-audit-skills v0.3.0+ installed.
- [ ] **Step 2:** Full suite: `python3 -m pytest tests/ -q` → all pass. Re-run the T6 self-checks once more from the final tree.
- [ ] **Step 3:** `git log --oneline main..HEAD` shows T1–T8 commits; working tree clean. **Do NOT push, tag, or release.**

```bash
git add README.md
git commit -m "docs: README lane updates for v0.2.0 (SP5 T8)"
```

---

### Phase 2: Self-build / self-audit loop — the rewired skill remediates its own repo

This is the point of SP5: the orchestrator skill audits ITSELF with the deterministic family and fixes itself following its own playbook. The orchestrator (Opus) drives the loop; one DeepSeek worker per remediation batch, own worktree; merges serialized.

- [ ] **Round protocol (max 4 rounds; findings may only SHRINK):**

  1. **Audit self** (orchestrator, read-only — both commands from `/home/jakub/projects/repo-audit-refactor-optimize`; `SKILLS=/home/jakub/.claude/skills`; pytest-cov verified importable by system `python3` on 2026-06-10):

```bash
python3 -m pytest tests/ -q --cov=scripts --cov-report=json:/tmp/sp5-phase2/coverage.json
python3 $SKILLS/code-health-audit-pipeline/scripts/code_health_pipeline.py \
  --root /home/jakub/projects/repo-audit-refactor-optimize \
  --source-prefix scripts/ \
  --coverage-json /tmp/sp5-phase2/coverage.json \
  --out-dir /tmp/sp5-phase2/round-N
```

  2. **Gate the backlog** per `references/prioritization.md`: findings in files carrying a TEST finding → `characterize-first` (the worker's batch becomes "write behavior tests for that file's contract", not the refactor). Everything else ranks normally.
  3. **Dispatch batches** per `references/remediation-playbook.md`: one signal class per worker per batch (LINT/FORMAT bulk first, then DELETE with reachability checks, then SIMPLIFY/DECOMPOSE only where the producing leaf confirms a net reduction). ACCEPT a worker only if, in its worktree, `python3 -m pytest tests/ -q` is green AND re-running the round's audit command over the touched scope shows the batch's findings shrank with nothing new elsewhere. Else discard/retry.
  4. **Merge, re-audit, record**: after merging the round's batches, re-run step 1; append a row to the round table in `docs/dogfood/2026-06-10-sp5-dogfood-report.md` (round, findings before → after, batches accepted/discarded, freezes + one-line justifications). Commit the round.
  5. **Stop conditions** (playbook): total findings grow → STOP and investigate; a remediation would change the checker's CLI or report contract → record as out-of-scope (needs human approval), do not do it; two consecutive no-progress rounds or every remaining finding individually justified → CONVERGED.

- [ ] **Phase 2 exit:** converged or 4-round bound; every remaining finding either fixed or justified in the report; final `python3 -m pytest tests/ -q` green; per-round table committed. The orchestrator skill has now demonstrably audited and improved itself with the skillset it orchestrates.

---

## Definition of Done (report with evidence)

1. `python3 -m pytest tests/ -q` green (expected `53 passed`; exact delta arithmetic recorded if T2 Step 4 surfaced extra stale tests); `grep -rn "m15-anti-pattern\|cpp-coding-standards\|rust-best-practices\|m10-performance\|performance-testing\|hypothesis-testing\|dignified-code-simplifier\|python-code-quality\|python-code-style" scripts/ references/ tests/ SKILL.md README.md` returns nothing.
2. The manifest guard test pins exactly 16 skills and 6 lanes; the 7 repo-audit-skills entries and the new `code-health-python` fallback + `coverage-python` lane resolve as specced (full/degraded/manual transitions tested).
3. `references/remediation-playbook.md` exists with all 10 signal procedures; prioritization is coverage-gated; activation matrix records the non-Python tooling gap honestly.
4. T6 bootstrap reports for both target repos show the deterministic lanes `full` with first-party skills only.
5. T7 dogfood evidence committed: deterministic double-run check, coverage handoff into both consumers (umbrella coverage leaf ACTIVE), test-audit-pipeline supervisor decision, coverage-gated top-10 backlog.
6. **Phase 2 self-build/self-audit loop ran on this repo**: per-round findings table committed (shrink-only), every batch accepted under green tests + leaf re-run evidence, converged or 4-round bound, residual findings individually justified.
7. `SKILL.md` v0.2.0; commits local only — **nothing pushed, tagged, or released**.

---

## Launch (paste as the goal of a fresh Opus session in /home/jakub/projects/repo-audit-refactor-optimize)

```
You are the ORCHESTRATOR (Opus) for the SP5 deterministic-skillset-rewire run of
repo-audit-refactor-optimize, in /home/jakub/projects/repo-audit-refactor-optimize. You
coordinate ONLY — you never implement: dispatch MULTIPLE OpenCode DeepSeek v4 Pro Max workers
in parallel (one packet each, own git worktree), keep the pool SATURATED at the cap of 4, verify
every gate yourself by reading real output, own all merges. Commit locally per task/round; do
NOT push, tag, or release — human reviews.

READ FIRST, authoritative: docs/plans/2026-06-10-sp5-deterministic-skillset-rewire.md. Workers
implement plan tasks VERBATIM via TDD. A worker's "green" is NOT evidence — re-run gates yourself.

WORKERS: PRIMARY = OpenCode DeepSeek v4 Pro Max via opencode-worker-bridge, multiple concurrent.
FALLBACK (automatic, one-way, logged) ONLY on infrastructure dispatch failure (credits/quota
exhausted, auth/billing, bridge unreachable): NATIVE OPUS workers (Agent tool, isolated worktree,
same packet + gates) for that and all later packets, no pause. A gate-failing CHANGE is a normal
discard/retry on DeepSeek, NOT a backend switch.

PRE-FLIGHT (any failure -> STOP and report): this repo clean, python3 -m pytest tests/ -q = 48
passed; repo-audit-skills v0.3.0 installed at ~/.claude/skills (coverage-gap-audit present);
/home/jakub/projects/repo-audit-skills clean with npm run check green; worker-bridge loads.

WAVES (from the plan's worker wave map — saturate, don't serialize):
  Wave 1: T1 || T3 || T4 (3 workers, disjoint files).
  Wave 2: T2 (after T1 merged) || T5 (after T3+T4 merged).
  Gate:   T6 bootstrap self-checks (YOU, no worker) — expected lane states are in the plan.
  Wave 3: T7a || T7b || T7c (3 read-only dogfood workers, disjoint /tmp out-dirs); YOU do T7d.
  Tail:   T8, then PHASE 2.
Per-merge gate: full pytest suite green in the worker's worktree AND re-run by you after merge.
Any divergence from a plan Expected line = STOP and surface; do not improvise.

PHASE 2 — SELF-BUILD/SELF-AUDIT (the point of the run; do not skip or summarize it away): the
rewired skill audits its OWN repo with code-health-audit-pipeline + coverage handoff, builds a
coverage-gated backlog, and remediates itself per references/remediation-playbook.md — one
DeepSeek worker per single-signal batch, merges serialized, findings may only SHRINK, max 4
rounds, per-round table committed in the dogfood report. ACCEPT only on green tests + leaf
re-run showing the batch shrank. Converge or bound; justify residuals individually.

DEFINITION OF DONE: plan's DoD, all 7 items, each with evidence in your final report (exact test
counts, bootstrap lane states, determinism check output, coverage-leaf activation lines, gated
backlog table, Phase 2 round table, version 0.2.0). Nothing pushed.
```
