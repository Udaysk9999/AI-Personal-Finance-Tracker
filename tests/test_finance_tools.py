"""Tests for finance_tools module: statement parsing, budget alerts, PDF generation."""

from datetime import date
import io

import pandas as pd

from finance_tools import budget_alerts, build_report_pdf, parse_statement


def test_parse_csv_statement():
    csv_data = b"Date,Amount,Type,Category,Description\n2026-09-01,1000,Credit,Salary,Salary\n2026-09-02,800,Debit,Food,Lunch\n"
    csv_file = io.BytesIO(csv_data)
    csv_file.name = "statement.csv"
    parsed = parse_statement(csv_file)
    assert len(parsed) == 2
    assert list(parsed["Type"]) == ["Income", "Expense"]


def test_budget_alerts_warning():
    budgets = [("Food", 1000.0)]
    curr_date = date.today().strftime("%Y-%m-%d")
    transactions = [(1, curr_date, "Expense", "Food", 800.0, "Lunch")]
    alerts = budget_alerts(budgets, transactions)
    # 800/1000 = 80% which is >= 75%, so should trigger a warning
    assert len(alerts) == 1
    assert alerts[0]["level"] == "warning"


def test_budget_alerts_empty():
    alerts = budget_alerts([("Food", 1000.0)], [])
    assert alerts == []


def test_build_report_pdf():
    transactions = [(1, "2026-09-01", "Income", "Salary", 50000.0, "Salary")]
    budgets = [("Food", 5000.0)]
    goals = [(1, "Emergency", 100000.0, 10000.0, "2027-01-01")]
    health = {"score": 65, "factors": {}, "suggestions": []}
    prediction = {"status": "insufficient", "message": "Not enough data"}
    alerts = [{"category": "Food", "spent": 4500.0, "limit": 5000.0, "percent": 0.9, "level": "warning"}]
    pdf = build_report_pdf("test-user", transactions, budgets, goals, health, prediction, alerts)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100


def test_build_report_pdf_custom_currency():
    transactions = [(1, "2026-09-01", "Expense", "Groceries", 150.0, "Supermarket")]
    budgets = [("Groceries", 500.0)]
    goals = []
    health = {"score": 80, "factors": {}, "suggestions": []}
    prediction = {"status": "ok", "amount": 180.0}
    alerts = [{"category": "Groceries", "spent": 150.0, "limit": 500.0, "percent": 0.3, "level": "info"}]
    pdf = build_report_pdf("john_doe", transactions, budgets, goals, health, prediction, alerts, currency="$")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100

