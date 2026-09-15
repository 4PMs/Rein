from unittest.mock import Mock, patch

import subprocess

import pytest

from tempera.agent.runtime import do_http, parse_action, run_episode
from tempera.agent.runtime_control import (
    AgentProcessError, ContainerAgentRuntime, ContainerNotFoundError,
    ContainerExecutionError, ContainerStoppedError, get_agent_runtime,
)
from tempera.agents.reference import ReferenceAgentAdapter


def test_parse_action_recovers_deepseek_reasoning_prefix():
    raw = 'reasoning\n\n<｜end▁of▁thinking｜>{"action":"done","reason":"ok"}'
    assert parse_action(raw) == {"action": "done", "reason": "ok"}


def test_parse_action_rejects_ambiguous_actions():
    raw = '{"action":"done"}\n{"action":"http_request","method":"GET","path":"/"}'
    assert parse_action(raw) is None


def test_absolute_url_uses_only_path_and_query_for_proxy_upstream():
    response = Mock(status_code=200, content=b"ok", text="ok")
    response.raw.headers = {}
    with patch("tempera.agent.runtime.requests.request", return_value=response) as request:
        do_http({"action": "http_request", "method": "GET",
                 "path": "http://tempera-juice:3000/api/Users/24?q=1"},
                "http://127.0.0.1:57842")
    assert request.call_args.args[1] == "http://127.0.0.1:57842/api/Users/24?q=1"


def test_relative_path_keeps_existing_proxy_forwarding():
    response = Mock(status_code=200, content=b"ok", text="ok")
    response.raw.headers = {}
    with patch("tempera.agent.runtime.requests.request", return_value=response) as request:
        do_http({"action": "http_request", "method": "GET", "path": "/api/Users/24"},
                "http://127.0.0.1:3001")
    assert request.call_args.args[1] == "http://127.0.0.1:3001/api/Users/24"


def test_malformed_url_is_action_parse_failure_not_gateway_failure():
    lifecycle = []
    steps = []
    result = run_episode(
        "mission", "http://127.0.0.1:57842", 1,
        adapter=ReferenceAgentAdapter([{
            "action": "http_request", "method": "GET", "path": "http://",
        }]),
        on_lifecycle=lambda *record: lifecycle.append(record),
        on_step=steps.append,
    )
    assert result["reason"] == "action_parse_failed"
    assert result["control_effectiveness"]["attempted_r2_violations"] == 0
    assert steps[0]["error"] == "action_parse_failed"
    assert steps[0]["executed"] is False
    assert steps[0]["observed"] is False
    assert lifecycle[0][0] == "proposed"
    assert lifecycle[0][3]["_forwarding"]["constructed_url"] is None
    assert lifecycle[0][3]["_forwarding"]["parse_error"]


def test_runtime_selection_defaults_to_host():
    assert get_agent_runtime().name == "host"
    assert get_agent_runtime("host").name == "host"
    assert get_agent_runtime("container", attacker_container="attacker").container == "attacker"


def test_runtime_selection_rejects_invalid_mode():
    with pytest.raises(ValueError):
        get_agent_runtime("invalid")


def _docker_runner(argv, **kwargs):
    if argv[1] == "inspect":
        return subprocess.CompletedProcess(argv, 0, "running\n", "")
    return subprocess.CompletedProcess(argv, 0, "out\n", "err\n")


def test_container_exec_captures_output_and_allowlists_environment():
    runtime = ContainerAgentRuntime("attacker", runner=_docker_runner)
    result = runtime.exec(["python", "--version"], env={"TEMPERA_RUN_ID": "run-1", "SECRET": "no"})
    assert result == runtime.exec(["python", "--version"], env={"TEMPERA_RUN_ID": "run-1"})


def test_container_missing_and_stopped_are_controlled():
    def missing(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "No such container")

    def stopped(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "exited\n", "")

    with pytest.raises(ContainerNotFoundError):
        ContainerAgentRuntime(runner=missing).exec(["python", "--version"])
    with pytest.raises(ContainerStoppedError):
        ContainerAgentRuntime(runner=stopped).exec(["python", "--version"])


def test_container_nonzero_agent_exit_is_agent_failure():
    def failed(argv, **kwargs):
        if argv[1] == "inspect":
            return subprocess.CompletedProcess(argv, 0, "running\n", "")
        return subprocess.CompletedProcess(argv, 7, "out", "bad")

    with pytest.raises(AgentProcessError, match="exited 7"):
        ContainerAgentRuntime(runner=failed).exec(["false"])


def test_docker_exec_failure_is_runtime_failure():
    def failed(argv, **kwargs):
        if argv[1] == "inspect":
            return subprocess.CompletedProcess(argv, 0, "running\n", "")
        return subprocess.CompletedProcess(argv, 125, "", "docker failed")

    with pytest.raises(ContainerExecutionError, match="docker exec failed"):
        ContainerAgentRuntime(runner=failed).exec(["python", "--version"])


def test_container_timeout_is_runtime_failure():
    def timed_out(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    with pytest.raises(ContainerExecutionError, match="timed out"):
        ContainerAgentRuntime(runner=timed_out).exec(["python", "--version"])


def test_container_environment_drops_secrets():
    assert ContainerAgentRuntime.environment({
        "TEMPERA_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "secret",
    }) == {"TEMPERA_PROVIDER": "deepseek"}


def test_container_smoke_uses_kali_python3_binary():
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "inspect":
            return subprocess.CompletedProcess(argv, 0, "running\n", "")
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    ContainerAgentRuntime(runner=runner).smoke_test()
    assert ["python3", "--version"] in [call[-2:] for call in calls if call[1] == "exec"]
