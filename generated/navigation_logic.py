def choose_action(front_blocked, left_blocked, right_blocked, goal_direction=None):
    if goal_direction == "FORWARD" and not front_blocked:
        return "FORWARD"
    elif goal_direction == "LEFT" and not left_blocked:
        return "LEFT"
    elif goal_direction == "RIGHT" and not right_blocked:
        return "RIGHT"
    if not front_blocked:
        return "FORWARD"
    if not left_blocked:
        return "LEFT"
    if not right_blocked:
        return "RIGHT"
    return "STOP"

def decide_next_move(state):
    goal_direction = None
    if state["goal_ahead"] and not state["front_blocked"]:
        goal_direction = "FORWARD"
    elif state["goal_on_left"] and not state["left_blocked"]:
        goal_direction = "LEFT"
    elif state["goal_on_right"] and not state["right_blocked"]:
        goal_direction = "RIGHT"
    return choose_action(state["front_blocked"], state["left_blocked"], state["right_blocked"], goal_direction)\n