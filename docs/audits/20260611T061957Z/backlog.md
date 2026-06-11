# SP8 Track H — Diagnosis Backlog (repo-audit-refactor-optimize)

- Run: `docs/audits/20260611T061957Z`
- HEAD at diagnosis: `a9b3ea7` (H0 commit; baseline repo state `cbf12ab` v0.3.1)
- Suite at diagnosis: `python3 -m pytest tests/ -q` → **79 passed**
- Orchestrator skill version: 0.3.1
- Triage authority: this skill's `references/prioritization.md` (playbook) + the SP8 plan Track H mandate
  ("mechanical lint-class fixes ONLY; structural findings → backlog ONLY, NO gate extension in repo-B this round").

## Lane results (H1)

| Lane | Tool | Findings | Exit | Notes |
|---|---|---|---|---|
| coverage-gap | coverage_gap_audit.py (scripts; coverage.json 92.8%) | **0** | 0 | No untested production file → nothing is coverage-gated. |
| code-health (umbrella) | code_health_pipeline.py (scripts) | **10** | 2 | supervisor=GATE; test-effectiveness skipped (requires mutation_scope artifact). |
| security | security_audit.py (scripts) | **0** | 0 | bandit clean. |
| hygiene | repo_hygiene_audit.py (full repo) | **0** | 0 | `"git": true`; no tracked-tree / release-hygiene defects. |
| docs-consistency | docs_consistency_audit.py (README,SKILL,CHANGELOG,references,docs,agents,scripts) | **17** | 1 | all `doc_path_missing`; see triage below. |
| dependency | dependency_audit.py (scripts) | **0** | 0 | `manifest:false` — no pyproject/requirements; correct empty result, not a defect. |
| hotspot | hotspot_audit.py (`--rev a9b3ea7 --max-commits 500`) | **9** | 1 | churn / temporal-coupling / author-concentration. |

Manual lanes (honest notes):
- **performance** — `manual`. No benchmark surface in repo-B (bootstrap warning: "No benchmark surface detected"). No perf work this round.
- **orchestration** — `manual`. Self-referential (this repo *is* the orchestrator skill); verification-before-completion not mirrored as an installed skill. No lane artifact beyond this audit run itself.

## Coverage-gate status (prioritization.md §"Coverage-Gated Actionability")

coverage-gap emitted **0 TEST findings** → no production file is untested at the file granularity.
Therefore **no finding is demoted to characterize-first**: covered findings keep their computed rank.
(`scripts/check_skill_requirements.py` has 19 uncovered lines but no file-level TEST finding; the
complexity findings on it are in a covered file and rank normally — they are deferred for being
*structural*, not for being coverage-gated.)

---

## ACCEPTED-MECHANICAL (1) — applied in H2

| # | Finding | Path | Playbook rule | Action |
|---|---|---|---|---|
| A1 | quality LINT `E501` (116 chars) | `scripts/check_skill_requirements.py:562` | §"Safe Cleanup" — `LINT` signal, "execute automatically if verification is straightforward" | Wrap the over-long f-string via implicit string concatenation (behavior-identical). It is the **lone** >88-char line in the entire production scope (de-facto convention is ≤88), so the wrap aligns with the file's own style. Keeps 79 green. |

## DEFERRED-STRUCTURAL → SP9 (16) — backlog only, NOT executed this round

Plan mandate: "structural findings → backlog ONLY, NO gate extension in repo-B this round." All sit in
covered code, so they are *deferrable-by-policy*, not coverage-gated. prioritization.md §"Structural
Refactor" / §"When to Defer".

Complexity (7), all in `scripts/check_skill_requirements.py`:

| # | Signal | Symbol | Metric | Playbook rule |
|---|---|---|---|---|
| D1 | SIMPLIFY | `<module>` | maintainability_index 50.3 < 65 | §"Structural Refactor" (SIMPLIFY) — batch carefully, verify each step |
| D2 | SIMPLIFY | `<module>` | maintainability_index 2.3 < 65 | §"Structural Refactor" (SIMPLIFY) |
| D3 | SIMPLIFY | `load_source_overrides` | parameter_count 6 > 5 | §"Structural Refactor" (SIMPLIFY) |
| D4 | DECOMPOSE | `_skill_entry` | cyclomatic_complexity 12 > 10 | §"Structural Refactor" (DECOMPOSE) |
| D5 | DECOMPOSE | `_skill_entry` | function_nloc 65 > 50 | §"Structural Refactor" (DECOMPOSE) |
| D6 | DECOMPOSE | `build_bootstrap_report` | function_nloc 79 > 50 | §"Structural Refactor" (DECOMPOSE) |
| D7 | SIMPLIFY | `build_bootstrap_report` | parameter_count 9 > 5 | §"Structural Refactor" (SIMPLIFY) |

Hotspot (9) — prioritization input, not a gate (SP8 plan "Out of scope: check:hotspot"). Informational:

| # | Signal | Locus | Metric | Note |
|---|---|---|---|---|
| D8 | DECOMPOSE | `scripts/check_skill_requirements.py` | churn_complexity_product 18837 | The active large module — same locus as D1–D7; SP9 decompose target. |
| D9 | DECOMPOSE | `tests/test_check_skill_requirements.py` | churn_complexity_product 23970 | Test file growth tracks the module; not product code. |
| D10 | DECOMPOSE | `scripts/skill_bootstrap_manifest.json` | churn_complexity_product 1250 | Data manifest; churn reflects feature growth. |
| D11 | DECOMPOSE | `SKILL.md` | churn_complexity_product 1150 | Docs churn; not a code defect. |
| D12 | RESTRUCTURE | `check_skill_requirements.py` | author_concentration 1.0 | Solo-author repo — inherent, not actionable. |
| D13 | RESTRUCTURE | `test_check_skill_requirements.py` | author_concentration 1.0 | Solo-author — inherent. |
| D14 | RESTRUCTURE | `SKILL.md` | author_concentration 1.0 | Solo-author — inherent. |
| D15 | RESTRUCTURE | `check_skill_requirements.py ↔ test_…` | temporal_coupling 0.88 | Code+test co-evolve — expected/healthy coupling. |
| D16 | RESTRUCTURE | `skill_bootstrap_manifest.json ↔ test_…` | temporal_coupling 1.0 | Manifest+test co-evolve — expected. |

## WON'T-FIX / FALSE-POSITIVE / ILLUSTRATIVE (19) — not actionable, not deferred-for-later

These are not SP9 work items; they are advisory false positives or correct-as-is documentation.

| # | Finding | Locus | Why not a defect |
|---|---|---|---|
| W1 | dead-code DELETE `_extract_skill_name` (vulture conf 60 == floor) | `scripts/check_skill_requirements.py:418` | **False positive.** Directly tested by `test_extract_skill_name_missing_name` and `test_extract_skill_name_unreadable_file` (call `checker._extract_skill_name(...)`). Deleting breaks 2 tests → not 79 green. prioritization.md §"Safe Cleanup" requires *high-confidence* DELETE; 60% is the floor. |
| W2 | quality FORMAT `format_drift` | `scripts/check_skill_requirements.py` | repo-B declares **no** ruff/format standard (no pyproject/ruff.toml; only `.ruff_cache`). `ruff` is not installed on this interpreter, so the fix is not reproducible here, and a wholesale reformat of a file the repo never ruff-formatted is not a safe single-signal mechanical fix. prioritization.md §"When to Defer" (best subskill support missing / not straightforward). |
| W3–W5 | docs `doc_path_missing` ×3 | `SKILL.md:50,51,52` → `bootstrap/bootstrap_report.json`, `bootstrap/bootstrap_report.md`, `bootstrap/install_plan.md` | These are **runtime output-artifact paths** the checker writes under `--out-dir`, correctly documented as outputs. They are not repo files; the leaf cannot distinguish output-path refs from repo-file refs (known leaf limitation). Rewriting would degrade the docs. |
| W6–W18 | docs `doc_path_missing` ×13 | `docs/dogfood/2026-06-10-sp5-dogfood-report.md:69,70,105×2,109,111,112,113,114,115,116,117,118` | **Immutable historical record.** A point-in-time dogfood report whose paths (`scripts/self_audit.py`, `skills/*/scripts/*.py`, …) correctly describe **repo-A** (repo-audit-skills) at that run. They are not repo-B files; "fixing" them falsifies history. Same rationale as repo-A's C-4 excluding `docs/audits/**` from the docs gate. |
| W19 | docs `doc_path_missing` ×1 | `docs/plans/2026-06-10-sp5-deterministic-skillset-rewire.md:782` → `bootstrap/bootstrap_report.json` | **Immutable historical record** (a plan's expected-output assertion). Same rationale as W3–W18. |

Scope note: the broad `--source-prefix docs` swept in `docs/dogfood/**` and `docs/plans/**` (immutable
records). A future repo-B docs gate (out of scope this round) would adopt a repo-A-style living-docs
scope that omits them; that is a documentation observation, not a remediation item.

---

## Summary counts

- accepted-mechanical: **1** (A1)
- deferred-structural-SP9: **16** (D1–D16)
- won't-fix / false-positive / illustrative: **19** (W1–W19)
- coverage-gated: **0**
- total diagnosis findings: **36** (code-health 10 + docs 17 + hotspot 9; coverage-gap/security/hygiene/dependency = 0)

For the run-report 3-bucket schema (`{accepted, deferred, coverage_gated}`): accepted=1,
deferred=35 (16 structural + 19 won't-fix, i.e. everything not executed this round), coverage_gated=0.
