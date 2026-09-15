"""Demo result formatting shared by the Rein CLI."""

from __future__ import annotations


def format_demo(scenario_id: str, task: str, condition: str, verdict: dict) -> str:
    return "\n".join(
        [
            scenario_id,
            f"Task: {task}",
            f"Condition: {condition}",
            "",
            f"Capability: {verdict['capability'].upper()}",
            f"Restraint: {verdict['restraint'].upper()}",
            f"Boundary: {verdict['boundary'].upper()}",
        ]
    )
