from control_plane import State, Task, route_language


def test_done_requires_evidence():
    task = Task("T1", "demo")
    for state in [State.PLAN, State.ROUTE, State.EXECUTE, State.QA, State.VERIFY, State.EVIDENCE, State.UPDATE, State.NEXT]:
        task.transition(state)
    try:
        task.transition(State.DONE)
    except ValueError as exc:
        assert "evidence" in str(exc).lower()
    else:
        raise AssertionError("DONE must require evidence")


def test_verified_task_can_finish():
    task = Task("T2", "demo")
    for state in [State.PLAN, State.ROUTE, State.EXECUTE, State.QA, State.VERIFY, State.EVIDENCE, State.UPDATE, State.NEXT]:
        task.transition(state)
    task.add_evidence("test://evidence")
    task.transition(State.DONE)
    assert task.state is State.DONE


def test_language_router():
    assert route_language("web") == "typescript"
    assert route_language("automation") == "python"
    assert route_language("database") == "sql"
    assert route_language("ci") == "shell"


def test_invalid_transition_is_rejected():
    task = Task("T3", "demo")
    try:
        task.transition(State.DONE)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid transition must be rejected")
