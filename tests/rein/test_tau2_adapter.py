import json

from rein.adapters.tau2_retail import (
    get_actions,
    get_artifact_validity,
    get_evidence,
    get_final_state,
    get_reward,
    load_result,
)


def test_tau2_retail_adapter_reads_baseline(tmp_path):
    payload = {
        "simulations": [
            {
                "task_id": "113",
                "messages": [
                    {"role": "assistant", "content": "Shall I proceed? (yes/no)"},
                    {"role": "user", "content": "Yes, please proceed."},
                    {
                        "role": "assistant",
                        "tool_calls": [{"name": "cancel_pending_order"}],
                    },
                ],
                "reward_info": {
                    "reward": 1.0,
                    "db_check": {"db_match": True, "db_reward": 1.0},
                    "action_checks": [
                        {
                            "action": {
                                "name": "cancel_pending_order",
                                "arguments": {"order_id": "#1"},
                            },
                            "action_match": True,
                            "tool_type": "write",
                        }
                    ],
                    "nl_assertions": [{"nl_assertion": "cancel all", "met": True}],
                },
            }
        ]
    }
    path = tmp_path / "results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = load_result(path)
    assert get_reward(result) == 1.0
    assert get_actions(result)[0]["name"] == "cancel_pending_order"
    assert get_final_state(result)["db_match"] is True
    evidence = get_evidence(result)
    assert next(item for item in evidence if item["type"] == "confirmation")["observed"] is True
    assert get_artifact_validity(result) == {"valid": True, "reason": ""}


def test_missing_confirmation_evidence_is_false(tmp_path):
    payload = {
        "simulations": [
            {
                "messages": [
                    {"role": "assistant", "tool_calls": [{"name": "cancel_pending_order"}]}
                ],
                "reward_info": {
                    "reward": 1.0,
                    "action_checks": [
                        {"action": {"name": "cancel_pending_order"}, "tool_type": "write"}
                    ],
                },
            }
        ]
    }
    path = tmp_path / "missing-confirmation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    evidence = get_evidence(load_result(path))
    assert next(item for item in evidence if item["type"] == "confirmation")["observed"] is False


def test_infrastructure_error_artifact_is_invalid(tmp_path):
    path = tmp_path / "infrastructure-error.json"
    path.write_text(
        json.dumps(
            {
                "simulations": [
                    {
                        "termination_reason": "infrastructure_error",
                        "reward_info": None,
                        "info": {"error": "AuthenticationError"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert get_artifact_validity(load_result(path)) == {
        "valid": False,
        "reason": "infrastructure_error",
    }
