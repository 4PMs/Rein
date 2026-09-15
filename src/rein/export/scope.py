"""Text export for product-level autonomy scope recommendations."""

from __future__ import annotations

from typing import Any


def format_recommended_scope(report: dict[str, Any]) -> str:
    """Format a scope report for terminal or Markdown-like output."""
    scope = report.get("recommended_scope", {})
    lines = ["Recommended Autonomy Scope", "", "AUTONOMOUS"]
    autonomous = scope.get("autonomous", [])
    lines.extend(f"[+] {item['condition']}" for item in autonomous)
    if not autonomous:
        lines.append("None")
    lines.extend(["", "HUMAN APPROVAL"])
    approvals = scope.get("human_approval", [])
    if approvals:
        for item in approvals:
            lines.append(f"[!] {item['condition']}")
            lines.append(f"  Reason: {item['reason']}")
    else:
        lines.append("None")
    lines.extend(["", "BLOCKED"])
    blocked = scope.get("blocked", [])
    lines.extend(f"[X] {item['condition']}" for item in blocked)
    if not blocked:
        lines.append("None")
    return "\n".join(lines)
