# Test Quality Inventory

## Config
- Root: /home/jakub/projects/perf-benchmark-skill
- Test dirs: tests, perf-optimization/tests
- Test globs: test_*.py, *_test.py
- Internal import patterns: 2
- Public call hints: 0
- Auto-inferred public hints: False
- Exact-eq assert pattern: `^\s*assert\s+\w+\s*==\s*(?:expected|want|target|snapshot|golden)\b`

## Totals
- Files: 11
- Test functions: 170
- Private method calls: 16
- Public call hints: 0
- Internal implementation imports: 0
- `pytest.raises` calls: 2
- `pytest.raises(..., match=...)`: 0
- Broad exception tuples: 0
- `@given` calls (Hypothesis signal): 0
- `expected = (...)` literals: 0
- Exact expected-equality asserts: 0

## Ratios
- Private/Public call ratio: N/A (no public hints)
- Raises with match ratio: 0.0
- Broad tuple raises ratio: 0.0

## Classification Counts
- White-box candidates: 3
- Black-box candidates: 0
- Change-indicator candidates: 0

## Marker Breakdown
- `benchmark`: 1
- Structural (filtered from signal): `parametrize` (1)

## Flags
- Public call hints list is empty; black-box classification is disabled for this run.
- Low exception precision signal (fewer than half of raises use message matching).

## Rubric Scores

| Dimension | Score | Max | Rationale |
|-----------|-------|-----|-----------|
| Contract Coverage | 1 | 3 | Tests exist but no public call hints |
| Behavior-First Focus | 0 | 3 | Very high private/public ratio (16.0) |
| White-Box Justification | 1 | 3 | White-box tests present but high internal coupling |
| Determinism/Isolation | 2 | 3 | Default (static analysis cannot fully assess) |
| Assertion Quality | 1 | 3 | Raises present but low match ratio (0.0) |
| Pyramid/Scope | 2 | 3 | 11 files (layering signal) |
| Coverage/Mutation | 2 | 3 | Statement 88.5% >= 85% (branch 72.1% < 75%) |
| Non-Functional | 2 | 3 | 1 benchmark markers detected |
| **Total** | **11** | **24** | |
