"""Exhaustive six-flag simulation of the generated navigation decision."""
import importlib.util
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAGS = ("goal_ahead", "goal_on_left", "goal_on_right", "front_blocked", "left_blocked", "right_blocked")
ACTIONS = ("FORWARD", "LEFT", "RIGHT")


def expected_move(state):
    for action, goal, blocked in zip(ACTIONS, FLAGS[:3], FLAGS[3:]):
        if state[goal] and not state[blocked]:
            return action
    for action, blocked in zip(ACTIONS, FLAGS[3:]):
        if not state[blocked]:
            return action
    return "STOP"


def load_navigation(path=ROOT / "generated" / "navigation_logic.py"):
    spec = importlib.util.spec_from_file_location("navigation_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide_next_move


def run_simulation(path=ROOT / "generated" / "navigation_logic.py"):
    decide = load_navigation(path)
    results = []
    for values in itertools.product((False, True), repeat=6):
        state = dict(zip(FLAGS, values))
        expected = expected_move(state)
        try:
            actual = decide(state)
            error = None
        except Exception as exc:
            actual, error = None, str(exc)
        results.append({"state": state, "expected": expected, "actual": actual,
                        "passed": actual == expected, "error": error})
    passed = sum(item["passed"] for item in results)
    return {"total_scenarios": len(results), "passed_scenarios": passed,
            "failed_scenarios": len(results) - passed,
            "success_rate": passed / len(results), "results": results}


if __name__ == "__main__":
    report = run_simulation()
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "simulation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{report['passed_scenarios']}/{report['total_scenarios']} scenarios passed")
