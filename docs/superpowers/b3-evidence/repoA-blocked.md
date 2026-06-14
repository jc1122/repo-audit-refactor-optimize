# repo-A — mutation BLOCKED by the spec_from_file_location test convention

repo-A's leaf tests load modules via `helpers.load_module()` /
`importlib.util.spec_from_file_location` (**97 test files**). mutmut 3.x instruments source
through a runtime trampoline that `spec_from_file_location` bypasses, so it cannot correlate test
execution with mutants (and the file-loaded tests also fail collection in the sandbox). Representative
reproduction (coverage-gap-audit leaf):

```
{"status": "error", "message": "mutmut run failed (exit 1): \u2838 Running stats\n\u283c Running stats\n\n==================================== ERRORS ====================================\n_____________ ERROR collecting tests/test_coverage_gap_findings.py _____________\nImportError while importing test module '/tmp/b3/repoA/.mutmut-work/mutants/tests/test_coverage_gap_findings.py'.\nHint: make sure your test modules/packages have valid Python names.\nTraceback:\n/usr/lib/python3.14/importlib/__in
```

**Decision: ACCEPT** — the `helpers.load_module`/`spec_from_file_location` convention is a
deliberate design choice (leaves are testable without packaging/installation). Native mutation
testing of repo-A would require rewriting ~97 test files to normal package imports whose dotted path
matches mutmut's mutant key. Logged as a future candidate (its own brainstorm→plan→ship); NOT done
in B3.
