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


def test_ai_advisor_model_name_is_valid():
    """Regression: the model name was 'gemini-3.6-flash' which doesn't exist.
    Verify the fixed source code references a real model in the page or engine module."""
    source_page = (Path(__file__).resolve().parent.parent / "pages" / "6_AI_Financial_Advisor.py").read_text(encoding="utf-8")
    engine_path = Path(__file__).resolve().parent.parent / "advisor_engine.py"
    source_engine = engine_path.read_text(encoding="utf-8") if engine_path.exists() else ""

    # The old invalid model should not appear in either file
    assert "gemini-3.6-flash" not in source_page, "Invalid model name still present in advisor page"
    assert "gemini-3.6-flash" not in source_engine, "Invalid model name still present in advisor_engine.py"

    # A valid model name must appear in the page or in the engine module (via DEFAULT_GEMINI_MODEL)
    valid_models = ("gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash")
    combined_source = source_page + source_engine
    assert any(m in combined_source for m in valid_models), (
        f"None of the expected valid model names {valid_models} found in advisor page or engine"
    )


def test_ai_advisor_uses_multi_turn_history():
    """Regression: the AI advisor previously sent only the current message
    without conversation history. Verify the fixed source builds a
    contents list from session state messages."""
    source_path = Path(__file__).resolve().parent.parent / "pages" / "6_AI_Financial_Advisor.py"
    source = source_path.read_text(encoding="utf-8")
    # Should construct Content objects for multi-turn
    assert "types.Content" in source, "Multi-turn Content construction not found"
    assert "system_instruction" in source, "system_instruction not used"


def test_currency_formatting_and_preference():
    """Verify format_currency correctly handles various symbols, negative numbers, and fallbacks."""
    from utils import format_currency
    assert format_currency(1234.56, "$") == "$1,234.56"
    assert format_currency(-50.0, "€") == "-€50.00"
    assert format_currency(0, "£") == "£0.00"
    assert format_currency(None, "$") == "$0.00"

