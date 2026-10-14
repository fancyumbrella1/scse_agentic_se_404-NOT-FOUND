"""Qwen test agent: generate pytest tests from requirements and plan."""
import ast
import json
import os
from ollama import chat
from analyst_agent import validate_requirements
from planner_agent import validate_plan

MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
SYSTEM_PROMPT = """Generate Python pytest-style tests for generated.navigation_logic.decide_next_move(state).
The state has six boolean keys: goal_ahead, goal_on_left, goal_on_right,
front_blocked, left_blocked, right_blocked. Cover safe goal priority, fallback,
all blocked STOP, and blocked goal with another safe goal. Use plain Python code
only, no markdown. Include `from generated.navigation_logic import decide_next_move`
and assert statements. Do not import external packages."""


def validate_test_code(code):
    if not isinstance(code, str) or not code.strip() or "```" in code:
        raise ValueError("Tests must be nonempty plain Python code")
    tree = ast.parse(code)
    if not any(isinstance(node, ast.ImportFrom) and node.module == "generated.navigation_logic" for node in tree.body):
        raise ValueError("Missing navigation import")
    tests = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    if len(tests) < 4 or not all(any(isinstance(item, ast.Assert) for item in ast.walk(test)) for test in tests):
        raise ValueError("At least four test functions with assertions are required")
    return code


def run_test_agent(requirements, plan):
    validate_requirements(requirements)
    validate_plan(plan)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"requirements": requirements, "plan": plan})}]
    for attempt in range(4):
        code = chat(model=MODEL, think=False, messages=messages).message.content.strip()
        try:
            return validate_test_code(code)
        except (SyntaxError, ValueError) as exc:
            if attempt == 3:
                return validate_test_code(FALLBACK_TESTS)
            messages.extend([{"role": "assistant", "content": code},
                             {"role": "user", "content": f"Fix: {exc}. Return Python only."}])


FALLBACK_TESTS = '''from generated.navigation_logic import decide_next_move

def test_goal_ahead():
    state = dict(goal_ahead=True, goal_on_left=False, goal_on_right=False,
                 front_blocked=False, left_blocked=False, right_blocked=False)
    assert decide_next_move(state) == "FORWARD"

def test_goal_left_over_clear_front():
    state = dict(goal_ahead=False, goal_on_left=True, goal_on_right=False,
                 front_blocked=False, left_blocked=False, right_blocked=False)
    assert decide_next_move(state) == "LEFT"

def test_blocked_goal_falls_back():
    state = dict(goal_ahead=True, goal_on_left=False, goal_on_right=True,
                 front_blocked=True, left_blocked=False, right_blocked=False)
    assert decide_next_move(state) == "RIGHT"

def test_all_blocked_stops():
    state = dict(goal_ahead=False, goal_on_left=False, goal_on_right=False,
                 front_blocked=True, left_blocked=True, right_blocked=True)
    assert decide_next_move(state) == "STOP"
'''
