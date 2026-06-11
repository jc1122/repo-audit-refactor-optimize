# code-health-audit-pipeline report — GATE

## DECOMPOSE (3)
- `scripts/check_skill_requirements.py:528` _skill_entry [medium/complexity] — Split _skill_entry() — complexity 12 exceeds 10
- `scripts/check_skill_requirements.py:528` _skill_entry [medium/complexity] — Shorten _skill_entry() — 65 lines exceeds 50
- `scripts/check_skill_requirements.py:823` build_bootstrap_report [medium/complexity] — Shorten build_bootstrap_report() — 79 lines exceeds 50

## DELETE (1)
- `scripts/check_skill_requirements.py:418` _extract_skill_name [low/dead-code] — Remove unused function '_extract_skill_name' if truly dead

## FORMAT (1)
- `scripts/check_skill_requirements.py:1` scripts/check_skill_requirements.py [low/quality] — Run the formatter on scripts/check_skill_requirements.py

## LINT (1)
- `scripts/check_skill_requirements.py:562` E501@562:89 [medium/quality] — Line too long (116 > 88)

## SIMPLIFY (4)
- `scripts/check_skill_requirements.py:1` <module> [medium/complexity] — Improve maintainability of scripts/check_skill_requirements.py — MI 2.3 below 65
- `scripts/check_release.py:1` <module> [low/complexity] — Improve maintainability of scripts/check_release.py — MI 50.3 below 65
- `scripts/check_skill_requirements.py:345` load_source_overrides [low/complexity] — Reduce parameters of load_source_overrides() — 6 exceeds 5
- `scripts/check_skill_requirements.py:823` build_bootstrap_report [low/complexity] — Reduce parameters of build_bootstrap_report() — 9 exceeds 5

