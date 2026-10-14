"""Run the provided IR-SIM harness against all four course worlds."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WORLDS = [ROOT / "irsim_worlds" / f"world_{name}.yaml" for name in ("easy", "medium", "hard", "custom")]


def run_world(world):
    env = dict(os.environ, MPLBACKEND="Agg")
    completed = subprocess.run([sys.executable, "test_irsim_with_agent.py", str(world)],
                               cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    output = completed.stdout + "\n" + completed.stderr
    marker = "IR-SIM report:"
    if completed.returncode != 0 or marker not in output:
        return {"world": world.name, "reached_goal": False, "efficiency_passed": False,
                "steps_taken": 0, "collision_or_done": False, "error": output[-2000:]}
    report_line = output.split(marker, 1)[1].strip().splitlines()[0]
    report = ast.literal_eval(report_line)
    if not isinstance(report, dict):
        raise ValueError("IR-SIM returned no report")
    report["world"] = world.name
    return report


def run_benchmark():
    results = [run_world(world) for world in WORLDS]
    total = len(results)
    reached = sum(bool(result.get("reached_goal")) for result in results)
    efficient = sum(bool(result.get("efficiency_passed")) for result in results)
    report = {"total_worlds": total, "goals_reached": reached,
              "success_rate": reached / total,
              "efficient_worlds": efficient,
              "inefficient_success_worlds": reached - efficient,
              "failed_worlds": total - reached,
              "efficiency_rate": efficient / total,
              "average_steps_taken": sum(result.get("steps_taken", 0) for result in results) / total,
              "results": results}
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "irsim_benchmark_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2))
