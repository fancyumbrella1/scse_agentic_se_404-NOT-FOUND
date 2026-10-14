from generated.navigation_logic import decide_next_move

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

