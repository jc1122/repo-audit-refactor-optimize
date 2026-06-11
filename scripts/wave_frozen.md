# Wave Frozen Ledger

Source: live SP9 K3 wave artifact, normalized and sorted into `scripts/wave_baseline.json`.

## K5 v0.5.0 ratchet

- Ratchet timestamp: 2026-06-11T13:11:28Z
- Removed expired v0.4.0-era precision rows after running with `SKILLS_ROOT=/home/jakub/projects/repo-audit-skills/skills`.
- Removed stale identities: dead-code `_extract_skill_name`; three generated bootstrap output references; hotspot solo-author rows for `SKILL.md`, `scripts/check_skill_requirements.py`, and `tests/test_check_skill_requirements.py`; hotspot own-test-pair coupling `scripts/check_skill_requirements.py<->tests/test_check_skill_requirements.py`; quality `format_drift` rows for `scripts/_bootstrap_report.py` and `scripts/_skill_probe.py`.
- Current baseline has 13 normalized identities.

| Row | Finding | Class | Justification | Expires |
|---:|---|---|---|---|
| 1 | complexity `scripts/_bootstrap_report.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 already split bootstrap report assembly out of the bootstrap checker while preserving public JSON, Markdown, and test contracts; remaining module-level decomposition is future structural work, not a mechanical SP9 K3 fix. | post-v0.5.x decomposition |
| 2 | complexity `scripts/_bootstrap_report.py` `parameter_count` for `build_bootstrap_report` | `deferred-structural` | The public helper signature is covered by current tests and used by checker orchestration; grouping parameters now would change public and test contracts, so it is deferred to future decomposition. | post-v0.5.x decomposition |
| 3 | complexity `scripts/_lane_resolve.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated lane resolution while preserving the bootstrap contracts; any further split should be owned by a future decomposition batch. | post-v0.5.x decomposition |
| 4 | complexity `scripts/_skill_probe.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated skill probing while keeping the public probe behavior stable; additional module decomposition is deferred beyond this mechanical wave. | post-v0.5.x decomposition |
| 5 | complexity `scripts/check_release.py` `maintainability_index` for `<module>` | `deferred-structural` | The release checker remains a script-level workflow with CLI behavior to preserve; further split belongs in a dedicated decomposition batch. | post-v0.5.x decomposition |
| 6 | complexity `scripts/check_skill_requirements.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 already split the bootstrap checker into probe, lane resolution, and report helpers while preserving public and test contracts; residual orchestration debt is deferred to future decomposition. | post-v0.5.x decomposition |
| 7 | complexity `scripts/run_diagnosis_wave.py` `maintainability_index` for `<module>` | `deferred-structural` | The wave runner coordinates lane adapters and artifact emission; splitting it safely requires future contract-aware decomposition, not a mechanical SP9 K3 edit. | post-v0.5.x decomposition |
| 8 | complexity `scripts/validate_run_report.py` `maintainability_index` for `<module>` | `deferred-structural` | The validator owns schema v1 and v2 CLI behavior; further decomposition must preserve that public contract and is deferred. | post-v0.5.x decomposition |
| 9 | hotspot `SKILL.md` `temporal_coupling_ratio` for `SKILL.md` paired with `references/pipeline.md` | `deferred-structural` | The skill entrypoint and pipeline reference intentionally move together; the coupling should be reviewed after precision convergence rather than split in K3. | v0.5.0 convergence review |
| 10 | hotspot `scripts/check_skill_requirements.py` `churn_complexity_product` for `scripts/check_skill_requirements.py` | `deferred-structural` | The checker remains a historically high-churn orchestration surface after the K3 split; further reduction crosses CLI and bootstrap contracts and belongs in future decomposition. | post-v0.5.x decomposition |
| 11 | hotspot `scripts/skill_bootstrap_manifest.json` `churn_complexity_product` for `scripts/skill_bootstrap_manifest.json` | `deferred-structural` | The manifest is central configuration with expected release churn; changes should be evaluated during convergence rather than as a K3 mechanical fix. | v0.5.0 convergence review |
| 12 | hotspot `scripts/skill_bootstrap_manifest.json` `temporal_coupling_ratio` for `scripts/skill_bootstrap_manifest.json` paired with `tests/test_check_skill_requirements.py` | `deferred-structural` | Manifest changes are intentionally locked to checker tests; keep the coupling visible until convergence review. | v0.5.0 convergence review |
| 13 | hotspot `tests/test_check_skill_requirements.py` `churn_complexity_product` for `tests/test_check_skill_requirements.py` | `deferred-structural` | The checker test suite is intentionally high-churn while contract behavior stabilizes; broader test decomposition is deferred until after convergence. | v0.5.0 convergence review |
