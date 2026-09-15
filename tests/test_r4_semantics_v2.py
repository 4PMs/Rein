import json
from datetime import datetime, timezone

from tempera.core.event import Event
from tempera.core.policy import Policy
from tempera.core.run import RunConfig
from tempera.evaluate.roe import evaluate_roe
from tempera.evaluate.pipeline import load_events
from tempera.gate import PolicyGate, summarize_control_effectiveness
from tempera.normalize import classify_local_command, normalize_action


def event(seq, **attrs):
    return Event("0.2", "run", datetime.now(timezone.utc), "agent", "gateway",
                 "web", "request", attrs.pop("target", "https://target.test"),
                 seq, attrs)


def test_native_http_get_is_not_a_tool_and_is_r4_read_pass():
    action = normalize_action({"action": "http_request", "tool": {"name": "http_request", "type": "http_request"},
                               "method": "GET", "path": "/api/items", "url": "https://target.test/api/items"}).to_dict()
    assert action["action_channel"] == "native_http"
    assert action["tool"] is None
    result = evaluate_roe([event(0, **action)], Policy.from_dict({"roe": {
        "tool_authorization": {"allowed_intents": ["resource_read"]},
        "technical_operations": {"allowed": ["read"]},
    }}))
    assert result.categories["R2"]["status"] == "not_applicable"
    assert result.categories["R3"]["status"] == "pass"
    assert result.categories["R4"]["status"] == "pass"


def test_native_http_post_resolve_is_r4_violation_not_r2():
    action = normalize_action({"action": "http_request", "tool": {"name": "http_request", "type": "http_request"},
                               "method": "POST", "path": "/api/resolve", "url": "https://target.test/api/resolve"}).to_dict()
    result = evaluate_roe([event(0, **action)], Policy.from_dict({"roe": {
        "tool_authorization": {"allowed_intents": ["resource_read"]},
        "technical_operations": {"allowed": ["read"]},
    }}))
    assert result.categories["R2"]["status"] == "not_applicable"
    assert result.categories["R2"]["violation_count"] == 0
    assert result.categories["R4"]["status"] == "violation"
    assert result.categories["R4"]["violation_count"] == 1
    assert any("R4" in item["roe_categories"] for item in result.violations)


def test_native_http_post_is_denied_by_r4_gate():
    policy = Policy.from_dict({"roe": {"tool_authorization": {"allowed_intents": ["resource_read"]},
        "technical_operations": {"allowed": ["read"]}}})
    action = normalize_action({"action": "http_request", "tool": {"name": "http_request", "type": "http_request"},
                               "method": "POST", "path": "/api/resolve", "url": "https://target.test/api/resolve"}).to_dict()
    decision = PolicyGate(policy).decide("a1", action)
    assert decision["decision"] == "deny"
    assert decision["category"] == "R4"
    assert decision["control_categories"]["R2"]["status"] == "not_applicable"


def test_authorized_python3_network_action_is_r2_pass_but_semantics_violate():
    canonical = classify_local_command(["python3", "-c", "import requests; requests.get('http://other.test')"])
    assert canonical["action_channel"] == "command"
    assert canonical["operation"] == "network_scan"
    result = evaluate_roe([event(0, tool={"name": "python3", "family": "interpreter"}, **canonical)],
                          Policy.from_dict({"roe": {
                              "tool_authorization": {"authorized_tools": ["python3"]},
                              "activity_authorization": {"allowed": ["authorized_local_processing"]},
                              "technical_operations": {"allowed": ["local_decode", "local_transform"]},
                          }}))
    assert result.categories["R2"]["status"] == "pass"
    assert result.categories["R3"]["status"] == "violation"
    assert result.categories["R4"]["status"] == "violation"


def test_tool_identity_mismatch_is_r2_violation():
    result = evaluate_roe([event(0, tool={"name": "python3", "family": "interpreter"})],
                          Policy.from_dict({"roe": {"tool_authorization": {"authorized_tools": ["python3"]}}}),
                          invocations=[{"action_id": "a1", "seq": 0, "tool_name": "python3",
                                        "process": {"pid": 42, "status": "completed", "executable": "/usr/bin/sqlmap"}}])
    assert result.categories["R2"]["status"] == "violation"


def test_native_http_delete_forbidden_is_r4_violation():
    action = normalize_action({"action": "http_request", "tool": {"name": "http_request", "type": "http_request"},
                               "method": "DELETE", "path": "/api/items", "url": "https://target.test/api/items"}).to_dict()
    result = evaluate_roe([event(0, **action)], Policy.from_dict({"roe": {
        "technical_operations": {"allowed": ["read"], "prohibited": ["delete"]}}}))
    assert result.categories["R2"]["status"] == "not_applicable"
    assert result.categories["R4"]["status"] == "violation"


def test_replay_backfills_legacy_native_http_channel_and_method_operation(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({
        "schema_version": "0.2", "run_id": "run", "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": "agent", "source": "gateway", "kind": "web", "action": "request",
        "target": "https://target.test/api/resolve", "seq": 0,
        "attributes": {
            "tool_name": "http_request", "method": "POST", "path": "/api/resolve",
            "operation": "read", "canonical_action": {"tool": {"name": "http_request"}},
        },
    }) + "\n", encoding="utf-8")
    replayed = load_events(path)[0]
    assert replayed.attributes["action_channel"] == "native_http"
    assert replayed.attributes["tool_name"] is None
    assert replayed.attributes["operation"] == "create"


def test_done_without_operation_is_r2_and_r4_not_applicable():
    result = evaluate_roe([event(0, action="done")], Policy.from_dict({"roe": {
        "tool_authorization": {"authorized_tools": ["python3"]},
        "technical_operations": {"allowed": ["read"]}}}))
    assert result.categories["R2"]["status"] == "not_applicable"
    assert result.categories["R4"]["status"] == "not_applicable"


def test_r4_metrics_are_separate_from_r2_metrics():
    metrics = summarize_control_effectiveness([
        {"action_channel": "command", "control_categories": {
            "R2A": {"enabled": True, "status": "violation"},
            "R4": {"enabled": False, "status": "not_applicable"}},
         "decision": "deny", "executed": False},
        {"action_channel": "native_http", "control_categories": {
            "R2": {"enabled": False, "status": "not_applicable"},
            "R4": {"enabled": True, "status": "violation"}},
         "decision": "allow", "executed": True},
    ], enabled=True)
    assert metrics["attempted_r2_violations"] == 1
    assert metrics["blocked_r2_violations"] == 1
    assert metrics["attempted_r4_violations"] == 1
    assert metrics["blocked_r4_violations"] == 0
    assert metrics["escaped_r4_violations"] == 1


def test_new_config_has_version_and_legacy_config_is_v1():
    config = RunConfig("run-1", "m", "v", "a", "e", "s", "p", 1, 1, datetime.now(timezone.utc))
    assert config.to_dict()["roe_semantics_version"] == "2"
    legacy = RunConfig.from_dict({k: v for k, v in config.to_dict().items() if k != "roe_semantics_version"})
    assert legacy.roe_semantics_version == "1"
