# Bootstrap

## Purpose

Bootstrap is Stage 0. Its job is to determine whether the relevant subskills are usable in the current agent session before the orchestrator starts repository discovery.

Bootstrap is required because the same metaskill can run on machines with different skill inventories, different repository-local skill trees, and different runtime roots. It is designed to work with any orchestrator — not only OpenAI Codex.

## Checker and Manifest

Use:

- `scripts/check_skill_requirements.py`
- `scripts/skill_bootstrap_manifest.json`

The checker is non-mutating. It never installs skills. It only:

- pre-scans the target repository
- resolves active lanes
- checks usable and advisory skill roots
- applies user and repo source overrides
- emits a bootstrap report and install plan

## Root Search Order

Search usable roots in this order:

1. orchestrator skills home: `$AGENT_SKILLS_HOME/skills`, falling back to `$CODEX_HOME/skills` (backward compatibility), then `~/.codex/skills`
2. bundled runtime roots under the orchestrator home (e.g. `<orchestrator-home>/vendor_imports/skills/skills`)
3. `~/.agents/skills` when present
4. `<repo>/.agents/skills`
5. explicit extra roots passed to the checker

> **Note:** `CODEX_HOME` and `~/.codex` are retained for backward compatibility with OpenAI Codex. Other orchestrators should set `AGENT_SKILLS_HOME` to their own skill root.

Foreign-agent roots are optional and advisory only. They may be reported, but they must never satisfy a usable dependency.

## Override Files

Use these optional source override files:

- user-level: `${XDG_CONFIG_HOME:-~/.config}/repo-audit-refactor-optimize/skill-sources.json`
- repo-level: `<repo>/.repo-audit-refactor-optimize/skill-sources.json`

Precedence is:

1. repo override
2. user override
3. built-in manifest defaults

Malformed override files hard-fail bootstrap. Invalid entries for inactive or unknown skills are ignored with warnings. Invalid entries for explicitly required skills or skills needed by a blocking lane are fatal.

## Dependency States

Use these states:

- `usable_now`: the skill exists in a usable root for the current session
- `installable_now`: the skill is missing but a public install source is known
- `available_next_run`: the post-install state when the skill would only become usable after restart
- `manual_only`: no trusted install path is known, or only local/private/manual recovery is allowed
- `advisory_only`: the skill exists only in a foreign-agent root
- `blocking_missing`: the skill is missing and there is no safe fallback for a blocking lane

## Lane States

Use these states:

- `full`: preferred lane behavior is available now
- `degraded`: a defined skill fallback is available now
- `manual`: only the manual fallback is safe in the current session
- `blocked`: the lane cannot proceed safely

## Install Policy

Use prompt-plus-install behavior:

- do not install anything until the user approves
- install only public skills automatically
- prefer `skill-installer` when it is already available
- fall back to raw `npx skills add` or `npx skills find` when bootstrap helpers are missing
- do not auto-install local or private skills even if a source override exists

Without a configured source mapping, local or private skills remain `manual_only`.

## Mixed Gate Failure Behavior

Use a mixed gate:

- hard-stop when a blocking lane has no safe equivalent and no safe manual fallback
- continue degraded when a non-blocking lane can still proceed safely
- keep the report explicit about which lanes are full, degraded, manual, or blocked

## Restart Rule

Installed skills are not assumed usable in the same session.

Apply this rule:

- if bootstrap installs a blocking skill, stop and restart before continuing
- if bootstrap installs only optional skills, continue the current run in degraded mode and treat those skills as `available_next_run`

## Required Outputs

Write outputs into the run artifact directory under `bootstrap/`:

- `bootstrap_report.json`
- `bootstrap_report.md`
- `install_plan.md`
