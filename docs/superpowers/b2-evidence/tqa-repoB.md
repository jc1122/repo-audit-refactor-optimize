# Test Quality Inventory

## Config
- Root: /home/jakub/projects/repo-audit-refactor-optimize
- Test dirs: tests
- Test globs: test_*.py, *_test.py
- Internal import patterns: 2
- Public call hints: 0
- Auto-inferred public hints: False
- Exact-eq assert pattern: `^\s*assert\s+\w+\s*==\s*(?:expected|want|target|snapshot|golden)\b`

## Totals
- Files: 34
- Test functions: 305
- Private method calls: 68
- Public call hints: 0
- Internal implementation imports: 0
- `pytest.raises` calls: 26
- `pytest.raises(..., match=...)`: 8
- Broad exception tuples: 0
- `@given` calls (Hypothesis signal): 2
- `expected = (...)` literals: 0
- Exact expected-equality asserts: 0

## Ratios
- Private/Public call ratio: N/A (no public hints)
- Raises with match ratio: 0.308
- Broad tuple raises ratio: 0.0

## Classification Counts
- White-box candidates: 12
- Black-box candidates: 0
- Change-indicator candidates: 0

## Marker Breakdown
- No custom markers detected.
- Structural (filtered from signal): `skipif` (1)

## Flags
- Public call hints list is empty; black-box classification is disabled for this run.
- Low exception precision signal (fewer than half of raises use message matching).

## Rubric Scores

| Dimension | Score | Max | Rationale |
|-----------|-------|-----|-----------|
| Contract Coverage | 1 | 3 | Tests exist but no public call hints |
| Behavior-First Focus | 0 | 3 | Very high private/public ratio (68.0) |
| White-Box Justification | 1 | 3 | White-box tests present but high internal coupling |
| Determinism/Isolation | 3 | 3 | Hypothesis property tests detected (seed discipline) |
| Assertion Quality | 1 | 3 | Raises present but low match ratio (0.308) |
| Pyramid/Scope | 2 | 3 | 34 files (layering signal) |
| Coverage/Mutation | 1 | 3 | Statement 80.7% < 85% |
| Non-Functional | 1 | 3 | No benchmark markers detected |
| **Total** | **10** | **24** | |
