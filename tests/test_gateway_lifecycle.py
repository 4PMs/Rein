from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tempera.core.run import RunConfig, RunStore
from tempera.core.sequence import SequenceAllocator
from tempera.observe import gateway
from environments.h3_tool_target.observer import H3ToolTargetObserver


def _config(run_id="run-gateway-lifecycle"):
    return RunConfig(
        run_id=run_id, model="test", model_version="test", agent_version="test",
        environment="h3_tool_target", scenario="H3-TOOL-001", policy="policy",
        max_steps=12, timeout=30, started_at=datetime.now(timezone.utc),
    )


def test_gateway_main_wires_observed_lifecycle_sink(tmp_path):
    config = _config()
    store = RunStore(tmp_path, config)
    store.initialize()
    args = SimpleNamespace(
        upstream="http://h3-tool-target:3000", run=config.run_id,
        runs_dir=tmp_path, config=store.config_path, observer=(
            "environments.h3_tool_target.observer:H3ToolTargetObserver"
        ), markers="TEMPERA-H3-FLAG-001", actor="agent",
    )
    with patch.object(gateway, "parse_args", return_value=args), \
            patch.object(gateway.Flask, "run"), \
            patch.object(gateway, "create_app", wraps=gateway.create_app) as create:
        gateway.main()

    lifecycle_sink = create.call_args.kwargs["lifecycle_sink"]
    assert callable(lifecycle_sink)
    assert lifecycle_sink.__self__.run_dir == store.run_dir
    assert lifecycle_sink.__name__ == "append_lifecycle"


def test_gateway_persists_observed_with_same_action_and_sequence():
    event_sink = Mock()
    lifecycle = []
    response = Mock(status_code=200, content=b'{"items":[{"value":"H3-FLAG-001"}]}')
    response.raw.headers = {"Content-Type": "application/json"}
    app = gateway.create_app(
        "http://target.test", "run-gateway-lifecycle", "agent", event_sink,
        observer=H3ToolTargetObserver(markers=("TEMPERA-H3-FLAG-001",)),
        sequence_allocator=SequenceAllocator(), lifecycle_sink=lifecycle.append,
    )
    with patch.object(gateway.requests, "request", return_value=response):
        result = app.test_client().get(
            "/api/resolve?key=H3-KEY-017", headers={"X-Tempera-Action-Id": "action-1"},
        )

    assert result.status_code == 200
    event = event_sink.call_args.args[0]
    assert event.seq == 0
    assert event.attributes["action_id"] == "action-1"
    assert event.attributes["matched_markers"] == ["TEMPERA-H3-FLAG-001"]
    observed = lifecycle[-1]
    assert observed.stage == "observed"
    assert observed.action_id == "action-1"
    assert observed.seq == 0
    assert observed.reference == {"event_seq": 0}


def test_lifecycle_merge_reconciles_interleaved_http_and_run_tool(tmp_path):
    config = _config("run-lifecycle-merge")
    store = RunStore(tmp_path, config)
    store.initialize()
    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"run_id": config.run_id, "action_id": "action-2", "seq": 0,
         "stage": "observed", "timestamp": now, "reference": {"event_seq": 0}},
        {"run_id": config.run_id, "action_id": "action-1", "seq": 0,
         "stage": "proposed", "timestamp": now, "raw_action": {"action": "run_tool"}},
        {"run_id": config.run_id, "action_id": "action-1", "seq": 0,
         "stage": "policy_decision", "timestamp": now, "reference": {"decision": "allow"}},
        {"run_id": config.run_id, "action_id": "action-1", "seq": 0,
         "stage": "executed", "timestamp": now, "raw_action": {"action": "run_tool"}},
        {"run_id": config.run_id, "action_id": "action-2", "seq": 1,
         "stage": "proposed", "timestamp": now, "raw_action": {"action": "http_request"}},
        {"run_id": config.run_id, "action_id": "action-2", "seq": 1,
         "stage": "policy_decision", "timestamp": now, "reference": {"decision": "allow"}},
        {"run_id": config.run_id, "action_id": "action-2", "seq": 1,
         "stage": "executed", "timestamp": now, "raw_action": {"action": "http_request"}},
    ]
    store.lifecycle_path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    store.sort_lifecycle()
    merged = [json.loads(line) for line in store.lifecycle_path.read_text(encoding="utf-8").splitlines()]
    assert [(item["action_id"], item["stage"], item["seq"]) for item in merged] == [
        ("action-1", "proposed", 0), ("action-1", "policy_decision", 0),
        ("action-1", "executed", 0), ("action-2", "proposed", 1),
        ("action-2", "policy_decision", 1), ("action-2", "observed", 1),
        ("action-2", "executed", 1),
    ]
