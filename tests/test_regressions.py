"""Regression tests for bugs fixed in Phase 1."""

import tempfile
from pathlib import Path

import database


def setup_module():
    global _tmp_dir
    _tmp_dir = tempfile.mkdtemp()
    database.DB_NAME = str(Path(_tmp_dir) / "test_regressions.db")
    database.create_database()


def teardown_module():
    import shutil
    shutil.rmtree(_tmp_dir, ignore_errors=True)


def test_savings_goal_requires_user_id():
    """Regression: pages/5_Savings_Goals.py previously called add_savings_goal
    without user_id, causing TypeError. Verify the correct 4-argument
    signature works and associates the goal with the right user."""
    user_id = database.create_user("goaluser", "password123")
    database.add_savings_goal(user_id, "Emergency Fund", 50000.0, "2027-06-01")

    goals = database.get_savings_goals(user_id)
    assert len(goals) == 1
    assert goals[0][1] == "Emergency Fund"
    assert goals[0][2] == 50000.0

    # Another user should not see this goal
    other_user = database.create_user("otheruser", "password456")
    assert database.get_savings_goals(other_user) == []


def test_savings_goal_add_wrong_arg_count_raises():
    """The old bug: calling with 3 args should raise TypeError."""
    try:
        database.add_savings_goal("Emergency Fund", 50000.0, "2027-06-01")
        assert False, "Should have raised TypeError"
    except TypeError:
        pass


def test_currency_formatting_and_preference():
    """Verify format_currency correctly handles various symbols, negative numbers, and fallbacks."""
    from utils import format_currency
    assert format_currency(1234.56, "$") == "$1,234.56"
    assert format_currency(-50.0, "€") == "-€50.00"
    assert format_currency(0, "£") == "£0.00"
    assert format_currency(None, "$") == "$0.00"

