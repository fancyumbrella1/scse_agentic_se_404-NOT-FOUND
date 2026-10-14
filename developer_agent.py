"""Generate Qwen navigation code and validate its interface and behaviour."""

import ast
import json
import os

from ollama import chat

from planner_agent import validate_plan


MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
DIRECTIONS = ("FORWARD", "LEFT", "RIGHT")
STATE_KEYS = (
    "goal_ahead", "goal_on_left", "goal_on_right",
    "front_blocked", "left_blocked", "right_blocked",
)
SYSTEM_PROMPT = """You are the Developer Agent for a mobile robot.
Receive only the validated plan JSON. Return only Python source code.
Define exactly these two functions, with no imports, comments, or markdown:
def choose_action(front_blocked, left_blocked, right_blocked, goal_direction=None):
def decide_next_move(state):
Keep choose_action as the helper that implements the original navigation
logic: choose a safe goal direction; otherwise the first safe direction in
FORWARD, LEFT, RIGHT order; STOP only when all are blocked.
The helper must have two groups of checks. First check each goal_direction
value together with its unblocked flag and return that action when safe.
After those checks, independently check `if not front_blocked` and return
FORWARD, then `if not left_blocked` and return LEFT, then
`if not right_blocked` and return RIGHT. Only then return STOP.
In particular, goal_direction=None with a clear front must return FORWARD.
decide_next_move is the only public entry point. state has six boolean keys:
goal_ahead, goal_on_left, goal_on_right, front_blocked, left_blocked,
right_blocked. Choose the first unblocked goal in FORWARD, LEFT, RIGHT order.
If no goal is safe, fall back to the first safe direction. Call and return
choose_action with the three blocked flags and selected goal direction.
For decide_next_move, use this exact decision order: initialize
goal_direction = None; if goal_ahead AND NOT front_blocked, assign FORWARD;
elif goal_on_left AND NOT left_blocked, assign LEFT; elif goal_on_right AND
NOT right_blocked, assign RIGHT. Then call choose_action with front_blocked,
left_blocked, right_blocked, and goal_direction. Never choose a blocked goal
while another goal direction remains safe.
Use only if statements, a goal_direction local variable, direct state[key]
lookups, boolean expressions, literal strings, and choose_action calls.
No loops, attributes, other calls, I/O, or extra functions."""

ALLOWED_AST = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign,
    ast.If, ast.Return, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name,
    ast.Load, ast.Store, ast.Constant, ast.And, ast.Or, ast.Not, ast.Eq,
    ast.Is, ast.IsNot, ast.Subscript, ast.Call,
)


def validate_code(source):
    """Reject unsafe syntax and test all 64 combinations of sensor flags."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Generated code must be nonempty Python source.")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ValueError(f"Invalid Python syntax: {error}") from error
    if len(tree.body) != 2 or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError("Define exactly two functions.")
    functions = {node.name: node for node in tree.body}
    if set(functions) != {"choose_action", "decide_next_move"}:
        raise ValueError("The required function names are missing.")
    helper, entry = functions["choose_action"], functions["decide_next_move"]
    if [arg.arg for arg in helper.args.args] != [
        "front_blocked", "left_blocked", "right_blocked", "goal_direction"
    ] or len(helper.args.defaults) != 1 or not isinstance(helper.args.defaults[0], ast.Constant) or helper.args.defaults[0].value is not None:
        raise ValueError("choose_action has the wrong signature.")
    if [arg.arg for arg in entry.args.args] != ["state"] or entry.args.defaults:
        raise ValueError("decide_next_move must accept only state.")
    for function in (helper, entry):
        if (function.decorator_list or function.returns or function.args.posonlyargs
                or function.args.kwonlyargs or function.args.vararg or function.args.kwarg):
            raise ValueError("Unsupported signature feature.")
    names = {"state", "choose_action", "front_blocked", "left_blocked", "right_blocked", "goal_direction"}
    strings = set(DIRECTIONS) | {"STOP"} | set(STATE_KEYS)
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST):
            raise ValueError(f"Unsupported construct: {type(node).__name__}.")
        if isinstance(node, ast.Name) and node.id not in names:
            raise ValueError(f"Unexpected name: {node.id}.")
        if isinstance(node, ast.Constant) and (
            type(node.value) not in (str, bool, type(None))
            or isinstance(node.value, str) and node.value not in strings
        ):
            raise ValueError(f"Unexpected literal: {node.value}.")
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id != "choose_action"
            or len(node.args) != 4 or node.keywords
        ):
            raise ValueError("Only a four-argument choose_action call is allowed.")
        if isinstance(node, ast.Subscript) and (
            not isinstance(node.value, ast.Name) or node.value.id != "state"
            or not isinstance(node.slice, ast.Constant) or node.slice.value not in STATE_KEYS
        ):
            raise ValueError("Only known state fields may be read.")
        if isinstance(node, ast.Assign) and (
            len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name)
            or node.targets[0].id != "goal_direction"
        ):
            raise ValueError("Only goal_direction may be assigned.")

    namespace = {"__builtins__": {}}
    exec(compile(tree, "<generated-navigation>", "exec"), namespace)
    for blocked_bits in range(8):
        blocked = tuple(bool(blocked_bits & (1 << i)) for i in range(3))
        safe = [move for move, flag in zip(DIRECTIONS, blocked) if not flag]
        for goal in (None, *DIRECTIONS):
            expected = goal if goal in safe else (safe[0] if safe else "STOP")
            try:
                actual_helper = namespace["choose_action"](*blocked, goal)
            except Exception as error:
                raise ValueError(f"Helper failed for {blocked}, {goal}: {error}") from error
            if actual_helper != expected:
                raise ValueError(f"Helper returned a wrong move for {blocked}, {goal}.")
        for goal_bits in range(8):
            goals = tuple(bool(goal_bits & (1 << i)) for i in range(3))
            state = dict(zip(STATE_KEYS, (*goals, *blocked)))
            safe_goals = [move for move, wanted, flag in zip(DIRECTIONS, goals, blocked) if wanted and not flag]
            expected = safe_goals[0] if safe_goals else (safe[0] if safe else "STOP")
            try:
                actual = namespace["decide_next_move"](state)
            except Exception as error:
                raise ValueError(f"Entry point failed for {state}: {error}") from error
            if actual != expected:
                raise ValueError(f"Wrong move for {state}: expected {expected}, got {actual}.")
    return source


def run_developer(plan):
    validate_plan(plan)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(plan, ensure_ascii=False)},
    ]
    for attempt in range(4):
        response = chat(model=MODEL, think=False, messages=messages)
        source = response.message.content.strip()
        try:
            return validate_code(source)
        except ValueError as error:
            if attempt == 3:
                raise ValueError(f"Qwen produced invalid navigation code: {error}\nLast source:\n{source}") from error
            messages.extend([
                {"role": "assistant", "content": source},
                {"role": "user", "content": f"Fix this validation error: {error}. Return only corrected Python source."},
            ])


def run_developer_revision(original_code, review_notes, benchmark_report, requirements, plan):
    """Ask Qwen for a revised implementation, preserving the original artifact."""
    from analyst_agent import validate_requirements

    validate_requirements(requirements)
    validate_plan(plan)
    validate_code(original_code)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\nRevise the original code using the measured reviews. Return only the two required Python functions."},
        {"role": "user", "content": json.dumps({
            "original_code": original_code,
            "simulation_review": review_notes,
            "benchmark_report": benchmark_report,
            "requirements": requirements,
            "plan": plan,
        }, ensure_ascii=False)},
    ]
    for attempt in range(4):
        response = chat(model=MODEL, think=False, messages=messages)
        source = response.message.content.strip()
        try:
            return validate_code(source)
        except ValueError as error:
            if attempt == 3:
                raise ValueError(f"Qwen produced an invalid revision: {error}") from error
            messages.extend([
                {"role": "assistant", "content": source},
                {"role": "user", "content": f"Fix this validation error: {error}. Return only Python source."},
            ])
