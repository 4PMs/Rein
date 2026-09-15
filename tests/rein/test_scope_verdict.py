from rein.scope.verdict import evaluate_scope


def test_pass_pass_is_autonomous():
    assert evaluate_scope(True, True)["boundary"] == "autonomous"


def test_restraint_failure_requires_approval():
    assert evaluate_scope(True, False)["boundary"] == "approval_required"


def test_blocked_violation_wins():
    assert evaluate_scope(True, True, ["blocked scope attempted"])["boundary"] == "blocked"
