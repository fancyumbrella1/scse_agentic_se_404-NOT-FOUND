"""Review measured simulation failures and recommend a revision."""
import json
import os
from ollama import chat

MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
KEYS = {"issue", "likely_cause", "recommendation", "needs_revision"}


def validate_review(data):
    if not isinstance(data, dict) or set(data) != KEYS or type(data["needs_revision"]) is not bool:
        raise ValueError("Review must contain the required JSON fields")
    if not all(isinstance(data[key], str) for key in KEYS - {"needs_revision"}):
        raise ValueError("Review descriptions must be strings")
    return data


def run_reviewer(report):
    failures = [item for item in report["results"] if not item["passed"]]
    measured = {"needs_revision": bool(failures), "failed_scenarios": report["failed_scenarios"],
                "failures": failures[:12]}
    prompt = "Return only JSON with string issue, likely_cause, recommendation, and boolean needs_revision. Base it on measured failures."
    try:
        raw = chat(model=MODEL, format="json", think=False,
                   messages=[{"role": "system", "content": prompt},
                             {"role": "user", "content": json.dumps(measured)}]).message.content
        review = validate_review(json.loads(raw))
        review["needs_revision"] = measured["needs_revision"]
        return review
    except (ValueError, json.JSONDecodeError):
        return validate_review({"issue": f"{len(failures)} simulation failures" if failures else "No simulation failures",
                                "likely_cause": "Navigation decision mismatch" if failures else "None observed",
                                "recommendation": "Correct failed decision states" if failures else "No simulation change required",
                                "needs_revision": bool(failures)})
