# Repo Audit Refactor Optimize (v1.0.0)

Thin portable skill for structured repository audits with optional authorized
fixes. Detection lives in the `repo-audit` CLI (package `repo-audit-checks`
v1.0.0+, owned by the repo-audit-skills repository); this skill owns the
workflow, ranking/execution discipline, and acceptance policy.

- `SKILL.md`: the portable workflow (audit-only default, authorized-fix mode)
- `references/`: prioritization, remediation playbook, verification, acceptance, migration guide
- `scripts/repo-audit`: launcher resolving the install-time isolated venv (no activation needed)
- `scripts/run_diagnosis_wave.py`: deprecated thin wrapper around `repo-audit scan`
- acceptance policy lives in the core (`repo_audit.accept`, single source of
  truth); this repo keeps the user-facing `references/acceptance.md` only
- `bootstrap/install.sh`: same-body two-host installer; core goes into an
  isolated `<dest>/repo-audit-venv` (or `--venv DIR`), never system Python

## Usage

```bash
"$SKILL_DIR/scripts/repo-audit" doctor
"$SKILL_DIR/scripts/repo-audit" scan --root /path/to/target-repo --out-dir /tmp/audit-run --preset code-health
./bootstrap/install.sh --harness codex --core 'git+https://github.com/jc1122/repo-audit-skills@v1.0.0'
```

(`SKILL_DIR` is the directory containing the installed `SKILL.md`.)

Run the checks:

```bash
pytest -q
python3 scripts/check_release.py
```

Migrating from v0.12.x? Read `references/MIGRATION.md`.
