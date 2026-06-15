# B4 — Tier-2 ↔ Tier-1 boundary decision (capstone)

Decided 2026-06-15 from B1–B3 evidence. **Only `coverage-gap` graduates** into a binary CI gate;
the other three Tier-2 lanes stay advisory.

| lane | B1–B3 evidence | Tier-1-ready? | decision |
|------|----------------|---------------|----------|
| **coverage-gap** | deterministic; input now cheap (B1: ~4–6 s suite + coverage); **converges to 0** on all 3 repos; repo-A **already** gates it (`check_coverage_gap.py`) | **YES** | **GRADUATE** to a binary CI gate for repo-B + repo-P |
| test-quality (TQA) | rubric is judgment-laden; the low dimensions are structural artifacts of white-box leaf-internal testing (B2) — a binary pass/fail would encode opinion | no | stay Tier-2 advisory |
| test-redundancy (TRT) | slow; conservative → **0 safe DELETE** across all targets (B2); output is MERGE-advice, not a pass/fail | no | stay Tier-2 advisory |
| test-effectiveness (mutation) | slow; **convention-blocked on repo-A** (97 `spec_from_file_location` files, B3); residual survivors are equivalents | no | stay Tier-2 advisory |

## Rationale

`coverage-gap` is the unique lane that is deterministic, cheap (now), convergent, and **already
proven as a binary gate** on repo-A. Graduating it for repo-B + repo-P closes the asymmetry (their
coverage-gap convergence from B1 was previously **unenforced** — nothing prevented regression) and
completes the campaign's *"CI-enforced convergence"* goal for the one ready lane.

It is gated as a **separate** binary check (`scripts/check_coverage_gap.py`), **not** folded into the
artifact-free Tier-1 wave — preserving the wave's deliberate artifact-free design (coverage-gap needs
a `coverage.json` artifact from running the suite), exactly as repo-A keeps `check_coverage_gap.py`
separate from its self-audit. Per-repo coverage mode: repo-B **plain** coverage (0 findings; its
production is in-process tested); repo-P **subprocess-capture** coverage (plain yields 2 false
findings on the subprocess-tested CLIs `verify_win.py`/`select_candidate.py`).

The other three lanes remain advisory — graduating them would encode judgment (TQA), gate on
slow/conservative advice (TRT), or be impossible on a third of the family (mutation). Their B2/B3
reports stand as the recorded convergence evidence.

Evidence: `../b1-evidence/`, `../b2-evidence/`, `../b3-evidence/`.
