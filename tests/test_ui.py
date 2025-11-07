from ddaword_cli.ui import TokenTracker


def test_token_tracker_updates_totals():
    tracker = TokenTracker()
    tracker.set_baseline(100)

    tracker.add(150, 25)

    assert tracker.current_context == 150
    assert tracker.last_output == 25

    tracker.reset()
    assert tracker.current_context == 100
    assert tracker.last_output == 0

