"""Run-level completion token budget behavior."""

from datetime import datetime, timezone

from tempera.agent import runtime
from tempera.core.run import RunConfig


def _config(**overrides):
    values = {
        "run_id": "budget-test",
        "model": "deepseek-chat",
        "model_version": "1",
        "agent_version": "test",
        "environment": "juice_shop",
        "scenario": "JS-003",
        "policy": "policy",
        "max_steps": 15,
        "timeout": 20,
        "started_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return RunConfig(**values)


def test_run_config_round_trips_run_token_budget():
    config = _config(run_token_budget=700)
    restored = RunConfig.from_dict(config.to_dict())
    assert restored.run_token_budget == 700
    assert config.to_dict()["run_token_budget"] == 700


def test_budget_uses_safe_floor_and_stops_before_next_call(monkeypatch):
    calls = []

    def fake_call(*args, **kwargs):
        calls.append(kwargs)
        runtime.MODEL_USAGE_LOG.append({
            "index": len(runtime.MODEL_USAGE_LOG) + 1,
            "usage_available": True,
            "prompt_tokens": 10,
            "completion_tokens": 201,
            "total_tokens": 211,
            "finish_reason": "stop",
        })
        return '{"action":"http_request","method":"GET","path":"/"}'

    monkeypatch.setattr(runtime, "call_llm", fake_call)
    monkeypatch.setattr(runtime, "do_http", lambda action, gateway: "status=200\\nbody=ok")
    runtime.reset_model_usage_log()
    outcome = runtime.run_episode(
        "mission", "http://127.0.0.1:1", 15,
        provider="deepseek", model="deepseek-chat", run_token_budget=360,
    )

    assert outcome["reason"] == "token_budget_exhausted"
    assert len(calls) == 1
    assert calls[0]["max_tokens"] is None
    assert outcome["usage"]["completion_tokens_used"] == 201
    assert outcome["usage"]["completion_tokens_remaining"] == 159
    assert outcome["usage"]["token_budget_exhausted"] is True


def test_budget_usage_missing_is_accounting_failure(monkeypatch):
    def fake_call(*args, **kwargs):
        runtime.MODEL_USAGE_LOG.append({
            "index": 1, "usage_available": False,
            "prompt_tokens": None, "completion_tokens": None,
            "total_tokens": None, "finish_reason": "stop",
        })
        return '{"action":"done"}'

    monkeypatch.setattr(runtime, "call_llm", fake_call)
    runtime.reset_model_usage_log()
    outcome = runtime.run_episode(
        "mission", "http://127.0.0.1:1", 15,
        provider="deepseek", model="deepseek-chat", run_token_budget=700,
    )
    assert outcome["reason"] == "token_accounting_failed"
    assert outcome["usage"]["completion_tokens_used"] is None
    assert outcome["usage"]["accounting_status"] == "failed"


def test_unlimited_preserves_per_call_max_tokens(monkeypatch):
    calls = []

    def fake_call(*args, **kwargs):
        calls.append(kwargs)
        return '{"action":"done"}'

    monkeypatch.setattr(runtime, "call_llm", fake_call)
    runtime.reset_model_usage_log()
    outcome = runtime.run_episode(
        "mission", "http://127.0.0.1:1", 15,
        provider="deepseek", model="deepseek-chat", max_tokens=42,
    )
    assert outcome["reason"] == "agent_done"
    assert calls[0]["max_tokens"] == 42
