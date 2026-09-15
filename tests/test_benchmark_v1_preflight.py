import argparse
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "benchmark_v1", ROOT / "scripts" / "archive" / "run_benchmark_v1.py"
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def args(**values):
    base = {"model_a": "a", "model_b": "b", "provider_a": "p", "provider_b": "p",
            "single_model": False}
    return argparse.Namespace(**(base | values))


def test_cases_a_d_and_f_are_explicit_in_design_and_fixtures():
    design = benchmark.load_design()
    assert set(design["design"]["pilot_scenario_ids"]) == {"A-target-boundary", "B-tool-intent-boundary"}
    assert design["scenarios"][0]["primary_categories"] == ["R1"]
    assert "unauthorized" in (benchmark.SCENARIOS / "A-target-boundary" / "prompt.txt").read_text().lower()
    assert "prohibited" in (benchmark.SCENARIOS / "B-tool-intent-boundary" / "prompt.txt").read_text().lower()
    assert "immediately" in (benchmark.SCENARIOS / "D-halt-boundary" / "prompt.txt").read_text().lower()


def test_cases_i_l_preflight_identity_and_go():
    design = benchmark.load_design()
    rows = benchmark.matrix(design, {"internal-model-a": {"model_id": "a", "provider": "p"},
                                     "internal-model-b": {"model_id": "b", "provider": "p"}})
    assert benchmark.preflight(design, rows, args())["status"] == "GO"
    assert benchmark.preflight(design, rows, args(model_b="a"))["status"] == "CONDITIONAL_GO"


def test_single_model_matrix_is_six_pairs_and_twelve_runs():
    design = benchmark.load_design()
    models = {"internal-model-a": {"model_id": "deepseek-chat", "provider": "deepseek"}}
    single = benchmark.matrix(design, models, single_model=True)
    default = benchmark.matrix(design, models)
    report = benchmark.preflight(design, single, args(model_b=None, provider_b=None, single_model=True))
    assert len(single) == 6
    assert len(single) * 2 == 12
    assert len(default) == 12
    assert report["mode"] == "single_model"
    assert report["planned_pairs"] == 6
    assert report["planned_runs"] == 12
    assert report["status"] == "GO"


def test_case_j_fairness_hash_mismatch():
    row = benchmark.matrix(benchmark.load_design(), {"internal-model-a": {"model_id": "a", "provider": "p"},
                                                       "internal-model-b": {"model_id": "b", "provider": "p"}})[0]
    row["arms"][0]["prompt_hash"] = "different"
    assert benchmark.fairness_check(row)[0] is False


def test_command_for_uses_planned_runtime_for_both_arms():
    design = benchmark.load_design()
    row = benchmark.matrix(design, {"internal-model-a": {"model_id": "a", "provider": "p"}}, single_model=True)[0]
    namespace = args(single_model=True, runs_dir=ROOT / "runs")
    commands = [benchmark.command_for(row, arm, namespace) for arm in row["arms"]]
    for command in commands:
        for flag, value in (("--upstream", "http://127.0.0.1:3001"), ("--temperature", "0"),
                            ("--max-steps", "12"), ("--timeout", "20")):
            assert command[command.index(flag) + 1] == value
    assert [item for item in commands[0] if item == "--enforce-policy"] == []
    assert [item for item in commands[1] if item == "--enforce-policy"] == ["--enforce-policy"]


def test_cases_b_c_k_denominators_and_policy_denied():
    off = {"proposed_r2_violations": 1, "classified_proposed_actions_r2": 2,
           "result": {"roe": {"categories": {"R1": {}}}}}
    on = {"proposed_r2_violations": 0, "result": {"control_effectiveness": {"blocked_r2_violations": 0},
                                                     "roe": {"categories": {}}}}
    metrics = benchmark.aggregate_metrics(off, on, "B-tool-intent-boundary")
    assert metrics["intrinsic_compliance_r2_action_level"] == 0.5
    assert metrics["control_dependency_r2"] is None
    assert benchmark.read_run
    assert json.loads((ROOT / "experiments/benchmark-v1/design.json").read_text())["validity"]["policy_denied"]["capability_success"] is False


def test_stage11_valid_matrix_is_ready_and_has_plan_hash(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="ollama", model="qwen", repetitions=1)
    report = benchmark.stage11_preflight(
        design, rows, probes={name: True for name in ("relay", "runtime", "gateway", "target", "reset", "network")},
        output_root=tmp_path,
    )
    assert report["ready"] is True
    assert report["planned_pairs"] == 2
    assert report["planned_runs"] == 4
    assert len(report["benchmark_plan_sha256"]) == 64
    assert rows[0]["scenario_hash"] and rows[0]["policy_hash"]
    assert rows[0]["max_steps"] == design["design"]["runtime"]["max_steps"]
    assert {item["name"] for item in report["checks"]} >= {"repository.commit", "repository.working_tree"}


def test_stage11_missing_scenario_blocks_readiness():
    design = benchmark.load_design()
    report = benchmark.stage11_preflight(design, [], scenario_ids=["missing-scenario"])
    assert report["ready"] is False
    assert any(item["name"] == "scenario.missing-scenario" for item in report["failures"])


def test_stage11_credentials_reset_network_and_artifact_fail_closed(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("x", encoding="utf-8")
    report = benchmark.stage11_preflight(
        design, rows, credentials={},
        probes={"reset": False, "network": False}, output_root=output_file,
    )
    assert report["ready"] is False
    assert {item["name"] for item in report["failures"]} >= {
        rows[0]["pair_id"] + ".credentials",
        "reset", "network", "artifacts.path",
    }


def test_stage11_repetition_seed_pairing_order_and_determinism():
    design = benchmark.load_design()
    kwargs = dict(provider="ollama", model="qwen", repetitions=10, seed_strategy="increment", base_seed=1000)
    first = benchmark.expand_stage11_matrix(design, **kwargs)
    second = benchmark.expand_stage11_matrix(design, **kwargs)
    assert len(first) == 20
    assert all(len(row["arms"]) == 2 for row in first)
    assert all(row["arms"][0]["seed"] == row["arms"][1]["seed"] for row in first)
    assert [row["execution_order"] for row in first[:2]] == [
        ["guardrail_off", "guardrail_on"], ["guardrail_on", "guardrail_off"],
    ]
    assert benchmark.stage11_plan_hash(first) == benchmark.stage11_plan_hash(second)


def test_stage11_unsupported_seed_is_explicit_not_applied():
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    assert rows[0]["seed"]["seed_strategy"] == "unsupported"
    assert rows[0]["seed"]["seed_applied"] is False
    assert rows[0]["seed"]["seed_requested"] is None


def test_stage11_failed_preflight_disallows_execution():
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="ollama", model="qwen", repetitions=1)
    report = benchmark.stage11_preflight(design, rows, probes={"reset": False})
    assert report["execution_allowed"] is False


def test_stage11_rows_are_executable_with_container_runtime():
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    command = benchmark.command_for(rows[0], rows[0]["arms"][0], args(single_model=True, runs_dir=ROOT / "runs"))
    assert rows[0]["scenario"]["id"] == rows[0]["scenario_id"]
    assert "--agent-runtime" in command and command[command.index("--agent-runtime") + 1] == "container"


def test_live_preflight_separates_presence_from_rejected_auth(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    report = benchmark.stage11_preflight(
        design, rows, credentials={"DEEPSEEK_API_KEY": "redacted"},
        probes={"provider_auth": "rejected", "relay": True, "runtime": True,
                "gateway": True, "target": True, "reset": True, "network": True},
        output_root=tmp_path, live=True,
    )
    assert report["logical_ready"] is True
    assert report["live_ready"] is False
    assert report["execution_allowed"] is False
    assert any(item["detail"] == "provider_auth_status=rejected" for item in report["failures"])
    assert all("redacted" not in json.dumps(item) for item in report["checks"])


def test_live_preflight_blocks_unresolved_critical_checks(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    report = benchmark.stage11_preflight(
        design, rows, probes={"provider_auth": "valid", "relay": True, "runtime": True},
        output_root=tmp_path, live=True,
    )
    assert report["execution_allowed"] is False
    assert {item["name"] for item in report["failures"]} >= {"gateway", "target", "reset", "network"}


def test_live_preflight_all_checks_passes(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    report = benchmark.stage11_preflight(
        design, rows, credentials={"DEEPSEEK_API_KEY": "redacted"},
        probes={"provider_auth": "valid", "relay": True, "runtime": True,
                "gateway": True, "target": True, "reset": True, "network": True},
        output_root=tmp_path, live=True,
    )
    assert report["live_ready"] is True
    assert report["execution_allowed"] is True


def test_provider_auth_probe_reuses_relay_and_redacts_credentials():
    response = type("Response", (), {"status_code": 401})()
    with patch.object(benchmark.requests, "post", return_value=response) as post:
        assert benchmark._provider_auth_probe("deepseek", "deepseek-chat", endpoint="http://relay") == "rejected"
    kwargs = post.call_args.kwargs
    assert "Authorization" not in kwargs["headers"]
    assert "DEEPSEEK_API_KEY" not in json.dumps(kwargs)
    assert "Reply with OK only." in kwargs["json"]["messages"][0]["content"]


def test_live_runner_validator_wiring_reuses_existing_topology_and_reset_validators(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    fake_adapter = type("Adapter", (), {
        "verify": lambda self: {"checks": {"application_health": "pass"}},
        "reset": lambda self: {"performed": True},
    })
    with patch.object(benchmark, "ForcedGatewayTopology") as topology, \
                patch("environments.juice_shop.adapter.JuiceShopAdapter", fake_adapter):
        result = benchmark._live_runner_validators(rows, args(runs_dir=tmp_path))
    topology.return_value.ensure.assert_called_once_with(rows[0]["arms"][0]["run_id"])
    topology.return_value.validate_current_arm.assert_called_once_with(rows[0]["arms"][0]["run_id"])
    assert {name: value["status"] for name, value in result.items()} == {
        "gateway": "pass", "network": "pass", "target": "pass", "reset": "pass",
    }


def test_live_artifact_path_mismatch_is_critical(tmp_path):
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    report = benchmark.stage11_preflight(
        design, rows,
        probes={"provider_auth": "valid", "relay": True, "runtime": True,
                "gateway": True, "target": True, "reset": True, "network": True,
                "artifacts.path": {"status": "fail", "detail": "current-arm artifact path mismatch"}},
        output_root=tmp_path, live=True,
    )
    assert report["execution_allowed"] is False
    assert any(item["name"] == "artifacts.path" for item in report["failures"])


def test_live_never_authorizes_unresolved_checks():
    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(design, provider="deepseek", model="deepseek-chat", repetitions=1)
    report = benchmark.stage11_preflight(design, rows, live=True)
    assert report["execution_allowed"] is False
    assert {item["name"] for item in report["failures"]} >= {
        "relay", "runtime", "gateway", "target", "reset", "network",
    }


def test_case_k_valid_relay_config_does_not_authorize_rejected_provider(tmp_path, monkeypatch):
    for name in ("TEMPERA_PROVIDER", "TEMPERA_MODEL"):
        monkeypatch.delenv(name, raising=False)
    topology = benchmark.ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    assert topology._model_relay_config()[1:3] == ("deepseek", "deepseek-chat")

    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(
        design, provider="deepseek", model="deepseek-chat", repetitions=1,
    )
    report = benchmark.stage11_preflight(
        design, rows, credentials={"DEEPSEEK_API_KEY": "redacted"},
        probes={"provider_auth": "rejected", "relay": True, "runtime": True,
                "gateway": True, "target": True, "reset": True, "network": True},
        output_root=tmp_path, live=True,
    )
    assert report["logical_ready"] is True
    assert report["live_ready"] is False
    assert report["execution_allowed"] is False
    assert report["planned_runs"] == 4


def test_case_k_synthetic_provider_auth_pass_with_valid_relay_config(tmp_path, monkeypatch):
    for name in ("TEMPERA_PROVIDER", "TEMPERA_MODEL"):
        monkeypatch.delenv(name, raising=False)
    topology = benchmark.ForcedGatewayTopology(
        model_relay_provider="deepseek", model_relay_model="deepseek-chat",
        model_relay_upstream="https://api.deepseek.com",
        model_relay_allowed_endpoints={"api.deepseek.com"},
    )
    assert topology._model_relay_config()[1:3] == ("deepseek", "deepseek-chat")

    design = benchmark.load_design()
    rows = benchmark.expand_stage11_matrix(
        design, provider="deepseek", model="deepseek-chat", repetitions=1,
    )
    report = benchmark.stage11_preflight(
        design, rows, credentials={"DEEPSEEK_API_KEY": "synthetic-redacted"},
        probes={"provider_auth": "valid", "relay": True, "runtime": True,
                "gateway": True, "target": True, "reset": True, "network": True},
        output_root=tmp_path, live=True,
    )
    assert report["logical_ready"] is True
    assert report["live_ready"] is True
    assert report["execution_allowed"] is True
    assert report["planned_runs"] == 4
