# Acceptance policy — `.repo-audit/accept.json`

Drop this file in an audited repo's root to mark findings acceptable. The audit **leaves
still detect everything**; acceptance is applied at the wave (reporting) and the MPRR
engine (remediation). Accepted findings are recorded with their reason in a sidecar —
never silently dropped. A malformed file is a hard error.

## Schema (version 1)

`{"version": 1, "accept": [ <entry>, ... ]}`. Each entry:

- `match.kind` — `finding` | `path` | `rule`
  - `finding`: requires `leaf`, `path`, `symbol`, `metric` (exact identity).
  - `path`: requires `glob` (repo-relative; no `..` or leading `/`). Matches a finding's
    `path` or any of its `files`. **Note:** `glob` uses `fnmatch` semantics where `*` also
    matches `/`, so prefer the `**/dir/**` idiom for directory subtrees.
  - `rule`: requires `leaf` and/or `metric` (subset; both → AND).
- `reason` — required, non-empty.
- `applies` — subset of `["report","remediation"]`; default both. `report` = not flagged
  by the wave/gate; `remediation` = never auto-fixed by the MPRR engine.
- `expires` — optional ISO date (`YYYY-MM-DD`) or version token. A past ISO date still
  applies but is flagged `expired` for re-triage; non-date tokens are informational.

## Example

(See the three-entry example in the design spec.)

## Validate

`python3 scripts/validate_accept.py --file <repo>/.repo-audit/accept.json` → `{"status":"pass"}` or
a `fail` verdict with defects. Auto-discovered by `run_diagnosis_wave.py` (also `--accept <file>`)
and by `mprr_run.py plan --repo <repo>`; `--baseline` rows are honored as report-stage `finding`
entries. `scripts/remediation_excludes.json` is honored as a back-compat remediation fallback.
