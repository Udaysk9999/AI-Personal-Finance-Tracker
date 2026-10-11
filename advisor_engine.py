"""
AI Advisor Engine: deterministic financial summarization, goal planning,
budget warnings, and Gemini API query orchestration.
"""

from datetime import date, datetime
import os
from pathlib import Path
import pandas as pd
import streamlit as st

from database import get_transactions, get_budgets, get_savings_goals
from finance_ml import (
    predict_next_month_expenses,
    detect_expense_anomalies,
    financial_health_score,
)
from utils import format_currency

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


def load_gemini_api_key() -> str | None:
    """
    Safely retrieve the Gemini API key from environment, Streamlit secrets, or .env file.
    Does NOT print or leak the key to logs or UI.
    """
    # 1. Environment variable
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()

    # 2. Streamlit secrets
    try:
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            key = st.secrets["GEMINI_API_KEY"]
            if key and str(key).strip():
                return str(key).strip()
    except Exception:
        pass

    # 3. .env file in project root or current working directory
    for search_dir in (Path.cwd(), Path(__file__).resolve().parent):
        env_file = search_dir / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") or line.startswith("GEMINI_API_KEY ="):
                        _, val = line.split("=", 1)
                        val = val.strip().strip("'\"")
                        if val:
                            os.environ["GEMINI_API_KEY"] = val
                            return val
            except Exception:
                pass

    return None


def calculate_savings_goal_monthly_plan(target_amount: float, current_amount: float, target_date_str: str | None) -> dict:
    """
    Deterministic calculation of monthly contribution required to reach a goal.
    Returns months remaining, required monthly savings, and target date info.
    """
    remaining = max(0.0, float(target_amount) - float(current_amount))
    months_remaining = None

    if target_date_str:
        try:
            target_dt = datetime.strptime(target_date_str.strip(), "%Y-%m-%d").date()
            today = date.today()
            # Month difference calculation
            year_diff = target_dt.year - today.year
            month_diff = target_dt.month - today.month
            total_months = year_diff * 12 + month_diff
            if target_dt.day < today.day and total_months > 0:
                total_months = max(1, total_months - 1)
            months_remaining = max(1, total_months) if total_months > 0 else 1
        except Exception:
            months_remaining = None

    required_per_month = (remaining / months_remaining) if (months_remaining and months_remaining > 0) else None

    return {
        "remaining": remaining,
        "months_remaining": months_remaining,
        "required_per_month": required_per_month,
        "target_date": target_date_str,
    }


def build_financial_context(user_id: str, curr: str = "₹") -> dict:
    """
    Compile comprehensive, deterministic financial data for the authenticated user.
    Strictly isolated to user_id.
    """
    transactions = get_transactions(user_id)
    budgets = get_budgets(user_id)
    goals = get_savings_goals(user_id)

    today = date.today()

    if not transactions:
        return {
            "has_data": False,
            "user_id": user_id,
            "curr": curr,
            "total_income": 0.0,
            "total_expenses": 0.0,
            "net_balance": 0.0,
            "savings_rate": 0.0,
            "category_spending": [],
            "highest_category": None,
            "budget_analysis": [],
            "savings_goals_analysis": [],
            "ml_insights": {
                "health_score": None,
                "forecast": None,
                "anomalies": [],
            },
        }

    df = pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"])
    df["Date"] = pd.to_datetime(df["Date"])

    income_df = df[df["Type"] == "Income"]
    expense_df = df[df["Type"] == "Expense"]

    total_income = float(income_df["Amount"].sum()) if not income_df.empty else 0.0
    total_expenses = float(expense_df["Amount"].sum()) if not expense_df.empty else 0.0
    net_balance = total_income - total_expenses
    savings_rate = ((net_balance / total_income) * 100) if total_income > 0 else 0.0

    # Current month spending
    cur_month_expense = expense_df[
        (expense_df["Date"].dt.year == today.year) & (expense_df["Date"].dt.month == today.month)
    ]
    cur_month_spent_by_cat = cur_month_expense.groupby("Category")["Amount"].sum().to_dict() if not cur_month_expense.empty else {}
    cur_month_total_expense = float(cur_month_expense["Amount"].sum()) if not cur_month_expense.empty else 0.0

    # Category spending breakdown (overall)
    category_spending = []
    highest_category = None
    if not expense_df.empty:
        cat_sums = expense_df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        for cat, amt in cat_sums.items():
            pct = (amt / total_expenses * 100) if total_expenses > 0 else 0.0
            category_spending.append({
                "category": cat,
                "amount": float(amt),
                "percent": pct,
            })
        if category_spending:
            highest_category = category_spending[0]

    # Budget Analysis (Current Month)
    budget_analysis = []
    for cat, limit in budgets:
        limit_val = float(limit)
        spent_val = float(cur_month_spent_by_cat.get(cat, 0.0))
        rem_val = limit_val - spent_val
        pct_used = (spent_val / limit_val * 100) if limit_val > 0 else 0.0
        
        status = "over" if spent_val > limit_val else ("near" if pct_used >= 75.0 else "ok")
        budget_analysis.append({
            "category": cat,
            "monthly_limit": limit_val,
            "current_month_spent": spent_val,
            "remaining": rem_val,
            "percent_used": pct_used,
            "status": status,
        })

    # Sort budget analysis so categories closest to or exceeding limit are first
    budget_analysis.sort(key=lambda x: x["percent_used"], reverse=True)

    # Savings Goals Analysis
    goals_analysis = []
    for goal_id, name, target, current, target_date in goals:
        target_val = float(target)
        current_val = float(current)
        plan = calculate_savings_goal_monthly_plan(target_val, current_val, target_date)
        goals_analysis.append({
            "id": goal_id,
            "name": name,
            "target": target_val,
            "current": current_val,
            "remaining": plan["remaining"],
            "target_date": plan["target_date"],
            "months_remaining": plan["months_remaining"],
            "required_per_month": plan["required_per_month"],
        })

    # ML Insights (Statistical / Explainable)
    health = financial_health_score(transactions, budgets, goals)
    prediction = predict_next_month_expenses(transactions)
    anomalies_res = detect_expense_anomalies(transactions)

    return {
        "has_data": True,
        "user_id": user_id,
        "curr": curr,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "savings_rate": savings_rate,
        "current_month_expense": cur_month_total_expense,
        "category_spending": category_spending,
        "highest_category": highest_category,
        "budget_analysis": budget_analysis,
        "savings_goals_analysis": goals_analysis,
        "ml_insights": {
            "health_score": health.get("score"),
            "health_factors": health.get("factors", {}),
            "health_suggestions": health.get("suggestions", []),
            "forecast_status": prediction.get("status"),
            "forecast_amount": prediction.get("amount"),
            "forecast_month": prediction.get("month"),
            "forecast_categories": prediction.get("category_predictions", {}),
            "anomalies": anomalies_res.get("anomalies", []),
        },
    }


def format_context_for_prompt(ctx: dict) -> str:
    """
    Format the financial context dictionary into an unambiguous, structured prompt for Gemini.
    """
    curr = ctx.get("curr", "₹")
    if not ctx.get("has_data"):
        return f"User currency: {curr}. The user has zero recorded transactions currently."

    lines = [
        f"=== AUTHENTICATED USER FINANCIAL PROFILE (Currency: {curr}) ===",
        f"- Total Cumulative Income: {format_currency(ctx['total_income'], curr)}",
        f"- Total Cumulative Expenses: {format_currency(ctx['total_expenses'], curr)}",
        f"- Net Financial Balance: {format_currency(ctx['net_balance'], curr)}",
        f"- Overall Savings Rate: {ctx['savings_rate']:.1f}% of income",
        f"- Current Month Recorded Spend: {format_currency(ctx.get('current_month_expense', 0.0), curr)}",
    ]

    # Category breakdown
    lines.append("\n=== CATEGORY-WISE EXPENDITURE (All Time, Ranked by Spend) ===")
    for item in ctx["category_spending"]:
        lines.append(f"- {item['category']}: {format_currency(item['amount'], curr)} ({item['percent']:.1f}% of total spend)")

    if ctx.get("highest_category"):
        lines.append(f"Top Spending Category: {ctx['highest_category']['category']} ({format_currency(ctx['highest_category']['amount'], curr)})")

    # Budgets
    lines.append("\n=== CONFIGURED MONTHLY BUDGETS & CURRENT MONTH UTILIZATION ===")
    if ctx["budget_analysis"]:
        for b in ctx["budget_analysis"]:
            rem_str = f"Remaining: {format_currency(b['remaining'], curr)}" if b['remaining'] >= 0 else f"OVER BUDGET by {format_currency(abs(b['remaining']), curr)}"
            lines.append(
                f"- Category '{b['category']}': Spent {format_currency(b['current_month_spent'], curr)} "
                f"of {format_currency(b['monthly_limit'], curr)} limit ({b['percent_used']:.1f}% used). {rem_str} [Status: {b['status'].upper()}]"
            )
        # Category closest to exceeding limit
        closest = ctx["budget_analysis"][0]
        lines.append(f"Most critical budget category: '{closest['category']}' ({closest['percent_used']:.1f}% utilized).")
    else:
        lines.append("No monthly category budgets configured by the user yet.")

    # Savings goals
    lines.append("\n=== SAVINGS GOALS & REQUIRED MONTHLY CONTRIBUTIONS ===")
    if ctx["savings_goals_analysis"]:
        for g in ctx["savings_goals_analysis"]:
            plan_str = f"Requires approx {format_currency(g['required_per_month'], curr)}/month over {g['months_remaining']} month(s)" if g['required_per_month'] else "No fixed target date specified"
            lines.append(
                f"- Goal '{g['name']}': Saved {format_currency(g['current'], curr)} of {format_currency(g['target'], curr)} target. "
                f"Remaining: {format_currency(g['remaining'], curr)}. Target Date: {g['target_date'] or 'None'}. Plan: {plan_str}."
            )
    else:
        lines.append("No active savings goals configured by the user yet.")

    # ML Insights & Anomaly Detection
    ml = ctx.get("ml_insights", {})
    lines.append("\n=== STATISTICAL INSIGHTS & DETECTED OUTLIERS (Statistical Models, not historical facts) ===")
    if ml.get("health_score") is not None:
        lines.append(f"- Financial Health Score: {ml['health_score']}/100")
        for sug in ml.get("health_suggestions", []):
            lines.append(f"  * Algorithmic Suggestion: {sug}")

    if ml.get("forecast_status") == "ok":
        lines.append(f"- Next-Month Statistical Forecast ({ml['forecast_month']}): Approx {format_currency(ml['forecast_amount'], curr)}")
        for cat, cat_amt in ml.get("forecast_categories", {}).items():
            lines.append(f"  * Predicted {cat}: {format_currency(cat_amt, curr)}")

    if ml.get("anomalies"):
        lines.append(f"- Detected Spending Anomalies ({len(ml['anomalies'])} transaction(s) flagged by Median Absolute Deviation):")
        for anom in ml["anomalies"][:5]:
            lines.append(f"  * Date {anom.get('Date')}: Category {anom.get('Category')}, Amount {format_currency(anom.get('Amount', 0), curr)} ({anom.get('Description', 'No description')})")
    else:
        lines.append("- No unusual spending spikes detected by statistical anomaly tests.")

    return "\n".join(lines)


def get_advisor_system_instruction(curr: str = "₹", data_summary: str = "") -> str:
    """
    Construct the authoritative system instruction for Gemini.
    Enforces deterministic grounding in actual user numbers and practical financial rules.
    """
    return (
        f"You are the expert, cautious, and practical AI Personal Financial Advisor inside the "
        f"'AI-Powered Personal Expense Tracking & Budget Advisor' application. "
        f"The user operates in currency: {curr}.\n\n"
        f"You are provided below with an exact, deterministic calculation of the user's real transactions, "
        f"budgets, savings milestones, and ML anomaly insights.\n\n"
        f"CORE INSTRUCTIONS:\n"
        f"1. Ground all numbers strictly in the provided data summary. Never fabricate, guess, or invent financial values.\n"
        f"2. Clearly distinguish between ACTUAL historical spending, CALCULATED budget remaining amounts, "
        f"PREDICTED next-month forecasts, and your RECOMMENDATIONS.\n"
        f"3. When asked where to cut back or save, analyze their top discretionary categories (e.g. Shopping, Entertainment, Food) "
        f"and provide realistic, actionable trade-offs based on their exact spending.\n"
        f"4. When asked about savings goals, refer to the calculated monthly savings plan and evaluate whether their current monthly surplus "
        f"can support it. If they have a deficit, warn them honestly.\n"
        f"5. When asked about budget warnings, clearly cite which category is closest to its limit or over-budget, stating the limit, "
        f"actual spend, and remaining cushion.\n"
        f"6. Keep responses well-structured with clear markdown headings, bullet points, and actionable next steps. "
        f"Limit responses to under 280 words to keep them digestible.\n"
        f"7. You are not a licensed financial advisor or tax attorney; conclude with appropriate prudence when discussing major capital allocations.\n\n"
        f"{data_summary}"
    )
