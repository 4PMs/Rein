"""Thin adapter for tau2-bench retail result artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_result(path: str | Path) -> dict[str, Any]:
    """Load one tau2 result file and return its first simulation record."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    simulations = payload.get("simulations", [])
    if not simulations:
        raise ValueError(f"No simulations found in {path}")
    return simulations[0]


def _simulation(result: dict[str, Any]) -> dict[str, Any]:
    return result.get("simulations", [result])[0] if "simulations" in result else result


def get_reward(result: dict[str, Any]) -> float:
    return float(_simulation(result).get("reward_info", {}).get("reward", 0.0))


def get_actions(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized agent actions from tau2 action checks."""
    checks = _simulation(result).get("reward_info", {}).get("action_checks") or []
    return [
        {
            "name": (action := check.get("action", {})).get("name"),
            "arguments": action.get("arguments", {}),
            "requestor": action.get("requestor"),
            "matched": bool(check.get("action_match", False)),
            "tool_type": check.get("tool_type"),
        }
        for check in checks
    ]


def get_final_state(result: dict[str, Any]) -> dict[str, Any]:
    """Expose final-state signals tau2 records without inventing state."""
    simulation = _simulation(result)
    db_check = simulation.get("reward_info", {}).get("db_check") or {}
    return {
        "db_match": bool(db_check.get("db_match", False)),
        "db_reward": float(db_check.get("db_reward", 0.0)),
        "termination_reason": simulation.get("termination_reason"),
    }


def get_artifact_validity(result: dict[str, Any]) -> dict[str, str | bool]:
    """Classify whether a tau2 simulation is safe to score."""
    simulation = _simulation(result)
    if simulation.get("termination_reason") == "infrastructure_error":
        return {"valid": False, "reason": "infrastructure_error"}
    if (simulation.get("info") or {}).get("error"):
        return {"valid": False, "reason": "result_contains_error"}
    if not isinstance(simulation.get("reward_info"), dict):
        return {"valid": False, "reason": "missing_reward_info"}
    return {"valid": True, "reason": ""}


def get_confirmation_evidence(result: dict[str, Any]) -> dict[str, Any]:
    """Detect an explicit affirmative user confirmation before a write action."""
    messages = _simulation(result).get("messages") or []
    write_indexes = [
        index
        for index, message in enumerate(messages)
        if message.get("role") == "assistant"
        and any(call.get("name") == "cancel_pending_order" for call in message.get("tool_calls") or [])
    ]
    first_write = min(write_indexes) if write_indexes else len(messages)
    confirmations = [
        message.get("content", "")
        for message in messages[:first_write]
        if message.get("role") == "user"
        and message.get("content", "").strip().lower() in {"yes", "yes, please proceed.", "proceed"}
    ]
    return {
        "type": "confirmation",
        "required": True,
        "observed": bool(confirmations),
        "responses": confirmations,
    }


def get_evidence(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact, audit-friendly evidence for a Rein verdict."""
    simulation = _simulation(result)
    reward_info = simulation.get("reward_info", {})
    actions = get_actions(simulation)
    evidence = [{"type": "action", **action} for action in actions]
    evidence.append(get_confirmation_evidence(simulation))
    evidence.append(
        {
            "type": "state_change",
            "observed": any(action["tool_type"] == "write" for action in actions),
            "actions": [action["name"] for action in actions if action["tool_type"] == "write"],
        }
    )
    evidence.extend(
        {
            "type": "nl_assertion",
            "assertion": assertion.get("nl_assertion"),
            "met": bool(assertion.get("met", False)),
            "justification": assertion.get("justification"),
        }
        for assertion in reward_info.get("nl_assertions") or []
    )
    evidence.append({"type": "db_check", **get_final_state(simulation)})
    evidence.append(
        {
            "type": "task_outcome",
            "reward": get_reward(simulation),
            "completed": get_reward(simulation) >= 1.0,
        }
    )
    return evidence
