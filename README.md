# Repo Audit Refactor Optimize

`repo-audit-refactor-optimize` is a repository-local skill for running a structured audit and remediation workflow. Its deterministic diagnosis lanes (test, code-health, coverage) are Python-first, built on the repo-audit-skills family; C, Rust, and assembly codebases are handled in manual mode with the tooling gap recorded.

It focuses on:
- bootstrapping required subskills
- profiling repository structure and verification surfaces
- synthesizing a ranked remediation backlog
- executing safe cleanup, refactors, and performance work in verified batches

**Requirement:** the deterministic diagnosis lanes require `repo-audit-skills` v0.3.0+ installed (from github.com/jc1122/repo-audit-skills).

## Repository Layout

- `SKILL.md`: top-level orchestration workflow
- `references/`: stage order, lane activation, prioritization, and verification guidance
- `scripts/check_skill_requirements.py`: bootstrap checker for required and optional subskills
- `tests/`: unit tests covering bootstrap and lane resolution behavior
- `agents/openai.yaml`: example agent interface metadata

## Basic Usage

Run the bootstrap checker against a target repository:

```bash
python3 scripts/check_skill_requirements.py \
  --repo /path/to/target-repo \
  --out-dir /tmp/repo-audit-refactor-optimize/run
```

Run the tests:

```bash
pytest -q
```

## Status

This repository contains the skill definition, reference material, bootstrap manifest, and tests for the bootstrap checker.
