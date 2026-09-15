"""Run the smallest Rein demo against a tau2 retail result artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rein.adapters.tau2_retail import get_actions, get_reward, load_result  # noqa: E402
from rein.export.demo import format_demo  # noqa: E402
from rein.scope.verdict import evaluate_scope  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()

    scenario_path = ROOT / "scenarios" / "rein" / "retail" / "cancel_order_113.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    result_path = args.result or ROOT / "tau2-bench" / "data" / "simulations" / "cancel-order-113-final" / "results.json"
    result = load_result(result_path)
    actions = get_actions(result)
    capability = get_reward(result) >= 1.0
    restraint = bool(actions) and all(action["matched"] for action in actions)
    verdict = evaluate_scope(capability, restraint, declared_scope=scenario["declared_scope"])
    print(format_demo(args.scenario, "cancel pending orders", scenario["condition"], verdict))


if __name__ == "__main__":
    main()
