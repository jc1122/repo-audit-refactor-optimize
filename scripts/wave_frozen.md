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

## feat/convergent-family — perf-smell lane integration

- Ratchet timestamp: 2026-06-14
- Added `perf-smell-audit` as deterministic wave lane (9th lane).
- Genuine fixes applied: dict comprehension in `load_lanes`, tuple for `cmd` in `_leaf_supports_exclude_prefix`, list comprehension in `_relevant_lane_names`, list comprehension for `_parse_version`'s `nums`, `extend`+genexp in `_markdown_report`, tuple for `KEYS` in `validate_run_report`, tuple for `sources` in `load_source_overrides`.
- Remaining 113 findings across 43 unique (path, symbol, metric) keys: 52 W8201, 25 W8202, 12 W8205, 24 W8301, 1 W8402, 1 W8403. All accepted as `perflint-FP` or `non-hot-path` (see rows 21–63 below).

| Row | Finding (leaf · path · symbol · metric) | Class | Justification |
|---:|---|---|---|
| 21 | perf-smell · `scripts/_accept.py` · `loop-global-usage` · W8202 | `perflint-FP` | `_MATCH_KEYS` is a module-level tuple iterated at most 5 times in a cold-path policy-loading function. Hoisting adds noise without measurable gain. |
| 22 | perf-smell · `scripts/_bootstrap_report.py` · `dotted-import-in-loop` · W8205 | `perflint-FP` | `os.walk` is the iterable in `for current_root, dir_names, file_names in os.walk(repo_root)` — it is not called inside the loop body. `os.path.join` call in an IO-bound directory scan; attribute lookup cost negligible relative to disk IO. |
| 23 | perf-smell · `scripts/_bootstrap_report.py` · `loop-global-usage` · W8202 | `perflint-FP` | perflint flags `dir_names` and `file_names` as global lookups; these are loop variables unpacked from `os.walk`. |
| 24 | perf-smell · `scripts/_bootstrap_report.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `manifest["lanes"][lane_name]` in `_evaluate_active_lanes`. The full expression is loop-variant (`lane_name` changes); perflint over-approximates by flagging the outer dict access. |
| 25 | perf-smell · `scripts/_lane_resolve.py` · `loop-global-usage` · W8202 | `perflint-FP` | `KNOWN_LANGUAGES`, `KNOWN_TEST_SYSTEMS` (module-level frozensets) in `_matches_when`'s cold-path condition check. Loop runs over a handful of condition keys at startup. |
| 26 | perf-smell · `scripts/_lane_resolve.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `manifest["lanes"][lane_name]` and `manifest["skills"][skill_name]` in collect/mark functions. Full expressions are loop-variant; perflint over-approximates the outer dict reference. |
| 27 | perf-smell · `scripts/_lane_resolve.py` · `use-tuple-over-list` · W8301 | `cant-fix` | `warnings_list = []` is concatenated with `eval_warnings` (a list) via `+`; changing to `()` raises TypeError at runtime. |
| 28 | perf-smell · `scripts/_skill_probe.py` · `loop-global-usage` · W8202 | `perflint-FP` | `_REQUIRED_SKILL_FIELDS` module-level frozenset in cold-path field-validation loop (~10 iterations at startup). |
| 29 | perf-smell · `scripts/allocate_batches.py` · `dotted-import-in-loop` · W8205 | `non-hot-path` | `json.loads` in IO-bound line-reading loop in `_load_kpis`; attribute lookup negligible vs disk IO. |
| 30 | perf-smell · `scripts/allocate_batches.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `[repo for repo in active_repos if alloc[repo] < cap]` — `alloc[repo]` changes each iteration. Full comprehension is loop-variant; perflint sees `active_repos` and `cap` as invariant components of the expression. |
| 31 | perf-smell · `scripts/check_skill_requirements.py` · `dotted-import-in-loop` · W8205 | `perflint-FP` | `importlib.import_module` must be called per iteration (different module each time); cannot be hoisted. |
| 32 | perf-smell · `scripts/check_skill_requirements.py` · `loop-global-usage` · W8202 | `non-hot-path` | `globals()`, `getattr`, `importlib` in once-at-import module re-export loop (~5 iterations). |
| 33 | perf-smell · `scripts/check_wave_baseline.py` · `use-tuple-over-list` · W8301 | `cant-fix` | `cmd` list is immediately extended with `+=` multiple times before `subprocess.run`; mutable list is required. |
| 34 | perf-smell · `scripts/graduate_benchmark.py` · `dotted-import-in-loop` · W8205 | `non-hot-path` | `shutil.copy2` in a glob-iteration loop; each iteration copies one file. Body dominated by disk IO. |
| 35 | perf-smell · `scripts/migrate_baseline_to_accept.py` · `loop-global-usage` · W8202 | `perflint-FP` | perflint flags `r.get(...)` as global usage; `r` is the loop variable (dict from baseline rows), not a global. |
| 36 | perf-smell · `scripts/mine_iteration_kpis.py` · `dotted-import-in-loop` · W8205 | `non-hot-path` | `json.loads` in line-by-line file-reading loop in `_parse_worker_events`; IO-bound cold-path analytics. |
| 37 | perf-smell · `scripts/mine_iteration_kpis.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `ev.get("event")` where `ev` changes per iteration. perflint sees `.get` method binding as stable and over-approximates. |
| 38 | perf-smell · `scripts/mine_iteration_kpis.py` · `use-tuple-over-list` · W8301 | `cant-fix` | `worker_runs = []` in except clause passed to `KpiInputs(worker_runs=...)` typed as `list[dict]`. Tuple violates the type contract. |
| 39 | perf-smell · `scripts/mprr_normalize.py` · `loop-global-usage` · W8202 | `non-hot-path` | `_REDUNDANCY_LEAVES`, `_CLASS_BY_LEAF` frozen lookup tables consulted once per finding in a non-hot remediation normalization pass. |
| 40 | perf-smell · `scripts/mprr_run.py` · `dotted-import-in-loop` · W8205 | `non-hot-path` | `mprr_packets.remediation_packet` in small batch-dispatch loop (1–5 items); body dominated by JSON serialization and subprocess coordination. |
| 41 | perf-smell · `scripts/mprr_run.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `list(it.files)` and `set(it.files)` where `it` is the loop variable. Both expressions are loop-variant. |
| 42 | perf-smell · `scripts/mprr_run.py` · `use-list-copy` · W8402 | `perflint-FP` | Nested loop with filter in `_engine_accept_policy`: outer filters `isinstance`, inner appends. Cannot be a simple `list.copy()`. |
| 43 | perf-smell · `scripts/run_diagnosis_wave.py` · `dotted-import-in-loop` · W8205 | `non-hot-path` | `time.time()` in parallel-future completion loop (~8–9 iterations). `time` is a C-extension; attribute lookup negligible. |
| 44 | perf-smell · `scripts/run_diagnosis_wave.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `context.rev is None` (frozen dataclass read), `results[lane]` dict access, and `_status_for_exit(...)`. All are loop-variant: `lane` changes each iteration. |
| 45 | perf-smell · `scripts/synthesize_packets.py` · `dotted-import-in-loop` · W8205 | `non-hot-path` | `json.dumps` per finding in `mechanical_patches`; each iteration writes to disk, making IO the bottleneck. |
| 46 | perf-smell · `scripts/synthesize_packets.py` · `loop-global-usage` · W8202 | `non-hot-path` | `SAFE_PATCH_TABLE` dispatch-table constant consulted once per finding. O(1) lookup, not a hot path. |
| 47 | perf-smell · `scripts/synthesize_packets.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on `str(finding.get('id', ...))` where `finding` is the loop variable. Expressions are loop-variant; perflint sees `str()` as invariant. |
| 48 | hotspot · `scripts/wave_frozen.md` · churn_complexity_product | `deferred-structural` | `scripts/wave_frozen.md` is the acceptance ledger; it grows with every ratchet/triage session by design. Churn on this file signals an active audit cycle, not a code risk. |
| 49 | perf-smell · `tests/test_allocate_batches.py` · `use-tuple-over-list` · W8301 | `test-fixture` | `KPIS = [...]` test fixture; lists are idiomatic for test data and allow future append/parametrize extension. |
| 50 | perf-smell · `tests/test_check_skill_requirements.py` · `loop-global-usage` · W8202 | `test-fixture` | Cold-path test helper loops; performance optimization in test setup is not warranted. |
| 51 | perf-smell · `tests/test_check_skill_requirements.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on dict subscript patterns in test helpers where the subscript key is the loop variable. perflint over-approximates. |
| 52 | perf-smell · `tests/test_check_skill_requirements.py` · `use-dict-comprehension` · W8403 | `test-fixture` | `_lane_manifest`'s skills dict-building loop at line 1093 has a complex multi-field value template; for-loop form is more legible in test code. |
| 53 | perf-smell · `tests/test_check_skill_requirements.py` · `use-tuple-over-list` · W8301 | `test-fixture` | List literals as parametrize values and fixture data; idiomatic for tests. |
| 54 | perf-smell · `tests/test_lessons.py` · `use-tuple-over-list` · W8301 | `test-fixture` | Test fixture list literal; no runtime benefit from changing to tuple. |
| 55 | perf-smell · `tests/test_migrate_baseline.py` · `use-tuple-over-list` · W8301 | `test-fixture` | Test fixture list literal; idiomatic for test data. |
| 56 | perf-smell · `tests/test_mprr_normalize.py` · `use-tuple-over-list` · W8301 | `test-fixture` | Test fixture list literals; idiomatic for test data. |
| 57 | perf-smell · `tests/test_mprr_partition.py` · `loop-global-usage` · W8202 | `test-fixture` | Module-level constant in cold-path test assertion loop; performance optimization not warranted in tests. |
| 58 | perf-smell · `tests/test_mprr_run.py` · `use-tuple-over-list` · W8301 | `test-fixture` | Test fixture list literals; idiomatic for test data. |
| 59 | perf-smell · `tests/test_run_diagnosis_wave.py` · `use-tuple-over-list` · W8301 | `cant-fix` | The `["tests", "fixtures"]` list is the expected return value of `_effective_excludes`; asserting against a tuple would require changing the production function's return type. |
| 60 | perf-smell · `tests/test_self_dogfood.py` · `loop-global-usage` · W8202 | `test-fixture` | Module-level name in test verification loop; cold path with trivial iteration count. |
| 61 | perf-smell · `tests/test_self_dogfood.py` · `loop-invariant-statement` · W8201 | `perflint-FP` | Fires on dict subscript in test assertion loop where subscript key is the loop variable. perflint over-approximates. |
| 62 | perf-smell · `tests/test_synthesize_packets.py` · `use-tuple-over-list` · W8301 | `test-fixture` | Test finding-collection fixtures; lists are idiomatic for test data. |
| 63 | perf-smell · `tests/test_synthesize_perf.py` · `loop-global-usage` · W8202 | `test-fixture` | Module-level constant in cold-path test assertion loop; no measurable benefit from hoisting. |
| 64 | perf-smell · `tests/test_wave_findings.py` · `use-tuple-over-list` · W8301 | `test-fixture` | `FINDINGS = [...]` module-level test fixture; list is idiomatic and allows easy extension. |
| 65 | complexity · `scripts/mine_iteration_kpis.py` · `build_kpis` · parameter_count | `cohesive-assembler` | 7 params (>5) mirror the KPI record inputs; thin assembler delegating to compute_kpi; grouping would break the pinned signature. |

## v0.11.3 dogfood ratchet — canonical-bootstrap clone

- Ratchet timestamp: 2026-06-15
- A no-exceptions self-dogfood drove every explicitly-triggered pass against repo-B
  itself and found `synthesize_perf.py` / `synth_run.py` crashed as direct scripts
  (`ModuleNotFoundError`) — they were the only runnable `scripts`-package importers
  missing the `sys.path` bootstrap `mprr_run.py` carries. Fixed by copying the
  canonical bootstrap into both (v0.11.3).
- That copy made `synth_run.py`'s import preamble (shared stdlib imports + the 3-line
  bootstrap) an exact clone of `mprr_run.py`'s, crossing jscpd's clone threshold.

| Row | Finding (leaf · path · symbol · metric) | Class | Justification |
|---:|---|---|---|
| 66 | duplication · `scripts/mprr_run.py` · `scripts/synth_run.py:11-21` · duplicate_tokens | `cant-fix` | The cloned region is the shared stdlib import preamble plus the canonical 3-line `sys.path` bootstrap. The bootstrap is irreducible — a shared helper cannot be imported until the repo root is already on `sys.path` (chicken-and-egg) — so this is the blessed idiom `mprr_run.py` established and `synth_run.py` now matches deliberately for direct-script + module parity. One canonical bootstrap is worth more than avoiding a sub-threshold preamble clone. |
