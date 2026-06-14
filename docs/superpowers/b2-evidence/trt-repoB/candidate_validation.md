# Candidate Validation

Baseline suite pass: `True`

## Decision Counts

- `MERGE_RECOMMENDED`: 17

## Results

| test_nodeid | entrypoint | intent | decision | confidence_tier | strict | branch_exact | branch_jaccard | deselect_pass | reason |
|---|---|---|---|---|---|---:|---:|---:|---|
| tests/test_run_instruction_eval.py::test_advisory_outputs_empty_on_pass | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.64) |
| tests/test_run_instruction_eval.py::test_build_parser_parses_required_args_with_default_model | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | True | 1.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.29, name_sim=0.44) |
| tests/test_run_instruction_eval.py::test_drift_is_advisory_not_pass | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.48, name_sim=0.69) |
| tests/test_run_instruction_eval.py::test_load_expected_bad_dict_raises | tests/test_run_instruction_eval.py::<module> | error_semantics | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.81) |
| tests/test_run_instruction_eval.py::test_load_expected_bool_json_raises | tests/test_run_instruction_eval.py::<module> | error_semantics | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.2 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.64, name_sim=0.81) |
| tests/test_run_instruction_eval.py::test_load_expected_int_literal | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.33, name_sim=0.72) |
| tests/test_run_instruction_eval.py::test_load_expected_json_bare_int | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.4 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.64, name_sim=0.87) |
| tests/test_run_instruction_eval.py::test_load_expected_json_dict | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.87) |
| tests/test_run_instruction_eval.py::test_load_expected_missing_file_raises | tests/test_run_instruction_eval.py::<module> | error_semantics | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.50, name_sim=0.77) |
| tests/test_run_instruction_eval.py::test_load_model_findings_missing_raises | tests/test_run_instruction_eval.py::<module> | error_semantics | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.50, name_sim=0.82) |
| tests/test_run_instruction_eval.py::test_load_model_findings_non_array_raises | tests/test_run_instruction_eval.py::<module> | error_semantics | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.82) |
| tests/test_run_instruction_eval.py::test_load_model_findings_valid | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.333333 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.63) |
| tests/test_run_instruction_eval.py::test_main_drift_writes_advisory_finding | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.5 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.81, name_sim=0.69) |
| tests/test_run_instruction_eval.py::test_main_malformed_expected_returns_two | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.82, name_sim=0.79) |
| tests/test_run_instruction_eval.py::test_main_malformed_model_findings_returns_two | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.82, name_sim=0.77) |
| tests/test_run_instruction_eval.py::test_main_pass_writes_artifact_and_returns_zero | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.5 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.81, name_sim=0.56) |
| tests/test_run_instruction_eval.py::test_pass_when_actual_equals_expected | tests/test_run_instruction_eval.py::<module> | shape_dtype_contract | MERGE_RECOMMENDED | MERGE_CANDIDATE | disabled | False | 0.0 | True | deselect pass + overlap candidate (dominated=True, src_sim=0.67, name_sim=0.52) |
