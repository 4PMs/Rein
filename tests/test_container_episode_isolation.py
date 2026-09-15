"""Container-mode isolation and real-episode-execution guarantees.

These tests target the architecture rules from the container-agent-episode
task: the Host must never run the real agent process, LLM calls in container
mode must go through the model relay (never a direct provider credential),
and the attacker container must never be able to reach the target directly.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tempera.agent.runtime_control import (
    AgentRuntimeError, CommandResult, ContainerAgentRuntime,
)
from tempera.agent.topology import ForcedGatewayTopology, TopologyError
from tempera.core.policy import Policy
from tempera.core.run import RunConfig


# --- Test A: container mode config sets gateway_required/network_mode/model_transport ---

def test_container_mode_config_declares_gateway_required_and_relay_transport():
    config = RunConfig(
        run_id="run-a", model="deepseek-chat", model_version="unknown", agent_version="test",
        environment="juice_shop", scenario="JS-P2-006", policy="policy", max_steps=4, timeout=20,
        started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        agent_runtime="container", attacker_container="tempera-attacker",
        network_mode="forced_gateway", gateway_required=True, control_plane="separate",
        model_transport="relay",
    )
    data = config.to_dict()
    assert data["agent_runtime"] == "container"
    assert data["gateway_required"] is True
    assert data["network_mode"] == "forced_gateway"
    assert data["model_transport"] == "relay"


# --- Test B: container branch actually executes an episode, not just smoke ---

def test_container_agent_run_writes_input_and_invokes_container_entrypoint(tmp_path):
    calls = []

    def fake_exec(command, **kwargs):
        calls.append(command)
        outcome = {"reason": "agent_done", "step": 1, "detail": None,
                   "usage": {"model_calls": 1, "total_tokens": 42}}
        (tmp_path / "container_outcome.json").write_text(json.dumps(outcome), encoding="utf-8")
        return CommandResult("ok", "", 0)

    runtime = ContainerAgentRuntime("tempera-attacker")
    runtime.exec = fake_exec
    outcome = runtime.run(
        Mock(), "mission text", "http://tempera-gateway-x:8080", 4,
        run_dir=tmp_path, run_id="run-b", provider="deepseek", model="deepseek-chat",
        policy=Policy.from_dict({}), scenario="JS-P2-006", goal={},
        model_endpoint="http://tempera-model-relay:8090",
    )
    assert outcome["reason"] == "agent_done"
    assert outcome["usage"]["model_calls"] == 1
    assert calls, "docker exec was never invoked"
    assert calls[0][:4] == ["python3", "-B", "-m", "tempera.agent.container_episode"]
    assert calls[0][-1] == "/app/runs/run-b"
    written = json.loads((tmp_path / "container_input.json").read_text(encoding="utf-8"))
    assert written["gateway_url"] == "http://tempera-gateway-x:8080"
    assert written["model_endpoint"] == "http://tempera-model-relay:8090"
    assert written["run_id"] == "run-b"


def test_container_agent_run_merges_trace_lifecycle_and_invocation_callbacks(tmp_path):
    """Regression test: runtime.run() must call on_step/on_lifecycle/on_invocation
    (the exact kwarg names the runner passes) with records replayed from the
    container's own JSONL output files, not silently drop them. This was
    broken once already: the merge loop matched kwargs.get(f"on_{name}") where
    name="trace", looking for a non-existent "on_trace" kwarg instead of the
    real "on_step" the runner actually passes, so trace.jsonl stayed empty
    for every real container-mode run despite the container writing real
    trace records to container_trace.jsonl.
    """
    def fake_exec(command, **kwargs):
        (tmp_path / "container_outcome.json").write_text(
            json.dumps({"reason": "agent_done", "step": 1}), encoding="utf-8",
        )
        (tmp_path / "container_trace.jsonl").write_text(
            json.dumps({"step": 1, "action": "http_request"}) + "\n", encoding="utf-8",
        )
        (tmp_path / "container_lifecycle.jsonl").write_text(
            json.dumps({
                "stage": "proposed", "action_id": "action-1", "seq": 0,
                "raw_action": {"action": "http_request"}, "normalized_action": {},
                "decision": None, "reason": None,
            }) + "\n", encoding="utf-8",
        )
        (tmp_path / "container_invocations.jsonl").write_text(
            json.dumps({"event_type": "tool_invocation", "stage": "invocation_created"}) + "\n",
            encoding="utf-8",
        )
        return CommandResult("ok", "", 0)

    runtime = ContainerAgentRuntime("tempera-attacker")
    runtime.exec = fake_exec
    steps, lifecycle_calls, invocations = [], [], []
    runtime.run(
        Mock(), "mission", "http://tempera-gateway-x:8080", 4,
        run_dir=tmp_path, run_id="run-h", model_endpoint="http://tempera-model-relay:8090",
        on_step=steps.append,
        on_lifecycle=lambda *args: lifecycle_calls.append(args),
        on_invocation=invocations.append,
    )
    assert steps == [{"step": 1, "action": "http_request"}]
    assert len(lifecycle_calls) == 1
    assert lifecycle_calls[0][0] == "proposed"
    assert lifecycle_calls[0][1] == "action-1"
    assert len(invocations) == 1
    assert invocations[0]["stage"] == "invocation_created"


def test_container_agent_run_requires_model_endpoint(tmp_path):
    runtime = ContainerAgentRuntime("tempera-attacker")
    with pytest.raises(AgentRuntimeError, match="model_endpoint"):
        runtime.run(
            Mock(), "mission", "http://tempera-gateway-x:8080", 4,
            run_dir=tmp_path, run_id="run-c",
        )


def test_container_agent_run_wraps_docker_exec_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("TEMPERA_MODEL_ENDPOINT", raising=False)
    runtime = ContainerAgentRuntime("tempera-attacker")

    def failing_exec(command, **kwargs):
        raise AgentRuntimeError("docker exec failed: boom")

    runtime.exec = failing_exec
    with pytest.raises(AgentRuntimeError, match="container agent episode failed"):
        runtime.run(
            Mock(), "mission", "http://tempera-gateway-x:8080", 4,
            run_dir=tmp_path, run_id="run-d", model_endpoint="http://tempera-model-relay:8090",
        )


def test_container_agent_run_never_calls_episode_func_directly(tmp_path):
    """The Host must not execute the real agent process; only docker exec may."""
    episode_func = Mock(side_effect=AssertionError("run_episode must not run on Host"))

    def fake_exec(command, **kwargs):
        (tmp_path / "container_outcome.json").write_text(
            json.dumps({"reason": "agent_done", "step": 1}), encoding="utf-8",
        )
        return CommandResult("ok", "", 0)

    runtime = ContainerAgentRuntime("tempera-attacker")
    runtime.exec = fake_exec
    runtime.run(
        episode_func, "mission", "http://tempera-gateway-x:8080", 4,
        run_dir=tmp_path, run_id="run-e", model_endpoint="http://tempera-model-relay:8090",
    )
    episode_func.assert_not_called()


# --- Test C: attacker is never connected to target-net ---

def test_ensure_attacker_never_joins_target_network():
    topology = ForcedGatewayTopology()
    calls = []
    topology._docker = lambda *args, **kwargs: calls.append(args) or type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )()
    topology._exists = lambda kind, name: False
    topology._running = lambda name: True
    topology._networks = lambda name: {"attacker-net", "tempera-control-net"}
    topology._ensure_attacker()
    run_call = next(call for call in calls if call[:3] == ("run", "-d", "--name"))
    assert "target-net" not in run_call
    assert "--network" in run_call
    assert run_call[run_call.index("--network") + 1] == "attacker-net"


def test_ensure_attacker_raises_if_target_network_present():
    topology = ForcedGatewayTopology()
    topology._docker = lambda *args, **kwargs: type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )()
    topology._exists = lambda kind, name: True
    topology._running = lambda name: True
    topology._networks = lambda name: {"attacker-net", "target-net"}
    with pytest.raises(TopologyError, match="attacker-net"):
        topology._ensure_attacker()


def test_isolation_report_fails_if_attacker_reaches_target_directly():
    topology = ForcedGatewayTopology()

    class Runtime:
        def exec(self, command, **kwargs):
            url = command[-1]
            if "tempera-juice-forced" in url:
                return CommandResult("200", "", 0)  # target reachable: unsafe
            return CommandResult("200", "", 0)

    with pytest.raises(TopologyError, match="reach the target directly"):
        topology.isolation_report(Runtime())


def test_isolation_report_passes_when_target_blocked_and_gateway_relay_ok():
    topology = ForcedGatewayTopology()

    class Runtime:
        def exec(self, command, **kwargs):
            url = command[-1]
            if "tempera-juice-forced" in url:
                raise AgentRuntimeError("connection refused")
            return CommandResult("200", "", 0)

    report = topology.isolation_report(Runtime())
    assert report == {
        "target_direct_access": "blocked", "gateway_access": "ok", "model_relay_access": "ok",
    }


# --- Test D: gateway URL used by the attacker is a container DNS name, never Host loopback ---

@pytest.mark.parametrize("bad_url", [
    "http://127.0.0.1:3001", "http://localhost:8080", "http://0.0.0.0:8080",
])
def test_container_episode_rejects_host_loopback_gateway_url(bad_url, tmp_path):
    import importlib
    container_episode = importlib.import_module("tempera.agent.container_episode")
    with pytest.raises(ValueError, match="host-loopback"):
        container_episode._validate_gateway_url(bad_url)


def test_container_episode_accepts_container_dns_gateway_url():
    import importlib
    container_episode = importlib.import_module("tempera.agent.container_episode")
    container_episode._validate_gateway_url("http://tempera-gateway-abc123:8080")  # no raise


@pytest.mark.parametrize("bad_url", ["http://127.0.0.1:8090", "http://localhost:8090"])
def test_container_episode_rejects_host_loopback_model_endpoint(bad_url):
    import importlib
    container_episode = importlib.import_module("tempera.agent.container_episode")
    with pytest.raises(ValueError, match="host-loopback"):
        container_episode._validate_model_endpoint(bad_url)


def test_runner_builds_gateway_container_dns_name_not_loopback():
    """The runner must hand the attacker a gateway DNS name, never 127.0.0.1."""
    import hashlib
    run_id = "run-f"
    gateway_name = f"tempera-gateway-{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    container_gateway_url = f"http://{gateway_name}:8080"
    assert "127.0.0.1" not in container_gateway_url
    assert "localhost" not in container_gateway_url
    assert container_gateway_url.startswith("http://tempera-gateway-")


# --- Test E: DEEPSEEK_API_KEY never reaches the attacker; only the model relay gets it ---

def test_attacker_container_exec_never_forwards_deepseek_api_key():
    """ContainerAgentRuntime.exec only forwards an explicit allowlist of env vars."""
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "inspect":
            return type("Result", (), {"returncode": 0, "stdout": "running\n", "stderr": ""})()
        return type("Result", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})()

    runtime = ContainerAgentRuntime("tempera-attacker", runner=runner)
    runtime.exec(
        ["python3", "--version"],
        env={"TEMPERA_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-should-not-leak"},
    )
    exec_call = next(call for call in calls if call[1] == "exec")
    assert "DEEPSEEK_API_KEY" not in " ".join(exec_call)
    assert "TEMPERA_PROVIDER=deepseek" in exec_call


def test_container_episode_scrubs_deepseek_api_key_from_own_environment(monkeypatch, tmp_path):
    """container_episode.main() must never leave a DEEPSEEK_API_KEY set even if injected."""
    import importlib
    container_episode = importlib.import_module("tempera.agent.container_episode")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-leaked-if-present")
    # container_episode.main() sets TEMPERA_MODEL_ENDPOINT/TEMPERA_PROVIDER/
    # TEMPERA_MODEL as real side effects (see the module docstring: this is
    # exactly how it routes call_llm through the relay). Route those through
    # monkeypatch too so they are restored after this test instead of
    # leaking into whichever test runs next in the same process.
    monkeypatch.setenv("TEMPERA_MODEL_ENDPOINT", "unset-before-run")
    monkeypatch.setenv("TEMPERA_PROVIDER", "unset-before-run")
    monkeypatch.setenv("TEMPERA_MODEL", "unset-before-run")
    run_dir = tmp_path / "run-g"
    run_dir.mkdir()
    (run_dir / "container_input.json").write_text(json.dumps({
        "run_id": "run-g", "scenario": "JS-P2-006", "mission": "m", "goal": {},
        "policy": None, "max_steps": 1, "provider": "deepseek", "model": "deepseek-chat",
        "temperature": 0, "seed": None,
        "gateway_url": "http://tempera-gateway-x:8080",
        "model_endpoint": "http://tempera-model-relay:8090",
    }), encoding="utf-8")
    # container_episode._run_dir enforces the real container mount root
    # (/app/runs), which only exists inside the Linux attacker image; on
    # this Windows test host we bypass just that path-root check while
    # exercising the actual DEEPSEEK_API_KEY-scrubbing logic in main().
    monkeypatch.setattr(container_episode, "_run_dir", lambda value: Path(value))
    with patch("tempera.agent.runtime.run_episode", return_value={"reason": "agent_done", "step": 1}):
        code = container_episode.main(["--run-dir", str(run_dir)])
    assert code == 0
    assert "DEEPSEEK_API_KEY" not in __import__("os").environ


def test_model_relay_container_still_receives_deepseek_api_key(monkeypatch):
    """The existing topology behavior: relay gets the key, attacker never does."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-relay-only")
    topology = ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    topology._exists = lambda kind, name: False
    topology._running = lambda name: True
    topology._networks = lambda name: {"tempera-control-net", "tempera-model-egress-net"}
    calls = []
    topology._docker = lambda *args, **kwargs: calls.append(args) or type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )()
    topology._ensure_model_relay()
    run_call = next(call for call in calls if call[:3] == ("run", "-d", "--name"))
    assert "DEEPSEEK_API_KEY" in run_call
