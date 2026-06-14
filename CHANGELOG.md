# Changelog

## 0.7.0

feat: self-audit hardening — honest benchmark-surface detection (no name-substring false
positives), default tests/fixtures exclusion + `--baseline` suppression in the diagnosis
wave, always-available process skills, and an MPRR self-engine merge guard; adds a
self-dogfood regression test.

## 0.6.0

feat: synthesized performance benchmark — when a repo has no benchmark surface, the
performance lane resolves to the new `synthesizable` state and the agent may synthesize
a focused microbenchmark that the existing `perf-benchmark` engine measures. New
stdlib-only modules under `scripts/`: `synthesize_perf` (gate decision over a
`perf-benchmark` summary — pass / honest-refusal / measurement-error, plus the
`verify_and_decide` revert seam), `_complexity_label` (local Big-O label),
`graduate_benchmark` (copies a proven harness into `benchmarks/`; the perf trend ledger
stays owned by `perf-benchmark --baseline-ledger`), and `synth_run` (a resumable
file-backed driver: `discover → select → measure → candidate → verify`). Companion
primitives live in `perf-benchmark-skill` (`profile_discover`, `synth_microbench`, a
stable top-level summary contract) and a new `perf-smell-audit` leaf (perflint-backed
PERF findings) lands in `repo-audit-skills`. The deterministic gate is reused from
`perf-benchmark`'s `scoring.py`, not rebuilt.

## 0.5.1

SP14 — remove the unused `running_ids` accessor from the MPRR `SaturatingScheduler`
(vulture dead-code finding; the engine never referenced it). No behavior change.

## 0.5.0

SP14 — massively-parallel redundancy-remediation (MPRR) engine. New stdlib-only
modules under `scripts/`: `mprr_normalize`, `mprr_partition`, `mprr_schedule`
(property-proven disjoint-lock invariant), `mprr_gate` (three-tier gate ladder),
`mprr_integrate` (scope check + conflict-free merge), `mprr_packets`, and the
orchestrator CLI `mprr_run` (plan/integrate/reaudit over persisted run-state).
KPI miner extended with pool-utilization, merge-conflict-rate, and concurrency
metrics. SKILL.md gains an MPRR remediation-track section; `references/mprr.md`
documents the locked decisions and gate ladder.

## 0.4.6

SP12 W6 — release gate repair.

## 0.4.5

SP12 W5 -- code-health wave-runner exit classification fix.

- Classify code-health lane exits with parsed findings as findings; preserve
  exit-without-findings as an error.

## 0.4.4

SP12 W3/W4 -- registry-driven diagnosis waves and advisory synthesis.

- Made the W3 diagnosis wave registry-driven and parallel, with
  `wave_timings.json` emitted for lane runtime accounting.
- Extended the W3 lane registry with exec and growth lanes.
- Added W4 synthesis output for advisory worker packets and mechanical patch
  proposals from `synthesize_packets.py`.

## 0.4.3

SP11 iteration 3 -- wave runner decomposition.

- Extracted diagnosis-wave finding normalization into scripts/_wave_findings.py.
- Ratcheted the wave baseline from 7 to 6 normalized identities by removing the
  loop-induced run_diagnosis_wave.py churn row after the helper extraction.

## 0.4.2

SP11 iteration 2 -- wave policy, bootstrap request, and runner config support.

- Pinned the hotspot wave window and counted declared coupling suppressions.
- Grouped bootstrap report inputs behind `BootstrapReportRequest` while keeping
  keyword-call compatibility.
- Updated CI workflow actions to current majors.
- Added wave-runner forwarding for security audit config files.
- Ratcheted the wave baseline from 9 to 6 normalized identities.

## 0.4.1

SP10 T5 -- diagnosis wave scope precision and convergence ratchet.

- Excludes historical `docs/superpowers` plan/spec files from living-doc
  diagnosis scope.
- Ratcheted the wave baseline from 13 to 9 after v0.5.1 entrypoint module-MI
  relaxation dissolved CLI script module-MI rows.

## 0.4.0

SP9 K3-T4 -- checkpoint/docs brevity pass and diagnosis orchestration updates.

- Decomposed checker scripts into smaller responsibilities and updated bootstrap
  behavior to match phase-based handoff.
- Added run-report v2 validator flow and enforced verification failures when report
  artifacts or schema keys are missing.
- Added diagnosis wave runner to the canonical workflow for installed diagnosis leaves.
- Expanded coverage of taxonomy, docs-repair, and run-report documentation references.
- Ran a brevity pass to condense operational text and preserve core contracts.

## 0.3.1

SP7 C4 -- perf-optimization joins the performance lane as a preferred fallback.

- Manifest registers `perf-optimization` (min_version 0.1.0) as a performance
  lane fallback companion for remediation after `perf-benchmark` proves a
  bottleneck.
- Performance lane now returns `degraded` when only `perf-benchmark` is
  installed and full when both `perf-benchmark` and `perf-optimization` are
  usable.
- Version bump 0.3.0 -> 0.3.1.

## 0.3.0

Track B — bootstrap hardening, CI release gates, and new lane surface.

- Bootstrap skill resolution enforces `min_version` pins and detects stale installed skills (SP7 B1)
- Bootstrap report includes advisory unreferenced-skills section (SP7 B2)
- CI workflow gates on pytest + `check_release.py` on every push/PR (SP7 B3, B6)
- Orchestration runs require committing a run report into `docs/audits/<run-id>/`; verification fails closed when absent (SP7 B4)
- Remediation playbook adds architecture-scale RESTRUCTURE procedures with mechanical verification conditions (SP7 B5)
- Manifest adds `hygiene` and `security` lanes, registers optional leaves, pins `min_version` for all repo-audit-skills leaves (SP7 B7)

## 0.2.0

Current state: SP5 rewire — decomposed bootstrap checker, refactored profile
scanning, resolved lint and format findings through mechanical rounds.

- Decomposed `scan_repo_profile` into smaller helpers (SP5 Phase2 R2)
- Decomposed `load_source_overrides` / `_discover_skills` (SP5 Phase2 R3)
- Ruff format and autofix lint passes (SP5 Phase2 R1)
- PERF signal procedure and prioritization docs (SP6 T8)

## 0.1.0

Initial release.
