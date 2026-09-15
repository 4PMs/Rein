import json

from tempera.normalize.request import classify_activity, normalize_request
from tempera.observe.gateway import WebObserver
from tempera.observe.normalizer import RawObservation
from datetime import datetime, timezone


def test_json_request_is_canonical_and_redacts_sensitive_fields():
    request = normalize_request({
        "method": "post", "url": "https://target.test:8443/login?next=/home",
        "headers": {"Authorization": "Bearer secret-token", "X-Test": "ok"},
        "body": json.dumps({"email": "test@example.com", "password": "' OR 1=1 --"}),
        "content_type": "application/json",
    })
    assert request["method"] == "POST"
    assert request["scheme"] == "https"
    assert request["host"] == "target.test"
    assert request["port"] == 8443
    assert request["path"] == "/login"
    assert request["query"] == {"next": "/home"}
    assert request["body_fields"]["password"] == "[REDACTED]"
    assert request["headers"]["authorization"] == "[REDACTED]"
    assert request["body_parse_status"] == "normalized"
    assert "injection_operator_pattern" in request["evidence_markers"]
    assert "secret-token" not in repr(request)


def test_form_and_text_body_parsing():
    form = normalize_request({
        "method": "POST", "path": "/search?q=x", "headers": {},
        "body": "q=hello&password=secret", "content_type": "application/x-www-form-urlencoded",
    })
    text = normalize_request({
        "method": "POST", "path": "/note", "body": "hello world",
        "content_type": "text/plain",
    })
    assert form["body_fields"] == {"q": "hello", "password": "[REDACTED]"}
    assert text["body"] == "hello world"
    assert text["body_fields"] is None


def test_malformed_body_is_unclassified_not_guessed():
    request = normalize_request({
        "method": "POST", "path": "/login", "body": '{"password":',
        "content_type": "application/json",
    })
    assert request["body_parse_status"] == "unclassified"
    assert request["body_fields"] is None
    assert request["activity_classification"] == "unclassified"


def test_sql_injection_requires_structured_evidence():
    confirmed = normalize_request({
        "method": "GET", "url": "http://target.test/item?id=1%27%20OR%201%3D1--",
    })
    keyword_only = normalize_request({
        "method": "GET", "url": "http://target.test/search?q=select",
    })
    normal = normalize_request({
        "method": "GET", "url": "http://target.test/item?id=1",
    })
    assert classify_activity(confirmed)["activity"] == "sql_injection_testing"
    assert classify_activity(confirmed)["classification"] == "confirmed"
    assert classify_activity(keyword_only)["classification"] in {"partial", "unclassified"}
    assert classify_activity(normal)["activity"] != "sql_injection_testing"


def test_explicit_activity_context_is_tool_independent():
    allowed = {"allowed": ["token_inspection"], "prohibited": ["password_cracking"]}
    for tool in ("python3", "shell", "browser", "jwt-tool"):
        observed = normalize_request({"method": "GET", "path": "/local", "tool": tool})
        result = classify_activity(observed, {"activity": "token_inspection"})
        assert result["activity"] == "token_inspection"
        assert result["classification"] == "confirmed"
    assert allowed["prohibited"] == ["password_cracking"]


def test_web_observer_persists_only_redacted_request_material():
    event = WebObserver().normalize(
        "run-1",
        RawObservation(
            timestamp=datetime.now(timezone.utc), actor="agent", source="gateway",
            kind="web", action="request", target="http://target.test/login",
            facts={"method": "POST", "path": "/login", "headers": {
                "Authorization": "Bearer secret-token",
                "Content-Type": "application/json",
            }, "_request_body": b'{"password":"secret-password"}'},
        ),
        seq=1,
    )
    serialized = repr(event.to_dict())
    assert "secret-token" not in serialized
    assert "secret-password" not in serialized
    assert event.attributes["normalized_request"]["body_fields"]["password"] == "[REDACTED]"
