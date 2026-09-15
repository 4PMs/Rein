"""Demo result formatting shared by the Rein CLI."""

from __future__ import annotations


def format_demo(
    scenario_id: str,
    task: str,
    condition: str,
    verdict: dict,
    evidence_summary: str = "",
) -> str:
    return "\n".join(
        [
            f"Scenario: {scenario_id}",
            f"Task: {task}",
            f"Condition: {condition}",
            "",
            f"Capability: {verdict['capability'].upper()}",
            f"Restraint: {verdict['restraint'].upper()}",
            f"Boundary: {verdict['boundary'].upper()}",
            "",
            f"Evidence summary: {evidence_summary}",
        ]
    )
