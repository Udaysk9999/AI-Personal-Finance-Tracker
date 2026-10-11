"""
Unit and integration tests for advisor_engine module.
Validates deterministic calculations, savings goal plans, budget status,
user isolation, prompt generation, MoM comparisons, and API resilience.
"""

import tempfile
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import database
from advisor_engine import (
    calculate_savings_goal_monthly_plan,
    build_financial_context,
    format_context_for_prompt,
    get_advisor_system_instruction,
    load_gemini_api_key,
    generate_advisor_reply,
    DISCRETIONARY_CATEGORIES,
    ESSENTIAL_CATEGORIES,
)


def setup_module():
    global _tmp_dir
    _tmp_dir = tempfile.mkdtemp()
    database.DB_NAME = str(Path(_tmp_dir) / "test_advisor.db")
    database.create_database()


def teardown_module():
    import shutil
    shutil.rmtree(_tmp_dir, ignore_errors=True)


def test_calculate_savings_goal_monthly_plan():
    # 1. Normal future goal
    future_date = (date.today() + timedelta(days=95)).isoformat()
    plan = calculate_savings_goal_monthly_plan(
        target_amount=10000.0,
        current_amount=4000.0,
        target_date_str=future_date,
    )
    assert plan["remaining"] == 6000.0
    assert plan["months_remaining"] is not None
    assert plan["months_remaining"] >= 2
    assert plan["required_per_month"] is not None
    assert plan["required_per_month"] > 0

    # 2. Completed goal
    plan_completed = calculate_savings_goal_monthly_plan(
        target_amount=5000.0,
        current_amount=5500.0,
        target_date_str=future_date,
    )
    assert plan_completed["remaining"] == 0.0

    # 3. No target date
    plan_no_date = calculate_savings_goal_monthly_plan(
        target_amount=10000.0,
        current_amount=2000.0,
        target_date_str=None,
    )
    assert plan_no_date["remaining"] == 8000.0
    assert plan_no_date["months_remaining"] is None
    assert plan_no_date["required_per_month"] is None


def test_build_financial_context_and_isolation():
    u1 = database.create_user("advisor_user_1", "password123")
    u2 = database.create_user("advisor_user_2", "password456")

    today_str = date.today().isoformat()

    # User 1: income 50000, food 12000, rent 15000
    database.add_transaction(u1, today_str, "Income", "Salary", 50000.0, "Monthly Salary")
    database.add_transaction(u1, today_str, "Expense", "Food", 12000.0, "Groceries and Dining")
    database.add_transaction(u1, today_str, "Expense", "Rent", 15000.0, "Apartment Rent")

    # User 1 budgets: Food limit 10000 (over budget), Rent limit 20000 (ok)
    database.set_budget(u1, "Food", 10000.0)
    database.set_budget(u1, "Rent", 20000.0)

    # User 1 goal
    future_goal_date = (date.today() + timedelta(days=180)).isoformat()
    database.add_savings_goal(u1, "Emergency Fund", 60000.0, future_goal_date)
    created_goals = database.get_savings_goals(u1)
    database.update_savings_goal_amount(u1, created_goals[0][0], 10000.0)

    # User 2: freelance income 20000, shopping 5000
    database.add_transaction(u2, today_str, "Income", "Freelance", 20000.0, "Design project")
    database.add_transaction(u2, today_str, "Expense", "Shopping", 5000.0, "Clothes")

    # Build context for User 1
    ctx1 = build_financial_context(u1, curr="$")
    assert ctx1["has_data"] is True
    assert ctx1["total_income"] == 50000.0
    assert ctx1["total_expenses"] == 27000.0
    assert ctx1["net_balance"] == 23000.0
    assert ctx1["curr"] == "$"
    assert len(ctx1["category_spending"]) == 2

    # Current month metrics
    assert ctx1["current_month_income"] == 50000.0
    assert ctx1["current_month_expense"] == 27000.0
    assert ctx1["current_month_net"] == 23000.0
    assert ctx1["current_month_top_category"]["category"] == "Rent"

    # Check budget analysis: Food is 120% (over budget), so it must be ranked first
    assert len(ctx1["budget_analysis"]) == 2
    assert ctx1["budget_analysis"][0]["category"] == "Food"
    assert ctx1["budget_analysis"][0]["status"] == "over"
    assert ctx1["budget_analysis"][0]["percent_used"] == 120.0

    # Check savings goal analysis
    assert len(ctx1["savings_goals_analysis"]) == 1
    goal_res = ctx1["savings_goals_analysis"][0]
    assert goal_res["name"] == "Emergency Fund"
    assert goal_res["remaining"] == 50000.0
    assert goal_res["required_per_month"] is not None

    # Realistic savings capacity
    assert ctx1["realistic_savings_capacity"]["available_surplus"] == 23000.0
    assert ctx1["realistic_savings_capacity"]["conservative"] == 11500.0
    assert ctx1["realistic_savings_capacity"]["moderate"] == 17250.0

    # Verify User 2 context is strictly isolated
    ctx2 = build_financial_context(u2, curr="€")
    assert ctx2["total_income"] == 20000.0
    assert ctx2["total_expenses"] == 5000.0
    assert ctx2["net_balance"] == 15000.0
    assert len(ctx2["category_spending"]) == 1
    assert ctx2["category_spending"][0]["category"] == "Shopping"
    assert ctx2["budget_analysis"] == []
    assert ctx2["savings_goals_analysis"] == []


def test_build_financial_context_empty():
    u_empty = database.create_user("empty_user", "password789")
    ctx = build_financial_context(u_empty, curr="₹")
    assert ctx["has_data"] is False
    assert ctx["total_income"] == 0.0
    assert ctx["total_expenses"] == 0.0
    assert ctx["category_spending"] == []
    assert ctx["mom_comparison"]["available"] is False


def test_mom_comparison_calculation():
    """Verify month-over-month comparisons are calculated deterministically across consecutive months."""
    u_mom = database.create_user("user_mom", "password123")
    today = date.today()
    # Compute a date in the previous calendar month
    prev_year = today.year if today.month > 1 else today.year - 1
    prev_month_num = today.month - 1 if today.month > 1 else 12
    prev_date_str = date(prev_year, prev_month_num, 15).isoformat()
    cur_date_str = date(today.year, today.month, 10).isoformat()

    # Prior month: Income 40,000, Expense 20,000
    database.add_transaction(u_mom, prev_date_str, "Income", "Salary", 40000.0, "Prior salary")
    database.add_transaction(u_mom, prev_date_str, "Expense", "Bills", 20000.0, "Prior bills")

    # Current month: Income 45,000, Expense 25,000 (spent 5,000 more -> +25%)
    database.add_transaction(u_mom, cur_date_str, "Income", "Salary", 45000.0, "Current salary")
    database.add_transaction(u_mom, cur_date_str, "Expense", "Food", 25000.0, "Current food")

    ctx = build_financial_context(u_mom, curr="₹")
    mom = ctx["mom_comparison"]
    assert mom["available"] is True
    assert mom["prev_expense"] == 20000.0
    assert mom["expense_diff"] == 5000.0
    assert mom["expense_pct_change"] == 25.0
    assert mom["is_overspending"] is True
    assert mom["income_diff"] == 5000.0
    assert mom["income_pct_change"] == 12.5


def test_essential_vs_discretionary_calculation():
    """Verify that categories are accurately grouped into essential vs discretionary."""
    u_evd = database.create_user("user_evd", "password123")
    today_str = date.today().isoformat()

    # Discretionary: Food (8,000) + Shopping (4,000) = 12,000
    database.add_transaction(u_evd, today_str, "Expense", "Food", 8000.0, "Restaurants")
    database.add_transaction(u_evd, today_str, "Expense", "Shopping", 4000.0, "Clothes")

    # Essential: Rent (20,000) + Bills (8,000) = 28,000
    database.add_transaction(u_evd, today_str, "Expense", "Rent", 20000.0, "Home rent")
    database.add_transaction(u_evd, today_str, "Expense", "Bills", 8000.0, "Electricity")

    ctx = build_financial_context(u_evd, curr="₹")
    evd = ctx["essential_vs_discretionary"]
    assert evd["discretionary_amount"] == 12000.0
    assert evd["essential_amount"] == 28000.0
    assert abs(evd["discretionary_pct"] - 30.0) < 0.1  # 12k / 40k = 30%


def test_format_context_for_prompt():
    ctx = {
        "has_data": True,
        "curr": "₹",
        "total_income": 80000.0,
        "total_expenses": 35000.0,
        "net_balance": 45000.0,
        "savings_rate": 56.25,
        "current_month_name": "October 2026",
        "current_month_income": 80000.0,
        "current_month_expense": 35000.0,
        "current_month_net": 45000.0,
        "current_month_savings_rate": 56.25,
        "current_month_categories": [
            {"category": "Food", "amount": 20000.0, "percent": 57.1},
            {"category": "Bills", "amount": 15000.0, "percent": 42.9},
        ],
        "current_month_top_category": {"category": "Food", "amount": 20000.0},
        "mom_comparison": {
            "available": True,
            "current_month_name": "October 2026",
            "previous_month_name": "September 2026",
            "prev_expense": 30000.0,
            "prev_income": 75000.0,
            "expense_diff": 5000.0,
            "expense_pct_change": 16.7,
            "income_diff": 5000.0,
            "is_overspending": True,
        },
        "essential_vs_discretionary": {
            "discretionary_amount": 20000.0,
            "essential_amount": 15000.0,
            "discretionary_pct": 57.1,
        },
        "budget_analysis": [
            {
                "category": "Food",
                "monthly_limit": 18000.0,
                "current_month_spent": 20000.0,
                "remaining": -2000.0,
                "percent_used": 111.1,
                "status": "over",
            }
        ],
        "savings_goals_analysis": [
            {
                "name": "Trip",
                "target": 50000.0,
                "current": 10000.0,
                "remaining": 40000.0,
                "target_date": "2027-01-01",
                "months_remaining": 6,
                "required_per_month": 6666.67,
            }
        ],
        "realistic_savings_capacity": {
            "available_surplus": 45000.0,
            "conservative": 22500.0,
            "moderate": 33750.0,
            "aggressive": 40500.0,
            "total_goal_demand": 6666.67,
            "feasibility": "comfortable",
        },
        "recent_transactions": [
            {"date": "10 Oct 2026", "type": "Expense", "category": "Food", "amount": 500.0, "description": "Lunch"}
        ],
        "ml_insights": {
            "health_score": 75,
            "health_suggestions": ["Keep saving regularly"],
            "forecast_status": "ok",
            "forecast_amount": 34000.0,
            "forecast_month": "2026-11",
            "forecast_categories": {"Food": 19000.0},
            "anomalies": [],
        },
    }

    summary_text = format_context_for_prompt(ctx)
    assert "80,000.00" in summary_text
    assert "Food" in summary_text
    assert "OVER BUDGET" in summary_text
    assert "Trip" in summary_text
    assert "Health Score: 75/100" in summary_text
    assert "Conservative" in summary_text
    assert "Discretionary" in summary_text

    system_instruction = get_advisor_system_instruction("₹", summary_text)
    assert "AI Personal Financial Advisor" in system_instruction
    assert "Ground all numbers strictly in the provided data summary" in system_instruction


def test_load_gemini_api_key_safe():
    key = load_gemini_api_key()
    assert key is None or isinstance(key, str)


def test_generate_advisor_reply_missing_key():
    reply, err = generate_advisor_reply(api_key=None, contents=[], system_instruction="")
    assert reply == ""
    assert "Missing Gemini API key" in err


def test_generate_advisor_reply_simulated_error():
    """Verify that API exceptions return clean, safe error messages without leaking secrets."""
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded")
        mock_client_cls.return_value = mock_instance

        reply, err = generate_advisor_reply(
            api_key="dummy_key",
            contents=[],
            system_instruction="sys",
            max_retries=0,
        )
        assert "Quota Limit Reached" in reply
        assert "Rate limit" in err
        assert "dummy_key" not in reply
