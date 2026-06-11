# hotspot-audit report

## DECOMPOSE (4)
- `SKILL.md:1` SKILL.md -- churn_complexity_product=1150 [low]
- `scripts/check_skill_requirements.py:1` scripts/check_skill_requirements.py -- churn_complexity_product=18837 [high]
- `scripts/skill_bootstrap_manifest.json:1` scripts/skill_bootstrap_manifest.json -- churn_complexity_product=1250 [low]
- `tests/test_check_skill_requirements.py:1` tests/test_check_skill_requirements.py -- churn_complexity_product=23970 [high]

## RESTRUCTURE (5)
- `SKILL.md:1` SKILL.md -- author_concentration=1 [low]
- `scripts/check_skill_requirements.py:1` scripts/check_skill_requirements.py -- author_concentration=1 [low]
- `scripts/check_skill_requirements.py:1` scripts/check_skill_requirements.py<->tests/test_check_skill_requirements.py -- temporal_coupling_ratio=0.88 [medium]
- `scripts/skill_bootstrap_manifest.json:1` scripts/skill_bootstrap_manifest.json<->tests/test_check_skill_requirements.py -- temporal_coupling_ratio=1 [medium]
- `tests/test_check_skill_requirements.py:1` tests/test_check_skill_requirements.py -- author_concentration=1 [low]

