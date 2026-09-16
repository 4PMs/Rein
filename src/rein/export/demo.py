"""Demo result formatting shared by the Rein CLI."""

from __future__ import annotations

from .events import evidence_to_events


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


def build_demo(
    scenario_id: str,
    task: str,
    condition: str,
    verdict: dict,
    evidence: list[dict],
) -> dict:
    """Structured demo payload for the static Rein console (rein.json)."""
    return {
        "scenario": scenario_id,
        "task": task,
        "condition": condition,
        "capability": verdict["capability"],
        "restraint": verdict["restraint"],
        "boundary": verdict["boundary"],
        "restraint_violation": verdict["restraint"] == "fail",
        "evidence": evidence,
        "events": evidence_to_events(evidence),
    }
