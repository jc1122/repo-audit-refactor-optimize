import scripts.allocate_batches as ab

KPIS = [
    {"iteration": 1,
     "rows_before": {"repo-a": 40, "repo-b": 10, "repo-p": 20},
     "rows_after":  {"repo-a": 38, "repo-b": 4,  "repo-p": 19}},
]
# closed this window: repo-a 2, repo-b 6, repo-p 1  -> repo-b best trailing yield


def test_guaranteed_minimum_every_active_repo_gets_at_least_one():
    alloc = ab.allocate(["repo-a", "repo-b", "repo-p"], KPIS, surplus=3, cap=6)
    assert alloc["repo-a"] >= 1
    assert alloc["repo-b"] >= 1
    assert alloc["repo-p"] >= 1


def test_surplus_goes_to_best_trailing_yield():
    alloc = ab.allocate(["repo-a", "repo-b", "repo-p"], KPIS, surplus=3, cap=6)
    assert alloc["repo-b"] == max(alloc.values())   # best yield repo wins surplus


def test_cap_per_repo_never_exceeded():
    alloc = ab.allocate(["repo-a"], KPIS, surplus=100, cap=6)
    assert alloc["repo-a"] <= 6


def test_no_kpis_still_gives_minimum():
    alloc = ab.allocate(["repo-a", "repo-b"], [], surplus=2, cap=6)
    assert alloc["repo-a"] >= 1
    assert alloc["repo-b"] >= 1


def test_rationale_is_one_line_and_cites_yield():
    alloc = ab.allocate(["repo-a", "repo-b", "repo-p"], KPIS, surplus=3, cap=6)
    r = ab.rationale(["repo-a", "repo-b", "repo-p"], KPIS, alloc)
    assert isinstance(r, str)
    assert "\n" not in r
    assert "repo-b" in r            # names the surplus winner
