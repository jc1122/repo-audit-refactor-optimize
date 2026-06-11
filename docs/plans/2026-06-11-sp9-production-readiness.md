# SP9: Production Readiness — final gap-fill, convergence proof, ship

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **For every SP9 orchestrator (K1–K5):** this plan is the single authority. You coordinate ONLY, never implement. Workers = **native Codex Spark subagents** (100k context — packets per C-4: ≤2 files, content inlined, ≤8k tokens). A gate-failing change is discard/retry, never a looser gate. A worker's "green" is NOT evidence: re-run every gate yourself and read real output. Commit locally per task. **Do NOT push, tag, or release** — only K5-T4 ships, and only after explicit human authorization in-session.

**Goal:** close every remaining gap in the skill family — leaf precision (5 FP classes found by SP8), ratchet ergonomics, orchestrator mechanization (wave runner, run-report validator, 4-class triage), the never-run perf-repo self-audit, convergence gates in all three repos, and a brevity pass — then prove two-run convergence and execute the human-authorized commit/push/release/reinstall run. End state: **a full software-improvement package (perf audit+optimization, code health, testing, security, docs audit+repair) that can be repeatedly dogfooded on itself and converges.**

**Architecture (FIXED):** up to 5 concurrent Codex gpt-5.5 orchestrator sessions. K3 (repo-B) and K4 (repo-P) launch NOW. K1/K2 (repo-A, isolated worktrees, path-disjoint) launch only after SP8 Track G completes. K5 (integration + convergence + ship) is serial, last, and the only session allowed to push — after human approval. Zero shared writes throughout.

**Tech stack:** Python 3.11+ stdlib (leaves), pytest, npm gate chain (repo-A), jscpd/lizard/radon/vulture/ruff/bandit/mutmut pinned as today. No new dependencies.

**Repos (verified 2026-06-11):**
- repo-A = `/home/jakub/projects/repo-audit-skills` — SP8 Track G IN FLIGHT (at G2-0, commits `3d0af2d`, `138d068` so far). K1/K2/K5 pre-flight requires G COMPLETE: `docs/audits/20260611T062217Z/run_report.json` exists AND `npm run check` = 9 gates green. Record post-G HEAD + baseline counts as the K-track starting point; drift from SP8 C-8 expectations is recorded, not chased.
- repo-B = `/home/jakub/projects/repo-audit-refactor-optimize` — `1e33e89` (SP8 H complete, ahead of origin by 4 + this plan), 79 passed. `scripts/` is a package (`scripts/__init__.py`; tests do `importlib.import_module("scripts.check_skill_requirements")`).
- repo-P = `/home/jakub/projects/perf-benchmark-skill` — `ceff6b7`, clean, 151 passed. **SP8 Track P never ran** (no `docs/audits/`): K4 absorbs it. `pyproject.toml` contains ONLY `[tool.ruff]` (no `[project]` table) — record the dependency leaf's manifest semantics honestly, whatever they turn out to be.
- Installed skills root `~/.claude/skills`: 16 repo-A leaves @ 0.4.0, repo-audit-refactor-optimize 0.3.1, perf-benchmark 0.2.0, perf-optimization 0.1.0. K3/K4 diagnosis uses these installed 0.4.0 copies (pre-K1 FPs are EXPECTED and get frozen with justification, then ratcheted away by K5 after the v0.5.0 leaves land — that ratchet IS the convergence demonstration).

## Out of scope (deliberate)

- Multi-language (JS/TS, C, Rust) leaves — SP10; the registry already supports plug-in language leaves.
- opencode-worker-bridge port fix — SP9 uses native Spark workers, no bridge. Lesson stands recorded (SP8-H deviation 1): concurrent bridge tracks must pass unique `--port`.
- `check:hotspot` / `check:test-effectiveness` gates (non-stationary / too slow — unchanged SP8 rationale), hotspot trend mode, perf tiers beyond `fast` (valgrind absent), service-level load lane.
- Any schema change beyond run-report v2 (C-3). SIGNALS frozenset unchanged.

---

## Empirical pre-flight (verified 2026-06-11; each orchestrator re-verifies its own rows)

1. **SP8-H backlog** (`repo-B docs/audits/20260611T061957Z/backlog.md`): 36 findings → 1 mechanical (fixed), 16 deferred-structural (D1–D7 = complexity in `scripts/check_skill_requirements.py`, 1050 lines; D8–D16 hotspot inherents), **19 won't-fix/FP** — the orchestrator had to invent that 4th class; the playbook lacks it (C-3 fixes this).
2. **FP evidence, exact loci:**
   - docs-consistency: inclusion-only prefixes cannot exclude a subtree (`docs/dogfood/**`, `docs/plans/**` swept under `--source-prefix docs` → 14 immutable-record FPs, W6–W19) and runtime/output-path refs fire (`SKILL.md:50-52` → `bootstrap/bootstrap_report.json` etc., W3–W5). repo-A hit the same wall (SP8 C-4 living-docs scope).
   - hotspot: `author_concentration` (emitted in `skills/hotspot-audit/scripts/_audit_knowledge.py:56`) is pure noise in single-author repos (H D12–D14, all 1.0); code↔own-test `temporal_coupling` pairs are expected co-evolution (D15–D16).
   - quality: `format_drift` (emitted at `skills/quality-audit/scripts/quality_audit.py:150` from `_ruff_format`, line 120) fired on repo-B which declares NO format config (H W2).
   - dead-code: vulture `DELETE _extract_skill_name` was contradicted by 2 direct tests (H W1); `_vulture_findings` at `skills/dead-code-audit/scripts/dead_code_audit.py:74-124`.
   - test-effectiveness: uncaught `subprocess.CalledProcessError` crash when mutmut baseline collection fails — `skills/test-effectiveness-audit/scripts/_pipeline.py` Phase 4 `subprocess.run(..., check=True)` catches only `TimeoutExpired` (G1 summary, all 3 mutation targets); subprocess-integration suites are inherently incompatible with mutmut's `mutants/` sandbox.
3. **Identity line-pin pain:** duplication finding symbols embed line ranges (e.g. `shared/health_common.py ↔ skills/complexity-audit/scripts/health_common.py:1-99`); ANY edit to a clone-pair file forces a stale+new baseline swap (SP7 INT-6, SP8 hard rules, 3 launch-prompt warnings). Identity built in `scripts/self_audit.py` `run()` (symbol at line 50: `f["location"]["symbol"]`).
4. **Coverage gate asymmetry:** `scripts/check_coverage_gap.py` is a one-way ratchet, no stale detection (SP8 pre-flight row 5). After G2-0, `scripts/gate_common.py` exists with `identities()`/`verdict()` to reuse.
5. **Brevity baseline (lines):** repo-A 16 SKILL.mds total 1737 — offenders: dependency-audit 295, test-redundancy-triage 194, test-quality-assurance 163, test-effectiveness 160; family median ≈ 100. repo-B: SKILL 176, references 581 total. repo-P: perf-optimization SKILL 357, perf SKILL 244, `references/sample-report.md` 296, tool-guide 193.
6. **B4 contract** (`repo-B references/pipeline.md` "Run Report"): v1 keys `schema_version(1), repo_root, started_utc, finished_utc, orchestrator_skill_version, lanes, findings_totals, backlog{accepted,deferred,coverage_gated}, batches, verification, warnings`. Enforced by prose only — H verified "key-by-key" by hand (C-3 adds the validator).
7. **repo-B test import style:** `checker = importlib.import_module("scripts.check_skill_requirements")` — K3-T1 decomposition MUST keep every name the 79 tests touch re-exported from that module.
8. **K4 cross-track dependency:** `check_wave_baseline.py` (K4-T4) shells out to repo-B's `scripts/run_diagnosis_wave.py` (K3-T3). K3 lands T3 as its 2nd task; K4 reaches T4 after hours of perf work. If absent when K4 needs it: poll `git -C /home/jakub/projects/repo-audit-refactor-optimize log --oneline | grep -i wave` every 30 min, STOP after 2h and report.

---

## Contracts (FROZEN — deviation = STOP and report)

### C-1. Leaf precision: deterministic, config-gated, advisory-only
Every FP fix is a behavior change ONLY for the FP class, with a regression test for both directions (FP suppressed; true positive still fires). Leaves never mutate the audited repo. Suppressions are COUNTED in the leaf report (`suppressed_*: N`) — silent dropping is forbidden. SKILL.md "Limits" documents each rule.

### C-2. Brevity budgets (token efficiency without scope loss)
SKILL.md hard cap **≤160 lines**, target ≤120; references stay load-on-demand. NOTHING contractual is deleted: every CLI flag, exit code, threshold, and Limit stays documented (move detail to `docs/`/`references/` if needed). Each track records a before/after line-count table in its final report. `check:docs` green proves no dead refs were introduced.

### C-3. Run-report schema v2 + 4-class triage
`schema_version: 2` = v1 keys with `backlog` gaining `wont_fix` (int). Triage classes: accepted-mechanical / deferred-structural / coverage-gated / **won't-fix-FP (per-row justification mandatory)**. `scripts/validate_run_report.py` (K3-T2) is the fail-closed authority; `--schema 1` accepted for historical reports. All SP9 run reports are v2 and validator-green.

### C-4. Spark worker packets
Per packet: one goal, ≤2 files, full current file content when ≤200 lines (else excerpt with function-name anchors — line numbers may have drifted post-G; locate by `grep`), the failing test to satisfy, exact run command + expected output. ≤8k tokens. No repo-wide context. TDD: worker returns diff + test output; orchestrator re-runs gates itself.

### C-5. Write partition (zero shared writes)
- K1: worktree `../ras-sp9-k1`, branch `sp9/leaf-precision` — may touch ONLY `skills/{docs-consistency,hotspot,quality,dead-code,test-effectiveness}-audit/**` + in-branch baseline swap edits to `scripts/self_audit_baseline.json`/`scripts/self_audit_frozen.md`.
- K2: worktree `../ras-sp9-k2`, branch `sp9/ratchet-brevity` — `scripts/**`, `shared/**`, `docs/self-audit/**`, README.md, and the 11 SKILL.mds NOT owned by K1. FORBIDDEN: K1's five leaf dirs.
- K3: repo-B main only. K4: repo-P main only. K5: serial after all others; merges into repo-A main; only session allowed to push (after authorization).

### C-6. Baseline discipline (inherited from SP8 C-5)
Fix first, then freeze residuals PER-FINDING with individual justifications; seed baselines only post-fix; shrink-only afterwards; growth = STOP. Frozen logs clone `scripts/self_audit_frozen.md` format. `npm run check` (repo-A) green after EVERY commit.

### C-7. Convergence definition (the program's DoD core)
With v0.5.0 leaves (`--skills-root /home/jakub/projects/repo-audit-skills/skills`), K5 runs the full wave on each of the three repos **twice consecutively**: run 2 must show zero new findings vs each repo's baselines, zero accepted-mechanical work remaining, all repo-A gates green, suites green (repo-A 645+N, repo-B 79+M, repo-P 151+K). Two identical consecutive runs = converged.

### C-8. Versions & expected final numbers (record actuals)
| Item | Expected |
|---|---|
| repo-A | v0.5.0 (package.json + 16 SKILL.mds + check_release + installer + README + CHANGELOG); `npm run check` 9 green |
| repo-B | SKILL.md 0.4.0; 79+M tests green; `wave_baseline.json` seeded then K5-ratcheted (post-ratchet expect ≤5 entries, all justified) |
| repo-P | perf-benchmark 0.3.0, perf-optimization 0.2.0; 151+K green; `docs/perf/baseline_ledger.jsonl` ≥2 lines; verdict committed (win or honest no-win) |
| Run reports | v2 + validator-green in all three repos |
| Ship (K5-T4, authorized) | pushes + tags (A v0.5.0, B v0.4.0, P v0.3.0) + GitHub release(s) + CI green ×3 + reinstall + readback probe |

---

# TRACK K1 — repo-A leaf precision (AFTER Track G; worktree `../ras-sp9-k1`, branch `sp9/leaf-precision`)

In-branch gates after EVERY commit: owning leaf suite green (from repo root AND leaf dir), `python3 -m pytest --collect-only -q` zero errors, `npm run check` green (9 gates; `npm install` once in the worktree; line-pinned duplication swaps ratcheted same-commit per C-6 — K2's de-pinning lands only at K5 merge, so K1 lives with swaps).

### Task K1-T1 — docs-consistency: `--exclude-prefix` + placeholder skip
**Files:** Modify `skills/docs-consistency-audit/scripts/docs_consistency_audit.py` (locate `_in_scope`, `build_parser`, the dead-path token checker by grep); Test `skills/docs-consistency-audit/tests/test_exclude_and_placeholders.py` (new).
- [ ] RED: three tests on tmp fixture repos, in-process `mod.main([...])`: (a) `--exclude-prefix docs/history` silences a dead ref inside `docs/history/old.md` while a sibling `docs/live.md` dead ref still fires; (b) a token containing any of `<>{}$*` (e.g. `docs/audits/<run-id>/run_report.json`) is skipped with NO finding; (c) plain missing path still emits `doc_path_missing`. Run: `python3 -m pytest skills/docs-consistency-audit/tests/test_exclude_and_placeholders.py -q` → FAIL (unknown flag).
- [ ] GREEN, kernels:
```python
_PLACEHOLDER = re.compile(r"[<>{}*$]")
def _in_scope(rel, prefixes, excludes=()):
    ok = not prefixes or any(rel.startswith(p) for p in prefixes)
    return ok and not any(rel.startswith(e) for e in excludes)
# parser: --exclude-prefix, action="append", default=[]
# token checker: if _PLACEHOLDER.search(token): skipped += 1; continue
```
Thread `excludes` through `analyze_tree`; report gains `skipped_placeholder_tokens: N`. SKILL.md: flags + Limits (output-path refs need exclusion or freezing).
- [ ] Gates; commit `feat(docs-consistency-audit): --exclude-prefix + placeholder token skip (SP9 K1-T1)`.

### Task K1-T2 — hotspot: solo-author + own-test-pair suppression
**Files:** Modify `skills/hotspot-audit/scripts/_audit_knowledge.py`, `_audit_coupling.py`, `hotspot_audit.py:73-90` (call sites); Test `skills/hotspot-audit/tests/test_solo_author_and_test_pairs.py` (new; reuse the suite's existing git-fixture helpers).
- [ ] RED: (a) single-author fixture repo → zero `author_concentration` findings, and report notes `suppressed_solo_author: true`; (b) two-author fixture → findings unchanged; (c) co-changing pair `foo.py` + `tests/test_foo.py` → no `temporal_coupling` finding; unrelated co-changing pair still fires.
- [ ] GREEN, kernels:
```python
distinct = {a for per_file in authors.values() for a in per_file}   # hotspot_audit.py
knowledge = _knowledge_concentration(...) if len(distinct) > 1 else []
def _is_own_test_pair(a: str, b: str) -> bool:                      # _audit_coupling.py
    na, nb = PurePosixPath(a).name, PurePosixPath(b).name
    return nb == f"test_{na}" or na == f"test_{nb}"
```
- [ ] Gates; commit `feat(hotspot-audit): suppress solo-author + own-test-pair noise (SP9 K1-T2)`.

### Task K1-T3 — quality: format_drift only when a format standard is declared
**Files:** Modify `skills/quality-audit/scripts/quality_audit.py` (gate the `_ruff_format` call, line ~120); Test `skills/quality-audit/tests/test_format_config_gate.py` (new).
- [ ] RED: (a) fixture with drifted file, NO config → zero FORMAT findings, report notes `format_check: "skipped (no declared standard)"`; (b) same fixture + `pyproject.toml` containing `[tool.ruff]` → FORMAT finding fires; (c) `.ruff.toml` variant also fires.
- [ ] GREEN, kernel (string check; no tomllib dependency):
```python
def _format_config_declared(root: Path) -> bool:
    if any((root / n).is_file() for n in (".ruff.toml", "ruff.toml")):
        return True
    py = root / "pyproject.toml"
    return py.is_file() and ("[tool.ruff" in py.read_text(encoding="utf-8", errors="replace")
                             or "[tool.black" in py.read_text(encoding="utf-8", errors="replace"))
```
- [ ] Gates; commit `feat(quality-audit): config-gate format_drift (SP9 K1-T3)`.

### Task K1-T4 — dead-code: suppress vulture findings contradicted by tests
**Files:** Modify `skills/dead-code-audit/scripts/dead_code_audit.py` (`analyze_tree`, line ~188); Test `skills/dead-code-audit/tests/test_test_referenced_suppression.py` (new).
- [ ] RED: fixture where `helpers.py` defines `used_in_test()` (referenced only by `tests/test_helpers.py`) and `truly_dead()` (referenced nowhere) → exactly one DELETE (`truly_dead`), report notes `suppressed_test_referenced: 1`.
- [ ] GREEN, kernel (after `_vulture_findings`, before merge with ruff findings):
```python
def _test_referenced(symbols: set[str], root: Path, source_prefixes: list[str]) -> set[str]:
    dirs = {root / "tests"} | {root / PurePosixPath(p).parent / "tests" for p in source_prefixes}
    hits: set[str] = set()
    for d in dirs:
        if not d.is_dir(): continue
        for f in d.rglob("test_*.py"):
            text = f.read_text(encoding="utf-8", errors="replace")
            hits |= {s for s in symbols if s in text}
    return hits
```
Filter vulture (not ruff) findings whose `location.symbol` is hit; count in report. SKILL.md Limits: substring match is deliberately conservative (a comment mention suppresses — acceptable for an advisory DELETE).
- [ ] Gates; commit `feat(dead-code-audit): test-referenced vulture suppression (SP9 K1-T4)`.

### Task K1-T5 — test-effectiveness: clean ToolError on mutmut baseline failure
**Files:** Modify `skills/test-effectiveness-audit/scripts/_pipeline.py` (Phase 4 try/except); Test `skills/test-effectiveness-audit/tests/test_baseline_failure_tool_error.py` (new).
- [ ] RED: monkeypatch `subprocess.run` to raise `CalledProcessError(1, "mutmut", stderr="failed to collect stats")` → leaf exits **2** with JSON `{"status":"error", ...}` containing "mutmut run failed", NO traceback.
- [ ] GREEN, kernel:
```python
except subprocess.CalledProcessError as exc:
    tail = (exc.stderr or "")[-400:]
    raise ToolError(f"mutmut run failed (exit {exc.returncode}): {tail}") from None
```
SKILL.md Limits: suites that shell out to the code under test are not mutation-testable inside mutmut's sandbox (G1 evidence); the leaf now reports a clean tool error — prefer per-file unit suites as `--tests-dir`.
- [ ] Gates; commit `fix(test-effectiveness-audit): ToolError on mutmut baseline failure (SP9 K1-T5)`.

### Task K1-T6 — brevity for the five owned SKILL.mds + track report
- [ ] Apply C-2 to the 5 SKILL.mds (test-effectiveness 160 → ≤120 target; others already near budget — tighten, don't pad). `npm run check` green (docs gate proves refs).
- [ ] Commit `docs(skills): brevity pass, K1 leaves (SP9 K1-T6)`. Final K1 report: per-task evidence + line-count table + in-branch baseline swap log.

# TRACK K2 — repo-A ratchet hardening + brevity (AFTER Track G; worktree `../ras-sp9-k2`, branch `sp9/ratchet-brevity`)

Same per-commit gates as K1. Path partition per C-5.

### Task K2-T1 — de-line-pin duplication identities (content-hash symbols)
**Files:** Modify `scripts/self_audit.py` (`run()`, symbol normalization at line ~50); Modify `scripts/self_audit_baseline.json` (one-time migration) + `scripts/self_audit_frozen.md` (round-log note); Test `tests/test_self_audit_stable_identity.py` (new).
- [ ] RED: build a tmp fixture with a clone pair; snapshot; insert 3 lines ABOVE the clone in one file; snapshot again → the two duplication identities are IDENTICAL (today they differ). Also: change the clone's text itself → identity changes (hash is honest).
- [ ] GREEN, kernel (duplication findings only; all other leaves keep raw symbols):
```python
_TAIL = re.compile(r"(\S+):(\d+)-(\d+)$")
def _stable_symbol(root: Path, f: dict) -> str:
    if f["leaf"] != "duplication": return f["location"]["symbol"]
    sym = f["location"]["symbol"]; m = _TAIL.search(sym)
    if not m: return sym
    p = root / m.group(1)
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        frag = "\n".join(l.strip() for l in lines[int(m.group(2)) - 1 : int(m.group(3))])
    except OSError:
        return sym
    return f"{sym[: m.start(1)]}{m.group(1)}#{hashlib.sha256(frag.encode()).hexdigest()[:12]}"
```
- [ ] MIGRATE: run `python3 scripts/self_audit.py`; baseline count MUST be unchanged (same findings, new symbols — if count moves, STOP); replace duplication entries in `scripts/self_audit_baseline.json` with the new-form snapshot entries in the SAME commit; frozen-log round note "identity scheme v2: content-hash, line-shift-immune". `npm run check` green.
- [ ] Commit `feat(selfaudit): content-hash duplication identities + baseline migration (SP9 K2-T1)`.

### Task K2-T2 — coverage gate stale detection (symmetry)
**Files:** Modify `scripts/check_coverage_gap.py` (rewire the compare block onto `gate_common.identities`/`verdict` — gate_common exists post-G2-0; SUITES execution unchanged); Test `tests/test_check_coverage_gap_stale.py` (new, in-process `--snapshot`/`--baseline` style if flags exist, else factor the compare into a testable function).
- [ ] RED: stale baseline entry (in baseline, not in snapshot) → exit 1 with `stale_baseline` + "same commit" message naming `scripts/coverage_gap_baseline.json`; equality → exit 0; new finding → exit 1 `new_findings`.
- [ ] GREEN: replace the one-way subset check with `gate_common.verdict(current, baseline)`. Post-G3 baseline is 1 entry (`scripts/self_audit.py`) and should be non-stale — verify live: `npm run check:coverage` → pass.
- [ ] Commit `feat(coverage-gate): stale-baseline detection via gate_common (SP9 K2-T2)`.

### Task K2-T3 — security advisory runbook
**Files:** Modify `docs/self-audit/security.md` (exists post-G2-6).
- [ ] Add "Advisory mode (out-of-band)" section: produce the artifact offline (`pip-audit -f json -o /tmp/pip_audit.json` on a network-allowed machine), then `python3 skills/security-audit/scripts/security_audit.py --root . --out-dir <dir> <prefixes> --advisory-report /tmp/pip_audit.json`; advisory findings are diagnosis-only, NEVER enter the gate baseline (gate stays bandit-only/offline — SP8 rationale). Commit `docs(self-audit): pip-audit advisory runbook (SP9 K2-T3)`.

### Task K2-T4 — brevity: the 11 non-K1 SKILL.mds + README
- [ ] dependency-audit SKILL.md 295 → ≤140 (move algorithm detail to `skills/dependency-audit/docs/`); test-redundancy-triage 194 and test-quality-assurance 163 → ≤160 hard / ≤120 target; tighten the rest; README pass. Versions stay 0.4.0 (the bump is K5-T2's). All flags/exit codes/limits preserved per C-2.
- [ ] `npm run check` green; commit `docs(skills): brevity pass, remaining skills + README (SP9 K2-T4)`. Final K2 report: evidence + line-count table.

# TRACK K3 — repo-B orchestrator completion (launch NOW; repo-B main)

Suite gate after every commit: `python3 -m pytest tests/ -q` → 79 + new, zero failures.

### Task K3-T1 — decompose `check_skill_requirements.py` (backlog D1–D7)
**Files:** Create `scripts/_skill_probe.py` (skill-root scanning: `_skill_entry`, `_extract_skill_name`, root iteration), `scripts/_lane_resolve.py` (lane resolution, `load_source_overrides`), `scripts/_bootstrap_report.py` (`build_bootstrap_report` + writers); Modify `scripts/check_skill_requirements.py` (CLI + re-exports ONLY).
- [ ] Move code in three worker packets (one module each); after each move `check_skill_requirements.py` re-exports moved names (`from scripts._skill_probe import _skill_entry, _extract_skill_name  # noqa: F401`) so all 79 tests pass UNCHANGED. New unit tests per module (happy path + one edge each).
- [ ] Clear the findings where test-compatible: `_skill_entry` CC 12/nloc 65 → split decision helpers; `build_bootstrap_report` nloc 79/params 9 → extract section builders; signatures the 79 tests call directly stay intact — a residual finding that would require breaking them goes to the wave baseline with justification (C-6).
- [ ] VERIFY: `python3 ~/.claude/skills/code-health-audit-pipeline/scripts/code_health_pipeline.py --root . --out-dir /tmp/sp9-k3-t1 --source-prefix scripts` → D1–D7 loci clear (record residuals). Commit per module move, then `refactor(bootstrap): decompose checker, D1-D7 cleared (SP9 K3-T1)`.

### Task K3-T2 — `scripts/validate_run_report.py` (B4 v2, fail-closed)
**Files:** Create script (<120 lines) + `tests/test_validate_run_report.py`.
- [ ] RED: valid v2 dir → exit 0; missing key → exit 1 listing it; `backlog` missing `wont_fix` under `--schema 2` → exit 1; `--schema 1` accepts 3-key backlog; missing `run_report.md` → exit 1.
- [ ] GREEN, kernel:
```python
KEYS = ["schema_version","repo_root","started_utc","finished_utc","orchestrator_skill_version",
        "lanes","findings_totals","backlog","batches","verification","warnings"]
BACKLOG = {1: {"accepted","deferred","coverage_gated"}, 2: {"accepted","deferred","coverage_gated","wont_fix"}}
# argparse: --run-dir, --schema {1,2} default 2; checks run_report.json keys + backlog keys + run_report.md exists; prints JSON verdict.
```
- [ ] Commit `feat(verify): run-report v2 validator (SP9 K3-T2)`.

### Task K3-T3 — `scripts/run_diagnosis_wave.py` (one-command wave)
**Files:** Create script (<250 lines) + `tests/test_run_diagnosis_wave.py` (stub leaves in tmp skills-root).
- [ ] Interface: `--repo R --out-dir O --skills-root ROOT [--source-prefix P]... [--coverage-json PATH] [--rev SHA] [--lanes csv]`. Lane table:
```python
LANES = {  # leaf relative to --skills-root; scope: prefixes|none|living-docs|rev
  "code-health": ("code-health-audit-pipeline/scripts/code_health_pipeline.py", "prefixes"),
  "security":    ("security-audit/scripts/security_audit.py",                   "prefixes"),
  "hygiene":     ("repo-hygiene-audit/scripts/repo_hygiene_audit.py",           "none"),
  "docs":        ("docs-consistency-audit/scripts/docs_consistency_audit.py",   "living-docs"),
  "dependency":  ("dependency-audit/scripts/dependency_audit.py",               "prefixes"),
  "hotspot":     ("hotspot-audit/scripts/hotspot_audit.py",                     "rev"),
}
```
living-docs default scope = `README.md SKILL.md CHANGELOG.md references docs agents scripts` minus `docs/audits docs/dogfood docs/plans` (passes `--exclude-prefix` when the installed leaf supports it — probe `--help`; else falls back to enumerated includes). Coverage passthrough: `--coverage-json` handed to code-health. Disjoint `O/<lane>/` out-dirs; merged normalized findings → `O/wave_findings.json` (4-key dicts `{leaf,path,symbol,metric}`); `O/wave_summary.json` = `{lane: {exit, findings}}`. Leaf exit 2 → lane recorded `"error"`, wave exit 1.
- [ ] Tests: stub skills-root with two fake leaves writing fixed findings JSON → summary/merge/exit semantics verified in-process.
- [ ] SKILL.md + `references/pipeline.md`: wave runner replaces the hand-built H1-style wave for deterministic lanes. Commit `feat(wave): one-command diagnosis wave runner (SP9 K3-T3)`.

### Task K3-T4 — taxonomy v2, run-report v2 docs, docs-repair procedure, brevity
**Files:** Modify `references/prioritization.md` (+WON'T-FIX/FP class, per-row justification mandatory), `references/pipeline.md` (Run Report v2: `schema_version: 2`, `backlog.wont_fix`, validator step `python3 scripts/validate_run_report.py --run-dir ...`), `references/remediation-playbook.md` (+"Docs repair": correct real-target refs; delete dead refs; placeholder/output-path → won't-fix justify; immutable records → exclude via scope, never edit), `references/verification.md` (validator is the B4 authority), `SKILL.md` (wave runner step; version 0.4.0), `CHANGELOG.md`.
- [ ] Brevity per C-2 across SKILL.md + references. Suite green. Commit `docs(orchestrator): taxonomy v2 + run-report v2 + docs-repair + brevity, v0.4.0 (SP9 K3-T4)`.

### Task K3-T5 — repo-B convergence gate
**Files:** Create `scripts/check_wave_baseline.py` + `scripts/wave_baseline.json` + `scripts/wave_frozen.md` + `tests/test_check_wave_baseline.py`.
- [ ] Canonical script (~55 lines; K4 implements the same from this spec — per-repo copies are the family architecture):
```python
#!/usr/bin/env python3
"""Convergence gate: diagnosis wave on this repo, equality-ratcheted against wave_baseline.json."""
import argparse, json, os, subprocess, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name("wave_baseline.json")
def identities(fs): return {tuple(sorted(d.items())) for d in fs}
def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot"); ap.add_argument("--baseline")
    a = ap.parse_args(argv)
    if a.snapshot: current = json.loads(Path(a.snapshot).read_text())
    else:
        runner = os.environ.get("WAVE_RUNNER", str(Path.home() / ".claude/skills/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py"))
        out = REPO / ".wave_out"
        subprocess.run([sys.executable, runner, "--repo", str(REPO), "--out-dir", str(out),
                        "--skills-root", os.environ.get("SKILLS_ROOT", str(Path.home() / ".claude/skills")),
                        "--source-prefix", "scripts"], check=False)
        current = json.loads((out / "wave_findings.json").read_text())
    baseline = json.loads(Path(a.baseline or BASELINE).read_text())
    cur, base = identities(current), identities(baseline)
    new, stale = cur - base, base - cur
    if new: print(json.dumps({"status": "fail", "new_findings": sorted(map(list, new))}, indent=2)); return 1
    if stale:
        print(json.dumps({"status": "fail", "stale_baseline": sorted(map(list, stale)),
                          "message": f"ratchet: remove them from {BASELINE.name} in the same commit"}, indent=2)); return 1
    print(json.dumps({"status": "pass", "count": len(cur), "baseline": len(base)}, indent=2)); return 0
if __name__ == "__main__": sys.exit(main())
```
(repo-P variant: `--source-prefix scripts --source-prefix perf-optimization/scripts`.) Tests: in-process `--snapshot`/`--baseline` tmp files — equality pass / new fail / stale fail (clone of repo-A's gate-test pattern).
- [ ] SEED: run live with `WAVE_RUNNER=$PWD/scripts/run_diagnosis_wave.py SKILLS_ROOT=~/.claude/skills`; fix anything mechanical the K3-T1 decomposition left; freeze residuals per-finding in `wave_frozen.md` (expected: 3 output-path docs refs W3–W5; format_drift and vulture FPs while installed leaves are 0.4.0 — mark `expires: v0.5.0 reinstall` so K5's ratchet removes them); commit baseline + gate.
- [ ] `.gitignore` += `.wave_out/`. Run report v2 for the whole K3 run at `docs/audits/<ts>/run_report.{json,md}`, validator-green. Commit `feat(gate): wave convergence baseline (SP9 K3-T5)`.

# TRACK K4 — repo-P self-audit + first perf-lane exercise + parity (launch NOW; repo-P main)

Suite gate: `python3 -m pytest -q` → 151 + new green after every commit. `RUN=docs/audits/$(date -u +%Y%m%dT%H%M%SZ)`, one timestamp for the track.

### Task K4-T1 — bootstrap probe + diagnosis wave (absorbs SP8 P0–P1)
- [ ] `python3 ~/.claude/skills/repo-audit-refactor-optimize/scripts/check_skill_requirements.py --repo /home/jakub/projects/perf-benchmark-skill --out-dir /home/jakub/projects/perf-benchmark-skill/$RUN --extra-root ~/.claude/skills` — performance lane expected ≠ manual (benchmark surface exists); record verbatim; commit.
- [ ] Coverage artifact: `python3 -m pytest -q --cov=scripts --cov=perf-optimization/scripts --cov-report=json:/tmp/sp9-k4/coverage.json`. Lanes (installed 0.4.0 leaves): umbrella `--coverage-json /tmp/sp9-k4/coverage.json --source-prefix scripts --source-prefix perf-optimization/scripts`; security + dependency same prefixes; hygiene unprefixed; docs prefixes `README.md SKILL.md references docs perf-optimization/SKILL.md perf-optimization/references scripts perf-optimization/scripts`; hotspot `--rev $(git rev-parse HEAD) --max-commits 500`. Dependency: pyproject has NO `[project]` — record actual `manifest` semantics verbatim (genuine leaf edge-case evidence; do NOT fix the leaf here, note for K5 report).
- [ ] Triage into `$RUN/backlog.md` with the C-3 four classes, playbook rule cited per row (expect hotspot solo-author + possible format/vulture FPs while leaves are 0.4.0 → won't-fix with `expires: v0.5.0`). Commit.

### Task K4-T2 — perf baseline (absorbs SP8 P2)
- [ ] `python3 scripts/perf_benchmark_pipeline.py --root . --out-dir $RUN/perf-before --target "python3 benchmarks/bench_parse_massif.py {SIZE}" --tier fast --sizes 1000,4000,16000 --expected-complexity linear --max-cv 5.0 --baseline-ledger docs/perf/baseline_ledger.jsonl --findings-out $RUN/perf-before/perf_findings.json` — exit 0; ledger line 1 created; CV>5% → one re-run, then record `N/A (noise)` honestly. Commit artifacts + ledger.

### Task K4-T3 — ONE bounded optimization attempt (absorbs SP8 P3)
- [ ] `python3 perf-optimization/scripts/select_candidate.py --findings $RUN/perf-before/perf_findings.json --out $RUN/opt/candidate.json` — STOP-gate/empty refusal = valid "no candidate", record verbatim and skip to K4-T4. If candidate: ONE revertable change commit per the optimization playbook; identical re-measure into `$RUN/perf-after`; `python3 -m pytest -q` exit recorded; `verify_win.py --before ... --after ... --suite-exit-code N --ledger docs/perf/baseline_ledger.jsonl --out $RUN/opt/verdict.json`; accept → keep, reject → `git revert` (keep evidence). SP6/SP8 precedent: honest no-win is LIKELY and fine.

### Task K4-T4 — mechanical fixes + convergence gate (depends on K3-T3, pre-flight row 8)
- [ ] Apply ONLY mechanical lint-class fixes from the backlog; suite green after each batch.
- [ ] Create `scripts/check_wave_baseline.py` from the K3-T5 canonical spec (prefixes `scripts` + `perf-optimization/scripts`) + tests + seed `scripts/wave_baseline.json`/`wave_frozen.md` per C-6 (`WAVE_RUNNER=/home/jakub/projects/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py`). `.gitignore` += `.wave_out/`. Commit.

### Task K4-T5 — brevity + versions + run report
- [ ] Brevity per C-2: `perf-optimization/SKILL.md` 357 → ≤160 (move playbook detail into `perf-optimization/references/`), root `SKILL.md` 244 → ≤160, `references/sample-report.md` 296 → ≤80 (minimal real example), tool-guide tighten. Suite + ruff green.
- [ ] Versions: root SKILL.md 0.3.0, perf-optimization/SKILL.md 0.2.0, CHANGELOGs. Run report v2 at `$RUN/run_report.{json,md}` (validate against the C-3 key list manually if repo-B's validator isn't reachable; K5 re-validates). Commit. Final K4 report: lane artifacts, ledger lines, verdict, line-count table.

# TRACK K5 — integration, convergence proof, SHIP (serial; AFTER G + K1–K4)

### Task K5-T1 — merge into repo-A main (ORDER MATTERS: K2 first)
- [ ] Pre-flight: G complete (9 gates green on main), K1/K2 branches green in their worktrees, K3/K4 committed.
- [ ] Merge `sp9/ratchet-brevity` (`--no-ff`): content-hash identities + migrated baseline land first. Full gates: `npm run check` 9 green, collect-only zero errors.
- [ ] Merge `sp9/leaf-precision` (`--no-ff`): K1's in-branch line-pinned baseline swaps will conflict with K2's migrated baseline — resolve by REGENERATION: take the merge tree, run `python3 scripts/self_audit.py`, and reconcile baseline to equality in the merge commit, allowing ONLY hash-swaps of existing pairs (count growth or a genuinely new finding = STOP). Full gates green. Remove both worktrees, keep branches.

### Task K5-T2 — repo-A release v0.5.0
- [ ] Bump package.json + all 16 SKILL.mds to 0.5.0; `scripts/check_release.py` expectations; installer + README + CHANGELOG (new flags: docs `--exclude-prefix`, suppression counters, identity scheme v2, coverage stale detection). `npm run check` 9 green; `node bin/install-repo-audit-skills.js --list` → 16 @ 0.5.0. Commit `release: v0.5.0 — leaf precision + ratchet hardening (SP9)`.

### Task K5-T3 — convergence proof (C-7) + baseline ratchets
- [ ] With `SKILLS_ROOT=/home/jakub/projects/repo-audit-skills/skills` and `WAVE_RUNNER=/home/jakub/projects/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py`:
  - repo-A: `npm run check` (9 gates) + wave run → all green/equality.
  - repo-B + repo-P: `python3 scripts/check_wave_baseline.py` → expect STALE failures where 0.4.0-era FP freezes (`expires: v0.5.0`) dissolved → ratchet baselines DOWN same-commit (this shrink is the precision fixes proving themselves). Then run 2 of everything: zero deltas everywhere = CONVERGED. Any growth = STOP.
- [ ] Commit ratchets + a v2 run report in each repo (`validate_run_report.py` green ×3).

### Task K5-T4 — SHIP (human-gated; the ONLY push authority in SP9)
- [ ] Present the evidence table (C-8 actuals, convergence outputs, suite counts) and STOP for explicit authorization.
- [ ] On authorization: repo-A `git push origin main && git tag v0.5.0 && git push origin v0.5.0` + `gh release create v0.5.0 --title "v0.5.0" --notes-file <(CHANGELOG excerpt)`; repo-B push + tag v0.4.0; repo-P push + tag v0.3.0. Watch CI on all three (`gh run list/watch`) → green.
- [ ] Reinstall: repo-A via `node bin/install-repo-audit-skills.js` (then `--list` readback 16 @ 0.5.0); repo-B + repo-P via `rsync -a --delete` into `~/.claude/skills/{repo-audit-refactor-optimize,perf-benchmark,perf-optimization}/`. Readback probe: bootstrap checker against repo-B with `--extra-root ~/.claude/skills` → lanes as recorded. Optional, separately authorized: stale-skill purge per the B2 unreferenced-skills advisory (60 entries recorded in SP8 H0).

### Task K5-T5 — final report
- [ ] `docs/self-audit/2026-06-sp9-production-run.md` in repo-A: per-track evidence, C-8 actuals, convergence proof outputs, brevity tables, freeze ledger (zero unjustified). Commit. **SP9 DoD below.**

---

## Schedule & global Definition of Done

```
now:        K3 (repo-B)        K4 (repo-P)          [G still finishing repo-A]
after G:    K1 (repo-A wt)  ∥  K2 (repo-A wt)
last:       K5 serial: merge → v0.5.0 → converge ×2 → SHIP (human-gated) → report
```

1. Five FP classes fixed with two-direction regression tests; suppressions counted, never silent (C-1).
2. Duplication identities line-shift-immune; coverage gate symmetric; baselines migrated count-neutral (K2).
3. Orchestrator: D1–D7 cleared (or justified), wave runner + validator + 4-class taxonomy + docs-repair procedure live, v0.4.0 (K3).
4. repo-P: probe + diagnosis + ledger + select/verify verdict (win or honest no-win) + gate + v0.3.0/v0.2.0 (K4).
5. Convergence per C-7: two identical consecutive full runs across all three repos, all gates green, zero unjustified freezes.
6. Brevity: every SKILL.md ≤160 lines, zero contract loss, before/after tables in reports (C-2).
7. Ship executed ONLY after explicit human authorization: pushes, tags, release, CI green ×3, reinstall + readback (K5-T4).
8. Run reports v2 + validator-green in all three repos; memory/status updated.

---

# Launch blocks (paste ONE per fresh Codex gpt-5.5 session)

## Launch K3 — repo-B orchestrator completion (launchable NOW)

```
You are the ORCHESTRATOR (Codex gpt-5.5) for SP9 TRACK K3 in /home/jakub/projects/repo-audit-refactor-optimize (repo-B, main — you own this repo ONLY; zero shared writes with other tracks). Coordinate ONLY, never implement. Workers: native Codex Spark subagents (100k context) — packets per plan C-4: one goal, ≤2 files, file content inlined (≤200 lines full, else grep-anchored excerpts), failing test included, ≤8k tokens. A worker's green is NOT evidence — re-run gates yourself. READ FIRST, authoritative: /home/jakub/projects/repo-audit-refactor-optimize/docs/plans/2026-06-11-sp9-production-readiness.md — pre-flight rows 1/6/7, Contracts C-1..C-8, Tasks K3-T1..T5. PRE-FLIGHT (failure -> STOP): git status clean (plan commit may be HEAD); python3 -m pytest tests/ -q -> 79 passed. ORDER: T1 decompose check_skill_requirements.py into _skill_probe/_lane_resolve/_bootstrap_report with re-exports keeping all 79 tests UNCHANGED-green, clear backlog D1-D7 (testable-signature residuals -> wave baseline justified) -> T2 validate_run_report.py (schema v2: backlog gains wont_fix) TDD -> T3 run_diagnosis_wave.py per the plan's lane table + living-docs scope + wave_findings.json/wave_summary.json, stub-leaf tests -> T4 prioritization taxonomy v2 + pipeline Run Report v2 + docs-repair playbook + brevity (SKILL.md <=160 lines, no contract loss) + SKILL.md v0.4.0 -> T5 check_wave_baseline.py (plan's canonical script) + seed wave_baseline.json per C-6 (0.4.0-era FP freezes marked expires: v0.5.0) + v2 run report validator-green. HARD RULES: suite green after EVERY commit; commit per task; write ONLY in this repo; DO NOT push. Final report: per-task evidence, line-count table, baseline + frozen-log contents.
```

## Launch K4 — repo-P self-audit + perf lane + parity (launchable NOW)

```
You are the ORCHESTRATOR (Codex gpt-5.5) for SP9 TRACK K4 in /home/jakub/projects/perf-benchmark-skill (repo-P, main — you own this repo ONLY; zero shared writes). Coordinate ONLY, never implement. Workers: native Codex Spark subagents per plan C-4 (≤2 files, inlined content, ≤8k tokens). Re-run all gates yourself. Valgrind ABSENT: --tier fast ONLY. READ FIRST, authoritative: /home/jakub/projects/repo-audit-refactor-optimize/docs/plans/2026-06-11-sp9-production-readiness.md — pre-flight row 8, Contracts C-1..C-8, Tasks K4-T1..T5; also perf-optimization/references/optimization-playbook.md. PRE-FLIGHT (failure -> STOP): git status clean; rev-parse HEAD expect ceff6b7; python3 -m pytest -q -> 151 passed; benchmarks/bench_parse_massif.py exists. ORDER: T1 bootstrap probe + diagnosis wave (installed 0.4.0 leaves; prefixes scripts + perf-optimization/scripts; dependency lane: pyproject has NO [project] — record actual manifest semantics verbatim, do NOT fix the leaf) + 4-class triage backlog (0.4.0-era FPs -> wont-fix expires: v0.5.0) -> T2 perf baseline per the plan's exact command (ledger docs/perf/baseline_ledger.jsonl) -> T3 ONE bounded optimization attempt (select_candidate STOP/refusal = valid no-candidate; verify_win is the only win authority; reject -> git revert keeping evidence) -> T4 mechanical fixes only + check_wave_baseline.py from the plan's canonical spec (WAVE_RUNNER=/home/jakub/projects/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py; if not yet committed by K3, poll its git log every 30 min, STOP after 2h) + seed baselines per C-6 -> T5 brevity (perf-optimization SKILL.md 357->160, root 244->160, sample-report 296->80; no contract loss) + versions 0.3.0/0.2.0 + v2 run report. HARD RULES: 151+new green after every commit; ONE optimization attempt max; never fabricate a win; commit per task; DO NOT push. Final report: lane artifacts, ledger lines, candidate+verdict, line-count table.
```

## Launch K1 — repo-A leaf precision (ONLY after SP8 Track G completes)

```
You are the ORCHESTRATOR (Codex gpt-5.5) for SP9 TRACK K1. Workspace: create worktree ../ras-sp9-k1 branch sp9/leaf-precision from repo-A main (/home/jakub/projects/repo-audit-skills); you may touch ONLY skills/{docs-consistency,hotspot,quality,dead-code,test-effectiveness}-audit/** plus same-commit ratchet swaps in scripts/self_audit_baseline.json + scripts/self_audit_frozen.md. Track K2 edits OTHER paths in its own worktree — zero shared writes. Coordinate ONLY; workers = native Codex Spark subagents per plan C-4 (≤2 files, inlined content, ≤8k tokens). Re-run all gates yourself. READ FIRST, authoritative: /home/jakub/projects/repo-audit-refactor-optimize/docs/plans/2026-06-11-sp9-production-readiness.md — pre-flight row 2, Contracts C-1/C-2/C-4/C-5/C-6, Tasks K1-T1..T6. PRE-FLIGHT (failure -> STOP): SP8 Track G COMPLETE on main (docs/audits/20260611T062217Z/run_report.json exists AND npm run check -> 9 passes — grep the printed gate JSON, never a piped exit code); record post-G HEAD; npm install in the worktree; python3 -m pytest --collect-only -q zero errors. ORDER (TDD, one commit per task, npm run check green after EVERY commit): T1 docs-consistency --exclude-prefix + placeholder-token skip (kernels in plan) -> T2 hotspot solo-author + own-test-pair suppression -> T3 quality format_drift config-gate -> T4 dead-code test-referenced vulture suppression -> T5 test-effectiveness ToolError on mutmut CalledProcessError -> T6 brevity for the five owned SKILL.mds (<=160/<=120 lines, no contract loss). Every suppression is COUNTED in the leaf report, never silent (C-1); each fix has both-direction regression tests (FP gone, true positive still fires). Duplication baseline entries are LINE-PINNED in this branch — any clone-pair file edit = stale+new swap ratcheted in the SAME commit. HARD RULES: leaf SKILL.md versions stay 0.4.0 (K5 bumps); DO NOT push; keep branch + worktree for K5. Final report: per-task evidence, suppression-counter outputs, line-count table, swap log.
```

## Launch K2 — repo-A ratchet hardening + brevity (ONLY after SP8 Track G completes)

```
You are the ORCHESTRATOR (Codex gpt-5.5) for SP9 TRACK K2. Workspace: create worktree ../ras-sp9-k2 branch sp9/ratchet-brevity from repo-A main (/home/jakub/projects/repo-audit-skills); you may touch scripts/**, shared/**, docs/self-audit/**, README.md, and the 11 SKILL.mds NOT in K1's five leaves; FORBIDDEN: skills/{docs-consistency,hotspot,quality,dead-code,test-effectiveness}-audit/**. Coordinate ONLY; workers = native Codex Spark subagents per plan C-4. Re-run all gates yourself. READ FIRST, authoritative: /home/jakub/projects/repo-audit-refactor-optimize/docs/plans/2026-06-11-sp9-production-readiness.md — pre-flight rows 3/4/5, Contracts C-2/C-5/C-6, Tasks K2-T1..T4. PRE-FLIGHT (failure -> STOP): SP8 Track G COMPLETE (run_report.json exists AND npm run check -> 9 passes, grep gate JSON); npm install in worktree; collect-only zero errors. ORDER (TDD, one commit per task, npm run check green after EVERY commit): T1 content-hash duplication identities in scripts/self_audit.py (kernel in plan) + COUNT-NEUTRAL baseline migration in the SAME commit (count moves -> STOP) + frozen-log round note -> T2 coverage-gate stale detection rewired onto gate_common.verdict (check_self_audit tests stay untouched) -> T3 pip-audit advisory runbook section in docs/self-audit/security.md (gate stays bandit-only) -> T4 brevity: dependency-audit SKILL.md 295->140, test-redundancy-triage 194 + test-quality-assurance 163 -> <=160/<=120, remaining SKILL.mds + README tightened; every flag/exit-code/limit preserved (C-2); check:docs green proves refs. HARD RULES: versions stay 0.4.0 (K5 bumps); DO NOT push; keep branch + worktree for K5. Final report: per-task evidence, identity-migration diff stats, line-count table.
```

## Launch K5 — integration, convergence, SHIP (serial, LAST)

```
You are the ORCHESTRATOR (Codex gpt-5.5) for SP9 TRACK K5 — integration + convergence + ship across /home/jakub/projects/{repo-audit-skills,repo-audit-refactor-optimize,perf-benchmark-skill}. You run ALONE (G, K1-K4 all complete and idle) and are the ONLY SP9 session allowed to push — and only at T4 after EXPLICIT human authorization in-session. Coordinate ONLY for code work; you may run gates/merges/releases directly. READ FIRST, authoritative: /home/jakub/projects/repo-audit-refactor-optimize/docs/plans/2026-06-11-sp9-production-readiness.md — Contracts C-6/C-7/C-8, Tasks K5-T1..T5. PRE-FLIGHT (failure -> STOP): SP8 G run report on repo-A main + 9 gates green; sp9/ratchet-brevity + sp9/leaf-precision green in their worktrees; K3/K4 final commits present; all suites green. ORDER: T1 merge sp9/ratchet-brevity FIRST then sp9/leaf-precision (--no-ff; resolve baseline conflicts by REGENERATION: run scripts/self_audit.py on the merge tree, reconcile to equality allowing only hash-swaps of existing pairs; count growth or new finding = STOP); full gates after each merge -> T2 release v0.5.0 (package.json + 16 SKILL.mds + check_release + installer + README + CHANGELOG; npm run check 9 green; installer --list 16 @ 0.5.0) -> T3 convergence per C-7: SKILLS_ROOT=/home/jakub/projects/repo-audit-skills/skills WAVE_RUNNER=/home/jakub/projects/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py; repo-A 9 gates + wave; repo-B/P check_wave_baseline.py -> ratchet dissolved expires-v0.5.0 freezes DOWN same-commit; run everything a SECOND time -> zero deltas everywhere or STOP -> T4 SHIP: present C-8 actuals table and STOP for explicit human authorization; then push+tag (A v0.5.0, B v0.4.0, P v0.3.0) + gh release + CI green x3 + reinstall (repo-A installer; B/P rsync) + readback probe; stale-skill purge ONLY if separately authorized -> T5 final report docs/self-audit/2026-06-sp9-production-run.md in repo-A. HARD RULES: nothing is pushed before the human says so, verbatim; never trust a piped exit code — grep gate JSON; baselines shrink-only. Final report: C-8 actuals, convergence outputs, freeze ledger zero-unjustified.
```

## Status notes (2026-06-11, plan time)

- SP8 Track G in flight at G2-0 (commits `3d0af2d`, `138d068`); this plan deliberately lives in repo-B so repo-A stays untouched until G finishes. Tracks H complete (`1e33e89`), P never launched (absorbed here as K4).
- K3/K4 diagnosis intentionally uses the installed 0.4.0 leaves: their known FPs are frozen with `expires: v0.5.0` justifications, and K5-T3's ratchet-down after the v0.5.0 build is the designed demonstration that the precision fixes work.
- The opencode bridge port-collision lesson (SP8-H deviation 1) does not apply to SP9 (native Spark workers, no bridge), but stands for any future bridge-backed sprint: unique `--port` per concurrent track.
