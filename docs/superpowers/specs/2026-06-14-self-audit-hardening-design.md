# Self-Audit Hardening — Design

**Date:** 2026-06-14
**Status:** Design (awaiting review → writing-plans)
**Scope:** the repo-audit-refactor-optimize orchestrator (repo-B), so that auditing *itself*
(dogfooding) produces honest signal instead of false positives and noise.

## Problem

Dogfooding the orchestrator on its own repository (`~/projects/repo-audit-refactor-optimize`)
surfaced four real gaps plus one self-application hazard. All were confirmed empirically by
running Stage 0 (bootstrap) and Stage 2 (diagnosis wave) on the repo itself:

- **G1 — the `synthesizable` perf lane can never fire on its own repo.**
  `_bootstrap_report._benchmark_surface` keyword-matches `*benchmark*`/`*bench*` in a filename
  regardless of directory, so the feature's own tooling — `scripts/graduate_benchmark.py` and
  `tests/test_graduate_benchmark.py` — is mistaken for a committed benchmark surface.
  `has_deterministic_perf_surface` becomes `True`, the performance lane resolves to `full`, and
  the synthesis path is unreachable. Any target with a file named `benchmark_utils.py` hits the
  same false positive.
- **G2 — the diagnosis wave scans tests and fixtures, so most findings are noise.** The SKILL.md
  `run_diagnosis_wave` command has no source scoping; a self-run produced **1013** findings, of
  which **~783 were under `tests/`** (raw bandit on asserts/subprocess/temp plus the
  *intentionally-dirty* perf-smell/mprr fixtures) and ~100 under docs. Only ~130 were in
  `scripts/`. repo-A already carries a durable tests/fixtures exclusion policy; the repo-B wave
  runner does not apply one.
- **G3 — the orchestrator re-surfaces a target's already-accepted residuals.** The wave emits raw
  findings and does not consult the target's accepted-residuals baseline (repo-B's own
  `wave_baseline.json`, 13 frozen entries, is enforced by a *separate* gate `check_wave_baseline.py`,
  not the generic audit path). Auditing itself, the orchestrator would re-propose remediation for
  residuals already triaged and frozen.
- **G4 — the bootstrap probe under-reports its own capability.** `_skill_probe` only resolves
  skills discovered on the filesystem skills-root. Harness/process skills
  (`verification-before-completion`, `dispatching-parallel-agents`, `subagent-driven-development`)
  live elsewhere and are not found, so the `orchestration` lane resolves to `manual` even though
  those skills are always available in this harness.
- **MPRR self-modification hazard (topology-dependent).** MPRR's `integrate` runs `git merge` into
  the current branch of the target repo. In the normal topology (the *installed copy* audits the
  *project* — distinct inodes, verified) there is **no** mid-run corruption. But an in-place run
  (`cd project && python3 scripts/mprr_run.py --repo .`) makes process-source == target, which is a
  real footgun, and in all topologies MPRR could auto-merge refactors into its own gating engine
  without a human reviewing the gater. This is a defense-in-depth concern, not a crash.

A non-issue was investigated and dismissed: the per-lane `blocking:false` on a `full` performance
lane is correct by design (`_bootstrap_report.py:379` defines report-`blocking` as "is a blocking
lane **and** currently blocked").

## Goals

Make a self-dogfood run honest and useful:

1. The performance lane resolves to `synthesizable` on a repo with no real benchmark surface (G1).
2. The diagnosis wave excludes tests and fixtures by default (G2).
3. The orchestrator can suppress a target's accepted residuals via a generic, target-agnostic
   input (G3).
4. Always-available process skills resolve as usable, so the orchestration lane is not falsely
   `manual` (G4).
5. MPRR refuses to silently auto-merge edits to its own engine (defense-in-depth).
6. A regression test dogfoods the skill on itself so these gaps cannot silently return.

### Non-goals

- Folding repo-B's `wave_baseline.json` gate into the orchestrator. G3 keeps the audit path and the
  repo's internal ratchet **decoupled**; suppression is an optional input, not a coupling.
- Fixing the `bootstrap`-lane `degraded` state (missing `find-skills`/`skill-installer`). Those are
  genuinely optional helpers; degraded is the correct report.
- Any change to the leaf audit skills in repo-A or the engine in repo-P. Every change here is in the
  repo-B project.

## Success criterion

Running bootstrap + a scoped diagnosis wave on repo-B's own root yields: performance lane
`synthesizable`, orchestration lane not `manual`, zero findings under `tests/` or `**/fixtures/`,
and (when the repo's `wave_baseline.json` is passed as a suppression input) the 13 frozen residuals
marked suppressed rather than re-proposed. A `--repo .` MPRR integrate touching an engine module is
refused with a clear reason.

---

## The six fixes

All changes are in the repo-B project. Each is independently testable; gates remain
`pytest tests/` + `python scripts/check_release.py`.

### Fix 1 — G1: honest benchmark-surface detection
**File:** `scripts/_bootstrap_report.py` (`_benchmark_surface` and its lookup tables).

Replace the loose filename-keyword match with a stricter rule. A file is part of a benchmark
*surface* only when **both**:

- it sits under a benchmark **path component** (`benchmarks/`, `benches/`) **or** its name follows
  the harness convention (`bench_*.py`, or `bench.<ext>` for native), **and**
- its path is **not** under `scripts/` or `tests/` (tooling and tests are never the surface).

`has_deterministic_perf_surface = bool(ordered_benchmarks)` is unchanged; only what qualifies as a
benchmark file changes. A graduated harness at `benchmarks/<name>/bench_<name>.py` still qualifies
(path component + harness name); `scripts/graduate_benchmark.py` and `tests/test_graduate_benchmark.py`
no longer do. Effect: repo-B's performance lane resolves to `synthesizable`.

### Fix 2 — G2: scope the diagnosis wave by default
**Files:** `scripts/run_diagnosis_wave.py`; SKILL.md / `references/pipeline.md` (command examples).

When no explicit `--source-prefix` is given, the wave excludes `tests/` and `**/fixtures/` by
default and scopes to the repo's code roots. Leaves that support `--exclude-prefix` receive the
exclusions; leaves that support only `--source-prefix` are scoped to the deterministically-computed
code roots (top-level entries containing Python, minus `tests`, fixtures, `docs`, and common vendor
dirs). An explicit `--source-prefix` overrides the default entirely. The documented wave command is
updated to reflect scoping so the default path is honest. Fixtures are intentionally dirty by
design and must always be excluded.

### Fix 3 — G3: generic accepted-residuals suppression
**Files:** `scripts/run_diagnosis_wave.py`; a small helper in `scripts/_wave_findings.py`.

Add an optional `--baseline <file>` honored for **any** target. The file is a JSON array of
finding identities using the existing `wave_baseline.json` schema:
`{"leaf", "path", "symbol", "metric"}`. After lanes merge, each finding whose identity matches a
baseline entry is marked `"suppressed": true`; suppressed findings are written to
`wave_findings.suppressed.json` (retained for audit) and excluded from the active
`wave_findings.json`. With no `--baseline`, behavior is unchanged. The mechanism is target-agnostic
— it has no knowledge of repo-B; repo-B's dogfood simply passes its own `wave_baseline.json`.

Finding identity is the 4-tuple `(leaf, path, symbol, metric)`. Note the key mismatch between the
two shapes: a baseline entry uses key `metric`, while a merged finding carries the attribute
`metric_name`; matching compares `baseline.metric == finding.metric_name` (the other three keys are
identical on both sides). Matching is exact on all four. A baseline entry that matches nothing is
reported in `wave_summary.json` as a stale-baseline warning (so a baseline cannot silently rot).

### Fix 4 — G4: process skills are always-available
**Files:** `scripts/_skill_probe.py` (`_skill_entry`); `scripts/skill_bootstrap_manifest.json`.

Add a declarative `"always_available": true` flag to the manifest entries for
`verification-before-completion`, `dispatching-parallel-agents`, and `subagent-driven-development`.
In `_skill_entry`, before the usable/advisory/installable cascade, a config with
`always_available` resolves to `state: "usable_now"` with `root_kind: "harness"` and no filesystem
probe. Effect: the orchestration lane resolves to `full`. The flag is opt-in per skill, so no other
lane's resolution changes.

### Fix 5 — MPRR self-guard (defense-in-depth)
**File:** `scripts/mprr_integrate.py` (the integrate/scope-check path).

At integrate, resolve the target repo root (`--repo`) and the engine's own repo root (the git
toplevel of the running `mprr_*.py` module). If they resolve to the **same** repo **and** any
declared diff-file is an engine-owned module under `scripts/`, refuse to auto-merge: the packet is
marked blocked with reason `"self-engine modification requires human review"`, and locks are
released as usual. This protects the in-place topology and the "gater rewrites itself" case while
leaving normal (installed-copy-audits-project) runs unaffected.

### Fix 6 — self-dogfood regression test
**Files:** `tests/test_self_dogfood.py`; targeted unit tests alongside the changed modules.

A fast, hermetic test asserting at the profile / lane-resolution layer (no heavy leaf execution):
on repo-B's own root, `has_deterministic_perf_surface is False`, the performance lane resolves to
`synthesizable`, the orchestration lane is not `manual`, and the wave command builder excludes
`tests/` and `**/fixtures/`. Targeted unit tests cover `_benchmark_surface` (harness vs tooling vs
test names), the suppression filter (match / no-match / stale-baseline warning), the
`always_available` probe path, and the MPRR self-guard (same-repo + engine file → blocked;
different repo → allowed).

---

## Data contracts

- **Benchmark file (G1):** qualifies iff `(under benchmarks/|benches/ OR name matches bench_*.py /
  bench.<ext>) AND not under scripts/|tests/`.
- **Suppression baseline (G3):** JSON array of `{"leaf": str, "path": str, "symbol": str,
  "metric": str}`; matched exactly against each finding via
  `(leaf, path, symbol, baseline.metric == finding.metric_name)`.
- **Manifest skill flag (G4):** optional boolean `"always_available"` on a skill entry; when true,
  the probe yields `state: "usable_now"`, `root_kind: "harness"`.
- **MPRR self-guard (Fix 5):** trigger iff `resolve(target_repo) == resolve(engine_repo)` AND
  `diff_files ∩ engine_scripts ≠ ∅`; result = packet blocked, reason string, locks released.

## Error handling

- A malformed or unreadable `--baseline` file is a hard error (non-zero exit, clear message), never
  a silent "no suppression" — consistent with the family's tool-error discipline.
- G1/G2/G4 are pure/deterministic and add no new failure modes; existing exits are preserved.
- The MPRR self-guard fails *closed* (refuse to merge) when repo-root resolution is ambiguous.

## Testing

Per-fix unit tests (above) plus the end-to-end self-dogfood smoke test. The existing tests that
these changes touch are updated in the same task as the change: `test_check_skill_requirements.py`
(perf lane now `synthesizable`, orchestration now non-manual), `test_lane_resolve.py` (unaffected —
the lane logic is unchanged; only the profile input differs), and `test_run_diagnosis_wave.py`
(default scoping + suppression). No golden is regenerated to hide a regression; if an existing test
asserts the old false-positive behavior, it is updated as an intended behavior change with a note.

## Sequencing

`G1 → G4 → MPRR-guard` are mutually independent. `G2 → G3` is ordered (both touch the wave runner;
suppression layers on top of scoped findings). The self-dogfood test depends on G1 + G2 + G4 and
lands after them. Docs + CHANGELOG + version bump (repo-B `0.6.0 → 0.7.0`, kept in sync with
`check_release.py`) close the work.

## Open questions (resolved as defaults)

1. **G3 depth** — generic suppression input (chosen), not orchestrator auto-detection of the
   target's baseline (avoids coupling to repo-B's file shapes).
2. **MPRR scope** — lightweight self-guard (chosen), not warn-only or out-of-scope.
3. **G4 approach** — treat process skills as always-available via a manifest flag (chosen), not
   extending the probe to plugin directories.
4. **Regression coverage** — an end-to-end self-dogfood smoke test (chosen), not unit-only.
