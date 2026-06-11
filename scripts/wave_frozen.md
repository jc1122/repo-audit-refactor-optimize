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

| Row | Finding | Class | Justification | Expires |
|---:|---|---|---|---|
| 1 | complexity `scripts/_bootstrap_report.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 already split bootstrap report assembly out of the bootstrap checker while preserving public JSON, Markdown, and test contracts; remaining module-level decomposition is future structural work, not a mechanical SP9 K3 fix. | post-v0.5.x decomposition |
| 2 | complexity `scripts/_bootstrap_report.py` `parameter_count` for `build_bootstrap_report` | `deferred-structural` | The public helper signature is covered by current tests and used by checker orchestration; grouping parameters now would change public and test contracts, so it is deferred to future decomposition. | post-v0.5.x decomposition |
| 3 | complexity `scripts/_lane_resolve.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated lane resolution while preserving the bootstrap contracts; any further split should be owned by a future decomposition batch. | post-v0.5.x decomposition |
| 4 | complexity `scripts/_skill_probe.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated skill probing while keeping the public probe behavior stable; additional module decomposition is deferred beyond this mechanical wave. | post-v0.5.x decomposition |
| 5 | hotspot `SKILL.md` `temporal_coupling_ratio` for `SKILL.md` paired with `references/pipeline.md` | `deferred-structural` | The skill entrypoint and pipeline reference intentionally move together; the coupling should be reviewed after precision convergence rather than split in K3. | v0.5.1 convergence review |
| 6 | hotspot `scripts/check_skill_requirements.py` `churn_complexity_product` for `scripts/check_skill_requirements.py` | `deferred-structural` | The checker remains a historically high-churn orchestration surface after the K3 split; further reduction crosses CLI and bootstrap contracts and belongs in future decomposition. | post-v0.5.x decomposition |
| 7 | hotspot `scripts/skill_bootstrap_manifest.json` `churn_complexity_product` for `scripts/skill_bootstrap_manifest.json` | `deferred-structural` | The manifest is central configuration with expected release churn; changes should be evaluated during convergence rather than as a K3 mechanical fix. | v0.5.1 convergence review |
| 8 | hotspot `scripts/skill_bootstrap_manifest.json` `temporal_coupling_ratio` for `scripts/skill_bootstrap_manifest.json` paired with `tests/test_check_skill_requirements.py` | `deferred-structural` | Manifest changes are intentionally locked to checker tests; keep the coupling visible until convergence review. | v0.5.1 convergence review |
| 9 | hotspot `tests/test_check_skill_requirements.py` `churn_complexity_product` for `tests/test_check_skill_requirements.py` | `deferred-structural` | The checker test suite is intentionally high-churn while contract behavior stabilizes; broader test decomposition is deferred until after convergence. | v0.5.1 convergence review |
