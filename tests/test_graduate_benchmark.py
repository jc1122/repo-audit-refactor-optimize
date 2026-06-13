# tests/test_graduate_benchmark.py
import importlib

gb = importlib.import_module("scripts.graduate_benchmark")


def test_graduate_copies_harness_into_benchmarks(tmp_path):
    # a synthesized (ephemeral) harness
    src = tmp_path / "run" / "perf" / "find_max"
    src.mkdir(parents=True)
    (src / "bench_find_max.py").write_text("print('bench')\n", encoding="utf-8")
    (src / "make_input.py").write_text("def make_input(n):\n    return list(range(n))\n", encoding="utf-8")

    repo = tmp_path / "repo"
    repo.mkdir()
    res = gb.graduate(harness_dir=src, repo_root=repo, name="find_max")

    assert (repo / "benchmarks" / "find_max" / "bench_find_max.py").exists()
    assert (repo / "benchmarks" / "find_max" / "make_input.py").exists()
    assert res["benchmark_dir"].endswith("benchmarks/find_max")
    assert sorted(res["copied"]) == ["bench_find_max.py", "make_input.py"]


def test_graduate_does_not_write_a_ledger(tmp_path):
    # the ledger is owned by perf-benchmark --baseline-ledger, never by graduation
    src = tmp_path / "h"
    src.mkdir()
    (src / "bench_x.py").write_text("x\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()

    gb.graduate(harness_dir=src, repo_root=repo, name="x")
    assert not (repo / "docs" / "perf" / "baseline_ledger.jsonl").exists()


def test_graduate_is_idempotent(tmp_path):
    src = tmp_path / "h"
    src.mkdir()
    (src / "bench_x.py").write_text("v1\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    gb.graduate(harness_dir=src, repo_root=repo, name="x")
    (src / "bench_x.py").write_text("v2\n", encoding="utf-8")
    gb.graduate(harness_dir=src, repo_root=repo, name="x")  # re-graduate refreshes
    assert (repo / "benchmarks" / "x" / "bench_x.py").read_text() == "v2\n"
