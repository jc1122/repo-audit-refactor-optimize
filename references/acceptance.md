# Acceptance policy — `.repo-audit/accept.json`

Drop this file in an audited repo's root to mark findings acceptable. The checks
**still detect everything**; acceptance is applied at the reporting stage by the
`repo-audit` CLI. Accepted findings are recorded with their reason in the run
record — never silently dropped. A malformed file is a hard error.

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
  in the run report; `remediation` = excluded from fix batches.
- `expires` — optional ISO date (`YYYY-MM-DD`) or version token. A past ISO date still
  applies but is flagged `expired` for re-triage; non-date tokens are informational.
- `max_value` — optional numeric ceiling. A finding whose value exceeds it stops being
  accepted and is reported again.

## Example

```json
{
  "version": 1,
  "accept": [
    {
      "match": {"kind": "finding", "leaf": "complexity", "path": "src/legacy.py",
                "symbol": "parse", "metric": "cyclomatic"},
      "reason": "Legacy parser, scheduled rewrite in Q4.",
      "applies": ["report", "remediation"],
      "expires": "2026-12-31"
    }
  ]
}
```

## Validate

The `repo-audit` CLI validates the file fail-closed on every scan: a malformed
policy is an error (exit 2), never silent. To check a policy without a full
scan, run any scan with `--strict` against the target repo — stale, expired,
and ceiling-exceeded entries become explicit errors. The CLI discovers
`<repo>/.repo-audit/accept.json` automatically (`--accept <file>` overrides);
stale entries — accepted identities the checks no longer produce — are
reported, never silently kept.
