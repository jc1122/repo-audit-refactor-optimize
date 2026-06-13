import json
import subprocess
import scripts.mine_iteration_kpis as m


def test_rows_per_hour_from_counts_and_duration():
    kpi = m.compute_kpi(
        iteration=5,
        rows_before={"repo-a": 40, "repo-b": 7},
        rows_after={"repo-a": 36, "repo-b": 7},
        phase_seconds={"diagnosis": 120.0, "execution": 3480.0, "ship": 600.0},
        worker_runs=[{"repairs": 1}, {"repairs": 0}, {"repairs": 0}],
        ci_wait_seconds=300.0,
    )
    assert kpi["rows_closed"] == 4
    assert round(kpi["rows_per_hour"], 2) == round(4 / (4200 / 3600), 2)
    assert kpi["repair_rate"] == 1 / 3
    assert kpi["ci_wait_seconds"] == 300.0
    assert kpi["iteration"] == 5


def test_regression_flag_only_on_loop_controlled_metrics():
    # CI wait growth must NOT trip the regression flag (external, not loop-controlled).
    prev = {"rows_per_hour": 4.0, "repair_rate": 0.1, "ci_wait_seconds": 100.0}
    cur = {"rows_per_hour": 4.1, "repair_rate": 0.1, "ci_wait_seconds": 9000.0}
    assert m.is_regression(cur, prev) is False
    worse = {"rows_per_hour": 1.0, "repair_rate": 0.5, "ci_wait_seconds": 100.0}
    assert m.is_regression(worse, prev) is True


def test_load_baseline_rows_counts_top_level_list(tmp_path):
    # A flat-list baseline (like instruction_lint_baseline.json) must count len(),
    # not return {} (which silently zeroes rows_closed).
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    bl = repo / "b.json"
    bl.write_text(json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "b.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    rows = m._load_baseline_rows(repo, sha, "b.json")
    assert sum(rows.values()) == 3      # was 0 before the fix
