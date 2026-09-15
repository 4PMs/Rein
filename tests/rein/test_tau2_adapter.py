import json

from rein.adapters.tau2_retail import get_actions, get_evidence, get_final_state, get_reward, load_result


def test_tau2_retail_adapter_reads_baseline(tmp_path):
    payload = {"simulations": [{"task_id": "113", "reward_info": {"reward": 1.0, "db_check": {"db_match": True, "db_reward": 1.0}, "action_checks": [{"action": {"name": "cancel_pending_order", "arguments": {"order_id": "#1"}}, "action_match": True, "tool_type": "write"}], "nl_assertions": [{"nl_assertion": "cancel all", "met": True}]}}]}
    path = tmp_path / "results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = load_result(path)
    assert get_reward(result) == 1.0
    assert get_actions(result)[0]["name"] == "cancel_pending_order"
    assert get_final_state(result)["db_match"] is True
    assert len(get_evidence(result)) == 3
