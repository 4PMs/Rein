from datetime import datetime, timezone

import pytest

from tempera.agent.runtime_control import CommandResult
from tempera.agent.topology import ForcedGatewayTopology, TopologyError
from tempera.core.run import RunConfig


def _topology() -> ForcedGatewayTopology:
    topology = ForcedGatewayTopology()
    topology._networks = lambda name: {
        "attacker": {"attacker-net", "tempera-control-net"},
        "gateway": {"attacker-net", "target-net"},
        "target": {"target-net"},
    }[{"tempera-attacker": "attacker", "tempera-gateway-forced": "gateway",
       "tempera-juice-forced": "target"}[name]]
    topology._has_host_publish = lambda name: False
    return topology


def test_forced_topology_validation_requires_isolated_target():
    _topology().validate()
    topology = _topology()
    original = topology._networks
    topology._networks = lambda name: (
        {"target-net", "attacker-net"}
        if name == "tempera-juice-forced" else original(name)
    )
    with pytest.raises(TopologyError, match="target"):
        topology.validate()


def test_forced_topology_rejects_host_publish():
    topology = _topology()
    topology._has_host_publish = lambda name: name == "tempera-juice-forced"
    with pytest.raises(TopologyError, match="publish"):
        topology.validate()


def test_container_run_metadata_is_explicit_and_backward_compatible():
    config = RunConfig(
        run_id="run-stage3", model="model", model_version="unknown", agent_version="test",
        environment="juice_shop", scenario="JS-001", policy="policy", max_steps=1, timeout=1,
        started_at=datetime.now(timezone.utc), agent_runtime="container",
        attacker_container="tempera-attacker", network_mode="forced_gateway",
        gateway_required=True, control_plane="separate",
    )
    data = config.to_dict()
    assert data["network_mode"] == "forced_gateway"
    assert data["gateway_required"] is True
    assert data["control_plane"] == "separate"


def test_gateway_smoke_uses_runtime_and_requires_http_200():
    topology = _topology()

    class Runtime:
        def exec(self, command, **kwargs):
            assert command[-1] == "http://tempera-gateway-forced:8080/__tempera_gateway_health__"
            return CommandResult("200", "", 0)

    assert topology.smoke(Runtime())["status"] == "200"


def _gateway_identity(topology, run_id, source=None):
    source = source or str(topology.run_dir)
    return ([{"Source": source, "Destination": f"/app/runs/{run_id}"}],
            {"com.tempera.owner": "benchmark-forced-gateway", "com.tempera.run_id": run_id,
             "com.tempera.artifact_path": source},
            ["--upstream", "http://tempera-juice-forced:3000", "--run", run_id])


def test_gateway_mount_identity_accepts_canonical_windows_docker_path(tmp_path):
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    drive, rest = str(tmp_path).replace("\\", "/").split(":", 1)
    docker_path = "/host_mnt/" + drive.lower() + rest
    topology._gateway_inspect = lambda name: _gateway_identity(topology, "run-a", docker_path)
    assert topology._gateway_matches("run-a", "http://tempera-juice-forced:3000")


def test_gateway_mount_identity_rejects_different_run_or_artifact(tmp_path):
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    topology._gateway_inspect = lambda name: _gateway_identity(topology, "run-a", str(tmp_path / "old"))
    assert not topology._gateway_matches("run-b", "http://tempera-juice-forced:3000")


def test_stale_unowned_gateway_is_not_removed(tmp_path):
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    topology._exists = lambda kind, name: True
    topology._gateway_matches = lambda run_id, upstream: False
    topology._gateway_owned = lambda: False
    with pytest.raises(TopologyError, match="gateway_mount_mismatch"):
        topology._ensure_gateway("run-b")


def test_owned_stale_gateway_is_recreated_for_current_arm(tmp_path):
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    topology._exists = lambda kind, name: True
    matches = iter((False, True))
    topology._gateway_matches = lambda run_id, upstream: next(matches)
    topology._gateway_owned = lambda: True
    topology._running = lambda name: True
    topology._gateway_poll_attempts = 1
    topology._gateway_poll_interval = 0
    topology._networks = lambda name: {"attacker-net", "target-net"}
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    topology._docker = docker
    topology._ensure_gateway("run-b")
    assert ("rm", "-f", "tempera-gateway-forced") in calls
    run_call = next(call for call in calls if call[:3] == ("run", "-d", "--name"))
    assert "com.tempera.run_id=run-b" in run_call
    assert "run-b" in run_call


def test_gateway_cleanup_removes_only_owned_gateway(tmp_path):
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    topology._exists = lambda kind, name: True
    topology._gateway_owned = lambda: True
    calls = []
    topology._docker = lambda *args, **kwargs: calls.append(args)
    topology.cleanup()
    assert calls == [("rm", "-f", "tempera-gateway-forced")]


def test_gateway_that_crashes_immediately_after_run_fails_closed_with_logs(tmp_path):
    """Reproduces the real incident: a stale GATEWAY_IMAGE whose bundled
    tempera.core.run.RunConfig rejected a config.json field the current
    Host writes (max_tokens) crashed the gateway process right after
    `docker run -d`. Before this fix _ensure_gateway() never checked
    _running() after starting a freshly created container, so
    topology.ensure() reported success with no gateway actually listening
    -- the container agent then failed minutes later with an opaque
    'curl: could not resolve host <gateway>' instead of an immediate,
    attributable TopologyError. This test locks in the fail-closed check
    and the crash-log attachment that made the real failure diagnosable."""
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    topology._exists = lambda kind, name: False
    topology._running = lambda name: False
    docker_calls = []

    def docker(*args, **kwargs):
        docker_calls.append(args)
        if args[0] == "logs":
            return type("Result", (), {
                "returncode": 0, "stdout": "TypeError: RunConfig.__init__() got an unexpected keyword argument 'max_tokens'",
                "stderr": "",
            })()
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    topology._docker = docker
    with pytest.raises(TopologyError, match="gateway failed closed during startup"):
        topology._ensure_gateway("run-b")
    # The crash detail must actually be surfaced, not just a bare
    # "failed closed" -- that is precisely what made the real incident
    # take an on-call round of manual `docker logs` digging to diagnose.
    with pytest.raises(TopologyError, match="max_tokens"):
        topology._ensure_gateway("run-b")


def test_gateway_that_crashes_after_reuse_start_fails_closed(tmp_path):
    """Mirrors the above for the 'container already exists but stopped'
    branch (docker start rather than docker run -d)."""
    topology = ForcedGatewayTopology(run_dir=tmp_path)
    topology._exists = lambda kind, name: True
    topology._gateway_matches = lambda run_id, upstream: True
    topology._running = lambda name: False
    topology._docker = lambda *args, **kwargs: type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )()
    with pytest.raises(TopologyError, match="gateway failed closed during startup"):
        topology._ensure_gateway("run-b")


def test_gateway_crash_between_startup_and_network_connect_fails_closed():
    """A gateway that survived the post-startup settle window but died
    while attacker-net/target-net were being attached must still be caught
    -- network membership is a static Docker-side fact even for a dead
    container, so validate()-style checks alone cannot see this."""
    topology = ForcedGatewayTopology()
    topology._gateway_poll_attempts = 1
    topology._gateway_poll_interval = 0
    topology._exists = lambda kind, name: False
    # Two True calls consumed by _await_gateway_running (the loop check and
    # the final settle-window check), then False for the last check in
    # _ensure_gateway after attacker-net/target-net have been attached.
    running_calls = iter([True, True, False])
    topology._running = lambda name: next(running_calls, False)
    topology._networks = lambda name: {"attacker-net", "target-net"}
    topology._docker = lambda *args, **kwargs: type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )()
    with pytest.raises(TopologyError, match="gateway failed closed after startup"):
        topology._ensure_gateway("run-b")


def test_gateway_dns_hostname_matches_container_name_used_by_runner():
    """runner.py's container branch builds the hostname the attacker will
    resolve as f"tempera-gateway-{sha256(run_id)[:12]}" and passes that
    exact string as ForcedGatewayTopology(gateway=...). Docker's embedded
    DNS resolves a container by its --name, so the hostname the container
    agent is told to reach must be identical to the --name given to
    `docker run` in _ensure_gateway() -- if these ever drift apart, the
    attacker gets exactly the 'could not resolve host' failure from the
    real incident even with a perfectly healthy gateway process."""
    import hashlib
    run_id = "run-dns-check"
    gateway_hostname = f"tempera-gateway-{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    topology = ForcedGatewayTopology(gateway=gateway_hostname)
    topology._gateway_poll_attempts = 1
    topology._gateway_poll_interval = 0
    topology._exists = lambda kind, name: False
    topology._running = lambda name: True
    topology._networks = lambda name: {"attacker-net", "target-net"}
    calls = []
    topology._docker = lambda *args, **kwargs: (calls.append(args) or type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )())
    topology._ensure_gateway(run_id)
    run_call = next(call for call in calls if call[:3] == ("run", "-d", "--name"))
    # --name is what Docker's embedded DNS actually resolves; it must be
    # byte-for-byte the same hostname the container agent is later told.
    assert run_call[3] == gateway_hostname


def test_gateway_container_is_attached_to_attacker_net_and_target_net():
    topology = ForcedGatewayTopology()
    topology._gateway_poll_attempts = 1
    topology._gateway_poll_interval = 0
    topology._exists = lambda kind, name: False
    topology._running = lambda name: True
    # First _networks() call (right after `docker run -d`) reports only
    # attacker-net -- as it would for a freshly created container that
    # hasn't been connected to target-net yet -- so _ensure_gateway() must
    # issue the target-net `docker network connect`. Later calls report
    # both networks (post-connect state).
    networks_calls = iter([{"attacker-net"}])
    topology._networks = lambda name: next(networks_calls, {"attacker-net", "target-net"})
    run_args = []
    topology._docker = lambda *args, **kwargs: (run_args.append(args) or type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )())
    topology._ensure_gateway("run-net-check")
    run_call = next(call for call in run_args if call[:3] == ("run", "-d", "--name"))
    assert "--network" in run_call
    assert run_call[run_call.index("--network") + 1] == "attacker-net"
    # target-net attachment happens via a separate `docker network connect`
    # call once the container exists (mirrors real dual-homing sequence).
    assert ("network", "connect", "target-net", topology.topology.gateway) in run_args


def test_model_relay_stays_off_attacker_net_and_target_net_even_when_relay_required(monkeypatch):
    """Gateway and Model Relay must never share a network scope: the
    gateway bridges attacker-net/target-net, the model relay bridges
    control-net/model-egress-net, and neither container may appear on the
    other's networks. This guards against the two roles ever being
    accidentally merged."""
    topology = ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    topology._exists = lambda kind, name: False
    topology._running = lambda name: True
    topology._networks = lambda name: {"tempera-control-net", "tempera-model-egress-net"}
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    topology._docker = lambda *args, **kwargs: type(
        "Result", (), {"returncode": 0, "stdout": "", "stderr": ""},
    )()
    topology._ensure_model_relay()
    relay_networks = topology._networks(topology.model_relay)
    assert "attacker-net" not in relay_networks
    assert "target-net" not in relay_networks


def test_model_relay_uses_explicit_benchmark_config_without_provider_env(monkeypatch):
    for name in ("TEMPERA_MODEL_UPSTREAM", "TEMPERA_MODEL_ALLOWED_ENDPOINTS",
                 "TEMPERA_PROVIDER", "TEMPERA_MODEL"):
        monkeypatch.delenv(name, raising=False)
    topology = ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    assert topology._model_relay_config() == (
        "https://api.deepseek.com", "deepseek", "deepseek-chat", {"api.deepseek.com"},
    )


@pytest.mark.parametrize("kwargs, message", [
    ({"model_relay_provider": "deepseek", "model_relay_model": "deepseek-chat",
      "model_relay_allowed_endpoints": {"api.deepseek.com"}}, "incomplete"),
    ({"model_relay_provider": "deepseek", "model_relay_model": "deepseek-chat",
      "model_relay_upstream": "https://other.test",
      "model_relay_allowed_endpoints": {"api.deepseek.com"}}, "not approved"),
])
def test_model_relay_config_fails_closed(kwargs, message):
    topology = ForcedGatewayTopology(**kwargs)
    with pytest.raises(TopologyError, match=message):
        topology._model_relay_config()


def test_unowned_stale_model_relay_is_preserved_and_rejected(monkeypatch):
    topology = ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    topology._exists = lambda kind, name: True
    topology._relay_matches = lambda *args: False
    topology._relay_owned = lambda: False
    with pytest.raises(TopologyError, match="not benchmark-owned"):
        topology._ensure_model_relay()


def test_owned_stale_model_relay_is_recreated_with_current_identity(monkeypatch):
    topology = ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    exists = iter((True, False))
    topology._exists = lambda kind, name: next(exists)
    topology._relay_matches = lambda *args: False
    topology._relay_owned = lambda: True
    topology._running = lambda name: True
    topology._networks = lambda name: {"tempera-control-net", "tempera-model-egress-net"}
    calls = []
    topology._docker = lambda *args, **kwargs: calls.append(args)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    topology._ensure_model_relay()
    assert ("rm", "-f", "tempera-model-relay") in calls
    run_call = next(call for call in calls if call[:3] == ("run", "-d", "--name"))
    assert "com.tempera.owner=benchmark-model-relay" in run_call
    assert "com.tempera.provider=deepseek" in run_call
    assert "com.tempera.model=deepseek-chat" in run_call
    assert "DEEPSEEK_API_KEY" not in " ".join(run_call)
