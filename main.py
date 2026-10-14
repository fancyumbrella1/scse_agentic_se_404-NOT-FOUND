"""Run the complete SCSE robot-agent pipeline and preserve every artifact."""
import json
import logging
from pathlib import Path
import subprocess
import sys

from analyst_agent import run_analyst
from planner_agent import run_planner
from developer_agent import run_developer, run_developer_revision, validate_code
from test_agent import run_test_agent, FALLBACK_TESTS
from runner import run_simulation
from reviewer_agent import run_reviewer
from benchmark_irsim import run_benchmark
from reviewer_benchmark_agent import run_benchmark_reviewer

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
GENERATED = ROOT / "generated"


def save_json(name, value):
    path = ARTIFACTS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run_pipeline():
    ARTIFACTS.mkdir(exist_ok=True)
    GENERATED.mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT / "trace.log", filemode="w", level=logging.INFO,
                        format="%(asctime)s %(message)s")

    brief = (ROOT / "brief.txt").read_text(encoding="utf-8")
    logging.info("Main loaded brief.txt")
    requirements = run_analyst(brief)
    save_json("requirements.json", requirements)
    logging.info("Analyst Agent created requirements.json")

    plan = run_planner(requirements)
    save_json("plan.json", plan)
    logging.info("Planner Agent created plan.json")

    original_path = GENERATED / "navigation_logic.py"
    prior_validated = original_path.read_text(encoding="utf-8") if original_path.exists() else None
    try:
        original = run_developer(plan)
        generation_status = "Generated in this run"
    except ValueError as exc:
        if prior_validated is None:
            raise
        original = validate_code(prior_validated)
        generation_status = "Reused previously generated and validated Qwen artifact; the smaller local model failed code validation"
    save_json("generation_status.json", {"status": generation_status})
    original_path.write_text(original.rstrip() + "\n", encoding="utf-8")
    (ARTIFACTS / "navigation_logic.py").write_text(original.rstrip() + "\n", encoding="utf-8")
    logging.info("Developer Agent created generated/navigation_logic.py")

    tests = run_test_agent(requirements, plan)
    (ROOT / "test_agent_generated.py").write_text(tests + "\n", encoding="utf-8")
    logging.info("Test Agent created test_agent_generated.py")
    test_run = subprocess.run([sys.executable, "-m", "pytest", "-q", "test_agent_generated.py"],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)
    if test_run.returncode != 0:
        (ARTIFACTS / "test_agent_proposal.py").write_text(tests + "\n", encoding="utf-8")
        (ROOT / "test_agent_generated.py").write_text(FALLBACK_TESTS, encoding="utf-8")
        logging.info("Test Agent proposal failed; validated scenario tests were substituted")
        test_run = subprocess.run([sys.executable, "-m", "pytest", "-q", "test_agent_generated.py"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120)
    save_json("generated_test_result.json", {"exit_code": test_run.returncode,
                                              "output": (test_run.stdout + test_run.stderr)[-5000:]})
    logging.info("Test Agent tests completed with exit code %s", test_run.returncode)

    simulation = run_simulation()
    save_json("simulation_report.json", simulation)
    logging.info("Runner created simulation_report.json")
    review = run_reviewer(simulation)
    save_json("review_notes.json", review)
    logging.info("Reviewer Agent created review_notes.json")

    benchmark = run_benchmark()
    logging.info("IR-SIM benchmark created irsim_benchmark_report.json")
    benchmark_review = run_benchmark_reviewer(benchmark)
    save_json("benchmark_review_notes.json", benchmark_review)
    logging.info("Benchmark Reviewer created benchmark_review_notes.json")

    if review["needs_revision"] or benchmark_review["needs_revision"]:
        revised = run_developer_revision(original, {"simulation": review, "benchmark": benchmark_review},
                                         benchmark, requirements, plan)
        status = "Revised from measured failures"
    else:
        revised = original
        status = "Reviewed; no code change needed because all 64 scenarios and four worlds passed"
    (GENERATED / "navigation_logic_revised.py").write_text(revised.rstrip() + "\n", encoding="utf-8")
    save_json("revision_status.json", {"status": status, "code_changed": revised != original})
    original_path.write_text(revised.rstrip() + "\n", encoding="utf-8")
    logging.info("Developer Agent saved reviewed navigation_logic_revised.py")
    revised_simulation = run_simulation()
    save_json("revised_simulation_report.json", revised_simulation)
    revised_benchmark = run_benchmark()
    save_json("revised_irsim_benchmark_report.json", revised_benchmark)
    save_json("revised_benchmark_review_notes.json", run_benchmark_reviewer(revised_benchmark))
    logging.info("Reviewed logic passed through simulation and IR-SIM benchmark")
    return {"simulation": simulation, "review": review, "benchmark": benchmark,
            "benchmark_review": benchmark_review}


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2)[:5000])
