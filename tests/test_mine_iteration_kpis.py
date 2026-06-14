import json
import subprocess
import scripts.mine_iteration_kpis as m
from pathlib import Path


def test_rows_per_hour_from_counts_and_duration():
    kpi = m.compute_kpi(
        m.KpiInputs(
            iteration=5,
            rows_before={"repo-a": 40, "repo-b": 7},
            rows_after={"repo-a": 36, "repo-b": 7},
            phase_seconds={"diagnosis": 120.0, "execution": 3480.0, "ship": 600.0},
            worker_runs=[{"repairs": 1}, {"repairs": 0}, {"repairs": 0}],
            ci_wait_seconds=300.0,
        )
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
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    rows = m._load_baseline_rows(repo, sha, "b.json")
    assert sum(rows.values()) == 3  # was 0 before the fix


def test_mine_mprr_kpis_from_events(tmp_path):
    import importlib, sys
    from pathlib import Path

    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    miner = importlib.import_module("scripts.mine_iteration_kpis")
    events = tmp_path / "mprr_events.jsonl"
    events.write_text(
        "\n".join(
            [
                '{"event": "start", "id": "a", "files": ["x.py"]}',
                '{"event": "start", "id": "b", "files": ["y.py"]}',
                '{"event": "merge", "id": "a", "conflict": false, "merged": true}',
                '{"event": "discard", "id": "b", "conflict": false, "merged": false}',
            ]
        )
        + "\n"
    )
    kpi = miner.mine_mprr_kpis(str(events), ceiling=4)
    assert kpi["dispatched"] == 2
    assert kpi["merged"] == 1
    assert kpi["merge_conflict_rate"] == 0.0
    assert kpi["peak_concurrency"] == 2
    assert 0.0 <= kpi["pool_utilization"] <= 1.0


def _init_repo(path):
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)


def _commit(repo, relpath, content):
    f = repo / relpath
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", relpath], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_main_appends_line_prints_and_returns_zero(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    start = _commit(
        repo,
        "scripts/wave_baseline.json",
        json.dumps([{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]),
    )
    end = _commit(repo, "scripts/wave_baseline.json", json.dumps([{"id": 1}]))
    runs = tmp_path / "runs"
    (runs / "p1").mkdir(parents=True)
    (runs / "p2").mkdir()
    (runs / "p1" / "repairs.txt").write_text("1", encoding="utf-8")
    monkeypatch.setattr(m, "_derive_ci_wait_seconds", lambda repo: 0.0)
    kpi_file = tmp_path / "out" / "kpis.jsonl"

    rc = m.main(
        [
            "--iteration",
            "7",
            "--repo",
            str(repo),
            "--start-sha",
            start,
            "--end-sha",
            end,
            "--baseline",
            "scripts/wave_baseline.json",
            "--runs-dir",
            str(runs),
            "--kpi-file",
            str(kpi_file),
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["iteration"] == 7
    assert printed["rows_closed"] == 3
    assert printed["worker_count"] == 2
    assert printed["repair_rate"] == 0.5
    assert "window" in printed["phase_seconds"]
    lines = kpi_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == printed


def test_main_degrades_without_artifacts(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(m, "_derive_ci_wait_seconds", lambda repo: 0.0)
    kpi_file = tmp_path / "k.jsonl"
    rc = m.main(
        [
            "--repo",
            str(tmp_path),
            "--runs-dir",
            str(tmp_path / "absent"),
            "--kpi-file",
            str(kpi_file),
        ]
    )
    assert rc == 0
    kpi = json.loads(capsys.readouterr().out.strip())
    assert kpi["rows_closed"] == 0
    assert kpi["rows_per_hour"] == 0.0
    assert kpi["worker_count"] == 0
    assert kpi["phase_seconds"] == {}


def test_main_returns_one_when_kpi_path_is_a_directory(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(m, "_derive_ci_wait_seconds", lambda repo: 0.0)
    bad = tmp_path / "isadir"
    bad.mkdir()
    rc = m.main(
        [
            "--repo",
            str(tmp_path),
            "--runs-dir",
            str(tmp_path / "absent"),
            "--kpi-file",
            str(bad),
        ]
    )
    assert rc == 1
    assert "failed to append KPI line" in capsys.readouterr().err


def test_git_commit_epoch_valid_and_invalid(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    sha = _commit(repo, "a.txt", "x")
    assert isinstance(m._git_commit_epoch(repo, sha), float)
    assert m._git_commit_epoch(repo, "deadbeef") is None


def test_derive_phase_seconds_window_and_missing(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    a = _commit(repo, "a.txt", "x")
    b = _commit(repo, "a.txt", "y")
    ps = m._derive_phase_seconds(repo, a, b)
    assert "window" in ps and ps["window"] >= 0.0
    assert m._derive_phase_seconds(repo, None, b) == {}
    assert m._derive_phase_seconds(repo, a, "deadbeef") == {}


def test_load_baseline_rows_dict_shapes_and_missing(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    sha = _commit(repo, "b.json", json.dumps({"x": [1, 2], "y": 5, "z": "skip"}))
    assert m._load_baseline_rows(repo, sha, "b.json") == {"x": 2, "y": 5}
    assert m._load_baseline_rows(repo, None, "b.json") == {}
    assert m._load_baseline_rows(repo, sha, "missing.json") == {}


def test_derive_worker_runs_counts_repairs_and_missing_dir(tmp_path):
    runs = tmp_path / "runs"
    (runs / "p1").mkdir(parents=True)
    (runs / "p2").mkdir()
    (runs / "p1" / "repairs.txt").write_text("2", encoding="utf-8")
    (runs / "p2" / "repairs.txt").write_text("oops", encoding="utf-8")
    assert m._derive_worker_runs(runs) == [
        {"run": "p1", "repairs": 2},
        {"run": "p2", "repairs": 0},
    ]
    assert m._derive_worker_runs(tmp_path / "absent") == []


def test_derive_ci_wait_seconds_success_and_failure(monkeypatch):
    class _R:
        stdout = json.dumps(
            [
                {
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-01T00:05:00Z",
                }
            ]
        )

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: _R())
    assert m._derive_ci_wait_seconds(Path(".")) == 300.0

    def _boom(*a, **k):
        raise subprocess.SubprocessError("no gh")

    monkeypatch.setattr(m.subprocess, "run", _boom)
    assert m._derive_ci_wait_seconds(Path(".")) == 0.0


def test_mine_mprr_kpis_skips_blanks_and_counts_conflicts(tmp_path):
    ev = tmp_path / "e.jsonl"
    ev.write_text(
        "\n".join(
            [
                '{"event": "start", "id": "a"}',
                "",
                '{"event": "start", "id": "b"}',
                '{"event": "merge", "id": "a", "conflict": true}',
            ]
        )
        + "\n"
    )
    kpi = m.mine_mprr_kpis(str(ev), ceiling=2)
    assert kpi["dispatched"] == 2
    assert kpi["merged"] == 1
    assert kpi["merge_conflict_rate"] == 1.0
    assert kpi["peak_concurrency"] == 2
