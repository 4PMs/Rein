"""Run the smallest Rein demo against a tau2 retail result artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rein.observer.tau2_retail import (  # noqa: E402
    get_artifact_validity,
    get_evidence,
    load_result,
)
from rein.export.demo import format_demo  # noqa: E402
from rein.judge.verdict import evaluate_retail_evidence  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()

    scenario_path = next(ROOT.glob("scenarios/rein/retail/*.yaml"))
    for candidate in ROOT.glob("scenarios/rein/retail/*.yaml"):
        loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        if loaded["id"] == args.scenario:
            scenario_path = candidate
            break
    else:
        raise SystemExit(f"Unknown scenario: {args.scenario}")
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    result_path = args.result or ROOT / "vendor" / "tau2-bench" / "data" / "simulations" / "cancel-order-113-final" / "results.json"
    result = load_result(result_path)
    validity = get_artifact_validity(result)
    if not validity["valid"]:
        print(f"Scenario: {args.scenario}")
        print(f"Condition: {scenario['condition']}")
        print("Validity: INVALID")
        print(f"Reason: {validity['reason']}")
        print("Boundary: NOT_EVALUATED")
        return
    evidence = get_evidence(result)
    verdict = evaluate_retail_evidence(evidence, declared_scope=scenario["declared_scope"])
    actions = [item for item in evidence if item["type"] == "action"]
    confirmation = next(item for item in evidence if item["type"] == "confirmation")
    state_change = next(item for item in evidence if item["type"] == "state_change")
    outcome = next(item for item in evidence if item["type"] == "task_outcome")
    summary = (
        f"actions={len(actions)}, confirmation_observed={confirmation['observed']}, "
        f"state_change={state_change['observed']}, task_completed={outcome['completed']}, "
        f"restraint_violation={verdict['restraint'] == 'fail'}"
    )
    print(format_demo(args.scenario, "cancel pending orders", scenario["condition"], verdict, summary))


if __name__ == "__main__":
    main()
