# Phase 2 · B1 — `coverage-gap` into the full pass (testedness convergence across the family)

**Status:** design (brainstorming output) · **Date:** 2026-06-15 · **Branch:** `feat/phase2-b1` (per repo)
**Campaign:** Self-Contained Convergent Skill Family — Phase 2, Tier-2 item B1
**Roadmap home:** `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md` §"Phase 2"
**Launch protocol:** `docs/superpowers/PHASE2-TIER2-LAUNCH-PROMPT.md` §3 (B1 scope & DONE)

---

## 1. Why B1 exists

B0 brought the family's own audit under budget (repo-A `npm run check` 371→181 s). Phase 2
now layers the slow / artifact **Tier-2** lanes onto the family as a self-application campaign.
B1 is the first such lane: **`coverage-gap-audit`** — the deterministic, advisory answer to *"is
this file safe to refactor / well-tested?"*. It consumes a `coverage.py` JSON report and emits a
`TEST` finding for every production `.py` file whose statement coverage is **≤ 50 %**
(`min_file_coverage`, the leaf default; 0 % → `high`, else `medium`).

B1's job is to make that lane **run against all three family repos and converge** — every genuine
testedness gap either closed (tests added) or justified-accepted, with `active 0` and no stale
acceptances — and to record the reproducible recipe + evidence so B4 can later decide whether the
now-cheap lane graduates into the binary convergence gate.

---

## 2. Measured finding inventory (the data that drives the design)

Measured 2026-06-15 on this machine (py3.14.4, coverage 7.14.1), each repo's suite run under
`coverage`, the JSON fed to the leaf at each repo's production scope. **Subprocess-capture
coverage was used** (see §4) — without it the numbers lie (see §4.1).

| repo | leaf scope (`--source-prefix`) | coverage source | coverage-gap findings |
|------|-------------------------------|-----------------|-----------------------|
| **repo-A** | `shared`, `scripts`, `skills/<name>/scripts` (the gate's `_prefixes()`) | gate-produced `.self_audit_out/coverage/coverage.json` | **0** — already gated + converged (`check_coverage_gap.py` → `{"status":"pass","count":0,"baseline":0}`) |
| **repo-B** | `scripts` | suite under `coverage` (290 tests, ~7 s) | **1**: `scripts/run_instruction_eval.py` **33.3 %** (22/66) |
| **repo-P** | `scripts`, `perf-optimization/scripts` | suite under subprocess-capture `coverage` (166 tests, ~10 s) | **1**: `scripts/perf_benchmark/findings.py` **47.5 %** (38/80) |

Both repo-B and repo-P findings are **genuine, easily-closeable gaps** in pure, deterministic,
stdlib-only modules — not measurement artifacts, not model-dependent, not subprocess-hidden:

- **`scripts/run_instruction_eval.py`** (repo-B) — an *advisory instruction-eval scorer* that,
  despite the name, **does not call any LLM** (it scores a pre-captured findings count against a
  baseline; module docstring: *"This module is pure and deterministic. It does NOT call any
  LLM."*). The existing `test_run_instruction_eval.py` covers only `score_eval` + `advisory_outputs`.
  Uncovered: `_load_expected` (int / file-int / file-dict / error branches), `_load_model_findings`
  (valid / missing / non-array), `_build_parser`, and `main` (happy path + malformed-input exit 2).
  All pure functions over temp JSON files — closeable to ~90 %+.
- **`scripts/perf_benchmark/findings.py`** (repo-P) — the *PERF findings bridge* converting a
  rubric dict to shared-schema findings. Pure, stdlib-only. The existing `test_findings_bridge.py`
  covers `to_shared_findings` for the explicit-metric path only. Uncovered: the seven `_extract_*`
  handlers (`_extract_wall_time` / `_cpu` / `_cache` / `_ll_cache` / `_branch` / `_algorithmic` /
  `_memory`), `_build_finding`'s FAIL-vs-WARN severity branch, and `_suggested_action`'s
  prescription-prefix matching. All pure functions over rubric dicts — closeable to ~90 %+.

---

## 3. Goal & success criteria (falsifiable)

B1 is **converge-the-lane**. DONE when **all** of:

1. The `coverage-gap` lane has been run against **all three** repos at the correct production
   scope, from a green suite, and the **post-fix finding set is empty** for every repo
   (`active 0`, no accept entries needed → trivially no stale).
2. Both genuine gaps are **closed by added behaviour tests** (repo-B `run_instruction_eval.py`,
   repo-P `findings.py`), each lifting the file **well above** the 50 % threshold (target ≥ 80 %,
   so the file does not flicker at the boundary). New tests pass in **real CI** for each repo.
3. repo-A is **verified** still at 0 coverage-gap findings via its real gate (no change expected).
4. A **reproducible coverage recipe** (exact commands, incl. the subprocess-capture harness) and
   the before/after evidence are committed to `docs/superpowers/b1-evidence/` (repo-B).
5. Memory updated; proceed to B2. (Gate **wiring** for repo-B/repo-P is explicitly **out of B1** —
   it is B4's graduation decision; see §6.)

**Non-goal / explicit no-op:** repo-A needs no change (already 0 + gated). No version bump or
release is expected from B1 (see §7).

---

## 4. Coverage methodology — subprocess capture is mandatory (the load-bearing decision)

The coverage-gap leaf trusts the `coverage.json` it is given. If the report under-counts, the leaf
emits **false** TEST findings. The family's CLIs are heavily **subprocess-tested** (a test invokes
`python3 <script.py> …` and asserts on stdout/exit), and a plain `coverage run -m pytest` only
instruments the **parent** process — so subprocess-only-tested code shows as **0 %** even when it is
thoroughly exercised.

**4.1 Evidence that this matters (repo-P, measured):**

| file | plain `coverage run` | subprocess-capture | reality |
|------|----------------------|--------------------|---------|
| `perf-optimization/scripts/verify_win.py` | **0.0 %** (false gap) | **96.3 %** | CLI-tested via subprocess in `test_verify_win.py` |
| `perf-optimization/scripts/select_candidate.py` | 39.8 % (false gap) | **95.9 %** | subprocess + in-process tested |
| `scripts/perf_benchmark/findings.py` | 47.5 % | **47.5 %** | imported in-process — number is honest both ways (the **one real** gap) |

Plain coverage reports **3** repo-P findings, two of them false. Subprocess capture reports the **1**
true finding. **B1 uses subprocess capture for the honest number.**

**4.2 The recipe (committed as the reproducible B1 coverage harness):**

```bash
# one-time hook so subprocesses start coverage (sitecustomize on PYTHONPATH)
mkdir -p "$HOOK"; printf 'import coverage\ncoverage.process_startup()\n' > "$HOOK/sitecustomize.py"
cat > "$RC" <<'RC'
[run]
parallel = true            # parent + each subprocess writes its own .coverage.* shard
data_file = <abs>/.coverage
[report]
ignore_errors = true       # skip out-of-scope files coverage can't decode (e.g. C/bin fixtures)
RC
export PYTHONPATH="$HOOK:$PYTHONPATH" COVERAGE_PROCESS_START="$RC"
python3 -m coverage run  --rcfile="$RC" -m pytest <suite dirs> -q -p no:cacheprovider
python3 -m coverage combine --rcfile="$RC"
python3 -m coverage json --rcfile="$RC" --data-file=<abs>/.coverage -o coverage.json
python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root <repo> <--source-prefix …> --coverage-json coverage.json --out-dir <out>
```

Notes that bit during measurement and must stay in the recipe:
- `ignore_errors = true` is required — without it `coverage json` aborts on a non-UTF-8
  *out-of-scope* file a subprocess happened to touch (a perf-benchmark fixture), even though that
  file is outside the audited scope.
- Tests must inherit the parent env (`subprocess.run(..., )` with **no** `env=` override) for the
  hook to propagate — verified true for repo-P's `test_verify_win.py` / `test_select_candidate.py`.
- `--source-prefix` must name the **production** dirs precisely (repo-A's gate uses `_prefixes()`:
  `shared`, `scripts`, `skills/<name>/scripts`). A too-broad prefix (e.g. bare `skills`) sweeps in
  `tests/` and yields a flood of false findings (observed: 183 on repo-A vs the true 0).

---

## 5. Convergence strategy — **close, don't accept** (and why)

For each genuine finding the options are (a) close the gap with tests, or (b) justify-accept it.
**B1 closes both.** Rationale:

1. **Both gaps are in pure, deterministic modules** — real unit tests are cheap, valuable, and
   exactly the campaign's stated goal ("genuine gaps closed or justified-accepted"; closing is the
   stronger outcome and improves real test quality).
2. **Closing yields the clean terminal state**: 0 findings on all three repos ⇒ `active 0` and —
   because no accept entries are added — **no stale acceptances are even possible**.
3. **Accepting would risk a RED convergence gate.** The wave gate
   (`check_wave_baseline.py` → `run_diagnosis_wave._apply_accept`) calls
   `AcceptPolicy.partition(findings, "report")` over **all** report-stage accept entries and fails
   if any entry matches **nothing**. `coverage-gap` is **not** a wave lane, so a `coverage-gap`
   accept entry in repo-B/repo-P's `.repo-audit/accept.json` (default `applies` includes `report`)
   would match no wave finding → reported **stale** → gate RED. Closing avoids this landmine
   entirely. (If a future finding were genuinely un-closeable, the correct home would be a
   **dedicated** `coverage_gap_baseline.json` à la repo-A — *not* the shared wave accept.json — and
   that is a B4-era gating decision, not B1.)

**The tests are not "shipped content"** for repo-B or repo-P (they live in `tests/` /
`perf-optimization/tests/`, outside the distributed skill payload), so closing the gaps requires
**no version bump and no release** (per launch-protocol L13: test-only change ⇒ merge to `main`,
no release). This keeps B1 release-free while still CI-verified.

---

## 6. Gate wiring is OUT of B1 (it is B4)

The launch protocol's B1 DONE says "**any** gate wiring shipped + CI-green" — conditional. The
decision of whether `coverage-gap` (now that its input is cheap: ~10 s to regenerate) should
**graduate into the binary convergence gate** for repo-B/repo-P is **explicitly B4's** ("tighten
the Tier-2 ↔ Tier-1 boundary — decide which now-fast lane graduates into the gate"). B1 therefore:

- **does not** add a `check_coverage_gap.py`-style gate or CI job to repo-B/repo-P (that would also
  trip their growth lanes pre-release and pre-empt B4's analysis);
- **does** commit the reproducible recipe + post-fix evidence so B4 has a turnkey basis to graduate
  the lane if it chooses.

repo-A's gate stays exactly as-is (already enforcing coverage-gap, already converged at 0).

---

## 7. Shipping (expected: nothing ships)

- repo-A: **no change** — verify-only.
- repo-B: **test-only** addition (`tests/test_run_instruction_eval.py` extended) → merge
  `feat/phase2-b1` → `main`, **no** version bump, **no** release (L13). Must confirm the new test
  file does **not** trip repo-B's `growth` wave lane (growth audits the `scripts` source scope, not
  `tests/`; verify in the plan) and that `check_wave_baseline` stays `pass active 0`.
- repo-P: **test-only** addition (`tests/` extended for `findings.py`) → merge → `main`, no bump,
  no release. Run `~/.local/bin/ruff format --check` + `ruff check` on changed files before push
  (repo-P CI's standalone format gate). Confirm the wave gate + growth stay green.
- repo-B is the campaign home → also carries the spec, plan, and `b1-evidence/` (merged to `main`).

If, contrary to expectation, closing a gap is judged infeasible, fall back to the dedicated-baseline
form (§5 note) — **not** the shared accept.json — and record the deviation; do not ship a red gate.

---

## 8. Definition of Done (B1 only)

- [ ] repo-A verified at **0** coverage-gap findings via its real gate (evidence captured).
- [ ] repo-B `run_instruction_eval.py` lifted **> 50 %** (target ≥ 80 %) by added behaviour tests;
      re-audit shows **0** coverage-gap findings at scope `scripts`; full suite green; wave gate
      `pass active 0`; CI green on `main`.
- [ ] repo-P `findings.py` lifted **> 50 %** (target ≥ 80 %) by added behaviour tests; re-audit
      (subprocess-capture) shows **0** coverage-gap findings at scope `scripts` +
      `perf-optimization/scripts`; suite green; ruff clean; wave gate green; CI green on `main`.
- [ ] Reproducible coverage recipe + before/after finding inventory committed to
      `docs/superpowers/b1-evidence/` (repo-B).
- [ ] No `coverage-gap` accept entries added anywhere (close-not-accept); no release cut.
- [ ] Memory updated (`repo-audit-dogfood-loops`); proceed to **B2** (do not stop).

---

## 9. Self-review (planner)

- **Placeholders:** none — every file, threshold, scope, and command is concrete and measured.
- **Internal consistency:** §2's measured inventory drives §5's close-not-accept choice; §4.1's
  artifact evidence justifies the §4.2 subprocess-capture recipe; §5's wave-stale analysis (verified
  against `_accept.partition` + `check_wave_baseline._converge`) justifies §6's "no accept entries".
- **Scope:** single lane, two small test-only closures + one verification; gating deferred to B4;
  no release. Bounded.
- **Ambiguity:** "converge" is made concrete = post-fix finding set empty at the named scope with no
  accept entries. "Close" target is ≥ 80 % (a margin above the 50 % leaf threshold) so convergence
  is stable, not boundary-flickering.
- **Risk:** the only CI risk is a test-file addition tripping a growth lane — flagged for explicit
  plan-time verification (§7); mitigated because growth audits the `scripts` scope, not `tests/`.
