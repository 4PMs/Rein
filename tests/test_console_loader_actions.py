import json

from console.backend.loader import RunLoader


def test_load_actions_merges_lifecycle_and_joins_gateway_facts(tmp_path):
    lifecycle = [
        {"action_id": "action-1", "seq": 0, "phase": "proposed", "raw_action": {"thought": "check", "path": "/"}},
        {"action_id": "action-1", "seq": 0, "phase": "policy_decision", "decision": {"blocked": True}},
        {"action_id": "action-1", "seq": 0, "phase": "executed"},
    ]
    events = [{"seq": 0, "action_id": "action-1", "target": "http://target/", "attributes": {"method": "GET", "path": "/", "status": 200}}]
    result = {"roe": {"violations": [{"dimension": "target", "roe_categories": ["R1"], "evidence": {"action_id": "action-1"}}]}}
    for name, rows in (("lifecycle.jsonl", lifecycle), ("events.jsonl", events)):
        (tmp_path / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")

    rows = RunLoader(tmp_path).load_actions(tmp_path)

    assert len(rows) == 1
    assert rows[0].phase == "executed"
    assert rows[0].method == "GET"
    assert rows[0].status_code == 200
    assert rows[0].thought == "check"
    assert rows[0].decision == "blocked"
    assert rows[0].roe_status == "escaped"
    assert rows[0].roe_dimension == "target"
    assert rows[0].roe_category == "R1"


def test_load_actions_does_not_surface_proposed_or_progress_placeholders(tmp_path):
    lifecycle = [
        {"action_id": "action-1", "seq": 0, "phase": "proposed", "raw_action": {"thought": "waiting", "path": "/"}},
    ]
    progress = [
        {"seq": seq, "type": "agent_step_started", "state": "running_agent", "step": seq}
        for seq in range(1, 50)
    ]
    for name, rows in (("lifecycle.jsonl", lifecycle), ("progress.jsonl", progress)):
        (tmp_path / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    assert RunLoader(tmp_path).load_actions(tmp_path) == []


def test_load_actions_surfaces_row_when_gateway_event_arrives(tmp_path):
    lifecycle = [
        {"action_id": "action-1", "seq": 0, "phase": "proposed", "raw_action": {"thought": "check", "path": "/health"}},
        {"action_id": "action-1", "seq": 0, "phase": "policy_decision", "decision": "allow"},
    ]
    (tmp_path / "lifecycle.jsonl").write_text(
        "\n".join(json.dumps(row) for row in lifecycle), encoding="utf-8",
    )
    assert RunLoader(tmp_path).load_actions(tmp_path) == []

    event = {
        "seq": 0, "action_id": "action-1", "target": "http://target/health",
        "attributes": {"method": "GET", "path": "/health", "status": 200},
    }
    (tmp_path / "events.jsonl").write_text(json.dumps(event), encoding="utf-8")
    rows = RunLoader(tmp_path).load_actions(tmp_path)

    assert len(rows) == 1
    assert rows[0].action_id == "action-1"
    assert rows[0].thought == "check"
    assert rows[0].method == "GET"
    assert rows[0].path == "/health"
    assert rows[0].decision == "allowed"
    assert rows[0].roe_status is None


def test_unclassified_result_record_is_not_shown_as_roe_violation(tmp_path):
    lifecycle = [
        {"action_id": "action-1", "seq": 0, "phase": "policy_decision", "decision": "allow"},
        {"action_id": "action-1", "seq": 0, "phase": "executed"},
    ]
    event = {
        "seq": 0, "action_id": "action-1", "target": "http://target/",
        "attributes": {"method": "GET", "path": "/", "status": 200},
    }
    result = {"roe": {"compliant": True, "violations": [{
        "severity": "unclassified", "dimension": "target",
        "roe_categories": ["R1"], "evidence": {"action_id": "action-1"},
    }]}}
    for name, rows in (("lifecycle.jsonl", lifecycle), ("events.jsonl", [event])):
        (tmp_path / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")

    row = RunLoader(tmp_path).load_actions(tmp_path)[0]
    assert row.decision == "allowed"
    assert row.roe_status == "unclassified"
    assert row.roe_categories == []


def test_load_actions_joins_token_usage_by_call_order(tmp_path):
    lifecycle = [
        {"action_id": "action-1", "seq": 0, "phase": "policy_decision", "decision": "allow"},
        {"action_id": "action-1", "seq": 0, "phase": "executed"},
        {"action_id": "action-2", "seq": 1, "phase": "policy_decision", "decision": "allow"},
        {"action_id": "action-2", "seq": 1, "phase": "executed"},
    ]
    events = [
        {"seq": 0, "action_id": "action-1", "target": "http://target/", "attributes": {"method": "GET", "path": "/", "status": 200}},
        {"seq": 1, "action_id": "action-2", "target": "http://target/next", "attributes": {"method": "GET", "path": "/next", "status": 200}},
    ]
    result = {"usage": {"calls": [
        {"index": 1, "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        {"index": 2, "prompt_tokens": 90, "completion_tokens": 10, "total_tokens": 100},
    ]}}
    for name, rows in (("lifecycle.jsonl", lifecycle), ("events.jsonl", events)):
        (tmp_path / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")

    rows = RunLoader(tmp_path).load_actions(tmp_path)

    assert len(rows) == 2
    assert rows[0].total_tokens == 120
    assert rows[0].prompt_tokens == 100
    assert rows[0].completion_tokens == 20
    assert rows[1].total_tokens == 100


def test_load_actions_uses_latest_live_roe_snapshot_before_result(tmp_path):
    lifecycle = [
        {"action_id": "action-1", "seq": 0, "phase": "policy_decision", "decision": "allow"},
        {"action_id": "action-1", "seq": 0, "phase": "executed"},
    ]
    events = [{
        "seq": 0, "action_id": "action-1", "target": "http://target/",
        "attributes": {"method": "GET", "path": "/", "status": 200},
    }]
    progress = [{
        "seq": 1, "type": "roe_evaluated", "detail": {"verdicts": [{
            "action_id": "action-1", "status": "escaped", "categories": ["R3"],
        }]},
    }]
    for name, rows in (
        ("lifecycle.jsonl", lifecycle), ("events.jsonl", events),
        ("progress.jsonl", progress),
    ):
        (tmp_path / name).write_text(
            "\n".join(json.dumps(row) for row in rows), encoding="utf-8",
        )

    row = RunLoader(tmp_path).load_actions(tmp_path)[0]
    assert row.decision == "allowed"
    assert row.roe_status == "escaped"
    assert row.roe_categories == ["R3"]
