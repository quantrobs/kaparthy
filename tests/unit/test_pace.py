from agentic_platform.loops.pace import can_still_reach, should_keep, wealth_update


def test_three_wins_keep_with_easy_gate() -> None:
    w = 1.0
    for _ in range(3):
        w = wealth_update(w, True, 0.8)
    assert should_keep(w, 3, 3, 0.2)


def test_one_win_two_losses_cannot_keep() -> None:
    w = 1.0
    w = wealth_update(w, True, 0.8)
    w = wealth_update(w, False, 0.8)
    w = wealth_update(w, False, 0.8)
    assert not should_keep(w, 3, 3, 0.2)
    assert not can_still_reach(w, 0, 0.8, 0.2)
