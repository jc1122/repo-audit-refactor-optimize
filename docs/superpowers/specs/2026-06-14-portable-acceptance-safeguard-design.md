# Portable Acceptance Safeguard — Design

**Date:** 2026-06-14
**Status:** Design (approved → writing-plans)
**Scope:** a single portable, in-repo acceptance file (`.repo-audit/accept.json`) honored by the
repo-B orchestrator's diagnosis wave **and** its MPRR remediation engine, so any audited repo
(repo-A, repo-B, repo-P, or a foreign target) can mark a finding acceptable once and have it neither
re-flagged nor auto-fixed — while the leaves keep detecting it.

## Problem

The family already has acceptance machinery, but it is **fragmented across three shapes and two
layers**, and none of it travels with the audited repo:

- **Diagnosis suppression exists but is flat and opt-in by flag.** `run_diagnosis_wave.py --baseline
  <file>` suppresses findings by the exact identity `{leaf, path, symbol, metric}`
  (`_wave_findings.partition`/`identity`/`load_baseline`; suppressed rows → `wave_findings.suppressed.json`).
  It must be passed explicitly, it only matches whole-identity tuples (no path-glob, no rule-class),
  and it carries no reason or expiry.
- **Remediation exclusion exists but is not wired in.** `repo-audit-skills/scripts/remediation_excludes.json`
  is a path-glob policy ("never *fix* `**/tests/fixtures/**`") that an orchestrator must read and apply
  by hand; the MPRR engine's `mprr_normalize`/`mprr_partition` does **not** consume it (top SP15
  candidate). So "don't report" and "don't fix" are two unrelated mechanisms.
- **Each family repo keeps its own internal baseline schema.** repo-A `self_audit_baseline.json`
  (+ `self_audit_frozen.md`), repo-B/P `wave_baseline.json` (+ `wave_frozen.md`). Three filenames,
  two on-disk shapes, all repo-local.
- **No target-repo convention.** For an arbitrary future repo there is no "drop one file in the repo
  root and every stage honors it." The audited repo cannot carry its own acceptance policy.

The leaf skills are advisory and **detect everything by design** — this is correct and stays. The gap
is purely at the aggregation layers (wave/gate and engine): no single, portable, granular,
reason-bearing acceptance contract.

## Goals

1. One conventional file, `<repo>/.repo-audit/accept.json`, auto-discovered when the wave/engine runs
   on that repo (no flag required); an explicit `--accept <file>` may augment it.
2. Three match granularities per entry: `finding` (exact 4-tuple), `path` (glob), `rule` (leaf/metric
   class).
3. Each entry blocks **both** reporting and remediation by default (`applies: ["report","remediation"]`),
   narrowable to one.
4. Every accepted finding is **counted and recorded** with its reason in a sidecar — never silently
   dropped (preserves the family's C-1 "every suppression is counted" invariant).
5. Mandatory `reason`; optional `expires`; fail-closed on a malformed file; stale entries surfaced.
6. The MPRR engine self-filters accepted paths/findings, closing the `remediation_excludes`
   auto-consume gap; `remediation_excludes.json` is honored as a back-compat fallback.
7. The existing `--baseline` keeps working (its entries map to `finding`-kind acceptances).

### Non-goals (Phase 1)

- Migrating repo-A/B/P's **internal** residual baselines onto the new schema. That is Phase 2
  (mechanical, count-neutral, one commit per repo) and has its own plan.
- Changing any leaf audit skill in repo-A or the perf engine in repo-P. Phase 1 is entirely in the
  repo-B project; the portable file is honored on *targets* via the orchestrator's wave + engine.
- A GUI / interactive "accept this finding" flow. The file is authored by hand or by an orchestrator.

## Success criterion

A repo containing a valid `.repo-audit/accept.json` is audited by the repo-B wave **without** any
`--baseline`/`--accept` flag and: every matching finding (by `finding`, `path`, or `rule`) is absent
from `wave_findings.json`, present in `wave_findings.accepted.json` with its `reason`; a `path`/`finding`
entry with `applies` including `remediation` is never selected into an MPRR packet (recorded in the
engine's exclusion sidecar with its reason); a malformed accept file aborts with a clear non-zero
error; an entry matching nothing is reported as stale. The existing `--baseline` path still produces
identical suppression for finding-identity inputs.

---

## Phase 1 — the portable safeguard (repo-B project)

All changes are in `~/projects/repo-audit-refactor-optimize`. Gates stay `pytest tests/` +
`python3 scripts/check_release.py`.

### The schema (`schema/accept.schema.json`)

```json
{
  "version": 1,
  "accept": [
    {
      "match": {"kind": "finding", "leaf": "complexity", "path": "scripts/x.py",
                "symbol": "<module>", "metric": "maintainability_index"},
      "reason": "Single-file standalone tool; splitting breaks vendored install.",
      "applies": ["report", "remediation"],
      "expires": null
    },
    {"match": {"kind": "path", "glob": "**/tests/fixtures/**"},
     "reason": "Detection-coupled fixtures must stay dirty.", "applies": ["remediation"]},
    {"match": {"kind": "rule", "leaf": "hotspot", "metric": "churn_complexity_product"},
     "reason": "Release-churn docs; expected.", "applies": ["report"], "expires": "v0.9.0"}
  ]
}
```

- `match.kind` ∈ `finding | path | rule`.
  - `finding`: requires `leaf`, `path`, `symbol`, `metric` (exact identity — the existing 4-tuple).
  - `path`: requires `glob` (matched against the finding's `path` with `pathlib.PurePath.match`/`fnmatch`
    semantics; must be repo-relative — `..`/absolute rejected by the validator).
  - `rule`: requires at least one of `leaf`, `metric` (subset match; both → AND).
- `reason`: **required**, non-empty string.
- `applies`: optional array ⊆ `{"report","remediation"}`, default both.
- `expires`: optional `string|null` — an ISO date (`YYYY-MM-DD`) or a version/rev token. Past-expiry
  entries still apply for the run but are surfaced (see Error handling).

### Components (new + modified)

- **Create** `schema/accept.schema.json` — the single source of truth for the format.
- **Create** `scripts/_accept.py` — stdlib loader + validator + matcher. Public surface:
  - `load_accept(repo: Path, extra: Path | None) -> AcceptPolicy` — discovers `<repo>/.repo-audit/accept.json`,
    merges an optional `--accept` file, validates (raises on malformed), returns a policy object.
  - `policy.matches(finding, stage) -> (bool, entry|None)` — stage ∈ `"report"|"remediation"`; returns
    the first matching entry whose `applies` includes `stage`.
  - `policy.partition(findings, stage) -> (active, accepted, stale)` — accepted carry `{**finding,
    "accepted": True, "accept_reason": ..., "expired": bool}`; stale = entries that matched nothing.
  - `policy.from_baseline(rows)` — adapt a flat `--baseline` array into `finding`-kind entries (back-compat).
- **Create** `scripts/validate_accept.py` — fail-closed CLI validator (mirrors `validate_run_report.py`).
- **Modify** `scripts/_wave_findings.py` — keep `identity`/`load_baseline`/`partition` (used by
  `check_wave_baseline`); the wave's suppression now goes through `_accept.partition(..., "report")`,
  with `load_baseline` results adapted via `from_baseline`.
- **Modify** `scripts/run_diagnosis_wave.py` — auto-discover the in-repo file; add `--accept`; merge
  with `--baseline`; write `wave_findings.accepted.json` (`{accepted, stale}`) replacing/extending the
  current `wave_findings.suppressed.json` (kept as an alias key for back-compat).
- **Modify** `scripts/mprr_normalize.py` / `scripts/mprr_partition.py` — load the policy for the target
  repo and drop any finding whose identity/path matches a `remediation`-stage entry **before**
  packetizing; record dropped items + reasons in an engine sidecar (`mprr_excluded.json`). Honor
  `remediation_excludes.json` as a fallback (mapped to `path`+`applies:["remediation"]`) with a
  one-line deprecation note pointing at `.repo-audit/accept.json`.
- **Create** `references/acceptance.md` — authoring guide, semantics, examples, the report-vs-remediation
  distinction, the "leaves still detect everything" principle; one cross-link line added to `SKILL.md`.
- **Tests:** `tests/test_accept.py` (3 kinds; `applies` narrowing; expiry; path-safety; merge with
  `--baseline`; reason-required), `tests/test_validate_accept.py` (fail-closed cases), plus integration
  assertions in `tests/test_run_diagnosis_wave.py` (auto-discovery + accepted sidecar) and the MPRR
  tests (remediation exclusion + fallback).

### Data flow

1. **Wave**: `main` resolves the target repo → `_accept.load_accept(repo, args.accept)` → merge
   `from_baseline(load_baseline(args.baseline))` if `--baseline` given → after lanes merge,
   `policy.partition(findings, "report")` → active set to `wave_findings.json`, accepted+stale to
   `wave_findings.accepted.json`. `check_wave_baseline.py` is unchanged (still consumes the repo's own
   `wave_baseline.json` via the shared `identity`).
2. **Engine**: `mprr_normalize` loads the same policy for `--repo`, runs `policy.partition(findings,
   "remediation")`, packetizes only the active set, writes `mprr_excluded.json`.

### Error handling — fail-closed, loud

- Missing `.repo-audit/accept.json` **and** no `--accept` → empty policy (normal; not an error).
- Malformed JSON / schema-invalid / `reason` missing / unknown `kind` / `applies` value / path traversal
  → **hard stop** (non-zero exit, clear message). A broken safeguard must never silently accept nothing
  or everything.
- Entry matching zero findings → `stale` in the accepted sidecar; the wave summary flags it (parity with
  today's `stale_baseline`).
- `expires` in the past → entry still applies this run, marked `"expired": true` in the sidecar and
  surfaced in the summary so it gets re-triaged.

### Testing

Per-component unit tests above; integration tests assert auto-discovery (no flag), the accepted sidecar
contents (reason + expired flag), back-compat parity (`--baseline` produces the same active set as the
equivalent `finding` entries), and engine exclusion + `remediation_excludes` fallback. No golden is
regenerated to hide a regression.

### Sequencing

`schema + _accept + validate_accept` (foundation) → wave wiring → engine wiring → docs/CHANGELOG +
version bump. Each task ends green. Do not push/tag/merge (human-gated, mirrors prior features).

---

## Phase 2 — migrate the family's internal baselines (mechanical, later)

Separate plan. Express each repo's internal residual baseline as a `.repo-audit/accept.json` instance
and point that repo's own gate at the shared loader, **count-neutral**, one commit per repo, verified by
the existing equality gates.

- **repo-B / repo-P** (`wave_baseline.json` + `wave_frozen.md`): generate `.repo-audit/accept.json`
  from the baseline rows (`finding`-kind) with each `wave_frozen.md` justification becoming the `reason`;
  point `check_wave_baseline.py` at `_accept` (it already shares `identity`). The frozen ledger's
  `deferred-structural`/`won't-fix-FP` class becomes a `class` annotation on the entry; `expires`
  carries the ledger's expiry notes. Verify: the gate's pass/fail and counts are identical pre/post.
- **repo-A** (`self_audit_baseline.json` + `self_audit_frozen.md`, 40 rows): same translation; point
  `check_self_audit.py` at the shared loader (or a vendored-free adapter honoring the schema). Fold
  `remediation_excludes.json` into the same file under `path`+`applies:["remediation"]`. Verify the
  `npm run check` equality gate stays green and count-neutral.
- **Cross-repo:** `_accept.py` is authored in repo-B; repo-A/P consume the **schema** (the contract),
  each with a small local loader — honoring the no-cross-skill-import + standalone-vendored-leaf rule
  (Approach B). No shared code is vendored across repos.
- **Migration safety:** each repo migrates independently; a converter script emits the new file from the
  old baseline so the diff is mechanical and reviewable; the old baseline file is removed only after the
  gate proves equivalence in the same commit.

### Phase 2 success criterion

Each family repo's self-audit gate reads `.repo-audit/accept.json`, every prior residual is represented
with its original justification as `reason`, and the gate's verdict + counts are byte-for-byte
equivalent to pre-migration (proven by running the gate before and after in the migration commit).

---

## Open questions (resolved as decisions)

1. **Meaning of "acceptable"** — both report + remediation by default (chosen), narrowable via `applies`.
2. **Granularity** — `finding | path | rule`, all three selectable per entry (chosen).
3. **Location** — in the audited repo at `.repo-audit/accept.json`, auto-discovered (chosen), with an
   optional `--accept` augmentation.
4. **Approach** — one schema + thin per-consumer adapters (chosen); no vendored shared module.
5. **Family migration** — Phase 2, mechanical/count-neutral (chosen); not bundled into Phase 1.
6. **Malformed file** — fail-closed hard stop (chosen); never silent.
