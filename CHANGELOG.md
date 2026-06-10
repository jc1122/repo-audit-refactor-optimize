# Changelog

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
