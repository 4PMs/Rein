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


def get_evidence(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact, audit-friendly evidence for a Rein verdict."""
    simulation = _simulation(result)
    reward_info = simulation.get("reward_info", {})
    evidence = [{"type": "action", **action} for action in get_actions(simulation)]
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
    return evidence
