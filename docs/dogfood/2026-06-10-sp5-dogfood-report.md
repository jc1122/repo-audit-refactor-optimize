# SP5 Dogfood Report — Rewired Deterministic Lanes (2026-06-10)

Evidence that the rewired `repo-audit-refactor-optimize` orchestrator drives the
first-party deterministic repo-audit-skills v0.3.0 family end-to-end. All gates
below were **re-run and read by the orchestrator** (a worker's "green" is not
evidence). Commands are pinned; outputs are real.

Environment: `SKILLS=/home/jakub/.claude/skills`; repo-audit-skills v0.3.0 installed
there; both target repos clean at audit time.

---

## 1. Bootstrap lane states — T6 (both target repos)

Working-tree checker (`scripts/check_skill_requirements.py`) over the rewired
manifest. Both repos resolve the three deterministic lanes to `full` with
first-party skills only.

| Lane | `repo-audit-skills` | `repo-audit-refactor-optimize` | Type |
|---|---|---|---|
| `test-python` | **full** `[test-audit-pipeline]` | **full** `[test-audit-pipeline]` | HARD |
| `code-health-python` | **full** `[code-health-audit-pipeline]` | **full** `[code-health-audit-pipeline]` | HARD |
| `coverage-python` | **full** `[coverage-gap-audit]` | **full** `[coverage-gap-audit]` | HARD |
| `performance` | **manual** + "No benchmark surface detected; performance work remains manual." | same | HARD |
| `bootstrap` | degraded (find-skills/skill-installer not mirrored to `~/.claude/skills`) | same | record-only |
| `orchestration` | manual (verification-before-completion not mirrored) | same | record-only |
| `summary.stop_before_discovery` | **false** | **false** | HARD |

All HARD assertions passed on both repos. Reports saved at
`/tmp/sp5-selfcheck/{repo-audit-skills,repo-audit-refactor-optimize}/bootstrap/bootstrap_report.json`.

> **Note (T6 Step 2 divergence, resolved):** this repo runs pytest (53 tests) but
> lacked a config marker the profiler recognizes (`pytest.ini` / `pyproject.toml`),
> so `test-python`/`coverage-python` initially stayed inactive and the blocking
> `performance` lane reported `blocked` (`stop_before_discovery=true`). Fixed by
> adding a minimal `pytest.ini` (`[pytest]` + `testpaths=tests`), a no-op for the
> pinned gate command `python3 -m pytest tests/ -q`. After the marker, both repos'
> lane states match (table above). Committed as `chore: add pytest.ini marker …`.

Commands:
```bash
python3 scripts/check_skill_requirements.py --repo /home/jakub/projects/repo-audit-skills            --out-dir /tmp/sp5-selfcheck/repo-audit-skills
python3 scripts/check_skill_requirements.py --repo /home/jakub/projects/repo-audit-refactor-optimize --out-dir /tmp/sp5-selfcheck/repo-audit-refactor-optimize
```

---

## 2. T7a — Code-health umbrella determinism (double-run)

Target `repo-audit-skills`, canonical production scope (mirrors
`self_audit.py::_prefixes()`: `shared`, `scripts`, each `skills/<name>/scripts`).
Ran the umbrella twice and diffed the summary (minus `meta`).

**Result:** `deterministic: OK, 78 findings` — both summaries byte-identical
(60046 bytes each). Signal breakdown: **DECOMPOSE 48, SIMPLIFY 30**; severity:
high 11 / medium 49 / low 18. Umbrella `exit_code: 2` = advisory
findings-above-threshold (expected; not a crash). Leaf set (no coverage artifact):
`[complexity, dead-code, duplication, quality, structure]`.

---

## 3. T7b — Coverage artifact handoff into BOTH consumers

Collected `coverage.json` from the test lane, then fed it to the coverage leaf
**and** the umbrella.

- **Consumer 1 — `coverage-gap-audit`** (standalone): emitted **2 TEST findings**
  (both `severity: high`, `file_coverage_percent` 0.0% < 50.0% threshold):
  - `scripts/check_self_audit.py` — `0/19 statements executed`
  - `scripts/self_audit.py`
- **Consumer 2 — `code-health-audit-pipeline --coverage-json`**: the
  **artifact-gated `coverage-gap` leaf was ACTIVE** (not skipped):
  - umbrella leaf set **with** coverage: `[complexity, coverage-gap, dead-code, duplication, quality, structure]`
  - umbrella leaf set **without** coverage (T7a): `[complexity, dead-code, duplication, quality, structure]`
  - → the `coverage-gap` leaf appears **only** when `--coverage-json` is supplied — proof of artifact-gated activation.
  - per-leaf record: `coverage-gap → status: findings, count: 2`. Supervisor verdict: `GATE`.

Assertion `"coverage-gap" in umbrella summary` → **OK**.

---

## 4. T7c — Test-audit pipeline (self, this repo)

Pipeline over `repo-audit-refactor-optimize` / `tests/test_check_skill_requirements.py`.

**Result:** pipeline completed; `pipeline_summary.json` carries the supervisor
decision; **exit code 1** (advisory; ≠ 2, so not a STOP). Stage status:
`{coverage: failed, tqa: ok, triage: ok}`.

- **Triage** (`total_candidates: 53`): `MERGE_RECOMMENDED: 51`, `KEEP_FOR_SIGNAL: 2`.
- **TQA rubric** (static): Contract Coverage 1/3, Coverage/Mutation 1/3 (no
  coverage data), Determinism 2/3, Non-Functional 0/3, Pyramid 0/3, White-Box 1/3.
- **Honest caveat:** the pipeline's internal coverage substage failed with
  `unrecognized arguments: -n` — its command uses `-n 0` (pytest-xdist) and
  **xdist is not installed in the system `python3`**. This is an environment
  tooling gap in the pipeline's coverage path, unrelated to the rewire; the
  pipeline degraded gracefully (tqa + triage produced decisions, exit 1).

---

## 5. T7d — Coverage-gated top-10 backlog (orchestrator synthesis)

`references/prioritization.md` applied to merged T7a+T7b findings, using the T7b
coverage-gap TEST findings as the gate. **TEST-flagged files** (never auto-executed):
`scripts/check_self_audit.py`, `scripts/self_audit.py`.

| # | File | Signal | Sev | Coverage gate | Action |
|---|---|---|---|---|---|
| 1 | `scripts/check_coverage_gap.py` | SIMPLIFY | med | covered, no TEST finding | **ACTIONABLE** (SIMPLIFY proc) |
| 2 | `scripts/check_release.py` | SIMPLIFY | med | covered, no TEST finding | **ACTIONABLE** |
| 3 | `scripts/check_vendored_common.py` | SIMPLIFY | low | covered, no TEST finding | **ACTIONABLE** |
| 4 | `scripts/self_audit.py` | TEST | high | 0% coverage | **TEST-DEBT** — add behavior tests |
| 5 | `scripts/check_self_audit.py` | TEST | high | 0% coverage | **TEST-DEBT** — add behavior tests |
| 6 | `scripts/self_audit.py` | SIMPLIFY | low | **in TEST-flagged file** | **CHARACTERIZE-FIRST** (demoted) |
| 7 | `skills/test-redundancy-triage/scripts/triage_redundancy.py` | DECOMPOSE | high | coverage unmeasured (T7a scope) | characterize-first (conservative) |
| 8 | `skills/test-audit-pipeline/scripts/audit_pipeline.py` | DECOMPOSE | high | coverage unmeasured | characterize-first |
| 9 | `skills/test-quality-assurance/scripts/audit_test_quality.py` | DECOMPOSE | high | coverage unmeasured | characterize-first |
| 10 | `skills/code-health-audit-pipeline/scripts/code_health_pipeline.py` | DECOMPOSE | med | coverage unmeasured | characterize-first |

**Mechanical proof of the gate:** rows 1–3 and row 6 are all `SIMPLIFY`. Rows 1–3
stay **ACTIONABLE** (their files are covered and carry no TEST finding); row 6 is
**demoted to characterize-first** solely because `self_audit.py` carries a TEST
finding. The coverage gate is therefore mechanically applicable, exactly as
`references/prioritization.md` specifies.

---

## 6. Exact commands

T7a, T7b, T7c command blocks are the plan's pinned blocks (Task 7), run verbatim:
- T7a: `code_health_pipeline.py --root <repo-audit-skills> <canonical prefixes> --out-dir …run1/…run2` + summary diff.
- T7b: `.venv/bin/python -m pytest … --cov-report=json:…/coverage.json` → `coverage_gap_audit.py --coverage-json …` + `code_health_pipeline.py --coverage-json …`.
- T7c: `audit_pipeline.py --root <this repo> --python python3 --suite tests/test_check_skill_requirements.py --source-prefix scripts/ --out-dir …`.

Out-dirs (disjoint): `/tmp/sp5-dogfood/{code-health-run1,code-health-run2,coverage.json,coverage-gap,code-health-cov,test-audit}`.

---

## 7. Phase 2 — Self-build / self-audit loop (round table)

The rewired skill audits and remediates ITS OWN repo
(`repo-audit-refactor-optimize`) with `code-health-audit-pipeline` + coverage
handoff, coverage-gated per `references/prioritization.md`, remediated in
single-signal batches per `references/remediation-playbook.md`. Findings may only
SHRINK. Max 4 rounds.

| Round | Findings before → after | Batches accepted / discarded | Freezes (justified) |
|---|---|---|---|
| _(populated during Phase 2 below)_ | | | |
