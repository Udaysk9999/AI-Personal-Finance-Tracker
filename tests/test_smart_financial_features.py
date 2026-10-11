"""
Comprehensive tests for smart financial features:
1. Transaction categorization (keywords, user history learning, fallback)
2. Practical budget alerts (80% threshold, over-budget, safe zero limits, cushion)
3. Savings planning (realistic targets, irregular income, deficits, feasibility)
4. Expense forecasting (2-month low confidence, multi-month, runaway dampening)
5. Anomaly detection (MAD outliers, sample size handling, review rationale)
6. Data integrity & user isolation
"""

from datetime import date, timedelta
import io
import tempfile
from pathlib import Path

import database
from finance_ml import (
    suggest_expense_category,
    suggest_income_category,
    suggest_category,
    predict_next_month_expenses,
    detect_expense_anomalies,
    calculate_savings_plan,
)
from finance_tools import budget_alerts, parse_statement


def setup_module():
    global _tmp_dir
    _tmp_dir = tempfile.mkdtemp()
    database.DB_NAME = str(Path(_tmp_dir) / "test_smart_features.db")
    database.create_database()


def teardown_module():
    import shutil
    shutil.rmtree(_tmp_dir, ignore_errors=True)


# =========================================================================
# 1. SMART TRANSACTION CATEGORIZATION TESTS
# =========================================================================

def test_smart_categorization_keywords():
    # Expense keywords
    assert suggest_expense_category("Swiggy Biryani Order")["category"] == "Food"
    assert suggest_expense_category("Uber cab ride to office")["category"] == "Travel"
    assert suggest_expense_category("Electricity bill payment")["category"] == "Bills"
    assert suggest_expense_category("Netflix monthly subscription")["category"] == "Entertainment"
    assert suggest_expense_category("Apollo pharmacy medicine")["category"] == "Healthcare"
    assert suggest_expense_category("College tuition fee")["category"] == "Education"
    assert suggest_expense_category("Amazon online shopping")["category"] == "Shopping"
    assert suggest_expense_category("House rent transfer")["category"] == "Rent"

    # Income keywords
    assert suggest_income_category("Monthly salary credit")["category"] == "Salary"
    assert suggest_income_category("Freelance Upwork gig payout")["category"] == "Freelance"
    assert suggest_income_category("Mutual fund dividend")["category"] == "Investment"
    assert suggest_income_category("Performance bonus incentive")["category"] == "Bonus"
    assert suggest_income_category("Tenant rent received")["category"] == "Rental"


def test_smart_categorization_user_history_learning():
    """Verify that custom merchant descriptions from user's history are remembered."""
    past_transactions = [
        (1, "2026-09-01", "Expense", "Food", 350.0, "Joe's Corner Deli"),
        (2, "2026-09-02", "Expense", "Healthcare", 1200.0, "Dr. Mehta Clinic"),
        (3, "2026-09-03", "Income", "Freelance", 15000.0, "Acme Corp Retainer"),
    ]

    # Exact match from history
    res1 = suggest_expense_category("Joe's Corner Deli", user_transactions=past_transactions)
    assert res1 is not None
    assert res1["category"] == "Food"
    assert "Matched previous transaction" in res1["reason"]

    # Fuzzy/substring match from history
    res2 = suggest_expense_category("Payment to Dr. Mehta Clinic", user_transactions=past_transactions)
    assert res2 is not None
    assert res2["category"] == "Healthcare"

    # Income history match
    res3 = suggest_income_category("Acme Corp Retainer", user_transactions=past_transactions)
    assert res3 is not None
    assert res3["category"] == "Freelance"


def test_smart_categorization_fallback_and_edge_cases():
    # Empty inputs
    assert suggest_expense_category("") is None
    assert suggest_expense_category("   ") is None
    assert suggest_income_category(None) is None

    # Unknown description without fallback -> None (preserves backward compatibility)
    assert suggest_expense_category("completely unknown merchant xyz") is None
    assert suggest_income_category("completely unknown sender abc") is None

    # Unknown description with fallback=True -> sensible fallback
    res_fallback_exp = suggest_expense_category("completely unknown merchant xyz", fallback=True)
    assert res_fallback_exp is not None
    assert res_fallback_exp["category"] == "Other Expense"
    assert res_fallback_exp["confidence"] == "fallback"

    res_fallback_inc = suggest_income_category("completely unknown sender abc", fallback=True)
    assert res_fallback_inc is not None
    assert res_fallback_inc["category"] == "Other Income"
    assert res_fallback_inc["confidence"] == "fallback"

    # Unified suggest_category
    res_unified = suggest_category("Starbucks Latte", tx_type="Expense")
    assert res_unified["category"] == "Food"
    res_unified_inc = suggest_category("Consulting fee payment", tx_type="Income")
    assert res_unified_inc["category"] == "Freelance"


def test_statement_import_auto_categorization():
    """Verify parse_statement auto-assigns intelligent categories when Category column is missing."""
    csv_content = (
        "Date,Amount,Description\n"
        "2026-10-01,450.00,Swiggy food order\n"
        "2026-10-02,320.00,Uber cab ride\n"
        "2026-10-03,1500.00,Electricity bill recharge\n"
        "2026-10-04,999.00,Unknown transaction 999\n"
    ).encode("utf-8")

    file_obj = io.BytesIO(csv_content)
    file_obj.name = "statement.csv"

    df = parse_statement(file_obj)
    assert len(df) == 4
    assert df.loc[0, "Category"] == "Food"
    assert df.loc[1, "Category"] == "Travel"
    assert df.loc[2, "Category"] == "Bills"
    assert df.loc[3, "Category"] == "Other Expense"


# =========================================================================
# 2. PRACTICAL BUDGET ALERTS TESTS
# =========================================================================

def test_budget_alerts_thresholds():
    today_str = date.today().strftime("%Y-%m-%d")
    budgets = [
        ("Food", 10000.0),
        ("Bills", 5000.0),
        ("Shopping", 8000.0),
    ]

    transactions = [
        # Food: 8000 / 10000 = 80% (approaching limit)
        (1, today_str, "Expense", "Food", 8000.0, "Groceries"),
        # Bills: 5500 / 5000 = 110% (over budget)
        (2, today_str, "Expense", "Bills", 5500.0, "Electricity"),
        # Shopping: 4000 / 8000 = 50% (under threshold, no alert)
        (3, today_str, "Expense", "Shopping", 4000.0, "Clothes"),
    ]

    alerts = budget_alerts(budgets, transactions, warning_threshold=0.80)
    assert len(alerts) == 2

    # Over budget alert
    over_alert = next(a for a in alerts if a["category"] == "Bills")
    assert over_alert["level"] == "over"
    assert over_alert["status"] == "over"
    assert over_alert["spent"] == 5500.0
    assert over_alert["limit"] == 5000.0
    assert over_alert["over_by"] == 500.0
    assert over_alert["remaining"] == 0.0
    assert over_alert["percent"] == 1.1

    # Warning alert
    near_alert = next(a for a in alerts if a["category"] == "Food")
    assert near_alert["level"] == "warning"
    assert near_alert["status"] == "approaching"
    assert near_alert["spent"] == 8000.0
    assert near_alert["limit"] == 10000.0
    assert near_alert["remaining"] == 2000.0
    assert near_alert["over_by"] == 0.0
    assert near_alert["percent"] == 0.80


def test_budget_alerts_safe_zero_limits_and_no_duplicates():
    today_str = date.today().strftime("%Y-%m-%d")
    budgets = [
        ("ZeroLimitCat", 0.0),
        ("UnusedCat", 5000.0),
    ]
    transactions = [
        (1, today_str, "Expense", "ZeroLimitCat", 250.0, "Test expense"),
    ]

    alerts = budget_alerts(budgets, transactions)
    # Zero limit with spent > 0 should trigger over budget safely without ZeroDivisionError
    assert len(alerts) == 1
    assert alerts[0]["category"] == "ZeroLimitCat"
    assert alerts[0]["level"] == "over"
    assert alerts[0]["limit"] == 0.0
    assert alerts[0]["spent"] == 250.0

    # Verify no duplicates
    categories = [a["category"] for a in alerts]
    assert len(categories) == len(set(categories))


# =========================================================================
# 3. USEFUL SAVINGS PLANNING TESTS
# =========================================================================

def test_savings_planning_realistic_target():
    transactions = [
        # Month 1
        (1, "2026-08-01", "Income", "Salary", 60000.0, "Salary"),
        (2, "2026-08-05", "Expense", "Rent", 20000.0, "Rent"),
        (3, "2026-08-10", "Expense", "Food", 10000.0, "Food"),
        # Month 2
        (4, "2026-09-01", "Income", "Salary", 60000.0, "Salary"),
        (5, "2026-09-05", "Expense", "Rent", 20000.0, "Rent"),
        (6, "2026-09-10", "Expense", "Food", 10000.0, "Food"),
    ]
    # Surplus = 60,000 - 30,000 = 30,000
    future_date = (date.today() + timedelta(days=120)).isoformat()
    goals = [
        (1, "Emergency Fund", 50000.0, 10000.0, future_date),  # remaining 40,000
    ]

    plan = calculate_savings_plan(transactions, goals)
    assert plan["status"] == "ok"
    assert plan["feasibility"] == "positive"
    assert plan["baseline_surplus"] == 30000.0
    # Moderate target = 70% of 30,000 = 21,000
    assert plan["realistic_monthly_target"] == 21000.0
    assert plan["conservative_target"] == 15000.0
    assert plan["aggressive_target"] == 25500.0

    # Goal evaluation
    assert len(plan["goals_plan"]) == 1
    g_res = plan["goals_plan"][0]
    assert g_res["name"] == "Emergency Fund"
    assert g_res["remaining"] == 40000.0
    assert g_res["status"] in ("on_track", "tight")
    assert g_res["estimated_months_at_target"] == 2  # ceil(40000 / 21000) = 2
    assert "Assumptions:" in plan["assumptions"]
    assert plan["is_projection"] is True


def test_savings_planning_irregular_income():
    """Verify that volatile income triggers irregular income warning and conservative median baseline."""
    transactions = [
        # Month 1: big windfall
        (1, "2026-07-01", "Income", "Freelance", 120000.0, "Windfall"),
        (2, "2026-07-05", "Expense", "Rent", 20000.0, "Rent"),
        # Month 2: low month
        (3, "2026-08-01", "Income", "Freelance", 30000.0, "Low month"),
        (4, "2026-08-05", "Expense", "Rent", 20000.0, "Rent"),
        # Month 3: moderate month
        (5, "2026-09-01", "Income", "Freelance", 40000.0, "Regular month"),
        (6, "2026-09-05", "Expense", "Rent", 20000.0, "Rent"),
    ]
    # Median income = 40,000, Mean income = 63,333.33
    # Conservative baseline surplus uses median (40,000 - 20,000 = 20,000) instead of mean (43,333)
    plan = calculate_savings_plan(transactions, [])
    assert plan["status"] == "ok"
    assert plan["is_irregular_income"] is True
    assert plan["baseline_surplus"] == 20000.0


def test_savings_planning_deficit_and_empty():
    # Deficit: expenses > income
    transactions_deficit = [
        (1, "2026-09-01", "Income", "Salary", 20000.0, "Salary"),
        (2, "2026-09-05", "Expense", "Rent", 25000.0, "Rent"),
    ]
    plan_deficit = calculate_savings_plan(transactions_deficit, [(1, "Car", 100000.0, 0.0, "2027-01-01")])
    assert plan_deficit["feasibility"] == "deficit"
    assert plan_deficit["realistic_monthly_target"] == 0.0
    assert "cash flow" in plan_deficit["target_message"].lower()

    # Empty transactions
    plan_empty = calculate_savings_plan([], [])
    assert plan_empty["status"] == "insufficient"
    assert plan_empty["realistic_monthly_target"] == 0.0


# =========================================================================
# 4. EXPENSE FORECASTING & RELIABILITY TESTS
# =========================================================================

def test_forecasting_reliability_and_edge_cases():
    # 2 months of history -> ok status, low reliability rating
    tx_2_months = [
        (1, "2026-07-01", "Expense", "Food", 5000.0, "groceries"),
        (2, "2026-08-01", "Expense", "Food", 6000.0, "groceries"),
    ]
    pred_2 = predict_next_month_expenses(tx_2_months)
    assert pred_2["status"] == "ok"
    assert pred_2["reliability"] == "low"
    assert "Early trend estimate" in pred_2["reliability_message"]
    assert pred_2["is_estimate"] is True

    # 4 months of history -> moderate or high reliability
    tx_4_months = [
        (1, "2026-05-01", "Expense", "Food", 5000.0, "groceries"),
        (2, "2026-06-01", "Expense", "Food", 5200.0, "groceries"),
        (3, "2026-07-01", "Expense", "Food", 5400.0, "groceries"),
        (4, "2026-08-01", "Expense", "Food", 5600.0, "groceries"),
    ]
    pred_4 = predict_next_month_expenses(tx_4_months)
    assert pred_4["status"] == "ok"
    assert pred_4["reliability"] in ("moderate", "high")
    assert pred_4["mae"] is not None

    # Runaway protection: steep slope is clamped to realistic maximum bound
    tx_steep = [
        (1, "2026-07-01", "Expense", "Food", 1000.0, "groceries"),
        (2, "2026-08-01", "Expense", "Food", 20000.0, "groceries"),
    ]
    pred_steep = predict_next_month_expenses(tx_steep)
    assert pred_steep["status"] == "ok"
    assert pred_steep["amount"] <= 20000.0 * 2.5  # Clamped within safe multiple


# =========================================================================
# 5. ANOMALY DETECTION TESTS
# =========================================================================

def test_anomaly_detection_review_flags():
    tx_normal = [
        (1, "2026-09-01", "Expense", "Food", 500.0, "Lunch"),
        (2, "2026-09-02", "Expense", "Food", 600.0, "Dinner"),
        (3, "2026-09-03", "Expense", "Food", 550.0, "Lunch"),
        (4, "2026-09-04", "Expense", "Food", 520.0, "Groceries"),
        (5, "2026-09-05", "Expense", "Food", 5000.0, "Luxury Banquet"),  # Outlier
    ]
    res = detect_expense_anomalies(tx_normal)
    assert res["status"] == "ok"
    assert len(res["anomalies"]) >= 1

    outlier = res["anomalies"][0]
    assert outlier["amount"] == 5000.0
    assert "Flagged for review" in outlier["reason"]
    assert "not classified as fraud" in res["explanation"]
    assert outlier["severity"] in ("high", "moderate")


# =========================================================================
# 6. DATA INTEGRITY & USER ISOLATION TESTS
# =========================================================================

def test_smart_features_strict_user_isolation():
    u_alice = database.create_user("smart_alice", "password123")
    u_bob = database.create_user("smart_bob", "password456")

    today_str = date.today().strftime("%Y-%m-%d")

    # Alice has budget limit 5000 and spent 4500 (90% - warning)
    database.set_budget(u_alice, "Food", 5000.0)
    database.add_transaction(u_alice, today_str, "Expense", "Food", 4500.0, "Alice Food")

    # Bob has budget limit 10000 and spent 1000 (10% - no alert)
    database.set_budget(u_bob, "Food", 10000.0)
    database.add_transaction(u_bob, today_str, "Expense", "Food", 1000.0, "Bob Food")

    # Query Alice
    alice_tx = database.get_transactions(u_alice)
    alice_budgets = database.get_budgets(u_alice)
    alice_alerts = budget_alerts(alice_budgets, alice_tx)
    assert len(alice_alerts) == 1
    assert alice_alerts[0]["category"] == "Food"
    assert alice_alerts[0]["spent"] == 4500.0

    # Query Bob
    bob_tx = database.get_transactions(u_bob)
    bob_budgets = database.get_budgets(u_bob)
    bob_alerts = budget_alerts(bob_budgets, bob_tx)
    assert len(bob_alerts) == 0  # 10% is below 80% threshold
