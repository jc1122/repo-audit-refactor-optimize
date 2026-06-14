# Wave Frozen Ledger

Source: live SP9 K3 wave artifact, normalized and sorted into the ratcheted baseline
(historically scripts/wave_baseline.json; since Phase 2 the report-stage `finding` entries
in `.repo-audit/accept.json`).

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

## SP11 iteration 3 C-6 hotspot re-anchor

- Ratchet timestamp: 2026-06-11T23:56:27Z
- Advanced `scripts/wave_anchor.txt` to
  `561c8396d519cdcd848139b95814d1954d49b72d`.
- Re-anchor surfaced one loop-induced churn row on
  `scripts/run_diagnosis_wave.py` from the accepted finding-collection
  extraction. Per SP11 pre-flight rule 5, it is recorded as real re-anchor
  residue for the next iteration rather than hidden or treated as unfixable
  growth.
- Current baseline has 7 normalized identities.

| Row | Finding | Class | Justification | Expires |
|---:|---|---|---|---|
| 1 | complexity `scripts/_bootstrap_report.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 already split bootstrap report assembly out of the bootstrap checker while preserving public JSON, Markdown, and test contracts; remaining module-level decomposition is future structural work, not a mechanical SP9 K3 fix. | post-v0.5.x decomposition |
| 2 | complexity `scripts/_lane_resolve.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated lane resolution while preserving the bootstrap contracts; any further split should be owned by a future decomposition batch. | post-v0.5.x decomposition |
| 3 | complexity `scripts/_skill_probe.py` `maintainability_index` for `<module>` | `deferred-structural` | K3 isolated skill probing while keeping the public probe behavior stable; additional module decomposition is deferred beyond this mechanical wave. | post-v0.5.x decomposition |
| 4 | hotspot `scripts/check_skill_requirements.py` `churn_complexity_product` for `scripts/check_skill_requirements.py` | `deferred-structural` | The checker remains a historically high-churn orchestration surface after the K3 split; further reduction crosses CLI and bootstrap contracts and belongs in future decomposition. | post-v0.5.x decomposition |
| 5 | hotspot `scripts/skill_bootstrap_manifest.json` `churn_complexity_product` for `scripts/skill_bootstrap_manifest.json` | `deferred-structural` | The manifest is central configuration with expected release churn; changes should be evaluated during convergence rather than as a K3 mechanical fix. | v0.5.1 convergence review |
| 6 | hotspot `tests/test_check_skill_requirements.py` `churn_complexity_product` for `tests/test_check_skill_requirements.py` | `deferred-structural` | The checker test suite is intentionally high-churn while contract behavior stabilizes; broader test decomposition is deferred until after convergence. | v0.5.1 convergence review |
| 7 | hotspot `scripts/run_diagnosis_wave.py` `churn_complexity_product` for `scripts/run_diagnosis_wave.py` | `loop-reanchor-residue` | The iteration accepted runner helper extraction, pushing the file over the hotspot churn threshold at the new anchor. The row is real and remains in the baseline for the next structural visit. | SP11 iteration 4 |

## v0.7.5 dogfood ratchet + ledger reconcile

- Ratchet timestamp: 2026-06-14T04:00:00Z
- Added `scripts/mprr_normalize.py` `<module>` `maintainability_index` (MI 61.63, radon
  grade A, just under the leaf's `mi_low=65`). The module is 85 LOC / 3 small functions;
  chasing MI to 65 via decomposition is low-value churn. Class: `deferred-structural`.
- **Ledger reconcile (closes prior drift):** the table above documented only 7 rows while
  the ratcheted baseline (then scripts/wave_baseline.json) held 13. The table below documents
  EVERY row in the baseline (count **14**), so the ledger and the baseline can no longer disagree.

| Row | Finding (leaf · path · symbol · metric) | Class | Justification |
|---:|---|---|---|
| 1 | complexity · `scripts/_bootstrap_report.py` · `<module>` · maintainability_index | `deferred-structural` | K3 split report assembly out of the checker; remaining module decomposition is future structural work. |
| 2 | complexity · `scripts/_lane_resolve.py` · `<module>` · maintainability_index | `deferred-structural` | K3 isolated lane resolution; any further split owned by a future decomposition batch. |
| 3 | complexity · `scripts/_skill_probe.py` · `<module>` · maintainability_index | `deferred-structural` | K3 isolated skill probing; additional decomposition deferred beyond the mechanical wave. |
| 4 | complexity · `scripts/synthesize_packets.py` · `mechanical_patches` · function_nloc | `deferred-structural` | Cohesive patch-emitter pipeline; splitting relocates rather than reduces the finding. |
| 5 | complexity · `scripts/synthesize_packets.py` · `<module>` · maintainability_index | `deferred-structural` | Central synthesis module; decomposition is future structural work, not a mechanical fix. |
| 6 | hotspot · `SKILL.md` · churn_complexity_product | `deferred-structural` | Release-churn surface (version + changelog edits each release); expected, not a code defect. |
| 7 | hotspot · `scripts/check_skill_requirements.py` · churn_complexity_product | `deferred-structural` | Historically high-churn checker; reduction crosses CLI and bootstrap contracts. |
| 8 | hotspot · `scripts/run_diagnosis_wave.py` · churn_complexity_product | `deferred-structural` | Core runner; churn from accepted helper extractions, revisit on the next structural pass. |
| 9 | hotspot · `scripts/skill_bootstrap_manifest.json` · churn_complexity_product | `deferred-structural` | Central configuration with expected release churn. |
| 10 | hotspot · `tests/test_check_skill_requirements.py` · churn_complexity_product | `deferred-structural` | Checker test suite, intentionally high-churn while contract behavior stabilizes. |
| 11 | hotspot · `tests/test_run_diagnosis_wave.py` · churn_complexity_product | `deferred-structural` | Runner test suite churn paired with runner evolution; deferred to a structural visit. |
| 12 | exec-audit · `.` · benchmark_entrypoints_missing | `won't-fix-FP` | The orchestration metaskill has no runtime benchmark surface by design (its perf lane is `synthesizable`, not native). |
| 13 | growth-audit · `<repo>` · net_loc_growth | `deferred-structural` | Net growth vs the pinned anchor; managed by re-anchoring `scripts/wave_anchor.txt`, not by editing code. |
| 14 | complexity · `scripts/mprr_normalize.py` · `<module>` · maintainability_index | `deferred-structural` | MI 61.63 (grade A) marginally below `mi_low=65`; low-value to chase on an 85-LOC module. |

## v0.7.6 dogfood ratchet — CONVERGED (gate green)

- Ratchet timestamp: 2026-06-14T04:30:00Z
- Ratcheted the 5 remaining anchor-relative residuals; the convergence gate is now
  **green** (`status: pass`, count == baseline == 19).

| Row | Finding (leaf · path · symbol · metric) | Class | Justification |
|---:|---|---|---|
| 15 | growth-audit · `<repo>` · cli_flag_growth | `deferred-structural` | Metaskill CLI surface grows with features; managed by anchor policy, not code edits (cf. row 13). |
| 16 | growth-audit · `<repo>` · docs_loc_growth | `deferred-structural` | Living docs (plans/specs/references) grow with the skill; expected, not a defect. |
| 17 | growth-audit · `<repo>` · tracked_files_growth | `deferred-structural` | New scripts/tests/docs are the unit of work for this skill; growth is the signal of progress. |
| 18 | hotspot · `CHANGELOG.md` · churn_complexity_product | `deferred-structural` | Release-churn doc (an entry every release), analogous to the already-accepted `SKILL.md` row 6. |
| 19 | hotspot · `references/pipeline.md` · churn_complexity_product | `deferred-structural` | Core reference doc edited as the pipeline evolves; documentation churn, not code risk. |

### Design finding (re-anchor tension — deferred to a future skill change, not a code fix)

`scripts/wave_anchor.txt` is shared by two lanes with opposite needs: growth-audit uses it
as a **comparison baseline** (`--baseline-rev`, so a *recent* rev minimizes growth), while
hotspot-audit uses it as a **window end-point** (`--rev`, walking `max_commits` back, so a
recent rev points the window at the latest churn). During this dogfood session, re-anchoring
to HEAD zeroed growth but surfaced 11 churn hotspots from the remediation burst itself. The
anchor was therefore left at the stable historical rev and the residuals ratcheted instead.
**Follow-up:** give hotspot and growth independent anchors (or a churn-window the dogfood
loop can exclude) so re-anchoring fixes growth without exposing loop-induced churn.

## Phase 2 migration — baseline moved into `.repo-audit/accept.json`

- The former scripts/wave_baseline.json has been removed; the 19 accepted-residual identities
  it held now live as report-stage `finding` entries in `.repo-audit/accept.json`, alongside
  the Phase 1 `scripts/_accept.py` module-MI residual (20 entries total). This ledger
  remains the human justification and is the machine source's documentation cross-reference;
  the convergence gate no longer reads `wave_baseline.json`.

| Row | Finding (leaf · path · symbol · metric) | Class | Justification |
|---:|---|---|---|
| 20 | complexity · `scripts/_accept.py` · `<module>` · maintainability_index | `deferred-structural` | Cohesive fail-closed acceptance-policy module (parse/validate + 3-kind match); per-function CC <=3 after helper extraction. Module-level MI (~42.7) reflects one coherent contract's aggregate size; splitting to chase MI would fragment a single contract (cf. the accepted `scripts/mprr_normalize.py` module-MI residual). |
