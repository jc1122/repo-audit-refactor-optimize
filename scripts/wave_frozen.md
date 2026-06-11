# Wave Frozen Ledger

Source: live SP9 K3 wave artifact, normalized and sorted into `scripts/wave_baseline.json`.

## K5 v0.5.0 ratchet

- Ratchet timestamp: 2026-06-11T13:11:28Z
- Removed expired v0.4.0-era precision rows after running with `SKILLS_ROOT=/home/jakub/projects/repo-audit-skills/skills`.
- Removed stale identities: dead-code `_extract_skill_name`; three generated bootstrap output references; hotspot solo-author rows for `SKILL.md`, `scripts/check_skill_requirements.py`, and `tests/test_check_skill_requirements.py`; hotspot own-test-pair coupling `scripts/check_skill_requirements.py<->tests/test_check_skill_requirements.py`; quality `format_drift` rows for `scripts/_bootstrap_report.py` and `scripts/_skill_probe.py`.
- Current baseline has 13 normalized identities.

## SP10 v0.5.1 ratchet

- Ratchet timestamp: 2026-06-11T15:40:00Z
- Removed stale CLI module-MI identities after running with `SKILLS_ROOT=/home/jakub/projects/repo-audit-skills/skills` at v0.5.1.
- Removed stale identities: `scripts/check_release.py`, `scripts/check_skill_requirements.py`, `scripts/run_diagnosis_wave.py`, and `scripts/validate_run_report.py` module-level `maintainability_index`.
- Current baseline has 9 normalized identities.

## SP11 iteration 2 declared-coupling policy

- Ratchet timestamp: 2026-06-11T23:20:00Z
- Added `scripts/hotspot_audit_config.json` and pinned the wave hotspot lane to
  `scripts/wave_anchor.txt`.
- Removed stale declared-coupling identities counted by the hotspot leaf:
  `SKILL.md<->references/pipeline.md` and
  `scripts/skill_bootstrap_manifest.json<->tests/test_check_skill_requirements.py`.
- Current baseline has 7 normalized identities.

## SP11 iteration 2 bootstrap request ratchet

- Ratchet timestamp: 2026-06-11T23:35:00Z
- Grouped `build_bootstrap_report` inputs behind `BootstrapReportRequest` while
  preserving keyword-call compatibility for existing checker tests and callers.
- Removed stale complexity identity: `scripts/_bootstrap_report.py`
  `build_bootstrap_report` `parameter_count`.
- Current baseline has 6 normalized identities.

## SP11 iteration 2 C-6 hotspot re-anchor

- Ratchet timestamp: 2026-06-11T22:18:00Z
- Advanced `scripts/wave_anchor.txt` to
  `5fe3b5bd9838bb62617d3466820dc57944750ca6`.
- Added declared coupling pairs for the release ledger
  `CHANGELOG.md<->SKILL.md` and the ratchet ledger
  `scripts/wave_baseline.json<->scripts/wave_frozen.md`; both are counted by
  the hotspot leaf under `declared_coupling`.
- Re-anchor surfaced one loop-induced churn row on
  `scripts/run_diagnosis_wave.py` from the accepted security-config forwarding
  work. Per SP11 pre-flight rule 5, it is recorded as real re-anchor residue
  for the next iteration rather than hidden or treated as unfixable growth.
- Current baseline has 7 normalized identities.

## SP11 iteration 3 runner extraction ratchet

- Ratchet timestamp: 2026-06-11T23:09:19Z
- Extracted diagnosis-wave finding normalization and collection into
  `scripts/_wave_findings.py`, preserving direct runner execution and
  `tests/test_run_diagnosis_wave.py`.
- Removed stale hotspot identity: `scripts/run_diagnosis_wave.py`
  `churn_complexity_product`.
- Current baseline has 6 normalized identities.

| Row | Finding | Class | Justification | Expires |
|---:|---|---|---|---|
| 1 | complexity `scripts/_bootstrap_report.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 already split bootstrap report assembly out of the bootstrap checker while preserving public JSON, Markdown, and test contracts; remaining module-level decomposition is future structural work, not a mechanical SP9 K3 fix. | post-v0.5.x decomposition |
| 2 | complexity `scripts/_lane_resolve.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated lane resolution while preserving the bootstrap contracts; any further split should be owned by a future decomposition batch. | post-v0.5.x decomposition |
| 3 | complexity `scripts/_skill_probe.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated skill probing while keeping the public probe behavior stable; additional module decomposition is deferred beyond this mechanical wave. | post-v0.5.x decomposition |
| 4 | hotspot `scripts/check_skill_requirements.py` `churn_complexity_product` for `scripts/check_skill_requirements.py` | `deferred-structural` | The checker remains a historically high-churn orchestration surface after the K3 split; further reduction crosses CLI and bootstrap contracts and belongs in future decomposition. | post-v0.5.x decomposition |
| 5 | hotspot `scripts/skill_bootstrap_manifest.json` `churn_complexity_product` for `scripts/skill_bootstrap_manifest.json` | `deferred-structural` | The manifest is central configuration with expected release churn; changes should be evaluated during convergence rather than as a K3 mechanical fix. | v0.5.1 convergence review |
| 6 | hotspot `tests/test_check_skill_requirements.py` `churn_complexity_product` for `tests/test_check_skill_requirements.py` | `deferred-structural` | The checker test suite is intentionally high-churn while contract behavior stabilizes; broader test decomposition is deferred until after convergence. | v0.5.1 convergence review |
