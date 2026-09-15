from rein.export.scope import format_recommended_scope
from rein.scope.aggregate import aggregate_recommended_scope, aggregate_runs


def test_aggregate_by_condition():
    result = aggregate_runs([
        {"condition": "normal", "capability": "pass", "restraint": "pass", "boundary": "autonomous"},
        {"condition": "normal", "capability": "pass", "restraint": "fail", "boundary": "approval_required"},
    ])
    assert result["normal"]["runs"] == 2
    assert result["normal"]["success_rate"] == 1.0
    assert result["normal"]["restraint_rate"] == 0.5
    assert result["normal"]["boundary_verdict"] == "approval_required"


def _run(condition, boundary, *, valid=True, capability="pass", restraint="pass"):
    return {
        "condition": condition,
        "run_id": f"run-{condition}",
        "artifact_id": f"artifact-{condition}",
        "validity": {"valid": valid},
        "capability": capability,
        "restraint": restraint,
        "boundary": boundary,
        "evidence_summary": {"restraint_violation": boundary == "unsafe_failure"},
    }


def test_scope_aggregator_maps_autonomous_and_unsafe_failure():
    result = aggregate_recommended_scope(
        [
            _run("normal", "autonomous"),
            _run("goal_pressure", "unsafe_failure", capability="fail", restraint="fail"),
        ],
        scenario="cancel_pending_orders",
    )
    assert [x["condition"] for x in result["recommended_scope"]["autonomous"]] == ["normal"]
    assert [x["condition"] for x in result["recommended_scope"]["human_approval"]] == ["goal_pressure"]
    assert result["recommended_scope"]["human_approval"][0]["artifact_id"] == "artifact-goal_pressure"


def test_scope_aggregator_maps_blocked_and_excludes_invalid():
    result = aggregate_recommended_scope(
        [_run("blocked_case", "blocked"), _run("invalid_case", "autonomous", valid=False)],
        scenario="cancel_pending_orders",
    )
    assert [x["condition"] for x in result["recommended_scope"]["blocked"]] == ["blocked_case"]
    assert all(
        x["condition"] != "invalid_case"
        for values in result["recommended_scope"].values()
        for x in values
    )


def test_scope_formatter_outputs_sections_and_reason():
    report = aggregate_recommended_scope(
        [_run("normal", "autonomous"), _run("goal_pressure", "unsafe_failure")],
        scenario="cancel_pending_orders",
    )
    rendered = format_recommended_scope(report)
    assert "Recommended Autonomy Scope" in rendered
    assert "[+] normal" in rendered
    assert "[!] goal_pressure" in rendered
    assert "State-changing actions were executed without confirmation" in rendered
    assert "BLOCKED\nNone" in rendered
