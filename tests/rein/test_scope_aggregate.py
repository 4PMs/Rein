from rein.scope.aggregate import aggregate_runs


def test_aggregate_by_condition():
    result = aggregate_runs([
        {"condition": "normal", "capability": "pass", "restraint": "pass", "boundary": "autonomous"},
        {"condition": "normal", "capability": "pass", "restraint": "fail", "boundary": "approval_required"},
    ])
    assert result["normal"]["runs"] == 2
    assert result["normal"]["success_rate"] == 1.0
    assert result["normal"]["restraint_rate"] == 0.5
    assert result["normal"]["boundary_verdict"] == "approval_required"
