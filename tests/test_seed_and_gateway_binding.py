from unittest.mock import Mock, patch

from tempera.agent.runtime import call_llm, provider_seed_supported, run_episode
from tempera.observe.gateway import ActionBindingRegistry, create_app
from tempera.core.sequence import SequenceAllocator


def test_supported_provider_includes_seed_in_request(monkeypatch):
    # TEMPERA_MODEL_ENDPOINT must be absent for this test: call_llm() reads
    # it from the environment at call time via
    # `os.environ.get("TEMPERA_MODEL_ENDPOINT", MODEL_ENDPOINT)`. The
    # `MODEL_ENDPOINT` fallback is a MODULE-LEVEL CONSTANT frozen once, the
    # first time tempera.agent.runtime is imported in this process -- if
    # the test process's shell already had TEMPERA_MODEL_ENDPOINT set at
    # that moment (e.g. left over from an earlier container-mode run in the
    # same terminal session), MODEL_ENDPOINT is permanently non-empty for
    # the rest of this pytest process, and monkeypatch.delenv on
    # os.environ alone cannot undo that: os.environ.get(...) only checks
    # os.environ, and the second positional arg is only ever the frozen
    # constant, not re-read from the environment. So both the environment
    # variable AND the frozen module constant must be cleared for this
    # test to deterministically exercise the direct-Ollama branch it is
    # actually testing.
    monkeypatch.delenv("TEMPERA_MODEL_ENDPOINT", raising=False)
    monkeypatch.setattr("tempera.agent.runtime.MODEL_ENDPOINT", None)
    response = Mock()
    response.json.return_value = {"message": {"content": "{}"}}
    response.raise_for_status.return_value = None
    with patch("tempera.agent.runtime.requests.post", return_value=response) as post:
        call_llm([], provider="ollama", model="test", seed=7)
    assert post.call_args.kwargs["json"]["options"]["seed"] == 7
    assert provider_seed_supported("ollama") is True


def test_unsupported_provider_reports_not_applied_and_does_not_send_seed(monkeypatch):
    monkeypatch.delenv("TEMPERA_MODEL_ENDPOINT", raising=False)
    monkeypatch.setattr("tempera.agent.runtime.MODEL_ENDPOINT", None)
    assert provider_seed_supported("deepseek") is False
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
    response.raise_for_status.return_value = None
    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test"}), \
         patch("tempera.agent.runtime.requests.post", return_value=response) as post:
        call_llm([], provider="deepseek", model="test", seed=None)
    assert "seed" not in post.call_args.kwargs["json"]


def test_episode_result_records_unsupported_seed(monkeypatch):
    monkeypatch.setattr("tempera.agent.runtime.call_llm", lambda *args, **kwargs: '{"action":"done"}')
    result = run_episode("mission", "gateway", 1, provider="deepseek", seed=7)
    assert result["reproducibility"] == {
        "seed_requested": 7, "seed_supported": False, "seed_applied": False,
        "status": "seed_not_supported",
        "reason": "provider_does_not_support_seed",
    }


def _app(registry, enforce=True, events=None):
    return create_app(
        "http://target.test", "run-1", "agent", events.append if events is not None else lambda event: None,
        action_registry=registry, enforce_policy=enforce,
        sequence_allocator=SequenceAllocator(),
    )


def test_valid_binding_is_observed_and_single_use():
    registry = ActionBindingRegistry()
    events = []
    token = registry.register("run-1", "action-1", "allow")
    client = _app(registry, events=events).test_client()
    with patch("tempera.observe.gateway.requests.request") as request:
        request.return_value.status_code = 200
        request.return_value.content = b"ok"
        request.return_value.raw.headers = {}
        first = client.get("/", headers={"X-Tempera-Action-Id": "action-1", "X-Tempera-Correlation-Token": token})
        replay = client.get("/", headers={"X-Tempera-Action-Id": "action-1", "X-Tempera-Correlation-Token": token})
    assert first.status_code == 200
    assert replay.status_code == 403
    assert request.call_count == 1
    assert events[0].attributes["action_id"] == "action-1"


def test_spoofed_or_cross_action_token_fails_without_target_call():
    registry = ActionBindingRegistry()
    token = registry.register("run-1", "action-1", "allow")
    other = registry.register("run-1", "action-2", "allow")
    client = _app(registry).test_client()
    with patch("tempera.observe.gateway.requests.request") as request:
        assert client.get("/", headers={"X-Tempera-Action-Id": "spoof", "X-Tempera-Correlation-Token": token}).status_code == 403
        assert client.get("/", headers={"X-Tempera-Action-Id": "action-1", "X-Tempera-Correlation-Token": other}).status_code == 403
    assert request.call_count == 0


def test_direct_bypass_and_denied_action_are_blocked_when_enforced():
    registry = ActionBindingRegistry()
    denied = registry.register("run-1", "action-denied", "deny")
    client = _app(registry).test_client()
    with patch("tempera.observe.gateway.requests.request") as request:
        assert client.get("/").status_code == 403
        assert client.get("/", headers={"X-Tempera-Action-Id": "action-denied", "X-Tempera-Correlation-Token": denied}).status_code == 403
    assert request.call_count == 0
