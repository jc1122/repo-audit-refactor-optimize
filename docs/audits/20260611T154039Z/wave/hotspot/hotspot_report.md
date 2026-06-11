# hotspot-audit report

Suppressions: `suppressed_solo_author`=1
`suppressed_own_test_pairs`=1

## DECOMPOSE (3)
- `scripts/check_skill_requirements.py:1` scripts/check_skill_requirements.py -- churn_complexity_product=1976 [low]
- `scripts/skill_bootstrap_manifest.json:1` scripts/skill_bootstrap_manifest.json -- churn_complexity_product=1250 [low]
- `tests/test_check_skill_requirements.py:1` tests/test_check_skill_requirements.py -- churn_complexity_product=23970 [high]

## RESTRUCTURE (2)
- `SKILL.md:1` SKILL.md<->references/pipeline.md -- temporal_coupling_ratio=0.71 [medium]
- `scripts/skill_bootstrap_manifest.json:1` scripts/skill_bootstrap_manifest.json<->tests/test_check_skill_requirements.py -- temporal_coupling_ratio=1 [medium]

