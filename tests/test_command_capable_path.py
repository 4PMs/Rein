import json
import shutil
import subprocess
import sys
from unittest.mock import Mock, patch

from tempera.agent.runtime import run_episode
from tempera.agent.runtime import parse_action
from tempera.agent.tool_runner import available_tools, run
from tempera.agents.reference import ReferenceAgentAdapter
from tempera.agents.internal import InternalLLMAgentAdapter


def test_run_tool_action_dispatches_argv_and_records_process_provenance():
    invocations = []
    steps = []
    executed = []

    def executor(argv, timeout):
        executed.append((argv, timeout))
        return {
            "status": "completed", "pid": 123, "executable": "/usr/bin/curl",
            "exit_code": 0, "stdout_preview": "ok", "stderr_preview": "",
        }

    result = run_episode(
        "mission", "http://gateway", 1,
        adapter=ReferenceAgentAdapter([{
            "action": "run_tool", "argv": ["curl", "--version"],
        }]),
        tool_executor=executor, on_invocation=invocations.append, on_step=steps.append,
        run_id="run-h3", runtime="container",
    )

    assert result["reason"] == "max_steps"
    assert executed == [(["curl", "--version"], 60)]
    assert any(item["stage"] == "execution_finished" for item in invocations)
    finished = [item for item in invocations if item["stage"] == "execution_finished"][-1]
    assert finished["action_id"] == "action-1"
    assert finished["seq"] == 0
    assert finished["process"]["executable"] == "/usr/bin/curl"
    assert finished["process"]["exit_code"] == 0
    assert steps[0]["argv"] == ["curl", "--version"]
    assert steps[0]["process"]["policy_decision"]["decision"] == "allow"


def test_parse_action_accepts_explicit_run_tool_type_variant():
    assert parse_action('{"type":"run_tool","argv":["curl","--version"]}') == {
        "type": "run_tool", "argv": ["curl", "--version"], "action": "run_tool",
    }


def test_internal_agent_contract_exposes_only_supplied_tools():
    calls = []
    adapter = InternalLLMAgentAdapter(
        mission="m", provider="deepseek", model="deepseek-chat", temperature=0,
        seed=None, available_tools=["curl", "python3"],
        call=lambda messages, **kwargs: calls.append(messages) or '{"action":"done"}',
        parse=json.loads,
    )
    adapter.prepare(None)
    assert "curl, python3" in adapter._messages[0]["content"]
    assert "sqlmap" not in adapter._messages[0]["content"]


def test_tool_runner_executes_real_process_and_reports_absolute_executable(tmp_path, monkeypatch):
    if sys.platform == "win32":
        # A copied python.exe cannot find its adjacent python DLLs from a
        # temporary directory. Keep the fixture on the real interpreter while
        # still exercising the isolated command-path lookup.
        monkeypatch.setattr(
            "tempera.agent.tool_runner.shutil.which",
            lambda name, path=None: sys.executable if name == "python3" else None,
        )
    else:
        tool = tmp_path / "python3"
        shutil.copyfile(sys.executable, tool)
    monkeypatch.setenv("TEMPERA_AGENT_COMMAND_PATH", str(tmp_path))
    result = run(["python3", "-c", "print('h3')"], timeout=10)
    assert result["status"] == "completed"
    assert result["pid"]
    assert result["executable"]
    assert result["exit_code"] == 0
    assert "h3" in result["stdout_preview"]


def test_tool_availability_uses_path_lookup(monkeypatch):
    monkeypatch.setattr("tempera.agent.tool_runner.shutil.which", lambda name, path=None: "/bin/" + name if name in {"curl", "sh"} else None)
    monkeypatch.setenv("TEMPERA_AGENT_COMMAND_PATH", "/opt/tempera/agent-bin")
    assert available_tools(("curl", "sqlmap", "sh")) == ["curl", "sh"]


def test_profile_materialization_defines_availability_and_keeps_native_actions_separate(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPERA_AGENT_COMMAND_PATH", str(tmp_path))
    monkeypatch.setattr("tempera.agent.tool_runner.shutil.which",
                        lambda name, path=None: (
                            str(tmp_path / name) if path == str(tmp_path) and name in {"python3", "bash"}
                            else (None if path == str(tmp_path) else "/usr/bin/" + name)
                        ))
    monkeypatch.setattr("pathlib.Path.symlink_to", lambda self, source: self.write_text(source))
    from tempera.agent.tool_runner import materialize_profile

    assert materialize_profile({"command_tools": ["python3", "bash"],
                                "native_actions": ["http_request", "done"]},
                               destination=tmp_path) == ["python3", "bash"]
    assert sorted(item.name for item in tmp_path.iterdir()) == ["bash", "python3"]
    assert available_tools(("python3", "bash", "curl")) == ["python3", "bash"]


def test_run_rejects_command_outside_agent_execution_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPERA_AGENT_COMMAND_PATH", str(tmp_path))
    result = run(["bash", "-c", "true"], timeout=1)
    assert result["status"] == "spawn_failed"
    assert result["error"] == "command unavailable in this variant"


def test_native_http_remains_available_with_empty_command_profile():
    response = Mock(status_code=200, content=b"ok", text="ok")
    response.raw.headers = {}
    with patch("tempera.agent.runtime.requests.request", return_value=response):
        result = run_episode(
            "mission", "http://gateway", 1,
            adapter=ReferenceAgentAdapter([{
                "action": "http_request", "method": "GET", "path": "/",
            }]),
            available_tools=[],
        )
    assert result["reason"] == "max_steps"


def test_unavailable_command_is_recorded_without_becoming_r2_violation():
    lifecycle = []
    steps = []

    def executor(argv, timeout):
        return {"status": "spawn_failed", "error": "command unavailable in this variant",
                "pid": None, "executable": None}

    result = run_episode(
        "mission", "http://gateway", 1,
        adapter=ReferenceAgentAdapter([{
            "action": "run_tool", "argv": ["curl", "--version"],
        }]),
        available_tools=[], tool_executor=executor,
        on_lifecycle=lambda *args: lifecycle.append(args), on_step=steps.append,
    )
    assert result["reason"] == "max_steps"
    assert steps[0]["event_type"] == "tool_unavailable"
    assert [item[0] for item in lifecycle] == ["proposed", "policy_decision", "executed", "observed"]
