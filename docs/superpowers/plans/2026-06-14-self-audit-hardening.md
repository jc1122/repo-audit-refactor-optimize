# Self-Audit Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four gaps + one hazard that dogfooding the orchestrator on itself exposed, so a self-run produces honest signal instead of false positives and noise.

**Architecture:** Six surgical, independently-testable changes in the repo-B project (`~/projects/repo-audit-refactor-optimize`): tighten benchmark-surface detection (G1), scope the diagnosis wave (G2), add generic accepted-residuals suppression (G3), resolve always-available process skills (G4), guard MPRR against self-engine merges, and add a self-dogfood regression test. No change to repo-A leaves or repo-P engine.

**Tech Stack:** Python 3.11+ stdlib; pytest; the existing repo-B scripts. Gates: `pytest tests/` + `python3 scripts/check_release.py`.

**Spec:** `docs/superpowers/specs/2026-06-14-self-audit-hardening-design.md`

---

## File Structure

- Modify `scripts/_bootstrap_report.py` — `_benchmark_surface` + harness-name helper; drop the now-unused `_BENCH_NAME_KW` table (G1).
- Modify `scripts/_skill_probe.py` — `_skill_entry` honors an `always_available` flag (G4).
- Modify `scripts/skill_bootstrap_manifest.json` — add `always_available: true` to three process skills (G4).
- Modify `scripts/run_diagnosis_wave.py` — `--exclude-prefix` + default tests/fixtures exclusion (G2); `--baseline` suppression wiring (G3).
- Modify `scripts/_wave_findings.py` — shared `identity` + `load_baseline` + `partition` (G3).
- Modify `scripts/check_wave_baseline.py` — reuse the shared `identity` (remove its duplicate identity notion) (G3).
- Modify `scripts/mprr_integrate.py` — `self_guard` + `_git_toplevel`; modify `scripts/mprr_run.py` `_cmd_integrate` to enforce it (Fix 5).
- Create `tests/test_self_dogfood.py` — end-to-end self-run regression (Fix 6).
- Add unit tests by **extending existing** files: `tests/test_check_skill_requirements.py`, `tests/test_skill_probe.py` (exists, 7 tests), `tests/test_run_diagnosis_wave.py`, `tests/test_mprr_integrate.py` (exists, 4 tests). **Create new** files: `tests/test_wave_findings.py`, `tests/test_self_dogfood.py`.
- Modify `SKILL.md`, `references/pipeline.md`, `CHANGELOG.md` — docs + version bump 0.6.0 → 0.7.0 (Task 7).

**Baseline before starting:** `git rev-parse HEAD`; `python3 -m pytest tests/ -q` (record the pass count); `python3 scripts/check_release.py` → `{"status": "pass"}`. Tasks are ordered G1 → G4 → G2 → G3 → Fix5 → Fix6 → docs. Each task ends green.

---

### Task 1 (G1): honest benchmark-surface detection

**Files:**
- Modify: `scripts/_bootstrap_report.py` (`_benchmark_surface` ~201-213; `_BENCH_NAME_KW` ~57-68)
- Test: `tests/test_check_skill_requirements.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_check_skill_requirements.py`:

```python
def test_benchmark_named_tooling_is_not_a_surface(tmp_path: Path):
    """Source/test files that merely mention 'benchmark' are not a benchmark surface."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts" / "graduate_benchmark.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests" / "test_graduate_benchmark.py").write_text("def test_x(): pass\n", encoding="utf-8")
    profile = checker.scan_repo_profile(repo)
    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_perf_surface"] is False


def test_benchmark_utils_at_src_is_not_a_surface(tmp_path: Path):
    """A 'benchmark'-substring utility outside a benchmark dir is not a surface."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "benchmark_utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    profile = checker.scan_repo_profile(repo)
    assert profile["has_deterministic_perf_surface"] is False


def test_real_harness_under_benchmarks_dir_is_a_surface(tmp_path: Path):
    """A graduated harness (bench_*.py under benchmarks/) is still a real surface."""
    repo = tmp_path / "repo"
    (repo / "benchmarks" / "sort").mkdir(parents=True)
    (repo / "benchmarks" / "sort" / "bench_sort.py").write_text("def main(): pass\n", encoding="utf-8")
    profile = checker.scan_repo_profile(repo)
    assert profile["benchmark_surfaces"] == ["python-benchmarks"]
    assert profile["has_deterministic_perf_surface"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_check_skill_requirements.py -k "tooling or benchmark_utils or real_harness" -q`
Expected: the first two FAIL (`has_deterministic_perf_surface` is `True` today because `graduate_benchmark.py` / `benchmark_utils.py` substring-match); the third passes.

- [ ] **Step 3: Implement** — in `scripts/_bootstrap_report.py`, replace `_benchmark_surface` (currently ~201-213) with the harness-convention version and add the helpers above it:

```python
# Directories that hold tooling or tests — never a benchmark *surface*.
_NON_SURFACE_DIRS: frozenset[str] = frozenset({"scripts", "tests"})


def _is_harness_name(lower_name: str, suffix: str) -> bool:
    """True for the benchmark harness naming convention: ``bench_*.<ext>`` or ``bench.<ext>``."""
    return lower_name.startswith("bench_") or lower_name == f"bench{suffix}"


def _benchmark_surface(
    suffix: str, lower_name: str, parts_lower: set[str]
) -> str | None:
    """Return the benchmark surface for a file, or None.

    A file counts as a benchmark *surface* only when it follows the harness naming
    convention (``bench_*.<ext>``) OR sits under a benchmark directory — and is not
    under a tooling/test directory. This stops source/tests that merely mention
    "benchmark" (e.g. ``scripts/graduate_benchmark.py``) from being mistaken for a
    committed benchmark surface.
    """
    if parts_lower & _NON_SURFACE_DIRS:
        return None
    if suffix in _BENCH_SURFACE and _is_harness_name(lower_name, suffix):
        return _BENCH_SURFACE.get(suffix)
    path_kws = _BENCH_PATH_KW.get(suffix)
    if path_kws:
        for kw in path_kws:
            if kw in parts_lower:
                return _BENCH_SURFACE.get(suffix)
    return None
```

Then add `"benchmarks"` to the Python path-keyword set so a graduated `benchmarks/<name>/bench_<name>.py` matches by directory too — change `_BENCH_PATH_KW` (~71):

```python
_BENCH_PATH_KW: dict[str, tuple[str, ...]] = {
    ".py": ("benches", "benchmarks"),
    ".c": ("benchmark",),
    ".h": ("benchmark",),
    ".cc": ("benchmark",),
    ".cpp": ("benchmark",),
    ".hpp": ("benchmark",),
    ".rs": ("benches",),
}
```

`_BENCH_NAME_KW` (the loose substring table, ~57-68) is now unused — delete it.

- [ ] **Step 4: Remove the other now-dead helper if unused**

Run: `grep -rn "_has_any_keyword" scripts/ tests/`
If the only hit is its definition in `_bootstrap_report.py` (no other caller), delete that function too. If anything else calls it, leave it.

- [ ] **Step 5: Run the new + existing surface tests**

Run: `python3 -m pytest tests/test_check_skill_requirements.py -q`
Expected: PASS, including the existing `test_scan_repo_profile_detects_languages_and_surfaces` (`benches/bench_hot.py` → harness name + `benches/` dir), `test_native_benchmarks_surface_detection` (`src/bench_fft.c` → `bench_` prefix), `test_cargo_benches_surface_detection` (`benches/my_bench.rs` → `benches/` dir), and `test_scan_repo_profile_no_false_positive_from_parent_dir`. If any of these regress, the harness predicate is wrong — fix the predicate, not the existing tests.

- [ ] **Step 6: Commit**

```bash
git add scripts/_bootstrap_report.py tests/test_check_skill_requirements.py
git commit -m "fix(bootstrap): benchmark-surface detection requires a real harness/dir, not a name substring (G1)"
```

---

### Task 2 (G4): always-available process skills

**Files:**
- Modify: `scripts/_skill_probe.py` (`_skill_entry` ~204-221)
- Modify: `scripts/skill_bootstrap_manifest.json`
- Test: `tests/test_skill_probe.py` (**extend — it already exists with 7 `_skill_entry` tests**)

> **Audit note:** `tests/test_skill_probe.py` already exists (it imports `from scripts import
> _skill_probe as probe` and has 7 tests incl. `test_skill_entry_marks_advisory_only_*` and
> `test_skill_entry_marks_manual_*`). APPEND the new tests — do not recreate the file or re-import
> `probe`. The two new names below do not collide with the existing 7 (verified).

- [ ] **Step 1: Write the failing test** — APPEND to the existing `tests/test_skill_probe.py`:

```python
_ALWAYS_CFG = {
    "priority": "preferred",
    "source_type": "user-local",
    "manual_fallback": "manual",
    "restart_required_if_installed": True,
    "always_available": True,
}


def test_always_available_resolves_usable_without_filesystem() -> None:
    entry = probe._skill_entry("verification-before-completion", _ALWAYS_CFG,
                               usable_skills={}, advisory_skills={})
    assert entry["state"] == "usable_now"
    assert entry["root_kind"] == "harness"


def test_always_available_skipped_when_flag_absent_is_manual() -> None:
    cfg = {k: v for k, v in _ALWAYS_CFG.items() if k != "always_available"}
    entry = probe._skill_entry("some-leaf", cfg, usable_skills={}, advisory_skills={})
    assert entry["state"] == "manual_only"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_skill_probe.py -q`
Expected: `test_always_available_resolves_usable_without_filesystem` FAILS (state is `manual_only` today);
the 7 existing tests stay green (their configs are unflagged, so the new early branch never fires).

- [ ] **Step 3: Implement** — in `scripts/_skill_probe.py`, add the early branch in `_skill_entry` (after `entry = _build_skill_entry_base(...)`, before the `usable_skills` check):

```python
def _skill_entry(
    skill_name: str,
    skill_config: dict[str, Any],
    usable_skills: dict[str, dict[str, Any]],
    advisory_skills: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    _validate_skill_entry_fields(skill_name, skill_config)
    entry = _build_skill_entry_base(skill_name, skill_config)
    if skill_config.get("always_available"):
        # Harness/process skills are guaranteed by the runtime, not the skills-root;
        # resolve them as usable without a filesystem probe (fixes orchestration=manual).
        return {**entry, "state": "usable_now", "root_kind": "harness", "skill_path": None}
    if skill_name in usable_skills:
        return {
            **entry,
            **_evaluate_installed_skill(
                skill_name, skill_config, usable_skills[skill_name]
            ),
        }
    if skill_name in advisory_skills:
        return _apply_advisory_state(entry, advisory_skills[skill_name])
    return _apply_installable_or_manual_state(entry)
```

- [ ] **Step 4: Flag the three process skills** — in `scripts/skill_bootstrap_manifest.json`, add `"always_available": true` to the entries for `verification-before-completion`, `dispatching-parallel-agents`, and `subagent-driven-development` (only these three; leave `find-skills`/`skill-installer` as optional helpers). Example:

```json
    "verification-before-completion": {
      "priority": "preferred",
      "source_type": "user-local",
      "install_source": null,
      "manual_fallback": "Rerun verification manually and record evidence.",
      "restart_required_if_installed": true,
      "always_available": true
    },
```

> **Audit caveat — flag ONLY the real manifest, never the `sample_manifest` test fixture.**
> The `always_available` branch short-circuits *before* the advisory/override branches, so a skill
> carrying the flag resolves `usable_now`/`harness` regardless of where it is found. Existing tests
> `test_check_skill_requirements.py:556-557` (assert `verification-before-completion` →
> `advisory_only`/`root_kind == "foreign"`) and `:591` (override `manual_fallback`) stay green **only
> because** they build their report from `sample_manifest`, which must NOT gain the flag. If you add
> `always_available` to the `sample_manifest` fixture, those two tests break. Intended production
> behavior change: a foreign-rooted always-available skill now reports `usable_now`, not `advisory_only`.

- [ ] **Step 5: Run unit + full bootstrap suite**

Run: `python3 -m pytest tests/test_skill_probe.py tests/test_check_skill_requirements.py -q`
Expected: PASS — including `test_orchestration_lane_full_with_optional` (skills also on disk there) and
the advisory/override tests at `:556` and `:591` (they use `sample_manifest`, which is unflagged). No
existing test asserts an orchestration `manual` state, so none should flip; if one does, that is a
real signal to investigate, not a test to blindly edit.

- [ ] **Step 6: Commit**

```bash
git add scripts/_skill_probe.py scripts/skill_bootstrap_manifest.json tests/test_skill_probe.py
git commit -m "fix(bootstrap): resolve always-available process skills without a filesystem probe (G4)"
```

---

### Task 3 (G2): default tests/fixtures exclusion in the diagnosis wave

**Files:**
- Modify: `scripts/run_diagnosis_wave.py`
- Test: `tests/test_run_diagnosis_wave.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_run_diagnosis_wave.py`:

```python
import importlib
wave = importlib.import_module("scripts.run_diagnosis_wave")


def test_effective_excludes_defaults_to_tests_and_fixtures():
    assert wave._effective_excludes(source_prefixes=[], exclude_prefixes=[]) == ["tests", "fixtures"]


def test_effective_excludes_explicit_source_prefix_disables_default():
    assert wave._effective_excludes(source_prefixes=["scripts"], exclude_prefixes=[]) == []


def test_effective_excludes_explicit_excludes_win():
    assert wave._effective_excludes(source_prefixes=[], exclude_prefixes=["vendor"]) == ["vendor"]


def test_audit_scope_args_emits_excludes_when_supported():
    args = wave._audit_scope_args(["scripts"], ["tests", "fixtures"], supports_exclude=True)
    assert args == ["--source-prefix", "scripts",
                    "--exclude-prefix", "tests", "--exclude-prefix", "fixtures"]


def test_audit_scope_args_drops_excludes_when_unsupported():
    args = wave._audit_scope_args([], ["tests"], supports_exclude=False)
    assert args == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py -k "effective_excludes or audit_scope" -q`
Expected: FAIL — `_effective_excludes` / `_audit_scope_args` undefined.

- [ ] **Step 3: Implement** — in `scripts/run_diagnosis_wave.py`:

Add the default constant near `DOC_EXCLUDES` (~37):

```python
DEFAULT_EXCLUDES = ("tests", "fixtures")
```

Add `exclude_prefixes` to `_LaneContext` (the frozen dataclass ~66-74):

```python
@dataclass(frozen=True)
class _LaneContext:
    repo: Path
    out_root: Path
    source_prefixes: list[str]
    exclude_prefixes: list[str]
    rev: str | None
    coverage_json: Path | None
    security_config: Path | None
    hotspot_config: Path | None
```

Add the `--exclude-prefix` arg in `_parse_args` (after the `--source-prefix` line ~82):

```python
    parser.add_argument("--exclude-prefix", action="append", default=[])
```

Add the two pure helpers (near `_append_flagged`):

```python
def _effective_excludes(
    source_prefixes: list[str], exclude_prefixes: list[str]
) -> list[str]:
    """Default exclusions when scoping is implicit; explicit scoping overrides.

    Explicit --exclude-prefix always wins. Otherwise, when no --source-prefix is
    given the wave scopes nothing positively, so it excludes tests/fixtures by
    default; an explicit --source-prefix means the caller is scoping deliberately,
    so no default exclusion is added.
    """
    if exclude_prefixes:
        return list(exclude_prefixes)
    if source_prefixes:
        return []
    return list(DEFAULT_EXCLUDES)


def _audit_scope_args(
    source_prefixes: list[str], exclude_prefixes: list[str], supports_exclude: bool
) -> list[str]:
    """Scope flags for the source-auditing lanes (code-health/security/dependency)."""
    args: list[str] = []
    for prefix in source_prefixes:
        args.extend(["--source-prefix", prefix])
    if supports_exclude:
        for prefix in exclude_prefixes:
            args.extend(["--exclude-prefix", prefix])
    return args
```

Replace the `code-health/security/dependency` branch inside `_append_scope_args` (currently ~180-181):

```python
    if lane in {"code-health", "security", "dependency"}:
        supports = _leaf_supports_exclude_prefix(leaf)
        cmd.extend(
            _audit_scope_args(context.source_prefixes, context.exclude_prefixes, supports)
        )
    elif lane == "docs":
        _add_docs_args(cmd, leaf, context)
    elif lane == "hotspot":
        _add_hotspot_args(cmd, context)
```

Update `main` to compute the effective excludes and pass them into the context (the `_LaneContext(...)` construction ~372-380):

```python
    context = _LaneContext(
        args.repo,
        args.out_dir,
        args.source_prefix,
        _effective_excludes(args.source_prefix, args.exclude_prefix),
        args.rev,
        args.coverage_json,
        args.security_config,
        args.hotspot_config,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py -q`
Expected: PASS. If existing wave tests construct `_LaneContext(...)` positionally, they now miss the new field — update those call sites to pass `exclude_prefixes=[]` (or positionally an empty list in the new slot). Fix the test call sites, not the dataclass order.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_diagnosis_wave.py tests/test_run_diagnosis_wave.py
git commit -m "feat(wave): exclude tests/fixtures by default; explicit --source-prefix overrides (G2)"
```

---

### Task 4 (G3): generic accepted-residuals suppression (extract + reuse the existing identity)

**Files:**
- Modify: `scripts/_wave_findings.py` (add shared `identity` + `load_baseline` + `partition`)
- Modify: `scripts/run_diagnosis_wave.py` (wire `--baseline`)
- Modify: `scripts/check_wave_baseline.py` (reuse the shared `identity` — delete its private one)
- Test: `tests/test_wave_findings.py` (create)

> **Audit fix — do NOT add a parallel identity.** `scripts/check_wave_baseline.py` already matches
> findings against `wave_baseline.json` by identity (`identities()`, line 29), set-difference
> (`new = cur - base`, line 101), and stale detection (`base - cur`). This task makes
> `_wave_findings.py` the single source of truth for finding `identity`, has both the wave's
> `--baseline` suppression **and** `check_wave_baseline` consume it, and adds `partition` for the
> suppress-and-continue case — instead of reimplementing matching with a second identity notion.
> Wave findings are already normalized to exactly `{leaf, path, symbol, metric}` (`_normalize_finding`)
> and `wave_baseline.json` entries share that shape, so one `identity` serves both. `check_wave_baseline`'s
> tests only substring-check `new_findings`/`stale_baseline` and assert order-insensitivity, so
> rerouting its `identities()` to the shared 4-tuple `identity` is behavior-safe (verified against
> `tests/test_check_wave_baseline.py`).

- [ ] **Step 1: Write the failing test** — create `tests/test_wave_findings.py`:

```python
import importlib
import json
import pytest

wf = importlib.import_module("scripts._wave_findings")
cwb = importlib.import_module("scripts.check_wave_baseline")

FINDINGS = [
    {"leaf": "complexity", "path": "scripts/a.py", "symbol": "<module>", "metric": "maintainability_index"},
    {"leaf": "security", "path": "scripts/b.py", "symbol": "f", "metric": "B603"},
]


def test_partition_suppresses_exact_matches():
    baseline = [{"leaf": "complexity", "path": "scripts/a.py", "symbol": "<module>", "metric": "maintainability_index"}]
    active, suppressed, stale = wf.partition(FINDINGS, baseline)
    assert [f["path"] for f in active] == ["scripts/b.py"]
    assert suppressed[0]["path"] == "scripts/a.py" and suppressed[0]["suppressed"] is True
    assert stale == []


def test_partition_reports_stale_entries():
    baseline = [{"leaf": "complexity", "path": "scripts/gone.py", "symbol": "<module>", "metric": "maintainability_index"}]
    active, suppressed, stale = wf.partition(FINDINGS, baseline)
    assert len(active) == 2 and suppressed == []
    assert stale == [("complexity", "scripts/gone.py", "<module>", "maintainability_index")]


def test_identity_is_order_insensitive():
    a = {"leaf": "x", "path": "y", "symbol": "z", "metric": "m"}
    b = {"metric": "m", "symbol": "z", "path": "y", "leaf": "x"}
    assert wf.identity(a) == wf.identity(b)


def test_check_wave_baseline_reuses_the_shared_identity():
    # the convergence ratchet and the wave's --baseline must agree on identity (single source).
    f = {"leaf": "x", "path": "y", "symbol": "z", "metric": "m"}
    assert cwb.identities([f]) == {wf.identity(f)}


def test_load_baseline_rejects_non_array(tmp_path):
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(ValueError):
        wf.load_baseline(bad)


def test_load_baseline_raises_on_bad_json(tmp_path):
    bad = tmp_path / "b.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        wf.load_baseline(bad)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_wave_findings.py -q`
Expected: FAIL — `partition` / `identity` / `load_baseline` undefined.

- [ ] **Step 3: Implement** — append to `scripts/_wave_findings.py`:

```python
def identity(finding: dict[str, str]) -> tuple[str, str, str, str]:
    """Canonical four-field wave identity, order-insensitive on dict keys.

    Single source of truth — consumed by both the wave's --baseline suppression and
    check_wave_baseline's convergence ratchet, so the two can never disagree.
    """
    return (
        finding.get("leaf", ""),
        finding.get("path", ""),
        finding.get("symbol", ""),
        finding.get("metric", ""),
    )


def load_baseline(path: Path) -> list[dict[str, str]]:
    """Load an accepted-residuals baseline (a JSON array of identities).

    Raises on unreadable/invalid input — never silently treats a broken baseline as
    "no suppression".
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(
            f"baseline must be a JSON array of identities, got {type(payload).__name__}"
        )
    return payload


def partition(
    findings: list[dict[str, str]], baseline: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[tuple[str, str, str, str]]]:
    """Split findings against a baseline by identity → (active, suppressed, stale).

    * active     — findings whose identity is NOT in the baseline (new work)
    * suppressed — findings whose identity IS in the baseline (accepted residuals)
    * stale      — baseline identities that matched nothing (sorted)

    The wave drops ``suppressed``; the convergence ratchet fails on ``active`` and ``stale``.
    """
    baseline_ids = {identity(entry) for entry in baseline}
    matched: set[tuple[str, str, str, str]] = set()
    active: list[dict[str, str]] = []
    suppressed: list[dict[str, str]] = []
    for finding in findings:
        fid = identity(finding)
        if fid in baseline_ids:
            matched.add(fid)
            suppressed.append({**finding, "suppressed": True})
        else:
            active.append(finding)
    stale = sorted(baseline_ids - matched)
    return active, suppressed, stale
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_wave_findings.py -q`
Expected: **5 passed, 1 failing** — `test_partition_*`, `test_identity_*`, and `test_load_baseline_*`
pass; `test_check_wave_baseline_reuses_the_shared_identity` FAILS because `check_wave_baseline.identities`
still returns `tuple(sorted(d.items()))`, not the shared 4-tuple. That one failure is expected and is
fixed in Step 5 (it is the RED for the reuse change).

- [ ] **Step 5: Reuse the shared identity in `check_wave_baseline.py`** — so there is one identity definition. At the top of `scripts/check_wave_baseline.py`, import the helper the import-robust way `run_diagnosis_wave.py` does:

```python
import importlib
_wf = importlib.import_module("scripts._wave_findings" if __package__ else "_wave_findings")
```

Then replace the body of `identities` (currently `return {tuple(sorted(d.items())) for d in fs}`, line ~29):

```python
def identities(fs):
    return {_wf.identity(d) for d in fs}
```

Leave `_compare`, `_stale_payload`, and the pass/fail policy untouched — only the identity *source* changes. (Its tests substring-check `new_findings`/`stale_baseline` and assert order-insensitivity, both preserved by the 4-tuple identity.)

- [ ] **Step 6: Wire `--baseline` into the wave** — in `scripts/run_diagnosis_wave.py`:

Add the arg in `_parse_args`:

```python
    parser.add_argument("--baseline", type=Path, help="Accepted-residuals JSON to suppress")
```

Replace the tail of `main` (currently `run = _run_wave(...)` / `return _write_wave_outputs(args.out_dir, *run)`):

```python
    wave_exit, summary, wave_findings, timings = _run_wave(
        selected, loaded, args.skills_root, context
    )
    if args.baseline is not None:
        baseline = _wave_findings.load_baseline(args.baseline)  # raises on bad input
        wave_findings, suppressed, stale = _wave_findings.partition(
            wave_findings, baseline
        )
        (args.out_dir / "wave_findings.suppressed.json").write_text(
            json.dumps(
                {"suppressed": suppressed, "stale_baseline": [list(s) for s in stale]},
                indent=2,
            ),
            encoding="utf-8",
        )
    return _write_wave_outputs(args.out_dir, wave_exit, summary, wave_findings, timings)
```

- [ ] **Step 7: Run the wave + baseline + ratchet suites (confirm check_wave_baseline still green)**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py tests/test_wave_findings.py tests/test_check_wave_baseline.py -q`
Expected: PASS — including the existing `check_wave_baseline` tests; the identity reroute is behavior-safe.

- [ ] **Step 8: Commit**

```bash
git add scripts/_wave_findings.py scripts/run_diagnosis_wave.py scripts/check_wave_baseline.py tests/test_wave_findings.py
git commit -m "feat(wave): --baseline suppression reusing the shared wave identity (G3; de-dupes check_wave_baseline)"
```

---

### Task 5 (Fix 5): MPRR self-engine merge guard

**Files:**
- Modify: `scripts/mprr_integrate.py`
- Modify: `scripts/mprr_run.py` (`_cmd_integrate` ~71-95)
- Test: `tests/test_mprr_integrate.py` (**extend — it already exists with 4 tests**)

> **Audit note:** `tests/test_mprr_integrate.py` already exists (it imports
> `integ = importlib.import_module("scripts.mprr_integrate")` plus `pytest`, and tests
> `assert_scope`/`merge_clean`). APPEND the new tests using the existing `integ` alias — do not
> recreate the file or re-import. The three new names do not collide with the existing 4 (verified).

- [ ] **Step 1: Write the failing test** — APPEND to the existing `tests/test_mprr_integrate.py` (reuse its `integ` alias):

```python
def test_self_guard_blocks_engine_self_merge(monkeypatch):
    monkeypatch.setattr(integ, "_git_toplevel", lambda p: "/repo")  # engine == target
    ok, reasons = integ.self_guard("/repo", ["scripts/mprr_run.py", "docs/x.md"])
    assert ok is False
    assert any("self-engine" in r and "mprr_run.py" in r for r in reasons)


def test_self_guard_allows_non_engine_files_in_self_repo(monkeypatch):
    monkeypatch.setattr(integ, "_git_toplevel", lambda p: "/repo")
    ok, reasons = integ.self_guard("/repo", ["docs/x.md", "README.md"])
    assert ok is True and reasons == []


def test_self_guard_allows_different_repo(monkeypatch):
    monkeypatch.setattr(integ, "_git_toplevel",
                        lambda p: "/engine" if p == integ._ENGINE_DIR else "/target")
    ok, reasons = integ.self_guard("/target", ["scripts/mprr_run.py"])
    assert ok is True and reasons == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_mprr_integrate.py -q`
Expected: FAIL — `self_guard` / `_git_toplevel` / `_ENGINE_DIR` undefined (the existing 4 tests still pass).

- [ ] **Step 3: Implement** — in `scripts/mprr_integrate.py`, add `from pathlib import Path` to the imports, then append:

```python
_ENGINE_DIR = Path(__file__).resolve().parent  # the engine repo's scripts/ dir


def _git_toplevel(path: Path | str) -> str | None:
    """Return the git toplevel for *path*, or None if it cannot be resolved."""
    try:
        proc = subprocess.run(  # nosec B603,B607 — fixed git argv, no shell
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def self_guard(repo: str, diff_files: Iterable[str]) -> tuple[bool, list[str]]:
    """Refuse to auto-merge edits to the engine's own ``scripts/*.py`` when the
    target resolves to the engine's own repo (or the target is unresolvable —
    fail closed). Defense-in-depth against the in-place / self-modification topology.
    """
    engine_root = _git_toplevel(_ENGINE_DIR)
    if engine_root is None:
        return True, []  # cannot identify the engine repo; nothing to protect
    target_root = _git_toplevel(Path(repo))
    if target_root is not None and target_root != engine_root:
        return True, []  # clearly a different repo
    offenders = sorted(
        f for f in diff_files if f.startswith("scripts/") and f.endswith(".py")
    )
    if offenders:
        return False, [
            f"self-engine modification requires human review: {f}" for f in offenders
        ]
    return True, []
```

- [ ] **Step 4: Enforce it in the integrate command** — in `scripts/mprr_run.py` `_cmd_integrate`, add the guard alongside the existing checks and include it in the merge condition + log:

```python
    scope_ok, scope_reasons = mprr_integrate.assert_scope(files, diff_files)
    gate_ok, gate_reasons = mprr_gate.verify(rc, evidence)
    guard_ok, guard_reasons = mprr_integrate.self_guard(a.repo, diff_files)
    merged = False
    status = "discard"
    if scope_ok and gate_ok and guard_ok:
        if not a.no_merge:
            mprr_integrate.merge_clean(a.repo, a.branch)  # raises on conflict
        merged = True
        status = "merge"
    # always release locks (complete)
    running.pop(a.packet_id, None)
    locked -= set(files)
    _write_state(run_dir, running, locked)
    _log(run_dir, {"event": status, "id": a.packet_id, "conflict": False,
                   "merged": merged,
                   "reasons": scope_reasons + gate_reasons + guard_reasons})
    return 0 if merged else 1
```

- [ ] **Step 5: Run to verify it passes**

Run: `python3 -m pytest tests/test_mprr_integrate.py tests/ -k "mprr" -q`
Expected: PASS. Existing MPRR tests that call `_cmd_integrate` with a tmp target repo still merge — their target is a fresh git repo distinct from the engine repo, so `self_guard` returns OK. If an existing MPRR integration test happens to use the engine repo as its target with engine-file diffs, update it to a tmp repo (that is the realistic case).

- [ ] **Step 6: Commit**

```bash
git add scripts/mprr_integrate.py scripts/mprr_run.py tests/test_mprr_integrate.py
git commit -m "feat(mprr): refuse auto-merge of self-engine edits (defense-in-depth)"
```

---

### Task 6 (Fix 6): self-dogfood regression test

**Files:**
- Test: `tests/test_self_dogfood.py` (create)

This locks G1+G2+G4 against silent regression by asserting at the profile/lane-resolution layer
on repo-B's own tree — hermetic, no heavy leaf execution, no dependency on the installed skills root.

- [ ] **Step 1: Write the test** — create `tests/test_self_dogfood.py`:

```python
"""Dogfood guard: running the orchestrator's own detectors on its own repo must be honest."""
import importlib
import json
from pathlib import Path

checker = importlib.import_module("scripts.check_skill_requirements")
lr = importlib.import_module("scripts._lane_resolve")
probe = importlib.import_module("scripts._skill_probe")
wave = importlib.import_module("scripts.run_diagnosis_wave")

REPO = Path(__file__).resolve().parents[1]


def test_repo_b_has_no_false_benchmark_surface():
    # G1: scripts/graduate_benchmark.py + tests/test_graduate_benchmark.py must NOT count.
    profile = checker.scan_repo_profile(REPO)
    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_perf_surface"] is False


def test_repo_b_performance_lane_resolves_synthesizable():
    # G1 end-to-end: real repo-B profile + perf-benchmark usable → synthesizable.
    profile = checker.scan_repo_profile(REPO)
    assert profile["has_deterministic_test_surface"] is True  # repo-B has pytest
    lane = {"preferred": ["perf-benchmark"], "fallback": ["perf-optimization"],
            "manual_fallback": "manual perf reasoning"}
    skills = {"perf-benchmark": {"state": "usable_now"},
              "perf-optimization": {"state": "manual_only"}}
    state, selected, _warnings = lr._evaluate_performance_lane(lane, skills, profile)
    assert state == "synthesizable"
    assert "perf-benchmark" in selected


def test_repo_b_orchestration_process_skills_are_always_available():
    # G4: the manifest flags the process skills, and the probe resolves them usable.
    manifest = json.loads((REPO / "scripts" / "skill_bootstrap_manifest.json").read_text())
    for name in ("verification-before-completion", "dispatching-parallel-agents",
                 "subagent-driven-development"):
        cfg = manifest["skills"][name]
        assert cfg.get("always_available") is True, name
        entry = probe._skill_entry(name, cfg, usable_skills={}, advisory_skills={})
        assert entry["state"] == "usable_now", name


def test_wave_excludes_tests_and_fixtures_by_default():
    # G2: an unscoped wave defaults to excluding tests/ and fixtures.
    assert wave._effective_excludes(source_prefixes=[], exclude_prefixes=[]) == ["tests", "fixtures"]
    args = wave._audit_scope_args([], ["tests", "fixtures"], supports_exclude=True)
    assert args.count("--exclude-prefix") == 2 and "tests" in args and "fixtures" in args
```

- [ ] **Step 2: Run to verify it passes** (all four fixes are now in)

Run: `python3 -m pytest tests/test_self_dogfood.py -v`
Expected: PASS (4 passed). If `test_repo_b_has_no_false_benchmark_surface` fails, G1 regressed; if the perf-lane test fails, the profile→lane wiring is wrong; etc.

- [ ] **Step 3: Commit**

```bash
git add tests/test_self_dogfood.py
git commit -m "test(self-audit): dogfood guard — synthesizable lane, no fixture noise, process skills usable"
```

---

### Task 7: docs + CHANGELOG + version bump

**Files:**
- Modify: `SKILL.md` (version + wave command), `references/pipeline.md`, `CHANGELOG.md`

- [ ] **Step 1: Update the wave command + lane docs** — in `SKILL.md`, in the Stage 2 diagnosis-wave example, show explicit scoping and the default exclusion, e.g. add after the command: "By default (no `--source-prefix`) the wave excludes `tests/` and `**/fixtures/`; pass `--source-prefix <dir>` to scope positively, and `--baseline <accepted-residuals.json>` to suppress already-triaged findings." Note the orchestration lane now resolves via always-available process skills.

- [ ] **Step 2: Update `references/pipeline.md`** — add one paragraph under the Diagnosis Wave Runner section documenting: default tests/fixtures exclusion, the `--baseline` suppression input (with the `{leaf,path,symbol,metric}` identity and `wave_findings.suppressed.json` output), and the MPRR self-engine merge guard.

- [ ] **Step 3: Bump version** — in `SKILL.md` frontmatter change `version: 0.6.0` → `version: 0.7.0`.

- [ ] **Step 4: CHANGELOG** — add a `## 0.7.0` entry at the top: "feat: self-audit hardening — honest benchmark-surface detection (no name-substring false positives), default tests/fixtures exclusion + `--baseline` suppression in the diagnosis wave, always-available process skills, and an MPRR self-engine merge guard; adds a self-dogfood regression test." Keep the heading text exactly `## 0.7.0` so `check_release.py` matches it to the SKILL.md version.

- [ ] **Step 5: Gate + commit**

Run: `python3 -m pytest tests/ -q` — Expected: PASS (baseline count + all new tests).
Run: `python3 scripts/check_release.py` — Expected: `{"status": "pass"}` (version ↔ CHANGELOG heading in sync).

```bash
git add SKILL.md references/pipeline.md CHANGELOG.md
git commit -m "docs(self-audit): document scoping/suppression/self-guard; bump repo-B 0.6.0 -> 0.7.0"
```

---

## Final verification

- [ ] Run the full suite: `python3 -m pytest tests/ -q` → all pass (baseline + new tests from Tasks 1-6).
- [ ] Run the release gate: `python3 scripts/check_release.py` → `{"status": "pass"}`.
- [ ] Re-dogfood to confirm the fixes hold end-to-end:
  - `python3 scripts/check_skill_requirements.py --repo "$(pwd)" --out-dir /tmp/selfcheck` → performance lane `synthesizable`, orchestration not `manual`.
  - A scoped wave (`--lanes security` with no `--source-prefix`) produces zero `tests/`-prefixed findings.
- [ ] Confirm the working tree is clean and every task committed: `git status --porcelain` empty, `git log --oneline` shows 7 task commits.
- [ ] Do NOT push/tag/merge — integration is a separate human-gated step (mirror the prior feature's release flow: re-install the skill after merge so `~/.agents/skills` picks up the changes).

---

## Self-Review (completed by planner)

- **Spec coverage:** G1 → Task 1; G2 → Task 3; G3 → Task 4; G4 → Task 2; MPRR self-guard → Task 5;
  self-dogfood regression → Task 6; docs/version → Task 7. All six spec fixes have a task.
- **Placeholder scan:** no TBD/TODO; every code step shows full code; commands have expected output.
- **Type/identity consistency:** `_benchmark_surface(suffix, lower_name, parts_lower)` signature
  unchanged (callers untouched); `_effective_excludes`/`_audit_scope_args` names match across Task 3,
  Task 6, and the self-dogfood test; `identity(finding)` + `partition(findings, baseline) ->
  (active, suppressed, stale)` match Task 4's wiring, tests, and the `check_wave_baseline` reuse; the
  wave identity `{leaf,path,symbol,metric}` matches `_normalize_finding` (already in `_wave_findings.py`)
  and `wave_baseline.json`; `self_guard(repo, diff_files) -> (ok, reasons)` matches the `_cmd_integrate`
  call site; `_LaneContext` gains `exclude_prefixes` and its **single** constructor call (only
  `run_diagnosis_wave.py:372`; no test constructs it) is updated (Task 3 Step 3).
- **Existing-test impact (verified against the code):** G1's stricter rule keeps every current
  benchmark test green (`bench_hot.py`/`bench_fft.c` → `bench_` prefix; `my_bench.rs` → `benches/`
  dir; parent-dir false-positive test rooted at the repo); `_BENCH_NAME_KW`/`_has_any_keyword` are
  used only by `_benchmark_surface` and are removed. G4 keeps `test_orchestration_lane_full_with_optional`
  and the advisory/override tests (`:556`, `:591`) green — they use the unflagged `sample_manifest`
  (Task 2 caveat). G3's `check_wave_baseline` identity reroute is behavior-safe (its tests substring-check
  output + assert order-insensitivity). Fix 5 breaks no MPRR test: none passes `scripts/`-prefixed
  diff-files (the one CLI integrate test uses `--diff-files a.py`).
- **Audit amendments incorporated (2026-06-14 audit pass):**
  - **G3 (Task 4) — was a DRY conflict:** the first draft added a parallel `apply_baseline` with a
    second identity notion alongside the one `check_wave_baseline.py` already has. Rewritten to extract
    one shared `identity` consumed by both, plus `partition` for suppress-and-continue.
  - **G4 (Task 2) — was a breakage trap:** added the explicit caveat to flag only the real manifest,
    never `sample_manifest` (else `:556`/`:591` break), and documented the foreign-root behavior change.
  - **Test-file collisions (Task 2 + Task 5) — 2nd audit pass:** `tests/test_skill_probe.py` (7 tests)
    and `tests/test_mprr_integrate.py` (4 tests) already exist; the draft said "create", which would
    overwrite them. Both tasks now say **extend/append**, reuse the existing `probe`/`integ` imports,
    and the new test names are verified non-colliding. Only `tests/test_wave_findings.py` and
    `tests/test_self_dogfood.py` are genuinely new.
- **Out of scope (intentional):** bootstrap-lane `degraded` (optional helpers), and coupling the
  orchestrator to repo-B's wave baseline (G3 stays a generic, optional input).
