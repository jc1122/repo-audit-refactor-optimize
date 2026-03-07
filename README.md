# Repo Audit Refactor Optimize

`repo-audit-refactor-optimize` is a repository-local skill for running a structured audit and remediation workflow across Python, C, Rust, and assembly codebases.

It focuses on:
- bootstrapping required subskills
- profiling repository structure and verification surfaces
- synthesizing a ranked remediation backlog
- executing safe cleanup, refactors, and performance work in verified batches

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
