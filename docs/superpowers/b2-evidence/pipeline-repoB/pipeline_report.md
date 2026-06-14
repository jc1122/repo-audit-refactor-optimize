# Test Audit Pipeline Report

**Generated**: 2026-06-14 23:24:52 UTC
**Root**: `/home/jakub/projects/repo-audit-refactor-optimize`
**Stages run**: coverage, tqa, triage, report

## Parallelism Opportunities

Stages run in parallel: **TQA audit, Redundancy triage**

For agent orchestrators with subagent capabilities:
- Stage 2a (TQA) can be delegated to a `test-quality-assurance` subagent
- Stage 2b (Triage) can be delegated to a `test-redundancy-triage` subagent
- Both subagents can run concurrently after coverage collection completes

## TQA Quality Scores

| Dimension | Score |
|-----------|-------|
| Assertion Quality | {'max': 3, 'rationale': 'Raises present but low match ratio (0.308)', 'score': 1} |
| Behavior-First Focus | {'max': 3, 'rationale': 'Very high private/public ratio (68.0)', 'score': 0} |
| Contract Coverage | {'max': 3, 'rationale': 'Tests exist but no public call hints', 'score': 1} |
| Coverage/Mutation | {'max': 3, 'rationale': 'unknown (no coverage data provided)', 'score': 1} |
| Determinism/Isolation | {'max': 3, 'rationale': 'Hypothesis property tests detected (seed discipline)', 'score': 3} |
| Non-Functional | {'max': 3, 'rationale': 'No benchmark markers detected', 'score': 1} |
| Pyramid/Scope | {'max': 3, 'rationale': '34 files (layering signal)', 'score': 2} |
| White-Box Justification | {'max': 3, 'rationale': 'White-box tests present but high internal coupling', 'score': 1} |
| max_total | 24 |
| total | 10 |

## Coverage Summary

*Coverage collection failed.*

## Redundancy Triage Decisions

| Decision | Count |
|----------|-------|
| MERGE_RECOMMENDED | 17 |

### Actionable Candidates

- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``
- **MERGE_RECOMMENDED**: ``

## Action Items

1. Review and consolidate 17 merge-candidate test(s)

## Stage Status

| Stage | Status |
|-------|--------|
| Coverage | ✗ FAILED |
| TQA Audit | ✓ OK |
| Triage | ✓ OK |
