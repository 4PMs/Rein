import pytest

import tempera.evaluate.roe as roe_module
import tempera.gate as gate_module
import tempera.r2 as r2_module
from tempera.agent.runtime import run_episode
from tempera.core.policy import Policy
from tempera.gate import PolicyGate, summarize_control_effectiveness


POLICY = Policy.from_dict({"roe": {
    "tool_authorization": {
        "allowed_tools": ["browser"],
        "prohibited_tools": ["shell"],
        "allowed_intents": ["resource_read"],
        "prohibited_intents": ["resource_delete"],
    },
}})


def action(tool="browser", intent="resource_read"):
    return {
        "tool": {"name": tool, "family": tool},
        "intent": intent,
        "normalization_status": "normalized",
    }


def test_gate_denies_prohibited_tool_and_intent():
    gate = PolicyGate(POLICY)

    tool = gate.decide("action-1", action(tool="shell"))
    intent = gate.decide("action-2", action(intent="resource_delete"))
    allowed = gate.decide("action-3", action())

    assert tool == {
        "decision": "deny", "reason": "prohibited tool",
        "policy_violation": True, "classification_status": "classified",
        "fail_closed_block": False,
        "matched_rule": "prohibited_tools.shell", "category": "R2",
        "subdimension": "tool_authorization", "action_id": "action-1",
    }
    assert intent["decision"] == "allow"
    assert allowed["decision"] == "allow"


def test_gate_r3_decision_reuses_activity_classification_rule():
    policy = Policy.from_dict({"roe": {
        "activity_authorization": {
            "allowed": ["target_data_access"],
            "prohibited": ["credential_dump"],
        },
    }})
    gate = PolicyGate(policy)

    prohibited = gate.decide("action-r3-1", {
        "activity": "credential_dump", "normalization_status": "normalized",
    })
    outside_allowlist = gate.decide("action-r3-2", {
        "activity": "discovery", "normalization_status": "normalized",
    })

    assert prohibited["matched_rule"] == "prohibited_activities.credential_dump"
    assert prohibited["reason"] == "prohibited activity"
    assert outside_allowlist["matched_rule"] == "allowed_activities"
    assert outside_allowlist["reason"] == "activity is not allowed"


def test_gate_deny_prevents_target_call_and_records_terminal_lifecycle(monkeypatch):
    monkeypatch.setattr(
        "tempera.agent.runtime.call_llm",
        lambda *args, **kwargs: '{"action":"http_request","method":"GET","path":"/"}',
    )
    target_calls = []
    monkeypatch.setattr(
        "tempera.agent.runtime.do_http",
        lambda action, gateway: target_calls.append(action) or "status=200",
    )
    lifecycle = []
    result = run_episode(
        "mission", "http://gateway", 1, policy=POLICY, enforce_policy=True,
        on_lifecycle=lambda *record: lifecycle.append(record),
    )

    assert result["reason"] == "max_steps"
    assert len(target_calls) == 1
    assert [item[0] for item in lifecycle] == ["proposed", "policy_decision", "executed"]
    assert lifecycle[1][4]["decision"] == "allow"
    assert result["control_effectiveness"]["attempted_violations"] == 0
    assert result["control_effectiveness"]["blocked_violations"] == 0


def test_allowed_action_reaches_target_when_enforcement_is_enabled(monkeypatch):
    policy = Policy.from_dict({"roe": {
        "tool_authorization": {
            "allowed_tools": ["http_request"],
            "allowed_intents": ["resource_read"],
        },
    }})
    monkeypatch.setattr(
        "tempera.agent.runtime.call_llm",
        lambda *args, **kwargs: '{"action":"http_request","method":"GET","path":"/"}',
    )
    target_calls = []
    monkeypatch.setattr(
        "tempera.agent.runtime.do_http",
        lambda action, gateway: target_calls.append(action) or "status=200",
    )

    result = run_episode("mission", "http://gateway", 1, policy=policy, enforce_policy=True)

    assert len(target_calls) == 1
    assert result["control_effectiveness"]["attempted_violations"] == 0
    assert result["control_effectiveness"]["allowed_allowed_actions"] == 1


def test_disabled_enforcement_still_measures_attempted_violation(monkeypatch):
    policy = Policy.from_dict({"roe": {
        "tool_authorization": {
            "prohibited_tools": ["http_request"],
            "allowed_intents": ["resource_read"],
        },
    }})
    monkeypatch.setattr(
        "tempera.agent.runtime.call_llm",
        lambda *args, **kwargs: '{"action":"http_request","method":"GET","path":"/"}',
    )
    monkeypatch.setattr("tempera.agent.runtime.do_http", lambda action, gateway: "status=200")

    result = run_episode("mission", "http://gateway", 1, policy=policy, enforce_policy=False)

    assert result["reason"] == "max_steps"
    assert result["control_effectiveness"]["enabled"] is False
    assert result["control_effectiveness"]["attempted_violations"] == 0
    assert result["control_effectiveness"]["escaped_violations"] == 0


def test_control_effectiveness_counts_allow_and_fault_injection_cases():
    records = [
        {"attempted_violation": True, "decision": "deny", "executed": False},
        {"attempted_violation": False, "decision": "allow", "executed": True},
        {"attempted_violation": True, "decision": "allow", "executed": True},
        {"attempted_violation": False, "decision": "deny", "executed": False},
    ]

    metrics = summarize_control_effectiveness(records, enabled=True)

    assert metrics["attempted_r2_violations"] == 2
    assert metrics["blocked_r2_violations"] == 1
    assert metrics["escaped_r2_violations"] == 1
    assert metrics["scope"] == {"categories": ["R2"]}


def test_fault_injected_allow_still_counts_proposed_violation():
    gate = PolicyGate(POLICY)
    records = [{
        "policy_violation": gate.violates(action(tool="shell")),
        "classification_status": "classified",
        "decision": "allow", "target_executed": True,
    }]

    metrics = summarize_control_effectiveness(records, enabled=True)

    assert metrics["attempted_violations"] == 1
    assert metrics["blocked_violations"] == 0
    assert metrics["escaped_violations"] == 1


def test_fault_injected_deny_counts_allowed_action_as_false_block():
    gate = PolicyGate(POLICY)
    records = [{
        "attempted_violation": gate.violates(action()),
        "decision": "deny", "executed": False,
    }]

    metrics = summarize_control_effectiveness(records, enabled=True)

    assert metrics["attempted_violations"] == 0
    assert metrics["blocked_allowed_actions"] == 1


def test_control_effectiveness_uses_none_for_zero_denominators():
    metrics = summarize_control_effectiveness([], enabled=True)

    assert metrics["enforcement_recall"] is None
    assert metrics["enforcement_fpr"] is None


def test_unclassified_action_is_denied_fail_closed():
    decision = PolicyGate(POLICY).decide(
        "action-unknown", {"tool": {"name": "browser", "family": "browser"},
                           "intent": None, "normalization_status": "unclassified"},
    )

    assert decision["decision"] == "deny"
    assert decision["reason"] == "unclassified normalized action"
    assert decision["policy_violation"] is False
    assert decision["classification_status"] == "unclassified"
    assert decision["fail_closed_block"] is True


def test_unknown_action_is_not_an_attempted_r2_violation(monkeypatch):
    monkeypatch.setattr(
        "tempera.agent.runtime.call_llm",
        lambda *args, **kwargs: '{"action":"mystery"}',
    )
    result = run_episode("mission", "http://gateway", 1, policy=POLICY, enforce_policy=True)
    metrics = result["control_effectiveness"]
    assert metrics["attempted_r2_violations"] == 0
    assert metrics["unclassified_actions"] == 1
    assert metrics["fail_closed_blocks"] == 1


def test_done_is_not_target_executed_or_escaped(monkeypatch):
    monkeypatch.setattr(
        "tempera.agent.runtime.call_llm",
        lambda *args, **kwargs: '{"action":"done"}',
    )
    result = run_episode("mission", "http://gateway", 1, policy=POLICY, enforce_policy=True)
    assert result["control_effectiveness"]["escaped_r2_violations"] == 0


def test_allowed_action_forced_deny_is_a_false_block():
    metrics = summarize_control_effectiveness([{
        "policy_violation": False, "classification_status": "classified",
        "decision": "deny", "target_executed": False,
    }], enabled=True)
    assert metrics["blocked_allowed_actions"] == 1


def test_prohibited_allow_without_target_execution_does_not_escape():
    metrics = summarize_control_effectiveness([{
        "policy_violation": True, "classification_status": "classified",
        "decision": "allow", "execution_attempted": True,
        "target_executed": False,
    }], enabled=True)
    assert metrics["attempted_r2_violations"] == 1
    assert metrics["escaped_r2_violations"] == 0


def test_lifecycle_metrics_reconcile_cases_and_legacy_aliases():
    records = [
        {"policy_violation": True, "decision": "deny", "target_executed": False},
        {"policy_violation": True, "decision": "allow", "target_executed": True},
        {"policy_violation": True, "decision": "allow", "target_executed": False},
        {"policy_violation": False, "classification_status": "classified", "decision": "deny"},
        {"policy_violation": False, "classification_status": "classified", "decision": "allow", "target_executed": True},
        {"policy_violation": False, "classification_status": "unclassified", "decision": "deny", "fail_closed_block": True},
    ]
    metrics = summarize_control_effectiveness(records, enabled=True)

    assert metrics["attempted_violations"] == 3
    assert metrics["correctly_blocked_violations"] == 1
    assert metrics["missed_blocks"] == 2
    assert metrics["escaped_violations"] == 1
    assert metrics["false_blocks"] == 1
    assert metrics["fail_closed_unclassified_blocks"] == 1
    assert metrics["block_recall"] == 1 / 3
    assert metrics["escape_rate"] == 1 / 3
    assert metrics["false_block_rate"] == 1 / 2


def test_effectiveness_aggregates_activity_and_tool_dimensions_without_duplicates():
    records = [
        {
            "run_id": "run-1", "seq": 17, "action_id": "A17",
            "decision": "deny", "target_executed": False,
            "control_categories": {
                "R2A": {"status": "violation"},
                "R3": {"status": "violation"},
            },
        },
        {
            "run_id": "run-1", "seq": 17, "action_id": "A17",
            "decision": "deny", "target_executed": False,
            "control_categories": {
                "R2A": {"status": "violation"},
                "R3": {"status": "violation"},
            },
        },
    ]
    metrics = summarize_control_effectiveness(records, enabled=True)

    assert metrics["attempted_violations"] == 1
    assert metrics["correctly_blocked_violations"] == 1


def test_gate_and_roe_evaluator_import_the_same_r2_helpers():
    """Guard against R2 matching duplication reappearing in gate.py/roe.py.

    Both modules must call the single canonical helper set defined in
    r2.py.  If either module regains a private copy of the tool/value
    decision logic or interpret_r2_action, this identity check fails even
    before any behavioral difference is observable.
    """
    assert gate_module.interpret_r2_action is r2_module.interpret_r2_action
    assert roe_module.interpret_r2_action is r2_module.interpret_r2_action
    assert roe_module.tool_decision is r2_module.tool_decision
    assert roe_module.value_decision is r2_module.value_decision


@pytest.mark.parametrize("name,family,expected_status", [
    ("browser", "browser", "pass"),
    ("shell", "shell", "violation"),
    ("unknown", None, "unclassified"),
])
def test_r2_tool_rule_matching_is_consistent_between_gate_and_roe(name, family, expected_status):
    """R2 tool decisions must agree across PolicyGate and the ROE evaluator
    for allowed, forbidden, and unclassified/unknown tool families."""
    action_payload = {
        "tool": {"name": name, "family": family},
        "intent": "resource_read",
        "normalization_status": "unclassified" if name == "unknown" else "normalized",
    }

    gate_decision = PolicyGate(POLICY).decide("action-r2-consistency", action_payload)
    roe_status, _ = roe_module._r2_tool_decision(
        name, family, action_payload["normalization_status"],
        ("browser",), ("shell",), enabled=True,
    )

    if expected_status == "violation":
        assert gate_decision["decision"] == "deny"
        assert gate_decision["policy_violation"] is True
    elif expected_status == "unclassified":
        assert gate_decision["classification_status"] == "unclassified"
        assert gate_decision["policy_violation"] is False
    else:
        assert gate_decision["decision"] == "allow"

    assert roe_status == expected_status


def test_r3_prohibited_activity_denied_and_allowlisted_activity_passes():
    """R3 decision consistency: prohibited activities are denied, allowed
    activities pass, and out-of-scope (not-configured) activity policy is a
    no-op, matching existing PolicyGate semantics unchanged by refactor."""
    policy = Policy.from_dict({"roe": {
        "activity_authorization": {
            "allowed": ["target_data_access"],
            "prohibited": ["credential_dump"],
        },
    }})
    gate = PolicyGate(policy)

    prohibited = gate.decide("action-r3-prohibited", {
        "activity": "credential_dump", "normalization_status": "normalized",
    })
    allowed = gate.decide("action-r3-allowed", {
        "activity": "target_data_access", "normalization_status": "normalized",
    })

    assert prohibited["decision"] == "deny"
    assert prohibited["policy_violation"] is True
    assert allowed["decision"] == "allow"

    no_activity_policy = PolicyGate(POLICY)
    out_of_scope = no_activity_policy.decide("action-r3-scope", action())
    assert out_of_scope["decision"] == "allow"
