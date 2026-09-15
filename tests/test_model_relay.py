from unittest.mock import Mock, patch
import sys

import pytest

from tempera.agent.model_relay import ModelRelayError, create_model_relay_app
from tempera.agent.runtime import ModelRelayUnavailableError, call_llm
from tempera.agent.invocation import ToolInvocation, child_correlation
from tempera.agent.tool_runner import run


def test_relay_forwards_fixed_provider_model_without_destination_override():
    app = create_model_relay_app(
        upstream="https://api.deepseek.com", provider="deepseek", model="deepseek-chat",
        api_key="secret", allowed_endpoints={"api.deepseek.com"},
    )
    response = Mock(status_code=200, content=b'{"choices":[{"message":{"content":"ok"}}]}')
    response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    with patch("tempera.agent.model_relay.requests.post", return_value=response) as post:
        result = app.test_client().post(
            "/v1/chat/completions", json={"messages": [], "upstream": "https://evil.test"},
        )
    assert result.status_code == 400
    post.assert_not_called()


def test_relay_masks_secret_from_upstream_request_metadata():
    app = create_model_relay_app(
        upstream="https://api.deepseek.com", provider="deepseek", model="deepseek-chat",
        api_key="secret", allowed_endpoints={"api.deepseek.com"},
    )
    response = Mock(status_code=200, content=b'{}')
    response.json.return_value = {}
    with patch("tempera.agent.model_relay.requests.post", return_value=response) as post:
        assert app.test_client().post("/v1/chat/completions", json={"messages": []}).status_code == 200
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"


def test_relay_rejects_unapproved_endpoint_and_provider_model():
    with pytest.raises(ModelRelayError):
        create_model_relay_app(upstream="https://evil.test", provider="deepseek",
                               model="deepseek-chat", allowed_endpoints={"api.deepseek.com"})
    app = create_model_relay_app(upstream="http://model", provider="ollama", model="qwen",
                                 allowed_endpoints={"model"})
    assert app.test_client().post("/v1/chat/completions", headers={"X-Tempera-Model": "other"},
                                  json={"messages": []}).status_code == 403


def test_upstream_401_is_auth_failure_without_secret_logging():
    app = create_model_relay_app(upstream="https://api.deepseek.com", provider="deepseek",
                                 model="deepseek-chat", api_key="secret",
                                 allowed_endpoints={"api.deepseek.com"})
    response = Mock(status_code=401, content=b'{"error":"unauthorized"}')
    response.json.return_value = {"error": "unauthorized"}
    with patch("tempera.agent.model_relay.requests.post", return_value=response):
        result = app.test_client().post("/v1/chat/completions", json={"messages": []})
    assert result.status_code == 401
    assert result.json["error_code"] == "upstream_auth"
    assert "secret" not in result.get_data(as_text=True)


def test_relay_client_has_bounded_failure_and_no_direct_fallback(monkeypatch):
    monkeypatch.setattr("tempera.agent.runtime.MODEL_ENDPOINT", "http://relay:8090")
    with patch("tempera.agent.runtime.requests.post", side_effect=__import__("requests").Timeout):
        with pytest.raises(ModelRelayUnavailableError):
            call_llm([], provider="deepseek", model="deepseek-chat")


def test_call_llm_adds_max_tokens_only_when_requested(monkeypatch):
    monkeypatch.delenv("TEMPERA_MODEL_ENDPOINT", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    response = Mock(status_code=200)
    response.json.side_effect = [
        {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}},
        {"choices": [{"message": {"content": "ok"}, "finish_reason": "length"}],
         "usage": {"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6}},
    ]
    with patch("tempera.agent.runtime.requests.post", return_value=response) as post:
        call_llm([], provider="deepseek", model="deepseek-chat")
        call_llm([], provider="deepseek", model="deepseek-chat", max_tokens=50)
    first_payload, second_payload = [call.kwargs["json"] for call in post.call_args_list]
    assert "max_tokens" not in first_payload
    assert second_payload["max_tokens"] == 50


def test_call_llm_relay_forwards_max_tokens_and_records_finish_reason(monkeypatch):
    monkeypatch.setenv("TEMPERA_MODEL_ENDPOINT", "http://relay:8090")
    response = Mock(status_code=200)
    response.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 50, "total_tokens": 52},
    }
    with patch("tempera.agent.runtime.requests.post", return_value=response) as post:
        call_llm([], provider="deepseek", model="deepseek-chat", max_tokens=50)
    payload = post.call_args.kwargs["json"]
    assert payload["max_tokens"] == 50
    from tempera.agent.runtime import MODEL_USAGE_LOG
    assert MODEL_USAGE_LOG[-1]["finish_reason"] == "length"


def test_tool_invocation_redacts_arguments_and_supports_one_to_many_children():
    invocation = ToolInvocation("run-1", "A17", "sqlmap",
                                {"url": "https://target", "api_key": "secret"})
    created = invocation.record("invocation_created")
    started = invocation.record("execution_started")
    finished = invocation.record("execution_finished", status="completed", child_event_count=3)
    assert created["arguments"]["api_key"] == "[REDACTED]"
    assert [item["stage"] for item in (created, started, finished)] == [
        "invocation_created", "execution_started", "execution_finished"]
    assert finished["child_event_count"] == 3
    assert child_correlation("A17", token_valid=True)["parent_action_id"] == "A17"
    assert child_correlation(None, token_valid=False)["correlation_status"] == "orphan"


def test_tool_runner_records_process_identity_and_bounded_output(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "do-not-log")
    result = run([sys.executable, "-c", "print('x' * 3000)"], timeout=5)
    assert result["status"] == "completed"
    assert isinstance(result["pid"], int)
    assert result["pid_namespace"] == "container"
    assert result["executable"]
    assert result["started_at"] < result["finished_at"] or result["started_at"] == result["finished_at"]
    assert result["stdout_truncated"] is True
    assert len(result["stdout_preview"]) <= 2000

    secret = run([sys.executable, "-c", "print('do-not-log')"], timeout=5)
    assert "do-not-log" not in secret["stdout_preview"]


def test_tool_runner_records_failure_and_timeout_statuses():
    failed = run([sys.executable, "-c", "raise SystemExit(7)"], timeout=5)
    timed_out = run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.05)
    assert failed["status"] == "failed" and failed["exit_code"] == 7
    assert timed_out["status"] == "timed_out"
