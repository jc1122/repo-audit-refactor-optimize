# Candidate Validation

Baseline suite pass: `True`

## Decision Counts

- `MERGE_RECOMMENDED`: 11

## Results

| test_nodeid | entrypoint | intent | decision | confidence_tier | strict | branch_exact | branch_jaccard | deselect_pass | reason |
|---|---|---|---|---|---|---:|---:|---:|---|
| skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::test_clean_exits_zero | skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.73, name_sim=0.83) |
| skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::test_gappy_exits_one_with_findings | skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.47, name_sim=0.52) |
| skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::test_help_exits_zero | skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.55, name_sim=0.83) |
| skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::test_missing_coverage_report_exits_two | skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.73, name_sim=0.70) |
| skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::test_missing_required_args_exits_two | skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.73, name_sim=0.70) |
| skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::test_output_is_byte_stable | skills/coverage-gap-audit/tests/test_coverage_gap_cli.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.29, name_sim=0.41) |
| skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::test_covered_file_is_not_flagged | skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.941176 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.62) |
| skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::test_fully_covered_tree_yields_no_findings | skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.764706 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.33, name_sim=0.62) |
| skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::test_multiple_reports_merge_by_union | skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.941176 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.43) |
| skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::test_partially_covered_file_is_medium_severity | skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.50, name_sim=0.60) |
| skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::test_untested_file_is_high_severity_zero_percent | skills/coverage-gap-audit/tests/test_coverage_gap_findings.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.50, name_sim=0.60) |
