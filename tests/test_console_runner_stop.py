import json
from unittest.mock import Mock, patch

from console.backend.loader import RunLoader
from console.backend.runner import RunnerService


def test_stop_run_captures_elapsed_and_terminates_process(tmp_path):
    service = RunnerService(tmp_path)
    process = Mock()
    item = {
        "run_id": "run-1", "status": "running", "process": process,
        "started_monotonic": 10.0,
    }
    service.active_jobs["job-1"] = {
        "runs": [item], "stopped": False, "scenario": "JS-001",
    }

    with patch("console.backend.runner.time.monotonic", return_value=17.5), patch.object(
        service, "_terminate_process_tree",
    ) as terminate:
        service.stop_run("run-1")

    assert item["status"] == "stopping"
    assert item["stopped_elapsed_sec"] == 7.5
    terminate.assert_called_once_with(process)


def test_mark_stopped_persists_terminal_status_and_freezes_elapsed(tmp_path):
    service = RunnerService(tmp_path)
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "status.json").write_text(json.dumps({
        "run_id": "run-1", "scenario": "JS-001", "policy": "policy",
        "state": "running_agent", "started_at": "2026-09-15T00:00:00+00:00",
        "updated_at": "2026-09-15T00:00:05+00:00",
        "execution": {"status": "running"}, "agent": {}, "progress": {},
    }), encoding="utf-8")

    with patch("console.backend.runner.datetime") as now:
        now.now.return_value.isoformat.return_value = "2026-09-15T00:00:12+00:00"
        service._mark_stopped("run-1")

    live = RunLoader(tmp_path / "runs").load_live_status(run_dir)
    assert live is not None
    assert live.state == "interrupted"
    assert live.elapsed_sec == 12.0
    assert json.loads((run_dir / "status.json").read_text(encoding="utf-8"))["execution"]["status"] == "stopped"
