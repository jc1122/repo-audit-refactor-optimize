# Self-Bootstrapping repo-audit Family — Design

**Status:** approved (brainstorming), pending implementation plan
**Date:** 2026-06-16
**Repos touched:** repo-B `repo-audit-refactor-optimize` (orchestrator), repo-P `perf-benchmark-skill`. repo-A `repo-audit-skills` unchanged (already ships a node installer).

## Problem

Today the orchestrator's Stage-0 bootstrap (`check_skill_requirements.py`) is a
non-mutating *checker*. On a bare machine it correctly detects that the family's
skills are missing, but it cannot install them: every family skill is declared
`source_type: "user-local"`, `install_source: null`, so `_install_command_for_skill`
returns `None` and the skills land in `state: "manual_only"`. A from-scratch run
emits `install_plan.md` = *"No public install candidates were detected"* and sets
`stop_before_discovery: true`. So "install from scratch using the orchestrator only"
is **not** possible — a human must first install the 19 repo-A leaves (via repo-A's
node installer) and perf-benchmark/perf-optimization (via git archive) out of band.

## Goal

One command installs the whole family on a bare machine, staying **private** (git
sources from the three PUBLIC GitHub repos, no public skills registry), with the
capability wired into the orchestrator's existing Stage-0 bootstrap so the
orchestrator's own checker can both *emit* and (with approval) *drive* the install.

## Decisions (locked during brainstorming)

1. **Distribution model:** git-based, private. No publishing to a public skills
   registry. Sources are the three repos at `github.com/jc1122`, all PUBLIC, so
   unauthenticated `git clone` works in a `curl | bash`.
2. **Entry point:** a single top-level installer that installs repo-B FIRST, then
   pulls the rest (solves the chicken-and-egg — repo-B can't install itself before
   it exists). True bare-machine "from scratch" in one command.
3. **Pinning:** the manifest pins fixed tags (reproducible). Bump on each family
   ship. (Not `main`-tracking.)
4. **CI depth:** the real-network end-to-end test is opt-in and excluded from the
   fast `check` job; CI exercises the install path hermetically via a `file://`
   local source so it needs no network.
5. **repo-P installer location:** `bootstrap/install-perf.sh` lives inside repo-P
   (repo-B does not reach into repo-P's directory layout).

## Architecture — three coordinated pieces

### Piece 1 — Manifest gains git `sources` (repo-B `scripts/skill_bootstrap_manifest.json`)

Add a top-level `sources` map (DRY: the 19 leaves all come from one repo) and a
`source` reference on each user-local family skill.

```jsonc
"sources": {
  "repo-audit-skills": {
    "kind": "git",
    "url": "https://github.com/jc1122/repo-audit-skills.git",
    "tag": "v0.8.0",
    "install": ["node", "bin/install-repo-audit-skills.js", "--dest", "{dest}", "--force"]
  },
  "perf-benchmark-skill": {
    "kind": "git",
    "url": "https://github.com/jc1122/perf-benchmark-skill.git",
    "tag": "v0.6.0",
    "install": ["bash", "bootstrap/install-perf.sh", "{dest}"]
  }
}
```

Each leaf entry gains `"source": "repo-audit-skills"`. `perf-benchmark` and
`perf-optimization` gain `"source": "perf-benchmark-skill"`. `find-skills` and
`skill-installer` are NOT family skills (external/registry) and keep their current
`manual_only` behavior — the self-bootstrap covers only the family.

`{dest}` is substituted with the resolved skills root at emit/run time.
`{tag}`/`{url}` are available for substitution in clone commands.

The manifest tags are the single source of truth for pinning. Initial pins:
`repo-audit-skills` → `v0.8.0`, `perf-benchmark-skill` → `v0.6.0`.

### Piece 2 — Bootstrap checker emits real install commands (repo-B `scripts/_skill_probe.py`)

- `_install_command_for_skill`: in addition to the existing `public`/`skills_cli`
  branch, resolve `skill["source"]` against the manifest `sources`. If `kind: "git"`,
  return a command that shallow-clones the source at its pinned tag into a temp dir
  and runs the source's `install` array (with `{dest}` substituted):
  `git clone --depth 1 -b <tag> <url> <tmp> && (cd <tmp> && <install...>)`.
- `_apply_installable_or_manual_state`: a skill with a resolvable git source becomes
  `state: "installable_now"`, `post_install_state: "available_next_run"` (instead of
  `manual_only`).
- **Dedupe by source:** the install plan must list ONE command per source repo
  (installing repo-A's node installer once deploys all 19 leaves), not 19 identical
  commands. Grouping happens where the install plan is assembled
  (`_bootstrap_report.py` install-plan section): collect the distinct source-derived
  commands, emit each once, ordered deterministically by source key.

Result: a from-scratch `check_skill_requirements` run produces an actionable
`install_plan.md` with exactly two `git clone … && …` commands, and the family
skills report `installable_now`. The checker still NEVER auto-runs anything.

### Piece 3 — Top-level one-line installer

**repo-B `bootstrap/install.sh`** (POSIX `sh`, fetchable via raw GitHub):
1. Resolve `dest`: `--dest` flag, else `$AGENT_SKILLS_HOME/skills`, else
   `$CODEX_HOME/skills`, else `~/.agents/skills`. `mkdir -p`.
2. Resolve `ref`: `--ref` flag, else a default pinned tag baked into the script.
   The baked default must equal the tag the script is committed under (when fetched
   from `.../<tag>/bootstrap/install.sh`, it installs repo-B `<tag>`). The release
   process sets this default to the new tag *before* tagging — added to the ship
   checklist below.
3. Clone repo-B at `ref` into a temp dir; install it into `dest/repo-audit-refactor-optimize`
   via `git archive <ref> | tar -x` (repo-B has no node installer; this matches the
   existing deploy method).
4. Read the just-installed repo-B manifest `sources`; for each, shallow-clone at its
   pinned tag into a temp dir and run its `install` array with `{dest}` substituted.
5. Run `python3 dest/repo-audit-refactor-optimize/scripts/check_skill_requirements.py`
   against a throwaway repo; assert `stop_before_discovery: false`; print a summary of
   installed skills + versions.
Flags: `--dest DIR`, `--ref TAG`, `--dry-run` (print the plan; execute nothing).
One-liner:
`curl -fsSL https://raw.githubusercontent.com/jc1122/repo-audit-refactor-optimize/<tag>/bootstrap/install.sh | bash`

**repo-P `bootstrap/install-perf.sh`** (POSIX `sh`, arg `$1 = dest`):
- repo-P contains two skills — `perf-benchmark` (root `SKILL.md`) and a nested
  `perf-optimization/` skill. The script deploys BOTH: root tree → `dest/perf-benchmark`
  (excluding the `perf-optimization/` subdir, docs, tests), and `perf-optimization/` →
  `dest/perf-optimization`. Idempotent (`--force`-style overwrite). Run from a checkout
  of repo-P (the top-level installer clones repo-P then invokes this script from inside it).

### Safety-rule refinement (repo-B `SKILL.md` + `references/bootstrap.md`)

Change *"Never auto-install local/private skills"* to:
> "Auto-install only the pinned git sources declared in the manifest. The top-level
> installer (explicitly invoked by the user) installs them directly; the in-session
> agent runs the checker-emitted commands only with explicit user approval. Never
> install undeclared or arbitrary skills."

This preserves the safety property (no silent/arbitrary installs) while enabling
self-bootstrap from declared, pinned, public sources.

## Data flow

```
bare machine
  └─ curl … install.sh | bash
        ├─ git archive repo-B@tag → dest/repo-audit-refactor-optimize
        ├─ read dest manifest.sources
        │     ├─ clone repo-audit-skills@v0.8.0 → node bin/install-repo-audit-skills.js --dest {dest} --force  (19 leaves)
        │     └─ clone perf-benchmark-skill@v0.6.0 → bash bootstrap/install-perf.sh {dest}  (perf-benchmark + perf-optimization)
        └─ check_skill_requirements → stop_before_discovery:false  ✅

in-session (repo-B already installed, deps missing/partial)
  └─ Stage-0 check_skill_requirements
        └─ install_plan.md lists the 2 deduped git-source commands (installable_now)
              └─ agent runs them ONLY after explicit user approval
```

## Error handling

- Pinned tag absent / clone fails → abort naming the repo + tag; nonzero exit; no
  partial silent success.
- Network offline → clear message ("could not reach <url>").
- `dest` not writable → fail early before any clone.
- Idempotent: re-running overwrites (installers already use `--force`/overwrite);
  safe to re-run after a partial failure.
- **Post-install version-drift guard:** after installing, verify each deployed
  skill's `version:` equals the manifest's pinned tag with the leading `v` stripped
  (`v0.8.0` → `0.8.0`); report any mismatch (catches the leaf-drift class fixed on
  2026-06-16 where deployed 0.7.5 ≠ main 0.8.0).

## Testing

- **repo-B manifest schema** (`check_release.py` extension or new test): every
  family user-local skill has a `source` that resolves to a `sources` entry; each
  source has `kind`/`url`/`tag`/`install`.
- **repo-B `_skill_probe` unit tests:** a git-source skill → `installable_now` +
  the emitted command contains the pinned tag, url, and `{dest}`-substituted install;
  a from-scratch probe (empty roots) → install plan lists EXACTLY the 2 deduped
  source commands (not 19).
- **repo-B installer `--dry-run` test:** `install.sh --dry-run` parses the manifest
  and prints the planned repo-B deploy + 2 source installs at pinned tags, executing
  nothing (assert via captured stdout; no filesystem writes outside a temp scratch).
- **repo-B hermetic e2e (CI-safe):** point a source at a `file://` path (a local
  clone/bundle of the repo) so the install path runs end-to-end with NO network;
  assert the dest ends up with the expected skill dirs + versions. Runs in the
  normal `check`/`convergence-gate` jobs.
- **repo-B real-network e2e (opt-in):** a marked test that actually clones from
  GitHub into a temp dest; excluded from the fast `check` job (network), run on demand.
- **repo-P `install-perf.sh` test:** invoked against a temp dest from a repo-P
  checkout → deploys both `perf-benchmark` and `perf-optimization` skill dirs with
  their `SKILL.md` versions.

## Versioning / ship

- repo-B → **v0.12.0** (new bootstrap capability; minor). Bump `SKILL.md` version,
  `run_diagnosis_wave.__version__`, CHANGELOG; `check_release` stays green.
- repo-P → minor bump for `install-perf.sh` (new install entrypoint).
- repo-A → unchanged (its node installer already exists and is referenced).
- Each repo: branch → PR → both CI jobs green → tag → reinstall → verify deployed
  == pinned. Multi-repo but one cohesive feature.
- **Ship-order + pin-sync checklist:** (1) ship repo-P first, tag it, set the
  manifest `perf-benchmark-skill` pin to that tag; (2) repo-A already at v0.8.0
  (manifest pin matches); (3) in repo-B, set `bootstrap/install.sh`'s baked default
  `ref` to the new repo-B tag (e.g. `v0.12.0`) BEFORE tagging repo-B, then ship +
  tag repo-B. This keeps every pin (manifest sources + installer self-ref) coherent
  with what is actually published.

## Scope / non-goals

- NOT publishing to a public skills registry (explicitly rejected).
- NOT adding a node installer to repo-B/repo-P beyond the shell entrypoints
  (git archive|tar remains repo-B's deploy method).
- NOT changing repo-A's leaf installer (works; only referenced).
- NOT auto-running installs without approval in-session (safety preserved).
