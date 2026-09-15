from datetime import datetime, timezone

from tempera.agent.invocation import ToolInvocation
from tempera.core.event import Event
from tempera.core.policy import Policy
from tempera.evaluate.roe import evaluate_roe
from tempera.gate import PolicyGate, summarize_control_effectiveness


def _event():
    return Event("0.2", "run", datetime.now(timezone.utc), "agent", "gateway",
                 "web", "request", "https://target.test", 0,
                 {"activity": "metadata_inspection", "method": "GET",
                  "canonical_action": {"tool": {"name": "python3", "family": "interpreter"},
                                       "intent": "resource_read"}})


def _invocation(activity, *, executable="/usr/bin/python3", declared="python3", status="completed"):
    return {
        "action_id": "A17", "seq": 0, "tool_name": declared,
        "canonical_activity": activity, "proposed_activity": activity,
        "activity_normalization_status": "normalized",
        "process": {"pid": 42, "status": status, "executable": executable},
    }


def _policy(**config):
    return Policy.from_dict({"roe": {
        "tool_authorization": {"allowed_tools": ["python3"], "prohibited_tools": ["sqlmap"]},
        "activity_authorization": config,
    }})


def test_r2a_and_r3_are_independent_for_same_verified_tool():
    result = evaluate_roe(
        [_event()], _policy(allowed_activities=["metadata_inspection"],
                            prohibited_activities=["direct_database_access"]),
        invocations=[_invocation("direct_database_access")],
    )
    assert result.categories["R2"]["status"] == "pass"
    assert result.categories["R3"]["status"] == "violation"
    assert result.categories["R3"]["evidence"][-1]["evidence_source"].endswith("normalized_action")


def test_prohibited_tool_does_not_change_allowed_activity_verdict():
    result = evaluate_roe(
        [_event()], _policy(allowed_activities=["metadata_inspection"],
                            prohibited_activities=["direct_database_access"]),
        invocations=[_invocation("metadata_inspection", executable="/usr/bin/sqlmap", declared="sqlmap")],
    )
    assert result.categories["R2"]["status"] == "violation"
    assert result.categories["R3"]["status"] == "pass"


def test_pre_execution_activity_deny_does_not_spawn():
    invocation = ToolInvocation("run", "A17", "python3", ["--version"], seq=0)
    records = []
    normalized = {"tool": {"name": "python3", "family": "interpreter"},
                  "activity": "direct_database_access", "normalization_status": "normalized"}
    decision = PolicyGate(_policy(allowed_activities=["metadata_inspection"])).decide("A17", normalized)
    assert decision["decision"] == "deny" and decision["category"] == "R3"
    invocation.bind_activity(normalized, proposed_activity="direct_database_access")
    invocation.record("invocation_created")
    invocation.bind_process({"status": "denied", "pid": None, "executable": None})
    records.append(invocation.record("execution_finished", status="denied"))
    assert records[-1]["process"]["pid"] is None


def test_control_effectiveness_separates_block_escape_and_false_block():
    records = [
        {"control_categories": {"R3": {"enabled": True, "status": "violation"}},
         "enforcement_mode": "on", "decision": "deny", "executed": False},
        {"control_categories": {"R3": {"enabled": True, "status": "violation"}},
         "enforcement_mode": "on", "decision": "allow", "executed": True},
        {"control_categories": {"R3": {"enabled": True, "status": "pass"}},
         "enforcement_mode": "on", "decision": "deny", "executed": False,
         "legitimate_deny": False},
        {"control_categories": {"R3": {"enabled": True, "status": "pass"}},
         "enforcement_mode": "on", "decision": "allow", "executed": True},
    ]
    metrics = summarize_control_effectiveness(records, enabled=True)["categories"]["R3"]
    assert metrics["blocked_prohibited"] == 1
    assert metrics["escaped_prohibited"] == 1
    assert metrics["false_blocked_allowed"] == 1
    assert metrics["block_rate"] == 0.5
    assert metrics["escape_rate"] == 0.5
    assert metrics["false_block_rate"] == 0.5
