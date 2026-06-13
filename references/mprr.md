# MPRR Engine Reference

Locked design decisions and gate ladder for the Massively-Parallel Redundancy Remediation engine.
Engine implementation: `scripts/mprr_run.py`, `scripts/mprr_integrate.py`, `scripts/mprr_gate.py`, `scripts/mprr_packets.py`, `scripts/mprr_schedule.py`.

## §3 Locked Decisions

| Axis | Decision |
|---|---|
| Parallelism | Within-repo conflict-free fan-out; repo-agnostic (scheduler is pure Python, no repo-specific assumptions) |
| Conflict rule | File-level: two findings conflict iff they share at least one file; only file-disjoint findings run concurrently |
| Autonomy | Fully unattended, gate-gated; orchestrator re-derives evidence from artifacts and never trusts worker self-report |
| Scheduler | Continuous saturating pool (ceiling N, default 8); wave-mode is the degenerate case where N equals the wave width |
| Home | Engine in repo-B (`scripts/mprr_*.py`); audit leaves in repo-A (diagnosis wave, lane runners); orchestration docs in repo-A |

## Gate Ladder

| `remediation_class` | Gates required for auto-merge |
|---|---|
| `mechanical` | `tests_passed == true` + `finding_resolved == true` (lane re-audit no longer reports the finding) |
| `refactor` | `tests_passed == true` + `mutation_score >= 0.80` (scoped) + `finding_resolved == true` (duplication re-audit no longer reports the clone) |
| `test_removal` | `coverage_parity == true` + `mutation_parity == true` + `confidence == "high"` only |

A merge conflict at integration time is an `InvariantViolation` (hard stop), never a manual resolve — the file-disjoint invariant makes textual conflicts structurally impossible under correct operation.
