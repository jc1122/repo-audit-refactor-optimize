# Phase 2 · Tier-2 Self-Application Campaign — Master Launch Prompt (B1→B4)

**What this is:** a single bootloader goal prompt that drives ONE fresh session continuously
through the rest of the Self-Contained Convergent Skill Family plan — Tier-2 items **B1, B2,
B3, B4** — using the **superpowers** pipeline (brainstorming → writing-plans →
subagent-driven-development). It is **not** for the `goal-*` orchestration skill pack; do
not invoke `goal-preflight` / `goal-main-orchestrator` / `goal-branch-orchestrator` / etc.

**To launch:** start a fresh **Claude Opus 4.8** session with primary working directory
`/home/jakub/projects` (so repo-A/B/P are all reachable), approvals disabled (unattended),
and paste the **short launch key** below — ideally as a `/goal` (the `/goal` *command* sets a
Stop hook that enforces continuous execution; that is allowed — it is not the `goal-*` skill
pack). The key sends the session to read this file's "Full run protocol", the roadmap, and
the B0 worked example, then execute B1→B4 to completion without check-ins.

---

## Short launch key (paste this — ~2k chars)

```
You are an UNATTENDED Claude Opus 4.8 engineer running the Phase-2 Tier-2 self-application
campaign for the repo-audit skill family. Primary dir /home/jakub/projects (repo-A
repo-audit-skills, repo-B repo-audit-refactor-optimize, repo-P perf-benchmark-skill).
Approvals are OFF — run continuously to a terminal state, NO check-ins between items.

DO NOT use the goal-* skill pack (no goal-preflight/goal-main-orchestrator/etc.). Use the
SUPERPOWERS pipeline only.

BEFORE acting, READ IN FULL and follow as binding instructions:
  1) repo-B docs/superpowers/PHASE2-TIER2-LAUNCH-PROMPT.md  (this file — the full protocol)
  2) repo-B docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md  (the roadmap; the "Phase 2" section lists B1-B4)
  3) repo-B docs/superpowers/specs/2026-06-14-phase2-b0-audit-budget-perf-design.md  + the matching plan + docs/superpowers/b0-evidence/  (the B0 WORKED EXAMPLE — copy its discipline)

MISSION: complete B1→B4 in order, each to convergence, in ONE continuous session. For EACH
item run the full superpowers pipeline: superpowers:brainstorming (write the item's spec to
repo-B docs/superpowers/specs/) -> superpowers:writing-plans (plan to repo-B
docs/superpowers/plans/) -> superpowers:subagent-driven-development (fresh implementer
subagent per task + two-stage spec then quality review). Measure-then-decide where empirical;
record a VERIFIED outcome or an HONEST no-win; converge advisory findings into
.repo-audit/accept.json where the lane is gated. Ship any change that touches a shipped repo
via the Phase-1 pipeline (order repo-A->repo-B->repo-P; verify REAL CI green incl
convergence-gate). Update memory after each item. Then proceed to the next item — do not stop.

B1 coverage-gap into the pass; B2 test-audit-pipeline/test-quality-assurance/
test-redundancy-triage on the family suites; B3 test-effectiveness (mutation) on a hot module
per repo; B4 tighten the Tier-2<->Tier-1 boundary (decide which now-fast lane graduates into
the gate). B1/B2/B3 are independent advisory lanes; B4 is the capstone and runs LAST.

GUARDRAILS (full list in file #1, all NON-NEGOTIABLE): convergence-gate CI keeps
fetch-depth:0; verify gates in REAL CI (gh run watch) every push; read gate JSON
status/active/stale, never a piped exit; CHANGELOG dated for repo-A & repo-P (date==commit
date), repo-B dateless; read back every bump via `git show HEAD:<file>`; repo-A growth
re-baselines ONLY after the new tag (a net-positive commit is RED pre-tag — tag, then confirm
growth green); run ruff locally before pushing repo-P; branch feat/phase2-b<N> per repo,
never detached HEAD. A worker's "green" is never evidence — re-run every gate yourself.

DONE: B1-B4 each converged + any shipped change on all 3 mains CI-green (incl
convergence-gate) bumped+tagged+reinstalled; each item's spec+plan+evidence committed; memory
updated. If an item is genuinely blocked, STOP with a complete written record — never fake a
win or suppress a real finding.
```

---

## Full run protocol (read before acting — binding)

### 0. Mission & non-negotiables
- **One continuous session, B1→B4, to convergence.** No pausing for "should I continue?"
  between items — the only terminal states are *all four done + green* or *a hard block with
  a complete record*.
- **Superpowers only.** For every item: `superpowers:brainstorming` → `superpowers:writing-plans`
  → `superpowers:subagent-driven-development` (fresh implementer subagent per task + two-stage
  **spec** then **quality** review, exactly as B0 ran). Do **not** touch the `goal-*` skill
  pack.
- **Measure-then-decide, honestly.** Where an item optimizes or has an empirical pass
  condition, apply one bounded change, re-measure identically, and record a **verified**
  result or an **honest no-win** (per `perf-benchmark-skill/perf-optimization`'s
  `verify_win.py` / `references/optimization-playbook.md`). Never chase unbounded scope or
  game a gate.
- **A worker's "green" is never evidence.** Re-run every gate yourself; read the JSON
  verdict, never a piped exit code.

### 1. The B0 worked example (your template)
B0 ("bring the family's full audit under budget") is the canonical pattern for this campaign.
Read it in full before B1:
- spec `repo-B docs/superpowers/specs/2026-06-14-phase2-b0-audit-budget-perf-design.md`
- plan `repo-B docs/superpowers/plans/2026-06-14-phase2-b0-audit-budget-perf.md`
- evidence `repo-B docs/superpowers/b0-evidence/` (baseline/after summaries, decision.md with
  the candidate decision rule + the growth-gate debugging note, verdict.json)
It demonstrates: measure → enumerate bounded candidates → deterministic decision rule → ONE
change → identical re-measure → `verify_win` accept OR honest no-win → ship via Phase-1 →
record. **Copy this discipline for each B-item.** B0 shipped repo-A **v0.7.3** (`npm run
check` 371→181s, −51%); the full-pytest gate is now opt-in `npm run check:pytest`.

### 2. Readiness facts (already established — do NOT re-derive)
- **Current versions:** repo-A **v0.7.3**, repo-B **0.8.1**, repo-P **0.4.2** (perf-optimization
  stays 0.2.1). All three mains CI-green.
- **B1 input is free:** repo-A's coverage gate already writes
  `repo-A/.self_audit_out/coverage/coverage.json` (≈79 files) every `npm run check`. repo-B and
  repo-P have no equivalent gate-produced coverage.json yet — generate theirs in-session by
  running their suites under `coverage`/`pytest --cov` and feeding the JSON to the
  `coverage-gap-audit` leaf via `--coverage-json`.
- **All Tier-2 leaves are installed and in repo-A:** `coverage-gap-audit`,
  `test-audit-pipeline`, `test-quality-assurance`, `test-redundancy-triage`,
  `test-effectiveness-audit` (mutation; entry `scripts/test_effectiveness_audit.py`).
- **Budget headroom exists:** after B0 the only heavy gate is `coverage` (budget 270 in
  `repo-A/scripts/check_budget.json`); cheap gates < 3s.
- **Ordering:** B1, B2, B3 are independent advisory lanes (do them in order but each stands
  alone); **B4 is the capstone — it depends on B1–B3 outcomes, run it LAST.** B2's redundancy
  triage of the 183s `test-redundancy-triage` suite also lowers the wall-clock floor B0 freed.

### 3. Per-item scope & falsifiable DONE
For each item: brainstorm a spec (repo-B `docs/superpowers/specs/`), write a plan (repo-B
`docs/superpowers/plans/`), execute via subagent-driven-development, ship if it touches a
shipped repo, update memory, proceed.

- **B1 — `coverage-gap` into the full pass.** Produce/locate `coverage.json` per repo, run the
  `coverage-gap-audit` leaf via `--coverage-json`, and converge its TEST findings into each
  repo's `.repo-audit/accept.json` (genuine gaps closed or justified-accepted). **DONE:** the
  coverage-gap lane runs against all three repos and converges (active 0, no stale); any gate
  wiring shipped + CI-green.
- **B2 — test-* on the family suites.** Apply `test-audit-pipeline` /
  `test-quality-assurance` / `test-redundancy-triage` to the family's own test suites; triage
  the DELETE/MERGE rows (conservatively — re-gate every removal), converge. **DONE:** the
  lanes run + their accepted/closed findings converge; any suite changes keep every repo green
  in REAL CI; redundancy reductions recorded (bonus if the `test-redundancy-triage` suite gets
  faster).
- **B3 — `test-effectiveness` (mutation).** Run `test-effectiveness-audit` advisory on one hot
  module per repo (pick via hotspot/churn); record mutation kill-rate + any test gaps it
  surfaces. **DONE:** a mutation report per repo committed as evidence; no source mutated
  in-place (the leaf sandboxes); decisions (close gap vs accept) recorded.
- **B4 — tighten the Tier-2 ↔ Tier-1 boundary.** Using B1–B3 results, decide whether any
  now-fast lane (e.g. coverage-gap once its input is cheap) should graduate into the binary
  convergence gate, and wire it if so. **DONE:** the decision is recorded with evidence; any
  promotion is CI-enforced and green across the family; the roadmap's Phase-2 section is marked
  complete.

### 4. Reusable guardrails (Phase-1 + B0 lessons — all binding)
- **Convergence-gate CI checkout keeps `fetch-depth: 0`** (hotspot/growth mine git history;
  shallow → stale accepts → red gate).
- **Verify in REAL CI** (`gh run watch` / `gh run list --branch main`) on every push — local
  sims can't see GitHub-only behavior. Read the gate JSON `status`/`active`/`stale`; **never
  trust a piped exit code (L4).**
- **`npm ci` in fresh worktrees (L1).** Fresh-clone / CI sim before push (L3).
- **Changelogs:** repo-A & repo-P **dated** (date == commit date, L2); repo-B dateless. After
  any bump **read back via `git show HEAD:<file>`** (one silently failed once).
- **repo-A growth (B0 lesson):** the growth lane has `net_loc_growth` threshold **0.0** — any
  net-positive-LOC commit is RED pre-release (it re-baselines only when the new tag exists, via
  `git describe`). A red `growth` makes `npm run check` exit nonzero, which also breaks any
  perf-benchmark measurement (no `wall_time_percentiles`) and `SUITE_RC`. So: for a release,
  **commit the bump+CHANGELOG, merge, TAG, then confirm growth green**; for a pre-release
  measurement keep the change net ≤ 0 LOC.
- **repo-P CI runs standalone `ruff format --check scripts/ tests/` (unpinned)** — run
  `~/.local/bin/ruff format --check scripts/ tests/` + `ruff check` locally before pushing
  repo-P.
- **Gate sims:** py3.14 + pinned toolchain (ruff==0.15.16, perflint 0.8.1) + cloned leaves at
  the pinned tag with `npm ci` jscpd, PATH-prepended. Local defaults already match.

### 5. Ship conventions (only when a change touches a shipped repo)
- **Order:** repo-A → repo-B → repo-P.
- **Versions to bump:** repo-A = `package.json` + **all 19** leaf `SKILL.md` + dated CHANGELOG;
  repo-B = `SKILL.md` (+ dateless CHANGELOG) only if its shipped content changes (doc-only =
  no release, per L13 — just merge to main); repo-P = `SKILL.md` (+ dated CHANGELOG),
  perf-optimization separate at 0.2.1.
- **Reinstall** after release: repo-A leaves via
  `node repo-A/bin/install-repo-audit-skills.js --dest ~/.claude/skills --force`; repo-P via
  rsync to `~/.claude/skills/perf-benchmark` AND `~/.claude/skills/perf-optimization`.
- **Gate pins:** only re-pin repo-B/repo-P convergence-gate leaf tags to a new repo-A tag if
  **leaf behaviour changed** (B0 didn't, so pins stayed v0.7.2). A version-string-only bump
  needs no pin bump.
- **Branch `feat/phase2-b<N>` per repo; never detached HEAD.** Delete merged branches.

### 6. Known issues to expect
- **repo-B flaky test** `tests/test_synthesize_quadratic_target_measures_and_gates`
  (timing-sensitive synthesis e2e) can fail under full-suite CPU contention but passes in
  isolation and in CI. It is orthogonal to this campaign — if it flakes locally, re-run; if it
  reds CI, re-run the job. (Optionally stabilize it under B2 if you touch that suite.)

### 7. Continuous-execution discipline & what NOT to do
- **Continuous:** do not summarize-and-pause between items; flow B1→B2→B3→B4. Long unattended
  runs are expected; background the slow measurements and keep working.
- **Do NOT:** use the `goal-*` skill pack; force-fit multiple B-items into one spec/plan; ship
  a doc-only repo-B change as a release; suppress a real finding or fake a `verify_win`; leave
  a red gate; edit source yourself during subagent-driven-development (workers edit in
  worktrees; you coordinate and re-gate).

### 8. Memory & closeout
After each item, update the `repo-audit-dogfood-loops` memory (and `MEMORY.md` index) with the
item's outcome (converged / shipped version / honest no-win / blocked). When B4 is done, mark
the roadmap's Phase-2 section complete and record that the full "every skill on every skill +
converge + full pass" goal is met.
