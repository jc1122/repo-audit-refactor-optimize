# Phase 3 · Deferred-Candidate Campaign — Master Launch Prompt (C1→C3)

**What this is:** a single bootloader goal prompt that drives ONE fresh session through the three
follow-up candidates **surfaced and deferred during Phase 2** (B0–B4). Each is an independent item
run via the **superpowers** pipeline (brainstorming → writing-plans → subagent-driven-development).
It is **not** for the `goal-*` orchestration skill pack. Phase 2 is COMPLETE (see
`plans/2026-06-14-self-contained-convergent-family.md` §"Phase 2 — COMPLETE"); these are the honest
"future candidate" items its evidence recorded — not gaps.

**To launch:** start a fresh **Claude Opus 4.8** session, primary working directory
`/home/jakub/projects` (repo-A/B/P all reachable), approvals disabled (unattended), and paste the
**short launch key** below — ideally as a `/goal` (the `/goal` *command* sets a Stop hook that
enforces continuous execution; that is allowed — it is not the `goal-*` skill pack).

**Items are INDEPENDENT** — run all three (C1→C2→C3) or any subset. Recommended order is by
effort/risk: C1 (small, clean leaf fix) → C2 (coordinated multi-repo, bounded) → C3 (largest;
pilot-first). C3 is the heaviest and is explicitly pilot-then-decide; it is fine to stop after C1+C2.

---

## Short launch key (paste this)

```
You are an UNATTENDED Claude Opus 4.8 engineer running the Phase-3 deferred-candidate campaign for
the repo-audit skill family. Primary dir /home/jakub/projects (repo-A repo-audit-skills, repo-B
repo-audit-refactor-optimize, repo-P perf-benchmark-skill). Approvals are OFF — run continuously,
NO check-ins between items.

DO NOT use the goal-* skill pack. Use the SUPERPOWERS pipeline only.

BEFORE acting, READ IN FULL and follow as binding instructions:
  1) repo-B docs/superpowers/PHASE3-LAUNCH-PROMPT.md  (this file — the full protocol)
  2) repo-B docs/superpowers/PHASE2-TIER2-LAUNCH-PROMPT.md  (the prior campaign's guardrails — all still binding)
  3) repo-B docs/superpowers/{b2-evidence/triage.md, b3-evidence/report.md, b4-evidence/decision.md}  (where these candidates were recorded)

MISSION: complete C1→C3 (or the chosen subset) in order, each to a terminal state, in ONE session.
For EACH item run the full superpowers pipeline: brainstorming (spec to repo-B
docs/superpowers/specs/) -> writing-plans (plan to repo-B docs/superpowers/plans/) ->
subagent-driven-development (fresh implementer subagent per task + two-stage spec-then-quality
review). Measure-then-decide where empirical; record a VERIFIED outcome or an HONEST no-win. Ship any
change that touches a shipped repo via the Phase-1 pipeline (order repo-A->repo-B->repo-P; verify
REAL CI green incl convergence-gate AND the new coverage-gap gate). Update memory after each item.

C1 fix the test-audit-pipeline umbrella's pytest-xdist assumption (repo-A leaf, ships a release).
C2 narrow perf-smell-audit to its high-precision subset (coordinated: re-version repo-A leaf, re-pin
repo-B/repo-P gate tags, prune now-stale perf-smell accepts, reconverge). C3 unblock repo-A
mutation-testability by migrating its spec_from_file_location leaf-test convention to normal package
imports — PILOT on ONE leaf first, measure value, then decide on full migration.

GUARDRAILS (full list in files #1 and #2, all NON-NEGOTIABLE): convergence-gate CI keeps
fetch-depth:0; verify gates in REAL CI (gh run watch) every push; read gate JSON status/active/stale,
never a piped exit; the pinned-jscpd wave sim + the new coverage-gap gate sim are the decisive
pre-push checks; CHANGELOG dated for repo-A & repo-P (date==commit date), repo-B dateless; read back
every bump via `git show HEAD:<file>`; repo-A version bump = package.json + ALL 19 leaf SKILL.md +
dated CHANGELOG; repo-A growth re-baselines ONLY after the new tag; run ruff locally before pushing
repo-P; only re-pin repo-B/repo-P gate leaf tags when a USED (wave/coverage-gap) leaf changed
behaviour; branch feat/phase3-c<N> per repo, never detached HEAD. A worker's "green" is never
evidence — re-run every gate yourself.

DONE: each chosen item terminal (verified win or honest no-win) + all 3 mains CI-green (incl
convergence-gate + coverage-gap gate) + each item's spec+plan+evidence committed + memory updated.
If genuinely blocked, STOP with a complete written record — never fake a win or leave a red gate.
```

---

## Full run protocol (read before acting — binding)

### 0. Mission & non-negotiables
- **Superpowers only**, full pipeline per item (brainstorming → writing-plans →
  subagent-driven-development with two-stage spec-then-quality review). No `goal-*` pack.
- **Measure-then-decide, honestly.** Record a VERIFIED outcome or an HONEST no-win. Never chase scope
  or game a gate. A worker's "green" is never evidence — re-run every gate yourself; read the JSON
  verdict, never a piped exit.
- **Carry forward EVERY Phase-1/Phase-2 guardrail** (file #2 §4–§5): convergence-gate `fetch-depth:0`;
  REAL-CI verification each push; the pinned-jscpd wave sim is the decisive pre-push recursion check;
  **and now also the B4 coverage-gap gate** (repo-B plain / repo-P subprocess-capture) must stay
  green — re-run `scripts/check_coverage_gap.py` with the cloned leaf before each push.

### 1. Readiness facts (established — do NOT re-derive)
- **Phase 2 is COMPLETE.** Current versions: repo-A **v0.7.3**, repo-B **0.8.1**, repo-P **0.4.2**.
  All three mains CI-green incl. `convergence-gate` + the new `Coverage-gap gate`.
- **Convergence-gate pins:** repo-B clones repo-A leaves `v0.7.2`; repo-P clones leaves `v0.7.2` +
  runner (repo-B) `v0.8.1`. Pins bump **only** when a USED leaf's behaviour changes (C2 does; C1/C3
  do not).
- **coverage-gap gate (B4):** repo-B `scripts/check_coverage_gap.py --suite tests --source-prefix
  scripts` (plain); repo-P `… --subprocess-capture --suite tests --suite perf-optimization/tests
  --source-prefix scripts --source-prefix perf-optimization/scripts`; baseline `scripts/
  coverage_gap_baseline.json` = `[]`. The script is itself wave-audited — keep it ≤88 cols, typed,
  tuple command lists (see B4 evidence) if you ever touch it.

### 2. Per-item scope & falsifiable DONE

#### C1 — fix the `test-audit-pipeline` umbrella's pytest-xdist assumption
- **Problem (B2 `triage.md`):** the umbrella's coverage stage builds `pytest … -n 0 …`
  (`repo-A skills/test-audit-pipeline/scripts/audit_pipeline.py:~140`); the family repos don't
  install `pytest-xdist`, so the stage fails (`error: unrecognized arguments: -n`, exit 4) while
  TQA + triage stages succeed.
- **Fix:** gate the `-n` flag on xdist availability (detect `importlib.util.find_spec("xdist")` or
  the `pytest -p xdist` plugin; only pass `-n` when present), or make `--max-workers` drive it.
  TDD: a test that the coverage command omits `-n` when xdist is absent. **Do not** add xdist as a
  hard dep.
- **Ship:** the umbrella is a **shipped leaf** → repo-A release (bump `package.json` `0.7.3→0.7.4` +
  **all 19** leaf `SKILL.md` + dated `CHANGELOG.md`; tag `v0.7.4`; `gh release`; reinstall via
  `node bin/install-repo-audit-skills.js --dest ~/.claude/skills --force`). **No repo-B/repo-P pin
  bump** (the umbrella is a Tier-2 lane, not in the wave or the coverage-gap gate; the leaves they
  pin are unchanged). repo-A growth re-baselines after the `v0.7.4` tag.
- **DONE:** umbrella runs end-to-end on a family suite (coverage stage green) with xdist absent;
  repo-A shipped v0.7.4, CI-green; repo-B/repo-P unaffected + still green.

#### C2 — narrow `perf-smell-audit` to its high-precision subset
- **Problem (B0 deferral + repo-A `SP15-CANDIDATES.md`):** the leaf
  (`repo-A skills/perf-smell-audit/scripts/perf_smell_audit.py`) keeps the WHOLE perflint
  `W81–W84 / R81–R82` range (`_PERFLINT_PREFIXES`), over-approximating → **77 family-wide accepts**
  (repo-B **43** + repo-P **34** perf-smell entries in `.repo-audit/accept.json`) papering over
  false positives.
- **Measure-then-decide:** narrow `_PERFLINT_PREFIXES` (or add a precision filter) to the advertised
  high-precision subset; **measure** how many of the 77 accepts become genuinely unnecessary vs
  still-load-bearing. Only ship if precision materially improves without losing true PERF signal.
- **Ship (coordinated — perf-smell IS a wave lane → behaviour changes):** repo-A release
  (`0.7.x→next` + 19 SKILL.md + dated CHANGELOG + tag + reinstall) **→ then** repo-B & repo-P:
  **re-pin** the convergence-gate leaf clone (`--branch v0.7.2 → <new repo-A tag>`), **prune** the
  now-**stale** perf-smell accepts, **reconverge** (`check_wave_baseline` → `pass active 0`, no
  stale). The decisive check: the pinned-jscpd wave sim using the **NEW** repo-A tag's leaves
  (re-clone `/tmp/leaves` at the new tag), in both repos, before push. Keep the coverage-gap gate
  green too.
- **DONE:** narrowed leaf shipped; repo-B/repo-P pins bumped + stale accepts pruned + reconverged;
  all 3 mains CI-green incl convergence-gate + coverage-gap gate; the accept-count reduction recorded
  in evidence. (Honest no-win allowed: if narrowing loses true signal or doesn't reduce accepts, do
  not ship — record why.)

#### C3 — unblock repo-A mutation-testability (test-convention migration; PILOT first)
- **Problem (B3 `report.md` / `repoA-blocked.md`):** repo-A's leaf tests load modules via
  `helpers.load_module()` / `importlib.util.spec_from_file_location` (**97 files**), which bypasses
  mutmut 3.x's trampoline → no repo-A module is natively mutation-testable.
- **PILOT (do this first, measure, then decide):** migrate **ONE** leaf's tests (suggest
  `coverage-gap-audit`, 4 files) from `helpers.load_module()` to a normal package import that
  matches mutmut's mutant key (`sys.path.insert(<leaf>/scripts); import <module>` — this preserves
  standalone testability, no packaging needed). Run `test-effectiveness-audit` on that leaf
  (per B3's staging recipe), record the kill rate + whether it surfaces real gaps. **Decide:** if
  the pilot surfaces genuine test gaps worth the churn, expand to more leaves; if not, record the
  honest finding and STOP (the convention's testability-without-packaging benefit may outweigh
  mutation coverage).
- **Ship:** test-only (no `SKILL.md`/leaf-behaviour change) → **no release**; migrated tests + the
  mutation evidence land on repo-A main (tests) and repo-B `docs/superpowers/c3-evidence/`. repo-A
  `npm run check` must stay green (the migrated tests still pass + still satisfy coverage-gap).
- **DONE:** the pilot leaf's tests migrated + green; a mutation report for it committed; the
  expand-or-stop decision recorded; repo-A CI-green. (Full 97-file migration is OUT of the pilot —
  it becomes its own item only if the pilot justifies it.)

### 3. Ship conventions & known issues (same as Phase 2)
- Order **repo-A → repo-B → repo-P**. repo-A bump = `package.json` + all 19 `SKILL.md` + dated
  CHANGELOG; repo-B SKILL.md + dateless CHANGELOG only if shipped content changes; repo-P SKILL.md +
  dated CHANGELOG; doc/test-only = no release (L13). Read back every bump via `git show HEAD:<file>`.
- repo-A growth lane is zero-tolerance for net-positive LOC pre-tag — for a release, commit the
  bump+CHANGELOG, merge, **TAG**, then confirm growth green.
- repo-P CI runs standalone `ruff format --check scripts/ tests/` + `ruff check` — run locally first.
- Known flaky repo-B test `test_synthesize_quadratic_target_measures_and_gates` — re-run on contention.
- Delete merged `feat/phase3-c<N>` branches.

### 4. Memory & closeout
After each item, update the `repo-audit-dogfood-loops` memory (+ `MEMORY.md` index) with the outcome
(shipped version / honest no-win / pilot decision). When the chosen items are done, record Phase 3
closeout.
