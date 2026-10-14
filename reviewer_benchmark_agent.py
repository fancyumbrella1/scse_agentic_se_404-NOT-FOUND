"""Review the measured IR-SIM benchmark, anchoring booleans to measurements."""
import json
import os
from ollama import chat

MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
KEYS = {"issue", "likely_cause", "recommendation", "safety_passed",
        "goal_completion_passed", "efficiency_passed", "needs_revision"}
BOOLEAN_KEYS = {"safety_passed", "goal_completion_passed", "efficiency_passed", "needs_revision"}


def validate_benchmark_review(data):
    if not isinstance(data, dict) or set(data) != KEYS:
        raise ValueError("Benchmark review has the wrong schema")
    if any(type(data[key]) is not bool for key in BOOLEAN_KEYS):
        raise ValueError("Pass/fail fields must be booleans")
    if any(not isinstance(data[key], str) for key in KEYS - BOOLEAN_KEYS):
        raise ValueError("Descriptions must be strings")
    return data


def deterministic_review(report):
    results = report.get("results", [])
    safety = not any(item.get("collision_or_done") and not item.get("reached_goal") for item in results)
    goal = report.get("success_rate", 0) == 1.0
    efficiency = report.get("efficiency_rate", 0) == 1.0 and report.get("inefficient_success_worlds", 0) == 0
    issue = "Unsafe benchmark behavior detected" if not safety else (
        "Goal completion failure" if not goal else (
            "Successful but inefficient navigation" if not efficiency else "No measured benchmark failures"))
    return validate_benchmark_review({"issue": issue, "likely_cause": "See individual world results",
                                      "recommendation": "Inspect failed world histories and revise navigation logic" if not all((safety, goal, efficiency)) else "No revision needed",
                                      "safety_passed": safety, "goal_completion_passed": goal,
                                      "efficiency_passed": efficiency,
                                      "needs_revision": not all((safety, goal, efficiency))})


def run_benchmark_reviewer(report):
    measured = deterministic_review(report)
    prompt = "Return only JSON with keys issue, likely_cause, recommendation, safety_passed, goal_completion_passed, efficiency_passed, needs_revision. Explain specific world failures and keep all boolean values equal to the measured review."
    try:
        raw = chat(model=MODEL, format="json", think=False,
                   messages=[{"role": "system", "content": prompt},
                             {"role": "user", "content": json.dumps({"benchmark": report, "measured": measured})}]).message.content
        review = validate_benchmark_review(json.loads(raw))
        review.update({key: measured[key] for key in BOOLEAN_KEYS})
        return review
    except (ValueError, json.JSONDecodeError):
        return measured
