from console.backend.database import ConsoleDatabase


def test_user_session_and_run_ownership(tmp_path):
    db = ConsoleDatabase(tmp_path / "console.sqlite3")
    user_id = db.create_user("owner@example.com", "correct horse battery")

    assert db.authenticate("owner@example.com", "correct horse battery") == user_id
    assert db.authenticate("owner@example.com", "wrong password") is None

    token = db.session(user_id)
    assert db.user_for_token(token) == user_id
    db.claim_runs(user_id, ["run-1"], "REIN-RETAIL-001")
    assert db.owner("run-1") == user_id

    db.delete_session(token)
    assert db.user_for_token(token) is None
