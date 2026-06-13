# Synthesized Performance Benchmark — Design

**Date:** 2026-06-13
**Status:** Design (awaiting review → writing-plans)
**Scope:** the performance lane of the repo-audit-refactor-optimize family (repos A/B/P)

## Problem

The performance lane is the only *blocking* lane, yet on any repository with no
benchmark surface it degrades to `manual` and contributes no perf signal. The skill
is a harness; the **agent** running it can construct a benchmark — measure wall-time,
then profile deeper — but today the harness gives that agent no scaffolding, and no
way to turn an ad-hoc measurement into something rigorous enough to *verify* an
optimization win.

## Goal

When a repo lacks a benchmark surface, let the agent **synthesize a gate-quality
benchmark** that drives `perf-optimization` to a **verified** before/after win —
preferring deterministic instrumentation so the win-claim does not depend on
wall-time noise.

### Non-goals (this spec)

- **Invariant inference** (Daikon-style "is this collection sorted/unique/bounded")
  and **datatype quantization** (float→int when values are integral). These are
  *correctness-changing* and need a separate correctness guard — see Future Work.
- Multi-language support. Python only.
- Forcing synthesis on every run. Synthesis is **agent-triggered, at convenience.**

## Success criterion

A run on a repo with no committed benchmark can: discover a hot path, synthesize a
focused microbenchmark, prove it is gate-quality, apply one optimization, and emit a
**verified-win** or **honest-no-win** verdict backed by reproducible evidence — with
the win measured on a deterministic instruction count whenever `valgrind` is present.

---

## Pipeline

```
DISCOVERY (three candidate sources)
  • cProfile ranking of an agent-named representative run   (deterministic; relative timings)
  • static algorithmic-smell detector (perflint/refurb)     (deterministic; AST)
  • agent insight                                           (judgment)
        │  agent picks a hotspot + writes make_input(size)
        ▼
SYNTHESIZE microbench   (harness template + agent-authored inputs)
        ▼
GATE = empirical Big-O fit + cost-delta, on the best available tier:
        callgrind instr-count (exact) ▸ perf stat ▸ wall-time + CV (fallback)
        pass only if: complexity class is non-degenerate
                      AND tier-appropriate stability holds
        else → advisory PERF finding, NO win-claim         (honest refusal)
        ▼
OPTIMIZE (perf-optimization: one candidate) → re-measure SAME harness, same fingerprint
        → verified win (fewer instructions / ≥5% median within CV) OR honest no-win/revert
        ▼
GRADUATE (on demand) → commit harness + inputs to benchmarks/ + baseline_ledger.jsonl
```

`cProfile` is used only for **ranking** (relative), never for the win measurement, so
profiler overhead cannot contaminate the verdict. The win is measured on a clean tier
below.

---

## Determinism is the spine

The original fear was wall-time noise forcing a coefficient-of-variation (CV) gate.
Deterministic instrumentation dissolves that: prefer the most deterministic tier
available.

| Gate tier | Signal | Determinism | Cost / caveat |
|---|---|---|---|
| **callgrind** (preferred) | instructions retired; cache/branch via cachegrind | exact, reproducible | ~10–50× slowdown (fine for a microbench); pin `PYTHONHASHSEED`; simulated cache ≠ real silicon |
| **perf stat** | HW instructions retired (~stable) + cycles/cache/branch (noisy) | mostly | needs `perf_event_paranoid` permission |
| **wall-time + CV** (fallback) | `perf_counter` median-of-N | noisy | always available; the CV honest-refusal contract applies **only** on this tier |

**Gate rule:** when `valgrind` is present, the win-claim rides on a strict
instruction-count delta and **no CV bound is needed**. Without it, fall back through
`perf stat` to wall-time + CV. The existing `perf-benchmark` skill already exposes a
`--tier` knob and `--max-cv`; this work adds/targets the deterministic tier.

### Empirical Big-O fit

Run the synthesized microbench over a geometric size ladder and fit measured cost to
{O(1), O(log n), O(n), O(n log n), O(n²), O(2ⁿ)} (the `big_O` method). Fit on
**instruction counts** when available → the complexity classification itself is
noise-free. This:

1. **Subsumes the size-sensitivity guard** — a degenerate benchmark fits O(1), so
   "refuse if O(1)" falls out for free.
2. **Emits an algorithmic finding** when the measured class is worse than the
   idiomatic expectation. `perf-benchmark` already checks `--expected-complexity`;
   this extends it to **report** the fitted class.

(Static/symbolic Big-O inference is undecidable in general; empirical-fit-on-counts is
the deterministic path.)

---

## Static algorithmic-smell detector (in-scope discovery source)

A new deterministic audit leaf wrapping the **perflint / refurb** rule families:
wrong-container (`x in list` → set), loop-invariant computations, `sorted(x)[0]` →
`min(x)`, `list.insert(0, …)` → `deque`, etc. Emits PERF/source findings to the shared
code-health finding schema. High-precision subset only; the deeper invariant-based
cases (knowing a list is *maintained* sorted) are explicitly deferred (Future Work).

All three discovery sources converge on the **same** deterministic gate: a perflint
hint, an empirical complexity fit, or a pure agent hunch are each verified by an
instruction-count delta.

---

## Component placement (3-repo split)

> **Open for review:** keep this split, or consolidate everything into the
> orchestrator (repo-B) to avoid cross-repo coordination?

- **repo-audit-skills (leaves):** new deterministic `perf-smell`/`algorithmic` audit
  leaf (perflint/refurb wrapper) → PERF findings on the shared schema.
- **perf-benchmark-skill (engine):** `profile_discover.py`; the microbench template;
  `validate_gate.py` (empirical Big-O fit + callgrind/perf/wall tiers); extend
  `--expected-complexity` to report the fitted class.
- **repo-audit-refactor-optimize (orchestrator):** performance-lane wiring; new lane
  state `synthesizable`; the agent-triggered synthesis protocol; `graduate_benchmark.py`;
  `perf/` run artifacts; run-report integration.

---

## Hybrid division of labor

| Step | Owner | Why |
|---|---|---|
| Profile a representative run, rank hotspots | harness (deterministic) | mechanical |
| Static smell detection | harness (deterministic) | mechanical |
| Pick which hotspot matters | **agent** | needs context |
| Author `make_input(size)` (realistic, scalable inputs) | **agent** | harness cannot guess domain-realistic data |
| Wrap inputs in the timing/CLI template | harness | boilerplate |
| Big-O fit + stability gate + tier selection | harness (deterministic) | the gate must be objective |
| Select & apply one optimization candidate | perf-optimization | existing |
| Verify win / no-win on identical fingerprint | harness (deterministic) | objective |

---

## Lane, trigger, artifacts, graduation

- **Lane state:** no benchmark + a runnable Python surface → **`synthesizable`** (not
  `manual`). Gate-quality target reached → effectively `full` for that target; refusal
  → `manual` with the recorded reason.
- **Trigger:** **agent-on-demand** — surfaced as available during diagnosis, never
  forced. *(Open for review.)*
- **Artifacts (ephemeral, in the run dir):**
  - `perf/discovery/profile_ranked.json`, `perf/discovery/smells.json`
  - `perf/<target>/{bench.py, make_input.py, complexity_fit.json, before.json, after.json, verdict.json}`
  - `perf/synthesis_report.md`
  - referenced from `run_report.json` (`batches`/`verification`).
- **Graduation (on demand, the only thing that writes into the audited repo):**
  `graduate_benchmark.py` copies the proven harness + inputs to `benchmarks/` and
  appends `docs/perf/baseline_ledger.jsonl`. **Default is not to graduate.**

---

## Honest-refusal contract

A synthesized benchmark may gate a **win-claim** only if all hold:

1. complexity fit is **non-degenerate** (not O(1) — it actually does size-dependent work);
2. **tier-appropriate stability** — exact match on callgrind, or CV ≤ threshold on the
   wall-time fallback;
3. before/after **fingerprints match** (same sizes, env, command, `PYTHONHASHSEED`).

Otherwise it degrades to an **advisory PERF finding**, the lane records the reason, and
the harness makes **no win-claim** — the same discipline as `perf-optimization`'s
existing honest-no-win. The size-sensitivity / non-degeneracy check is the key guard
against a benchmark that "passes" by being trivially stable on a constant workload.

---

## Testing (deterministic fixtures)

- **Known O(n²) target** → discovery + smell flag it; fit reports n²; gate passes; a
  `sorted()` fix verifies fewer instructions (verified win).
- **Constant-time / degenerate target** → gate **refuses** via the complexity fit (O(1)).
- **valgrind-absent environment** → falls back to wall-time + CV; a high-jitter target
  → **refusal** after bounded stabilization attempts.
- **Graduation** writes to `benchmarks/` + ledger; a **default run writes nothing** into
  the audited repo.

---

## Risks & caveats

- **valgrind availability.** The current dev environment lacks valgrind (`--tier fast`
  only). callgrind is therefore an *optional, strongly-preferred* tier, not a hard
  dependency; wall-time + CV must remain fully functional.
- **Simulated vs real.** cachegrind models a cache; instruction-count reductions are a
  strong deterministic proxy for "faster," not a wall-clock guarantee. Record this in
  the verdict.
- **Hash randomization.** Pin `PYTHONHASHSEED` so callgrind counts are reproducible.
- **Scope creep.** This spec is deliberately the *speed foundation*. Correctness-changing
  optimizations are out (Future Work) precisely because they need a second gate axis.

---

## Future work (recorded, not designed here)

A separate **correctness-preserving optimization** spec, reusing this spec's
instruction-count verify-gate but adding a correctness axis (output-equivalence over
the corpus + error/overflow bounds, all coverage-gated):

- **Invariant inference** — a small "mini-Daikon" observer over the test corpus
  (sorted / unique / monotonic / bounded / integral predicates at call boundaries),
  with **Hypothesis** (falsify) and **CrossHair** (symbolic prove/refute) as
  confirmation engines. Exploit confirmed invariants: sorted ⇒ `max`→`[-1]` (O(n)→O(1)),
  membership ⇒ `bisect` (O(n)→O(log n)).
- **Datatype quantization** — observe a `float` value is integral and range-bounded,
  confirm via CrossHair/Hypothesis, quantize float→int (or double→float32 under an error
  bound, the Precimonious/FPTuner method). Requires overflow/range proof, not just
  "values were whole."

Pattern: `OBSERVE → CONFIRM → agent judges contractual-vs-coincidental → EXPLOIT →
VERIFY twice (correctness AND speed)`.

---

## Open questions for review

1. **Trigger** — agent-on-demand (proposed) vs automatic when a surface exists?
2. **Placement** — 3-repo split (proposed) vs everything in the orchestrator?
3. **perf stat middle tier** — worth implementing now, or just callgrind + wall-time to
   start?
