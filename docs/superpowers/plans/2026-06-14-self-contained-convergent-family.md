# Self-Contained Convergent Skill Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Supersedes** `2026-06-14-skillset-gap-closeout.md` (this reorients those fixes around the family goal and corrects the 13 self-review findings).

**Goal:** Make the repo-audit family (orchestrator repo-B + leaves repo-A + perf repo-P) a self-contained, mutually-dogfooding, **convergent** system: the orchestrator runs a pass of *all* applicable skills on any target, every skill is applied to every family repo, and the dogfood gate stays green — enforced in CI for all three repos.

**Architecture — two tiers of "pass" (the pivotal design decision):**
- **Tier 1 — the deterministic convergence wave (the GATE).** Fast, artifact-free, runs *every deterministic leaf*: the code-health umbrella (complexity, duplication, dead-code, structure, quality) + security + hygiene + docs + dependency + hotspot + exec + growth **+ perf-smell** (the one deterministic leaf currently missing). This is what must **converge** (green) on every family repo and what CI enforces. Self-contained: runs against a pinned installed/cloned leaf set.
- **Tier 2 — the full advisory pass (the orchestrator's agent stages).** The artifact/slow lanes the deterministic wave cannot host: `coverage-gap` (needs `coverage.json`), `test-audit-pipeline` / `test-quality-assurance` / `test-redundancy-triage` (need a pytest target; the 300s-timeout cohort), `test-effectiveness` (mutation), `perf-benchmark` / `perf-optimization`. The orchestrator drives these per `SKILL.md` when pointed at a target; they are advisory (no fast binary convergence gate), and applying them to the family is the **self-application campaign** (Phase 2), gated on a perf fix.

This split is what makes "all skills on all skills + converge + full pass" actually achievable: Tier 1 gives deterministic all-on-all convergence today; Tier 2 finishes comprehensiveness without forcing slow/artifact lanes into a binary gate. **If you instead want the slow lanes inside the convergence gate, Phase 2's gating changes — flagged at the end.**

**Tech Stack:** Python 3.14 (matches how the accept.json baselines were generated + repo-A CI); pinned leaf toolchain (`lizard radon vulture ruff bandit pylint perflint mypy coverage` + `jscpd` via npm); pytest; GitHub Actions. Lessons honored: L1 (`npm ci`), L2 (changelog date == commit date), L3 (fresh-clone/CI sim), L4 (read the gate JSON / rely on real exit codes, never piped).

---

## Phase 1 — comprehensive deterministic pass + self-contained converging gate (+ the corrected closeout fixes)

Each repo gets a branch `feat/convergent-family`. **Baseline before starting:** repo-B `0.8.0` / repo-P `0.4.1` / repo-A `0.7.1`, all `main` clean + CI green; record each gate result (repo-B `check_wave_baseline` → `pass active 0 accepted 20`; repo-P → pass; repo-A `npm run check` 10/10+2/2).

### Task 1 (repo-B): add `perf-smell` to the deterministic wave registry

**Files:**
- Modify: `scripts/wave_lanes.json`
- Test: `tests/test_run_diagnosis_wave.py`

The wave invokes every leaf as `<python> <leaf> --root <repo> --out-dir <dir> [--source-prefix ...]` (`_run_lane`, line ~249). `perf-smell-audit`'s CLI is `--root`/`--out-dir`/`--source-prefix` — an exact match, so registration needs no shim. The runner loads its own `wave_lanes.json`, so this single add makes the orchestrator run perf-smell on **every** target (repo-A/B/P + foreign).

- [ ] **Step 1: Write the failing test** — append to `tests/test_run_diagnosis_wave.py`:

```python
def test_perf_smell_lane_is_registered():
    import importlib
    wave = importlib.import_module("scripts.run_diagnosis_wave")
    lanes = wave.load_lanes(wave._DEFAULT_REGISTRY)
    assert "perf-smell" in lanes
    assert lanes["perf-smell"].endswith("perf-smell-audit/scripts/perf_smell_audit.py")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py -k perf_smell -q`
Expected: FAIL (`perf-smell` not in registry).

- [ ] **Step 3: Implement** — add to `scripts/wave_lanes.json` `"lanes"` array (after `dependency`, before `hotspot`, so language-scoped lanes group; order is cosmetic):

```json
    {
      "name": "perf-smell",
      "script": "perf-smell-audit/scripts/perf_smell_audit.py",
      "languages": ["python"]
    },
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py -q`
Expected: PASS.

- [ ] **Step 5: Observe what perf-smell finds on repo-B (do NOT accept blindly)** — run the wave and inspect the new lane's findings:
```
ANCHOR=$(cat scripts/wave_anchor.txt)
python3 scripts/run_diagnosis_wave.py --repo "$(pwd)" --out-dir /tmp/ps --skills-root ~/.claude/skills \
  --source-prefix scripts --rev "$ANCHOR" --lanes perf-smell
cat /tmp/ps/perf-smell/*findings*.json 2>/dev/null
```
For each PERF finding: **fix it if it is a real loop-invariant/wrong-container smell**; only add to `.repo-audit/accept.json` (a `finding` entry with a concrete reason) if it is a deliberate pattern. Re-converge: a full wave gate must end `active 0`. (This is the same discipline that fixed 15/16 findings on the new `_accept.py`.)

- [ ] **Step 6: Commit** (the registry + any genuine perf fixes + justified accept entries):
```bash
git add scripts/wave_lanes.json tests/test_run_diagnosis_wave.py .repo-audit/accept.json
git commit -m "feat(wave): run perf-smell-audit as a deterministic lane (full leaf pass on every target)"
```

### Task 2 (repo-A): MEASURE perf-smell on repo-A, then decide (do not commit to converging an unknown volume)

**Files:** none yet (measurement); possibly `scripts/self_audit.py` + accept.json *only if* the measurement says it's bounded.

repo-A's own convergence uses `scripts/self_audit.py` (the code-health pipeline over `skills/*/scripts`), NOT the wave runner — so Task 1 does not make repo-A's *own* gate run perf-smell (the orchestrator wave from Task 1 *does* cover repo-A when it audits it, so repo-A is not unaudited — this task is only about repo-A's self-gate parity). The perf-smell finding volume across repo-A's ~19 leaf scripts is **unknown** and could be large, so measure before committing.

- [ ] **Step 1: Measure** — run perf-smell over repo-A's production scope and COUNT findings:
```
python3 ~/.claude/skills/perf-smell-audit/scripts/perf_smell_audit.py \
  --root ~/projects/repo-audit-skills --source-prefix skills --source-prefix scripts --source-prefix shared \
  --out-dir /tmp/ps-repoA
python3 -c "import json,glob;print(sum(len(json.load(open(f)).get('findings',json.load(open(f)))) for f in glob.glob('/tmp/ps-repoA/*findings*.json')))"
```
Record the count.

- [ ] **Step 2: Decide (record the decision in the commit or the plan):**
  - **If ≤ ~10 findings and all are genuine quick fixes or clearly-justifiable accepts:** add perf-smell to repo-A's self-audit leaf set (mirror how `quality`/`complexity` are enumerated in `scripts/self_audit.py`), triage (fix real / justify-accept in repo-A `.repo-audit/accept.json`), `npm run check` green (grep JSON, L4), commit `feat(selfaudit): run perf-smell on repo-A's own code`.
  - **If the volume is large or needs structural work:** STOP. Do NOT add it to repo-A's self-gate in this phase. Record a one-line note (in repo-A `docs/superpowers/SP15-CANDIDATES.md`) that repo-A self-gate perf-smell parity is deferred to the Phase-2 self-application campaign; repo-A is already perf-smell-audited via the orchestrator wave (Task 1). This keeps Phase 1 bounded.

> Rationale: "every skill on every skill" is satisfied for repo-A by the orchestrator wave (Task 1); making repo-A's *separate* self-audit engine also run perf-smell is parity-nice-to-have, not a Phase-1 blocker, and must not drag an unbounded burn-down into this phase.

### Task 3 (repo-B + repo-P): delete the stale `wave_baseline.json` coupling pair

**Files:** Modify `scripts/hotspot_audit_config.json` (repo-B and repo-P)

The pair suppressed `wave_baseline.json↔wave_frozen.md`; that file is deleted and `.repo-audit/accept.json` is outside the wave's `--source-prefix scripts` scope, so a replacement pair would never fire. **Delete the pair** (do not replace).

- [ ] **Step 1:** In each repo, edit `scripts/hotspot_audit_config.json` and remove the `declared_coupling` entry containing `"scripts/wave_baseline.json"`. Keep JSON valid.
- [ ] **Step 2: Verify the gate stays green** (repo-B `check_wave_baseline` → `pass active 0`; repo-P → pass). If a new coupling finding surfaces, it was load-bearing — accept it with a reason instead.
- [ ] **Step 3: Commit** (each repo): `git commit -am "fix(hotspot): drop declared-coupling pair for the removed wave_baseline.json"`.

### Task 4 (repo-P): guard repo-P's own `.repo-audit/accept.json`

**Files:** Create `tests/test_accept_policy.py` (repo-P)

(repo-B has `test_baseline_ledger.py`; repo-A is covered by `npm run check`; repo-P has nothing. This test also runs in repo-P's pytest CI, so it lands even before the Tier-1 gate job.)

- [ ] **Step 1: Write the test** — create `tests/test_accept_policy.py`:

```python
"""Guard repo-P's own .repo-audit/accept.json: well-formed + every entry justified."""
from __future__ import annotations

import json
from pathlib import Path

ACCEPT = Path(__file__).resolve().parents[1] / ".repo-audit" / "accept.json"
_STAGES = {"report", "remediation"}
_KINDS = {"finding", "path", "rule"}


def _entries() -> list[dict]:
    data = json.loads(ACCEPT.read_text(encoding="utf-8"))
    assert data.get("version") == 1, "version must be 1"
    accept = data.get("accept")
    assert isinstance(accept, list) and accept, "accept must be a non-empty array"
    return accept


def test_accept_exists():
    assert ACCEPT.is_file(), f"missing {ACCEPT}"


def test_every_entry_well_formed_and_justified():
    for i, e in enumerate(_entries()):
        m = e.get("match")
        assert isinstance(m, dict) and m.get("kind") in _KINDS, f"accept[{i}].match invalid"
        assert isinstance(e.get("reason"), str) and e["reason"].strip(), f"accept[{i}] reason required"
        applies = e.get("applies", ["report", "remediation"])
        assert applies and set(applies) <= _STAGES, f"accept[{i}].applies invalid"
        if m["kind"] == "finding":
            assert all(k in m for k in ("leaf", "path", "symbol", "metric")), f"accept[{i}] finding incomplete"
        elif m["kind"] == "path":
            assert isinstance(m.get("glob"), str) and ".." not in m["glob"], f"accept[{i}] glob invalid"
        else:
            assert "leaf" in m or "metric" in m, f"accept[{i}] rule needs leaf/metric"
```

- [ ] **Step 2: Run → PASS** (`python3 -m pytest tests/test_accept_policy.py -q`); negative-test by blanking a `reason` in a scratch copy, confirm it fires, discard the scratch edit.
- [ ] **Step 3: Commit:** `git add tests/test_accept_policy.py && git commit -m "test(accept): guard repo-P's .repo-audit/accept.json"`.

### Task 5 (repo-B): fix LM2 — emit per-**repo** rows so allocator yield is real

**Files:** Modify `scripts/mine_iteration_kpis.py`; Test `tests/test_mine_iteration_kpis.py`, `tests/test_allocate_batches.py`

**Key-convention trace (the part the first cut got wrong).** `allocate_batches` is invoked `--active repo-a,repo-b,repo-p` (comma-split logical labels; `tests/test_allocate_batches.py` keys `rows_before` by `"repo-a"`/`"repo-b"`/`"repo-p"`). `trailing_yield(repo, kpis)` does `rec["rows_before"].get(repo, 0)`. But `mine_iteration_kpis` only has `--repo` as a **Path**, and its basename is `repo-audit-skills`, **not** `repo-a` — so emitting `{path_basename: n}` would never match `--active`. The fix MUST give the miner an explicit label and emit under it, and the orchestration MUST pass the same label on both sides. Also `_load_baseline_rows` over the new accept.json returns `{"version":1,"accept":N}` — it would count `version` as a row.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_mine_iteration_kpis.py`:

```python
def test_accept_baseline_row_count_ignores_version_key():
    import importlib
    kpi = importlib.import_module("scripts.mine_iteration_kpis")
    # accept.json shape: count the accept[] entries, never the {version, accept} dict keys
    assert kpi._count_baseline_rows({"version": 1, "accept": [{"x": 1}, {"y": 2}, {"z": 3}]}) == 3
    assert kpi._count_baseline_rows([{"a": 1}, {"b": 2}]) == 2  # legacy flat list


def test_emit_per_repo_rows_keyed_by_explicit_label():
    import importlib
    kpi = importlib.import_module("scripts.mine_iteration_kpis")
    payload = kpi.build_kpis(repo_name="repo-b", rows_before_n=19, rows_after_n=20,
                             worker_runs=[], phase_seconds={}, ci_wait_seconds=0)
    assert payload["rows_before"] == {"repo-b": 19}
    assert payload["rows_after"] == {"repo-b": 20}
    assert payload["rows_closed"] == 1  # scalar kept for back-compat
```

- [ ] **Step 2: Run → FAIL** (`_count_baseline_rows` / `build_kpis(repo_name=...)` undefined).

- [ ] **Step 3: Implement** in `scripts/mine_iteration_kpis.py`:
  - Add `_count_baseline_rows(data)`: if `isinstance(data, dict)` and `"accept" in data` → `len(data["accept"])`; elif `isinstance(data, list)` → `len(data)`; elif `isinstance(data, dict)` → `sum(len(v) for v in data.values() if isinstance(v, list))` (legacy multi-key); else `0`. Route `_load_baseline_rows`' count through this so `version` is never counted.
  - Add a `--repo-name` arg whose default is `args.repo.resolve().name` (so standalone use still works) — **but the convergent-family wiring passes the logical label explicitly** (`--repo-name repo-a|repo-b|repo-p`), matching `allocate_batches --active`.
  - Extract `build_kpis(repo_name, rows_before_n, rows_after_n, worker_runs, phase_seconds, ci_wait_seconds, **rest)` from `main`; emit `"rows_before": {repo_name: rows_before_n}`, `"rows_after": {repo_name: rows_after_n}`, and keep scalar `"rows_closed": max(rows_before_n - rows_after_n, 0)`. `main` computes the two counts via `_count_baseline_rows` at the start/end SHAs and passes `args.repo_name`.

- [ ] **Step 4: Run → PASS** (`python3 -m pytest tests/test_mine_iteration_kpis.py -q`).

- [ ] **Step 5: Prove the allocator consumes what the miner emits (e2e, using the SAME label convention as `tests/test_allocate_batches.py`)** — append to `tests/test_allocate_batches.py`:

```python
def test_trailing_yield_matches_miner_emitted_shape():
    import importlib
    kpi = importlib.import_module("scripts.mine_iteration_kpis")
    alloc = importlib.import_module("scripts.allocate_batches")
    # the record the miner emits for repo-b...
    rec = kpi.build_kpis(repo_name="repo-b", rows_before_n=20, rows_after_n=17,
                         worker_runs=[], phase_seconds={}, ci_wait_seconds=0)
    # ...is consumed by the allocator keyed on the SAME label
    assert alloc.trailing_yield("repo-b", [rec]) == 3
```
Run: `python3 -m pytest tests/test_allocate_batches.py -k miner_emitted_shape -q` → PASS. This binds the two sides to one label; it fails if the miner and allocator ever disagree on the key.

> **Wiring note for whoever invokes the loop:** the miner MUST be called `--repo-name <label>` with the same `<label>` listed in `allocate_batches --active <labels>` (the established labels are `repo-a`/`repo-b`/`repo-p`). The default-from-path basename is only for standalone/manual runs and will NOT match `--active`.

- [ ] **Step 6: Commit:**
```bash
git add scripts/mine_iteration_kpis.py tests/test_mine_iteration_kpis.py tests/test_allocate_batches.py
git commit -m "fix(kpis): per-repo rows_before/after + correct accept.json row count -> allocator yield works (LM2)"
```

### Task 6 (repo-A): SP15 doc + lesson bookkeeping (no code move)

**Files:** repo-A `docs/superpowers/SP15-CANDIDATES.md`, `docs/self-audit/lessons.jsonl`

**Decision (corrects closeout Task 3):** do NOT move the remediation accept-filter into `mprr_partition.py` — that module is pure (`conflicts`/`eligible`, no I/O); injecting policy file-loading would break its contract. The filter correctly lives at the orchestration layer (`mprr_run._cmd_plan` already loads `.repo-audit/accept.json` and filters before `normalize`). Just record reality.

- [ ] **Step 1:** In `SP15-CANDIDATES.md`, mark the "auto-consume the remediation-scope policy in the engine" candidate **RESOLVED** (Phase 2 of the safeguard wired `mprr_run` to load `.repo-audit/accept.json`; the filter lives at the orchestration boundary by design, since `normalize()` takes an already-loaded list). Use the doc's existing `~~strikethrough~~ **RESOLVED**` style.
- [ ] **Step 2:** In `lessons.jsonl`, mark `LM2` `"escalated": true` with an escalation note pointing at repo-B's Task-5 commit. (This commits on repo-A's branch — see Task 9.)
- [ ] **Step 3: Commit** (repo-A): `git commit -am "docs(sp15): mark engine-auto-consume resolved; escalate LM2"`.

### Task 7 (repo-B + repo-P): self-contained, pinned, converging gate in CI

**Files:** Modify `.github/workflows/check.yml` (repo-B and repo-P)

Enforce the Tier-1 wave gate in CI, **self-contained and reproducible**: pin the leaf source to a tag (hermetic), match the baseline Python (3.14), and rely on the gate's real exit code (no fragile JSON re-parse — `check_wave_baseline.main` returns 0/1 directly, and the step is not piped).

- [ ] **Step 1 (repo-B): add a `convergence-gate` job** to `.github/workflows/check.yml`:

```yaml
  convergence-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with: { node-version: '22' }
      - uses: actions/setup-python@v6
        with: { python-version: '3.14' }
      - name: Install leaf toolchain
        run: |
          python -m pip install --upgrade pip
          python -m pip install coverage==7.14.1 lizard==1.23.0 radon==6.0.1 \
            vulture==2.16 ruff==0.15.16 mypy==2.1.0 bandit==1.9.4 pylint==3.3.9 \
            astroid==3.3.11 perflint==0.8.1
      - name: Clone leaves at a pinned tag
        run: |
          git clone --depth 1 --branch v0.7.1 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves
          (cd /tmp/leaves && npm ci)   # jscpd for the duplication leaf (L1)
          test -x /tmp/leaves/node_modules/.bin/jscpd || (echo "jscpd missing" && exit 1)
      - name: Convergence gate (Tier-1 wave)
        env:
          WAVE_RUNNER: ${{ github.workspace }}/scripts/run_diagnosis_wave.py
          SKILLS_ROOT: /tmp/leaves/skills
          PATH: /tmp/leaves/node_modules/.bin:${{ env.PATH }}
        run: python3 scripts/check_wave_baseline.py   # exits non-zero on fail; not piped (L4)
```
**Pin the CURRENTLY-EXISTING tag** (repo-A `v0.7.1`) when committing this YAML — `v0.7.2` does not exist until Task 9 ships repo-A, and CI fires `on: [push]` to the branch, so a not-yet-created pin would make the branch CI red immediately. The pin is bumped to `v0.7.2` during repo-B's own ship (Task 9 Step 4a), after repo-A's `v0.7.2` exists. The `PATH` prepend makes the duplication leaf's `jscpd` resolvable — closes the unverified-jscpd gap. (repo-B's own runner is `$GITHUB_WORKSPACE`, not a clone, so it needs no pin.)

- [ ] **Step 2 (repo-P): the same job**, but clone BOTH the leaves (`v0.7.2`) AND the runner (`repo-audit-refactor-optimize` `v0.8.1`), and point `WAVE_RUNNER` at the cloned runner:

```yaml
  convergence-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with: { node-version: '22' }
      - uses: actions/setup-python@v6
        with: { python-version: '3.14' }
      - name: Install leaf toolchain
        run: |
          python -m pip install --upgrade pip
          python -m pip install coverage==7.14.1 lizard==1.23.0 radon==6.0.1 \
            vulture==2.16 ruff==0.15.16 mypy==2.1.0 bandit==1.9.4 pylint==3.3.9 \
            astroid==3.3.11 perflint==0.8.1
      - name: Clone leaves + runner at pinned tags
        run: |
          git clone --depth 1 --branch v0.7.1 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves
          (cd /tmp/leaves && npm ci)
          test -x /tmp/leaves/node_modules/.bin/jscpd || (echo "jscpd missing" && exit 1)
          git clone --depth 1 --branch v0.8.0 https://github.com/jc1122/repo-audit-refactor-optimize.git /tmp/runner
      - name: Convergence gate (Tier-1 wave)
        env:
          WAVE_RUNNER: /tmp/runner/scripts/run_diagnosis_wave.py
          SKILLS_ROOT: /tmp/leaves/skills
          PATH: /tmp/leaves/node_modules/.bin:${{ env.PATH }}
        run: python3 scripts/check_wave_baseline.py
```
**Pin existing tags** (`v0.7.1` leaves, `v0.8.0` runner) when committing; bump to `v0.7.2`/`v0.8.1` during repo-P's own ship (Task 9 Step 5a), after both dependency tags are cut. **Ordering matters:** repo-A → repo-B → repo-P, so each pin's target exists before the pin is bumped.

- [ ] **Step 3: Local CI sim (L3) — the decisive check.** Reproduce the job exactly per repo in a scratch dir: clone the leaves at the pinned tag to `/tmp/leaves`, `npm ci`, prepend `node_modules/.bin` to `PATH`, then run the gate command under **python3.14**. Confirm `{"status":"pass","active":0,...}` and exit 0. **This sim is mandatory because the gate runs the wave (incl. the new perf-smell lane) against the pinned leaves under 3.14 — if it does not match the committed accept.json here, it will not in CI.** If it diverges, the accept.json / baselines are environment-dependent — reconcile before pushing (do not ship a red gate).

- [ ] **Step 4: Commit** (each repo): `git commit -am "ci: self-contained convergence gate (pinned leaves, py3.14, perf-smell lane)"`.

### Task 8 (repo-B): record the two deferred review decisions

**Files:** repo-B `references/pipeline.md` (or `references/verification.md`)

Close review items #9/#10 with explicit decisions instead of silence:
- [ ] **Step 1:** Add a short note: the convergence gate has **two shapes by design** — Tier-1 wave repos (repo-B, repo-P) use the active-empty + no-stale verdict (the wave auto-suppresses accept.json); repo-A's self-audit uses an equality-compare sourced from accept.json (it does not auto-suppress). State that this is intentional, not drift.
- [ ] **Step 2:** Note that repo-A's `.repo-audit/accept.json` is intentionally **not** in `package.json` `files` — it is a dev/CI convergence artifact, not shipped to skill consumers. (Decision: keep it unshipped.)
- [ ] **Step 3: Commit:** `git commit -am "docs(verification): record dual gate semantics + accept.json non-distribution decisions"`.

### Task 9 (all repos): housekeeping + decomposed ship

- [ ] **Step 1: Delete merged local branches** (already on `main`): `git -C <repo> branch -d <merged-branch>` for `feat/acceptance-safeguard` (B), `chore/accept-migration` (A), `chore/reanchor-accept-migration` (P). Use `-d` (refuses if unmerged).

Ship each repo as its **own ordered sub-sequence** (do NOT collapse into one step). **Order: repo-A first (so its `v0.7.2` tag exists for the gate pins), then repo-B, then repo-P.**

- [ ] **Step 2 (repo-A ship):** merge `feat/convergent-family` → `main` (`--no-ff`); bump family version `0.7.1→0.7.2` + dated CHANGELOG (`## 0.7.2 - <commit-date>`, L2) synced per `check_release.py`; `npm run check` green (grep JSON); fresh-clone sim (`npm ci` then `npm run check`, L1/L3); push `main` + tag `v0.7.2` + `gh release`; **read back `git show HEAD:package.json`/a SKILL.md to confirm the bump persisted** (a version-bump edit silently failed once this session); reinstall (`node bin/install-repo-audit-skills.js --dest ~/.claude/skills --force`).
- [ ] **Step 3 (repo-A growth purge):** if the bump trips growth allowances, reset `scripts/growth_allowances.json` to only `dependency_growth`, confirm `python3 scripts/check_growth.py` → `pass count 0 baseline v0.7.2`, commit `chore(gates): purge growth allowances at v0.7.2`, push.
- [ ] **Step 4 (repo-B ship):** merge → `main`; bump `0.8.0→0.8.1` + dated CHANGELOG.
  - **Step 4a (pin bump, before push):** repo-A `v0.7.2` now exists (Step 2) → bump repo-B `.github/workflows/check.yml` leaf pin `--branch v0.7.1` → `v0.7.2`; commit `ci: bump gate leaf pin to v0.7.2`.
  - Then **`~/.local/bin/ruff format --check` + `ruff check` on changed files** (consistency) + `pytest tests/ -q` + `check_release.py` + the Tier-1 gate local sim (Task 7 Step 3, now pinning v0.7.2); fresh-clone sim; push `main` + tag `v0.8.1` + `gh release`; **read back `git show HEAD:SKILL.md`** to confirm the bump persisted; reinstall (rsync to `~/.claude/skills/repo-audit-refactor-optimize`, excluding `.git`/caches/`.wave_out`/`docs/audits`).
- [ ] **Step 5 (repo-P ship):** merge → `main`; bump `0.4.1→0.4.2` + dated CHANGELOG.
  - **Step 5a (pin bump, before push):** repo-A `v0.7.2` and repo-B `v0.8.1` now exist → bump repo-P `.github/workflows/check.yml` pins: leaves `v0.7.1`→`v0.7.2`, runner `v0.8.0`→`v0.8.1`; commit `ci: bump gate pins to v0.7.2/v0.8.1`.
  - Then **`~/.local/bin/ruff format --check scripts/ tests/` + `ruff check scripts/ tests/`** (repo-P CI's standalone format gate — the trap that bit this session) + `pytest tests/ -q` + the Tier-1 gate local sim; fresh-clone sim; push `main` + tag `v0.4.2` + `gh release`; **read back `git show HEAD:SKILL.md`**; reinstall (rsync to `~/.claude/skills/perf-benchmark` AND `~/.claude/skills/perf-optimization`).
- [ ] **Step 6: Verify CI green on every pushed commit, including the new `convergence-gate` job**, for all three repos (`gh run list --branch main --limit 3` per repo → `success`). If the gate job is red, `gh run view <id> --log-failed`, fix, do not leave a red gate.

---

## Phase 2 — full-pass self-application campaign (Tier-2 slow lanes) — SEPARATE SPEC

These complete "every skill on every skill" for the artifact/slow lanes. They are **not bite-sized** (each needs measurement/judgment) and **must not be force-fit here** — each gets its own spec after the prerequisite below. Listed so the goal is fully tracked:

- **B0 (prerequisite): bring the family's full audit under budget.** Profile repo-A's `npm run check` with `perf-benchmark` — the cost is the **coverage gate (188.5s) + full-pytest gate (183.4s)** running the 20 leaf suites (the heaviest is `test-redundancy-triage`, ~220 tests); coverage instrumentation adds only ~5s, so the lever is the **double test run**, not a probe. (There is **no bootstrap probe**; the only 300s timeout is the coverage-gap *leaf-audit* subprocess in `check_coverage_gap.py:147`. The Tier-1 wave is **9-lane and fast**.) Apply one bounded `perf-optimization` win (or honestly record no-win) per `docs/superpowers/specs/2026-06-14-phase2-b0-audit-budget-perf-design.md`. Until the family's own audit runs comfortably under budget, the slow lanes cannot be dogfooded reliably. **This is the gating effort and the first self-application of `perf-benchmark`/`perf-optimization` on the family.**
- **B1: `coverage-gap` into the pass** — produce `coverage.json` from each repo's suite, feed via `--coverage-json`; converge its TEST findings.
- **B2: `test-audit-pipeline` / `test-quality-assurance` / `test-redundancy-triage` on the family suites** — apply, triage DELETE/MERGE rows (which also attack the B0 wall-clock floor), converge.
- **B3: `test-effectiveness` (mutation)** — advisory on a hot module per repo.
- **B4: tighten the Tier-2 ↔ Tier-1 boundary** — decide whether any now-fast lane (e.g. coverage once cached) graduates into the gate.

Each B-item: its own `docs/superpowers/specs/` brainstorm → plan, because the pass condition is empirical (timings, mutation scores), not a fixed literal.

---

## Final verification (Phase 1)

- [ ] Orchestrator runs the full **deterministic** leaf set: `wave_lanes.json` lists 9 lanes incl. `perf-smell`; a wave on any target runs them all.
- [ ] All three repos converge on the expanded wave: repo-B `check_wave_baseline` → `pass active 0`; repo-P → pass; repo-A `npm run check` green incl. perf-smell.
- [ ] **CI enforces the convergence gate** (new `convergence-gate` job green) on repo-B + repo-P; repo-A `npm run check` green.
- [ ] LM2 fixed (allocator `trailing_yield` non-zero test passes); SP15 doc + lessons updated; dual-gate-semantics + non-distribution decisions recorded.
- [ ] `git grep wave_baseline.json` in repo-B/P → only synthetic test fixtures + historical docs.
- [ ] Installed: repo-B `0.8.1`, perf-benchmark `0.4.2`, repo-A family `0.7.2`; tags pushed; merged branches deleted.
- [ ] Memory updated: family now runs perf-smell on all targets; convergence gate CI-enforced for all three; Phase-2 campaign + B0 prerequisite recorded.

---

## Self-Review (completed by planner)

- **Goal coverage:** "orchestrator runs a pass of all skills" → Task 1 (deterministic leaves complete via perf-smell) + Phase 2 (slow lanes); "all skills on all skills" → Tasks 1+2 (perf-smell on B/P wave *and* repo-A self-audit) + Phase 2; "self-contained + converge" → Task 7 (pinned, py3.14, exit-code gate) + Tasks 1/2 re-converge; "dogfood converges, CI-enforced" → Task 7 + final verification.
- **The 13 closeout findings, each resolved:** (1) mprr purity → Task 6 keeps the filter at the orchestration layer (no module-purity break). (2) LM2 shape → Task 5 emits per-repo dicts keyed by repo + `_count_baseline_rows` ignores the `version` key. (3) py-version → Task 7 pins 3.14. (4) unpinned leaves → Task 7 pins tags. (5) LM2 e2e → Task 5 Step 5 allocator yield test. (6) jscpd → Task 7 `npm ci` + `node_modules/.bin` on PATH + existence check. (7) cross-repo locus → tasks grouped by repo; repo-A edits (Tasks 2,6) on repo-A's branch. (8) #9/#10 → Task 8 records both decisions. (9) heredoc → Task 7 relies on the real exit code, no pipe. (10) coupling pair → Task 3 deletes (not replaces). (11) fragile inline example → dropped (the spec already has the example). (12) ship mega-step → Task 9 decomposed per-repo, per-step, with read-back + ruff-format guards from this session's failures. (13) instruction-eval / doc-only releases → instruction-eval removed from the critical path (it is model-dependent; left to Phase 2 if pursued), releases are real (perf-smell + LM2 + gate are substantive, not doc-only).
- **Type/identity consistency:** `build_kpis(repo, rows_before_n, rows_after_n, ...)` + `_count_baseline_rows(data)` (Task 5) match the tests and `allocate_batches.trailing_yield`'s `rec["rows_before"][repo]` shape. The perf-smell registry entry matches `_run_lane`'s `--root`/`--out-dir`/`--source-prefix` invocation (verified). Pin tags (`v0.7.2`/`v0.8.1`) are produced in Task 9 before being depended on (repo-A ships first).
- **Ordering/risk:** repo-A ships first (its tag is a gate pin); the Task-7 local CI sim is the decisive pre-push check (catches the py-version/env risk that is the likeliest cause of a red gate); ship steps carry the read-back and ruff-format guards that this session proved necessary.
- **Honest scope:** Phase 2 (slow-lane self-application) is deferred to its own specs with the 300s perf fix as the explicit prerequisite — not hand-waved into bite-sized tasks. The two-tier model is the one load-bearing assumption; flagged for override.
