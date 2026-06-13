# Changelog

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

- Bootstrap skill resolution now enforces `min_version` pins and detects stale
  installed skills (SP7 B1)
- Bootstrap report includes an advisory unreferenced-skills section listing
  installed skills not referenced in the manifest (SP7 B2)
- CI workflow (`check.yml`) gates on pytest + `check_release.py` on every push
  and pull request (SP7 B3, B6)
- Every orchestration run is now contractually required to commit a run report
  into `docs/audits/<run-id>/`; verification fails closed when the report is
  absent or incomplete (SP7 B4)
- Remediation playbook adds architecture-scale RESTRUCTURE procedures
  (dependency inversion, interface extraction, module split/merge, strangler fig)
  with mechanical verification conditions (SP7 B5)
- Manifest adds `hygiene` and `security` lanes, registers `hotspot-audit` and
  `test-effectiveness-audit` as optional leaves, and pins `min_version` for all
  repo-audit-skills leaves (SP7 B7)

## 0.2.0

Current state: SP5 rewire — decomposed bootstrap checker, refactored profile
scanning, resolved lint and format findings through mechanical rounds.

- Decomposed `scan_repo_profile` into smaller helpers (SP5 Phase2 R2)
- Decomposed `load_source_overrides` / `_discover_skills` (SP5 Phase2 R3)
- Ruff format and autofix lint passes (SP5 Phase2 R1)
- PERF signal procedure and prioritization docs (SP6 T8)

## 0.1.0

Initial release.
