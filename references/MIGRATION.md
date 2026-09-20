# Migration guide: v0.12.x → v1.0.0

v1.0.0 turns this repository into a thin portable skill. Detection moved to the
`repo-audit` CLI (package `repo-audit-checks`, owned by repo-audit-skills).
This skill keeps the workflow, the ranking and execution discipline, and the
acceptance policy — not the engines.

## Command mapping

| v0.12.x | v1.0.0 |
|---|---|
| `python3 scripts/check_skill_requirements.py --repo R --out-dir D` | `repo-audit doctor` (capability diagnostics, no skill scanning) |
| `python3 scripts/run_diagnosis_wave.py --repo R --out-dir D --lanes ...` | `repo-audit scan --root R --out-dir D --checks ...` (wrapper forwards `--repo/--root`, `--out-dir`, `--lanes` as `--checks`, `--checks`, `--preset`, `--accept`, `--coverage-json`, `--source-prefix`, `--rev` for one release; `--baseline`, `--registry`, `--skills-root`, `--exclude-prefix`, `--security-config`, `--hotspot-config` are rejected with exit 2) |
| `python3 scripts/check_wave_baseline.py` | retired; the CLI run record carries completed / findings / skipped / error states |
| `python3 scripts/mprr_run.py plan/integrate/reaudit` | retired with no replacement; the host schedules and merges |
| `python3 scripts/check_toolchain.py` | retired; the CLI reports tool capabilities per check |
| `python3 scripts/check_mutation_floor.py`, `check_coverage_gap.py` | retired as gates; mutation and coverage remain individually selectable checks |
| `python3 scripts/synth_run.py`, `synthesize_perf.py`, `synthesize_packets.py` | retired; performance work goes through the perf-benchmark skill |
| `scripts/mine_iteration_kpis.py`, `allocate_batches.py`, `run_instruction_eval.py` | retired campaign telemetry; not shipped |

## Baselines → acceptance

`--baseline <array-of-identities.json>` no longer exists. Convert each baseline
row into a `.repo-audit/accept.json` `finding` entry with a reason (expiry and
ceilings optional), then pass `--accept <file>` or drop the file at the target
repo root. The old `migrate_baseline_to_accept.py` helper is retired; the
format is small enough to convert by hand (see `references/acceptance.md`).

## Installer

`bootstrap/install.sh` no longer clones skill source repos or scans skill
roots. It copies this skill body into `--dest DIR` (or `--harness codex |
claude` for the default roots) and installs the detection runtime from
`--core SPEC` (local directory, wheel file, or pip requirement, default
`git+https://github.com/jc1122/repo-audit-skills@v1.0.0`) into an isolated
`<dest>/repo-audit-venv` — or into an existing environment with `--venv DIR`
(`--python BIN` selects the interpreter new venvs are created from). System
Python is never touched. The installed `scripts/repo-audit` launcher resolves
that environment, so the skill works from any cwd with no activation.

## Frontmatter

Skills now use Agent Skills frontmatter: `name`, `description`, and
`metadata.version` (1.0.0). The old top-level `version:` key is gone; tooling
that parsed it must read `metadata.version`.

## Removed guarantees

File-disjoint batches are no longer claimed conflict-free; harness-guaranteed
process skills (`verification-before-completion`, `dispatching-parallel-agents`,
`subagent-driven-development`) no longer exist — delegation is host-native and
optional, sequential execution is fully supported. Exit statuses are bounded
(0 clean, 1 findings, 2 incomplete/error); finding counts live in JSON.
