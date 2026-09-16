"""Canonical execution-event projection for UI and report consumers."""

from __future__ import annotations

from typing import Any, Iterable


def _detail(item: dict[str, Any]) -> str:
    kind = item.get("type")
    if kind == "action":
        order_id = (item.get("arguments") or {}).get("order_id")
        target = f" · {order_id}" if order_id else ""
        mode = "state-changing write" if item.get("tool_type") == "write" else "read-only"
        result = "matched" if item.get("matched", True) else "expected result mismatch"
        return f"{mode}{target} · {result}"
    if kind == "confirmation":
        return "confirmation observed before action" if item.get("observed") else "required confirmation not observed"
    if kind == "state_change":
        actions = ", ".join(item.get("actions") or []) or "none"
        return f"state change {'observed' if item.get('observed') else 'not observed'} · {actions}"
    if kind == "nl_assertion":
        return item.get("justification") or ("assertion met" if item.get("met") else "assertion not met")
    if kind == "db_check":
        return f"database match {'confirmed' if item.get('db_match') else 'not confirmed'}"
    if kind == "task_outcome":
        return "task completed" if item.get("completed") else "task not completed"
    return kind or "evidence recorded"


def evidence_to_events(evidence: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert legacy evidence records into the shared execution-event model."""
    events = []
    for seq, item in enumerate(evidence, 1):
        kind = item.get("type")
        if kind == "action":
            title = item.get("name") or "Tool action"
            status = "allowed" if item.get("matched", True) else "violation"
        elif kind == "confirmation":
            title = "User confirmation"
            status = "allowed" if item.get("observed") else "review"
        elif kind == "state_change":
            title = "State change"
            status = "allowed" if item.get("observed") else "blocked"
        elif kind == "task_outcome":
            title = "Task outcome"
            status = "allowed" if item.get("completed") else "blocked"
        else:
            title = {"nl_assertion": "Goal evaluation", "db_check": "Database state check"}.get(kind, kind or "Evidence recorded")
            status = "allowed" if item.get("met", item.get("db_match", True)) else "violation"
        events.append({"seq": seq, "type": kind or "observation", "title": title, "detail": _detail(item), "status": status})
    return events
