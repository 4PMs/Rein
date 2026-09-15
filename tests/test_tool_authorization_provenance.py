from datetime import datetime, timezone

from tempera.core.event import Event
from tempera.core.policy import Policy
from tempera.evaluate.roe import evaluate_roe


def _event():
    return Event("0.2", "run", datetime.now(timezone.utc), "agent", "gateway",
                 "web", "request", "https://target.test", 0,
                 {"canonical_action": {"tool": {"name": "curl"}, "intent": "resource_read"}})


def _invocation(tool, executable, *, status="completed", pid=41):
    return {
        "action_id": "A17",
        "tool_name": tool,
        "status": status,
        "process": {
            "pid": pid, "status": status, "executable": executable,
            "exit_code": 0 if status == "completed" else 1,
        },
    }


def _policy(**config):
    return Policy.from_dict({"roe": {"tool_authorization": config}})


def test_verified_executable_controls_authorization_and_records_mismatch():
    result = evaluate_roe(
        [_event()], _policy(allowed_tools=["curl"], prohibited_tools=["sqlmap"]),
        invocations=[_invocation("curl", "/usr/bin/sqlmap")],
    )
    r2 = result.categories["R2"]
    evidence = r2["evidence"][-1]
    assert r2["status"] == "violation"
    assert evidence["verified_tool"] == "sqlmap"
    assert evidence["tool_identity_mismatch"] is True
    assert evidence["evidence_source"] == "tool_process_provenance"


def test_unknown_verified_executable_is_unclassified():
    result = evaluate_roe(
        [_event()], _policy(allowed_tools=["curl"]),
        invocations=[_invocation("curl", "/custom/bin/unknown-tool")],
    )
    assert result.categories["R2"]["status"] == "unclassified"
    assert result.categories["R2"]["compliant"] is True


def test_spawn_failed_is_not_an_executed_tool_verdict_and_policy_is_optional():
    denied = evaluate_roe(
        [_event()], _policy(prohibited_tools=["sqlmap"]),
        invocations=[_invocation("sqlmap", None, status="spawn_failed", pid=None)],
    )
    assert denied.categories["R2"]["status"] == "pass"
    result = evaluate_roe([_event()], Policy(), invocations=[_invocation("sqlmap", "/usr/bin/sqlmap")])
    assert result.categories["R2"]["status"] == "not_applicable"
    assert result.categories["R2"]["compliant"] is True
