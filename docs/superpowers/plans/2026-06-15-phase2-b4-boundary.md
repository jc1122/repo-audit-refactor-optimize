# Phase 2 · B4 (capstone) — graduate coverage-gap to a binary CI gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record the evidence-based boundary decision (coverage-gap graduates to a binary CI gate; TQA/TRT/mutation stay Tier-2 advisory), wire a `check_coverage_gap.py` gate + empty baseline + CI step into repo-B (plain coverage) and repo-P (subprocess-capture), keep each repo's own wave gate `active 0` (recursion-safe), verify green in real CI, and mark Phase-2 complete — no release.

**Architecture:** coverage-gap becomes a **separate** binary gate (NOT folded into the artifact-free wave; mirrors repo-A's `check_coverage_gap.py`). One small arg-driven gate script per repo runs the suite under coverage, runs the cloned leaf (`$LEAF`), and ratchets findings against `scripts/coverage_gap_baseline.json` (`[]`). The script is added to the existing `convergence-gate` CI job (it already clones the leaf + uses `fetch-depth: 0`).

**Tech Stack:** Python 3.14, coverage.py 7.14.1, pytest, the coverage-gap leaf, GitHub Actions, git + `gh`.

**Spec:** `docs/superpowers/specs/2026-06-15-phase2-b4-boundary-design.md`

---

## Repo / path conventions

- **repo-A** = `/home/jakub/projects/repo-audit-skills` (unchanged — already gates coverage-gap)
- **repo-B** = `/home/jakub/projects/repo-audit-refactor-optimize` (campaign home)
- **repo-P** = `/home/jakub/projects/perf-benchmark-skill`
- Pinned leaves clone (from B1 sims, reused): `/tmp/b1/leaves` (leaf at `/tmp/b1/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py`)
- Evidence (repo-B, committed): `docs/superpowers/b4-evidence/`

---

## File Structure

| File | Repo | Responsibility | Task |
|------|------|----------------|------|
| `docs/superpowers/b4-evidence/decision.md` | B | graduation decision + B1–B3 evidence | Task 1 |
| `scripts/check_coverage_gap.py` | B, P | the binary coverage-gap gate (arg-driven) | Tasks 2,3 |
| `scripts/coverage_gap_baseline.json` | B, P | `[]` (B1 converged to zero) | Tasks 2,3 |
| `.github/workflows/check.yml` | B, P | coverage-gap step in `convergence-gate` job | Tasks 2,3 |
| roadmap `...self-contained-convergent-family.md` | B | mark Phase-2 complete | Task 4 |

No `SKILL.md`/version/CHANGELOG change → no release.

---

## The gate script (identical in both repos; used verbatim by Tasks 2 & 3)

`scripts/check_coverage_gap.py`:

```python
#!/usr/bin/env python3
"""Binary coverage-gap convergence gate (Phase-2 B4 graduation).

Runs this repo's suite under coverage, feeds the JSON report to the coverage-gap
leaf, and ratchets findings against scripts/coverage_gap_baseline.json. Returns a
real non-zero exit on any finding outside the baseline (not piped — L4). The leaf
path comes from $LEAF (CI clones it) or the local installed skills dir.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404: local trusted coverage + leaf invocation
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "coverage_gap_baseline.json"
_DEFAULT_LEAF = Path.home() / ".claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py"


def _leaf() -> str:
    return os.environ.get("LEAF") or str(_DEFAULT_LEAF)


def _write_rc(out_dir: Path) -> Path:
    rc = out_dir / ".coveragerc"
    rc.write_text(
        f"[run]\nparallel = true\ndata_file = {out_dir / '.coverage'}\n"
        "[report]\nignore_errors = true\n",
        encoding="utf-8",
    )
    return rc


def _coverage_env(out_dir: Path, rc: Path, capture: bool) -> dict[str, str]:
    env = dict(os.environ)
    if capture:
        hook = out_dir / "hook"
        hook.mkdir(exist_ok=True)
        (hook / "sitecustomize.py").write_text(
            "import coverage\ncoverage.process_startup()\n", encoding="utf-8"
        )
        env["PYTHONPATH"] = os.pathsep.join([str(hook), env.get("PYTHONPATH", "")])
        env["COVERAGE_PROCESS_START"] = str(rc)
    return env


def generate_coverage(out_dir: Path, suites: list[str], capture: bool) -> Path:
    rc = _write_rc(out_dir)
    env = _coverage_env(out_dir, rc, capture)
    base = [sys.executable, "-m", "coverage"]
    run = base + ["run", f"--rcfile={rc}", "-m", "pytest", *suites, "-q", "-p", "no:cacheprovider"]
    subprocess.run(run, cwd=ROOT, env=env, check=False, capture_output=True)  # nosec B603
    subprocess.run(base + ["combine", f"--rcfile={rc}"], cwd=ROOT, check=False, capture_output=True)  # nosec B603
    cov_json = out_dir / "coverage.json"
    subprocess.run(
        base + ["json", f"--rcfile={rc}", f"--data-file={out_dir / '.coverage'}", "-o", str(cov_json)],
        cwd=ROOT, check=False, capture_output=True,  # nosec B603
    )
    return cov_json


def run_leaf(cov_json: Path, out_dir: Path, prefixes: list[str]) -> list[dict]:
    cmd = [sys.executable, _leaf(), "--root", str(ROOT), "--out-dir", str(out_dir / "leaf"),
           "--coverage-json", str(cov_json)]
    for prefix in prefixes:
        cmd += ["--source-prefix", prefix]
    subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True)  # nosec B603
    raw = json.loads((out_dir / "leaf" / "coverage-gap_findings.json").read_text(encoding="utf-8"))
    return sorted(
        ({"path": f["path"], "metric": f["metric"]["name"]} for f in raw),
        key=lambda d: (d["path"], d["metric"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Binary coverage-gap convergence gate.")
    parser.add_argument("--suite", action="append", dest="suites", default=[],
                        help="Pytest suite dir/file (repeatable).")
    parser.add_argument("--source-prefix", action="append", dest="prefixes", default=[],
                        help="Production source prefix for the leaf (repeatable).")
    parser.add_argument("--subprocess-capture", action="store_true",
                        help="Capture subprocess coverage (for subprocess-tested CLIs).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        cov_json = generate_coverage(out_dir, args.suites or ["tests"], args.subprocess_capture)
        current = run_leaf(cov_json, out_dir, args.prefixes or ["scripts"])
    new = [f for f in current if f not in baseline]
    if new:
        print(json.dumps({"status": "fail", "new_findings": new, "baseline": len(baseline)}))
        return 1
    print(json.dumps({"status": "pass", "count": len(current), "baseline": len(baseline)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## Task 0: Setup

- [ ] **Step 1:** repo-B branch `feat/phase2-b4` (created in brainstorming); `mkdir -p docs/superpowers/b4-evidence`. repo-P: `cd /home/jakub/projects/perf-benchmark-skill && git checkout main && git checkout -b feat/phase2-b4`.
- [ ] **Step 2:** Confirm `/tmp/b1/leaves` exists (`test -x /tmp/b1/leaves/node_modules/.bin/jscpd`); if not, `git clone --depth 1 --branch v0.7.2 https://github.com/jc1122/repo-audit-skills.git /tmp/b1/leaves && (cd /tmp/b1/leaves && npm ci)`.

---

## Task 1: Record the graduation decision

**Files:** Create `docs/superpowers/b4-evidence/decision.md` (repo-B)

- [ ] **Step 1:** Write `decision.md` with the spec §2 evidence table (coverage-gap GRADUATES — deterministic, cheap input, converges 0, repo-A already gates it; TQA stays advisory — judgment-laden rubric; TRT stays advisory — slow, 0 safe DELETE; mutation stays advisory — convention-blocked on repo-A) and the rationale that coverage-gap is gated **separately** (not folded into the artifact-free wave). Reference `b1-evidence/`, `b2-evidence/`, `b3-evidence/`.
- [ ] **Step 2: Commit:** `git add docs/superpowers/b4-evidence/decision.md && git commit -m "evidence(b4): record Tier-2->Tier-1 graduation decision (coverage-gap graduates; TQA/TRT/mutation stay advisory)" ...trailer`.

---

## Task 2: Wire repo-B coverage-gap gate (plain coverage)

**Files:** Create `scripts/check_coverage_gap.py`, `scripts/coverage_gap_baseline.json`; Modify `.github/workflows/check.yml` (repo-B)

- [ ] **Step 1:** Create `scripts/check_coverage_gap.py` with the verbatim gate script above; create `scripts/coverage_gap_baseline.json` containing exactly `[]`.

- [ ] **Step 2: Run the gate locally — expect pass, 0 findings** (repo-B uses **plain** coverage):
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
LEAF=/tmp/b1/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  python3 scripts/check_coverage_gap.py --suite tests --source-prefix scripts; echo "exit=$?"
```
Expected: `{"status": "pass", "count": 0, "baseline": 0}` and `exit=0`.

- [ ] **Step 3: Recursion check — the new script must NOT break repo-B's own wave gate.** Run the pinned-jscpd wave sim:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
WAVE_RUNNER="$(pwd)/scripts/run_diagnosis_wave.py" SKILLS_ROOT=/tmp/b1/leaves/skills \
  PATH="/tmp/b1/leaves/node_modules/.bin:$PATH" python3 scripts/check_wave_baseline.py | tail -6
```
Expected: `{"status":"pass","accepted":N,"active":0}`. **If `active != 0`** (the new script tripped a code-health/perf-smell/security lane), read the new finding: **fix the script** to be clean (smaller function, stdlib idiom, add a `# nosec` only where bandit legitimately flags the trusted subprocess call), re-run. Only if a finding is a deliberate pattern, add a justified **wave-lane** `.repo-audit/accept.json` entry. Do not proceed until `active 0`.

- [ ] **Step 4:** Add the coverage-gap step to `.github/workflows/check.yml`'s `convergence-gate` job — after the existing wave step, add pytest/hypothesis to the install and the gate step:
  - In the "Install leaf toolchain" run block, append: `python -m pip install pytest==9.0.3 hypothesis==6.155.2`
  - After the "Convergence gate (Tier-1 wave)" step, add:
```yaml
      - name: Coverage-gap gate (Tier-1 graduation)
        env:
          LEAF: /tmp/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py
        run: python3 scripts/check_coverage_gap.py --suite tests --source-prefix scripts
```

- [ ] **Step 5: Commit:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add scripts/check_coverage_gap.py scripts/coverage_gap_baseline.json .github/workflows/check.yml
git commit -m "feat(gate): graduate coverage-gap to a binary CI gate (plain coverage; baseline 0)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Wire repo-P coverage-gap gate (subprocess-capture)

**Files:** Create `scripts/check_coverage_gap.py`, `scripts/coverage_gap_baseline.json`; Modify `.github/workflows/check.yml` (repo-P)

- [ ] **Step 1:** Create `scripts/check_coverage_gap.py` (the **same** verbatim gate script) and `scripts/coverage_gap_baseline.json` = `[]`.

- [ ] **Step 2: Run the gate locally with `--subprocess-capture` — expect pass, 0 findings:**
```bash
cd /home/jakub/projects/perf-benchmark-skill
LEAF=/tmp/b1/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  python3 scripts/check_coverage_gap.py --subprocess-capture \
  --suite tests --suite perf-optimization/tests \
  --source-prefix scripts --source-prefix perf-optimization/scripts; echo "exit=$?"
```
Expected: `{"status": "pass", "count": 0, "baseline": 0}` and `exit=0`. (Plain coverage would falsely report `verify_win.py`/`select_candidate.py` — confirm `--subprocess-capture` gives 0.)

- [ ] **Step 3: ruff-clean the new script** (repo-P CI's format/lint gate):
```bash
cd /home/jakub/projects/perf-benchmark-skill
~/.local/bin/ruff format scripts/check_coverage_gap.py && ~/.local/bin/ruff format --check scripts/check_coverage_gap.py && ~/.local/bin/ruff check scripts/check_coverage_gap.py
```
Expected: clean.

- [ ] **Step 4: Recursion check — repo-P wave gate stays `active 0`:**
```bash
cd /home/jakub/projects/perf-benchmark-skill
WAVE_RUNNER=/tmp/b1/runner/scripts/run_diagnosis_wave.py SKILLS_ROOT=/tmp/b1/leaves/skills \
  PATH="/tmp/b1/leaves/node_modules/.bin:$PATH" python3 scripts/check_wave_baseline.py | tail -6
```
(If `/tmp/b1/runner` is absent: `git clone --depth 1 --branch v0.8.1 https://github.com/jc1122/repo-audit-refactor-optimize.git /tmp/b1/runner`.)
Expected: `{"status":"pass","active":0}`. **If `active != 0`, fix the script** (same discipline as Task 2 Step 3) until `active 0`.

- [ ] **Step 5:** Add the coverage-gap step to repo-P `.github/workflows/check.yml`'s `convergence-gate` job — append `python -m pip install pytest` to its install block, then after the wave step add:
```yaml
      - name: Coverage-gap gate (Tier-1 graduation)
        env:
          LEAF: /tmp/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py
        run: python3 scripts/check_coverage_gap.py --subprocess-capture --suite tests --suite perf-optimization/tests --source-prefix scripts --source-prefix perf-optimization/scripts
```

- [ ] **Step 6: Commit:**
```bash
cd /home/jakub/projects/perf-benchmark-skill && git add scripts/check_coverage_gap.py scripts/coverage_gap_baseline.json .github/workflows/check.yml
git commit -m "feat(gate): graduate coverage-gap to a binary CI gate (subprocess-capture; baseline 0)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Mark Phase-2 complete + ship + verify

- [ ] **Step 1: Mark the roadmap Phase-2 section complete** — in repo-B `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md`, append a "Phase 2 — COMPLETE (2026-06-15)" note under the Phase-2 section: B0 (audit-budget −51%), B1 (coverage-gap converged), B2 (test-* triaged), B3 (mutation per repo), B4 (coverage-gap graduated to a binary CI gate for all three repos). Commit on `feat/phase2-b4`.

- [ ] **Step 2: repo-B ship** — full suite + merge + push:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/ -q -p no:cacheprovider | tail -1
git checkout main && git merge --no-ff feat/phase2-b4 -m "Merge feat/phase2-b4: graduate coverage-gap to a binary CI gate (capstone) + Phase-2 complete" && git push origin main
```

- [ ] **Step 3: repo-B real CI — verify ALL THREE checks green** (`check`, `convergence-gate` incl. the new coverage-gap step):
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && rid=$(gh run list --branch main --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $rid --exit-status && gh run view $rid --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'
```
Expected: `check: success`, `convergence-gate: success` (the coverage-gap step runs inside convergence-gate). If the coverage-gap step is red: `gh run view $rid --log-failed`, fix, do not leave a red gate. **If it cannot be made green for repo-P specifically, apply the spec §4 fallback** (ship repo-B, defer repo-P with a recorded reason) — never a red gate.

- [ ] **Step 4: repo-P ship** — ruff + suite + merge + push:
```bash
cd /home/jakub/projects/perf-benchmark-skill
~/.local/bin/ruff format --check scripts/ tests/ && ~/.local/bin/ruff check scripts/ tests/
python3 -m pytest tests/ perf-optimization/tests/ -q -p no:cacheprovider | tail -1
git checkout main && git merge --no-ff feat/phase2-b4 -m "Merge feat/phase2-b4: graduate coverage-gap to a binary CI gate (capstone)" && git push origin main
```

- [ ] **Step 5: repo-P real CI — verify green:**
```bash
cd /home/jakub/projects/perf-benchmark-skill && rid=$(gh run list --branch main --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $rid --exit-status && gh run view $rid --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'
```
Expected: `check: success`, `convergence-gate: success`. Same red-gate discipline + fallback.

- [ ] **Step 6: Delete merged branches** (`git branch -d feat/phase2-b4` in repo-B and repo-P).

- [ ] **Step 7: Update memory** — refresh `repo-audit-dogfood-loops` (+ `MEMORY.md`): **B4 SHIPPED — coverage-gap graduated to a binary CI gate across all 3 repos (repo-A pre-existing; repo-B plain, repo-P subprocess-capture; baseline 0); TQA/TRT/mutation stay Tier-2 advisory; Phase-2 COMPLETE; "every skill on every skill + converge + full pass, CI-enforced" met; no release.** Mark the campaign terminal.

---

## Self-Review (planner)

- **Spec coverage:** §2 decision → Task 1; §3 wiring (per-repo coverage mode) → Tasks 2 (plain) / 3 (capture); §4 DoD → Task 4; §5 recursion safety → Tasks 2 Step 3 / 3 Step 4 (wave sim + fix-until-active-0); §6 no-release/fetch-depth → Tasks 2/3 (infra-only) ; §4 fallback → Task 4 Steps 3/5.
- **Placeholder scan:** none — the gate script is complete and verbatim; per-repo suites/prefixes/flags are concrete; CI YAML snippets are exact. (`$rid` is a runtime gh id.)
- **Type/identity consistency:** the gate script's `build_parser`/`generate_coverage`/`run_leaf`/`main` are internally consistent; the leaf invocation (`--root/--out-dir/--coverage-json/--source-prefix`) matches `coverage_gap_audit.py` read 2026-06-15; `$LEAF` is set in CI to the cloned leaf, default to `~/.claude/skills` locally; baseline `[]` matches B1's converged-zero.
- **Risk:** recursion (new script tripping the repo's own wave) → Tasks 2/3 wave sim catches pre-merge with a fix loop; subprocess-capture-in-CI (repo-P) → local capture sim + real-CI verify with the honest no-red-gate fallback; ruff on repo-P → Task 3 Step 3.
