# Phase 2 · B4 (capstone) — tighten the Tier-2 ↔ Tier-1 boundary

**Status:** design (brainstorming output) · **Date:** 2026-06-15 · **Branch:** `feat/phase2-b4` (repo-B, repo-P)
**Campaign:** Self-Contained Convergent Skill Family — Phase 2, Tier-2 item **B4 (capstone, runs LAST)**
**Roadmap home:** `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md` §"Phase 2"
**Launch protocol:** `docs/superpowers/PHASE2-TIER2-LAUNCH-PROMPT.md` §3 (B4 scope & DONE)

---

## 1. Why B4 exists

Phase 1 drew a **two-tier** boundary: **Tier-1** = the fast, artifact-free deterministic wave (the
binary CI **convergence gate**); **Tier-2** = the slow/artifact advisory lanes. B1–B3 ran the four
Tier-2 lanes on the family. B4 is the capstone decision: **given B1–B3 evidence, which Tier-2 lane
(if any) is now ready to graduate into a binary CI gate — and wire it.**

---

## 2. The decision (evidence-based)

| lane | B1–B3 evidence | Tier-1-ready? | decision |
|------|----------------|---------------|----------|
| **coverage-gap** | deterministic; input now cheap (B1: ~10 s suite+coverage); converges to **0** on all 3 repos; repo-A **already** gates it (`check_coverage_gap.py`) | **YES** | **GRADUATE** to a binary CI gate for repo-B + repo-P (close the asymmetry; lock in B1) |
| test-quality (TQA) | rubric is judgment-laden; low dims are structural artifacts (B2) — a binary pass/fail would encode opinion | no | stay Tier-2 advisory |
| test-redundancy (TRT) | slow; conservative → 0 safe DELETE (B2); output is MERGE-advice, not pass/fail | no | stay Tier-2 advisory |
| test-effectiveness (mutation) | slow; **convention-blocked on repo-A** (97 spec_from_file files, B3); residual survivors are equivalents | no | stay Tier-2 advisory |

**Only `coverage-gap` graduates.** It is the one lane that is deterministic, cheap, convergent, and
already proven as a binary gate (repo-A). The other three remain advisory — graduating them would
either encode judgment (TQA), gate on slow/conservative advice (TRT), or be impossible on a third of
the family (mutation). This **completes the campaign's "CI-enforced convergence" goal for the one
ready lane** while preserving the deliberate artifact-free purity of the *wave* gate (coverage-gap
is gated as a **separate** binary check, not folded into the artifact-free wave — exactly as repo-A
keeps `check_coverage_gap.py` separate from its self-audit).

---

## 3. Wiring design (repo-B + repo-P)

Each repo gets, mirroring repo-A:

- **`scripts/check_coverage_gap.py`** — a small, focused gate that (a) runs the repo's suite under
  `coverage`, (b) runs the **cloned** coverage-gap leaf (`$LEAF`, env-injected like the wave's
  `$WAVE_RUNNER`), (c) ratchets findings against `scripts/coverage_gap_baseline.json`, returning a
  real non-zero exit on any finding outside the baseline (no piped exit — L4). Functions kept small
  (the family audits this script too — see §5).
- **`scripts/coverage_gap_baseline.json`** = `[]` (B1 converged both repos to zero).
- **CI:** a step in the existing **`convergence-gate`** job (it already clones the leaf + sets
  `fetch-depth: 0`). Add pytest (+ hypothesis for repo-B) to that job's install and run the gate
  with `LEAF=/tmp/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py`.

**Per-repo coverage mode (measured, §2-of-B1):**

- **repo-B:** **plain** `coverage run` → 0 findings (its production is in-process tested). Simple,
  lowest CI risk.
- **repo-P:** **subprocess-capture** coverage (sitecustomize hook + `COVERAGE_PROCESS_START` +
  `parallel` + `combine`) → 0 findings; **plain coverage yields 2 false findings**
  (`verify_win.py`, `select_candidate.py` are subprocess-tested CLIs). The gate script takes a
  `--subprocess-capture` flag (off=repo-B, on=repo-P) so the two repos share one clean
  implementation, differing only by that flag.

---

## 4. Goal & success criteria (falsifiable)

DONE when **all** of:

1. The graduation **decision is recorded** with B1–B3 evidence (`b4-evidence/decision.md`):
   coverage-gap graduates; TQA/TRT/mutation stay Tier-2.
2. `check_coverage_gap.py` + `coverage_gap_baseline.json` ([]) added to **repo-B** (plain) and
   **repo-P** (subprocess-capture); each reports `{"status":"pass", ...}` 0 findings locally.
3. Each repo's **own wave convergence gate stays `pass active 0`** with the new files present
   (recursion-safe — §5), verified by the pinned-jscpd CI-sim.
4. The new coverage-gap CI step is **green in REAL CI** for repo-B and repo-P (alongside the
   existing `convergence-gate` wave step and `check`).
5. The roadmap's **Phase-2 section is marked complete**; the full "every skill on every skill +
   converge + full pass" goal is recorded as met.
6. Memory updated. **Campaign terminal** (B1–B4 done).

**Honest fallback (never leave a red gate):** if repo-P's subprocess-capture gate cannot be made
**robustly green in real CI**, ship repo-B's graduation, and record repo-P's as **graduation-ready
design, deferred** (with the exact reason) — an honest asymmetric outcome, not a red gate.

---

## 5. Recursion safety (the capstone's hard part)

repo-B/repo-P **audit their own `scripts/`** via their wave gate, so the new `check_coverage_gap.py`
is itself audited. Mitigations (all verified before merge):

- **growth:** repo-B/repo-P growth findings are **repo-level** (path `<repo>`, metric
  `net_loc_growth`/`tracked_files_growth`/…), already accepted **by identity** — a new file changes
  the *value*, not the identity, so the accept still matches (no new active/stale). Verified by the
  CI-sim (`active 0`).
- **code-health (complexity/duplication/dead-code/structure/quality/perf-smell) + security + docs +
  dependency:** the gate script must be **clean** — small functions, stdlib-only imports (the leaf
  is invoked as a subprocess, not imported), no copy-paste of existing code, type-annotated. If the
  wave surfaces any new active finding on the script, **fix the script** (preferred) or, only if the
  finding is a deliberate pattern, add a justified `.repo-audit/accept.json` entry (a *wave-lane*
  accept, which is legitimate — unlike the non-wave coverage-gap accepts B1 rejected).
- **Decisive check:** the §3-of-B1 pinned-jscpd wave sim must still print `{"status":"pass",
  "active":0}` with the new files staged, in **both** repos, before merge.

---

## 6. Scope guardrails (hard)

- **Only coverage-gap graduates.** No TQA/TRT/mutation gating.
- **coverage-gap is a SEPARATE binary gate, not folded into the artifact-free wave** (preserves the
  Tier-1 wave's artifact-free design; matches repo-A).
- **Infra-only** (gate script + baseline + CI) → **no `SKILL.md`/version/CHANGELOG** change → **no
  release** (L13). If, unexpectedly, shipped skill content must change, re-evaluate (not expected).
- **Convergence-gate CI keeps `fetch-depth: 0`.** Verify gates in REAL CI; read JSON
  status/active/stale; never a piped exit (L4).
- Ship order **repo-A → repo-B → repo-P** (repo-A unchanged here; so repo-B then repo-P).

---

## 7. Definition of Done (B4 + Phase-2 closeout)

- [ ] `b4-evidence/decision.md` records the graduation decision + B1–B3 evidence table.
- [ ] repo-B + repo-P: `check_coverage_gap.py` + `coverage_gap_baseline.json` ([]) added; gate
      `pass` 0 findings locally; each repo's wave gate still `pass active 0` (pinned CI-sim).
- [ ] coverage-gap CI step **green in real CI** for repo-B + repo-P (or repo-P honestly deferred per
      §4 fallback, never red).
- [ ] Roadmap Phase-2 section marked **complete**; full-goal-met recorded.
- [ ] No release; all touched mains CI-green incl. `convergence-gate`. Memory updated. **Campaign
      terminal.**

---

## 8. Self-review (planner)

- **Placeholders:** none — decision, per-repo coverage mode, file paths, and CI insertion point are
  concrete and feasibility-measured (repo-B plain → 0; repo-P capture → 0 / plain → 2 false).
- **Internal consistency:** §2's evidence drives the single graduation; §3's per-repo mode follows
  the measured plain-vs-capture finding; §5's recursion mitigations follow the measured
  repo-level/identity-accepted growth shape; §6 preserves the wave's artifact-free design.
- **Scope:** one lane graduates; two repos wired; three lanes explicitly stay Tier-2; infra-only,
  no release. Bounded, with an honest no-red-gate fallback.
- **Ambiguity:** "graduate" = a separate binary CI gate (not folded into the wave); "green across
  the family" = repo-A (pre-existing) + repo-B + repo-P coverage-gap gates all pass in real CI.
- **Risk:** recursion (new script tripping the repo's own wave) and subprocess-capture-in-CI
  (repo-P) — both gated by the pinned-jscpd wave sim + a real-CI check before declaring done, with
  the §4 fallback if repo-P can't be made robustly green.
