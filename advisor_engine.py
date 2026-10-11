"""
AI Advisor Engine: deterministic financial summarization, goal planning,
budget warnings, and Gemini API query orchestration.

Grounded in authenticated user data only. Preserves strict user isolation.
"""

from datetime import date, datetime
import os
from pathlib import Path
import time
from typing import Any
import pandas as pd

from database import get_transactions, get_budgets, get_savings_goals
from finance_ml import (
    predict_next_month_expenses,
    detect_expense_anomalies,
    financial_health_score,
)
from utils import format_currency

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

DISCRETIONARY_CATEGORIES = {"Food", "Shopping", "Entertainment", "Travel", "Other Expense"}
ESSENTIAL_CATEGORIES = {"Rent", "Bills", "Healthcare", "Education"}


def load_gemini_api_key() -> str | None:
    """
    Safely retrieve the Gemini API key from environment, Streamlit secrets, or .env file.
    Does NOT print, log, or leak the key.
    """
    # 1. Environment variable
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()

    # 2. Streamlit secrets (lazy import so advisor_engine works outside Streamlit)
    try:
        import streamlit as _st
        if hasattr(_st, "secrets") and "GEMINI_API_KEY" in _st.secrets:
            key = _st.secrets["GEMINI_API_KEY"]
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
    Returns remaining amount, months remaining, and required monthly savings.
    """
    remaining = max(0.0, float(target_amount) - float(current_amount))
    months_remaining = None

    if target_date_str:
        try:
            target_dt = datetime.strptime(target_date_str.strip(), "%Y-%m-%d").date()
            today = date.today()
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


def build_financial_context(user_id: str, curr: str = "₹") -> dict[str, Any]:
    """
    Compile comprehensive, deterministic financial data for the authenticated user.
    Strictly isolated to user_id. Computes:
    - Current month income, expenses, net surplus, and category spending
    - Previous month income, expenses, and Month-over-Month comparisons
    - Historical monthly averages (income, expenses, surplus)
    - Essential vs. Discretionary spending breakdown
    - Active budgets, thresholds, and warning statuses
    - Savings milestones, target dates, and required monthly contributions
    - Realistic savings capacity (Conservative, Moderate, Aggressive)
    - Recent transactions
    - Explainable ML insights (Health Score, Next-Month Forecast, MAD Anomalies)
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
            "balance": 0.0,
            "savings_rate": 0.0,
            "current_month_name": today.strftime("%B %Y"),
            "current_month_income": 0.0,
            "current_month_expense": 0.0,
            "current_month_net": 0.0,
            "current_month_savings_rate": 0.0,
            "current_month_categories": [],
            "current_month_top_category": None,
            "mom_comparison": {"available": False, "message": "No transaction history recorded yet."},
            "monthly_averages": {"recorded_months": 0, "avg_income": 0.0, "avg_expense": 0.0, "avg_surplus": 0.0},
            "essential_vs_discretionary": {"discretionary_amount": 0.0, "essential_amount": 0.0, "discretionary_pct": 0.0},
            "category_spending": [],
            "highest_category": None,
            "budget_analysis": [],
            "has_budgets": bool(budgets),
            "savings_goals_analysis": [],
            "has_goals": bool(goals),
            "realistic_savings_capacity": {
                "available_surplus": 0.0,
                "conservative": 0.0,
                "moderate": 0.0,
                "aggressive": 0.0,
                "total_goal_demand": 0.0,
                "feasibility": "insufficient_data",
            },
            "recent_transactions": [],
            "ml_insights": {
                "health_score": None,
                "health_factors": {},
                "health_suggestions": [],
                "forecast_status": "insufficient",
                "forecast_amount": 0.0,
                "forecast_month": None,
                "forecast_categories": {},
                "anomalies": [],
            },
        }

    df = pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"])
    df["Date"] = pd.to_datetime(df["Date"])
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)

    income_df = df[df["Type"] == "Income"]
    expense_df = df[df["Type"] == "Expense"]

    total_income = float(income_df["Amount"].sum()) if not income_df.empty else 0.0
    total_expenses = float(expense_df["Amount"].sum()) if not expense_df.empty else 0.0
    net_balance = total_income - total_expenses
    savings_rate = ((net_balance / total_income) * 100) if total_income > 0 else 0.0

    # Current month data
    cur_month_mask = (df["Date"].dt.year == today.year) & (df["Date"].dt.month == today.month)
    cur_df = df[cur_month_mask]
    cur_income_df = cur_df[cur_df["Type"] == "Income"]
    cur_expense_df = cur_df[cur_df["Type"] == "Expense"]

    cur_month_income = float(cur_income_df["Amount"].sum()) if not cur_income_df.empty else 0.0
    cur_month_expense = float(cur_expense_df["Amount"].sum()) if not cur_expense_df.empty else 0.0
    cur_month_net = cur_month_income - cur_month_expense
    cur_month_savings_rate = ((cur_month_net / cur_month_income) * 100) if cur_month_income > 0 else 0.0

    # Current month categories ranked
    cur_month_categories = []
    cur_month_top_category = None
    if not cur_expense_df.empty:
        cur_cat_sums = cur_expense_df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        for cat, amt in cur_cat_sums.items():
            pct = (amt / cur_month_expense * 100) if cur_month_expense > 0 else 0.0
            cur_month_categories.append({"category": str(cat), "amount": float(amt), "percent": pct})
        if cur_month_categories:
            cur_month_top_category = cur_month_categories[0]

    # Previous month data and Month-over-Month comparison
    prev_year = today.year if today.month > 1 else today.year - 1
    prev_month_num = today.month - 1 if today.month > 1 else 12
    prev_month_label = datetime(prev_year, prev_month_num, 1).strftime("%B %Y")
    cur_month_label = today.strftime("%B %Y")

    prev_month_mask = (df["Date"].dt.year == prev_year) & (df["Date"].dt.month == prev_month_num)
    prev_df = df[prev_month_mask]
    prev_income_df = prev_df[prev_df["Type"] == "Income"]
    prev_expense_df = prev_df[prev_df["Type"] == "Expense"]

    prev_month_income = float(prev_income_df["Amount"].sum()) if not prev_income_df.empty else 0.0
    prev_month_expense = float(prev_expense_df["Amount"].sum()) if not prev_expense_df.empty else 0.0
    prev_month_net = prev_month_income - prev_month_expense

    mom_available = not prev_df.empty
    if mom_available:
        mom_expense_diff = cur_month_expense - prev_month_expense
        mom_expense_pct = ((mom_expense_diff / prev_month_expense) * 100) if prev_month_expense > 0 else None
        mom_income_diff = cur_month_income - prev_month_income
        mom_income_pct = ((mom_income_diff / prev_month_income) * 100) if prev_month_income > 0 else None

        mom_comparison = {
            "available": True,
            "previous_month_name": prev_month_label,
            "current_month_name": cur_month_label,
            "prev_income": prev_month_income,
            "prev_expense": prev_month_expense,
            "prev_net": prev_month_net,
            "expense_diff": mom_expense_diff,
            "expense_pct_change": mom_expense_pct,
            "income_diff": mom_income_diff,
            "income_pct_change": mom_income_pct,
            "is_overspending": mom_expense_diff > 0,
        }
    else:
        mom_comparison = {
            "available": False,
            "message": f"Previous month ({prev_month_label}) has no recorded transactions. At least two distinct billing months are needed for MoM comparisons.",
        }

    # Historical monthly baselines and averages
    df["MonthPeriod"] = df["Date"].dt.to_period("M")
    recorded_months = df["MonthPeriod"].nunique()
    monthly_incomes = df[df["Type"] == "Income"].groupby("MonthPeriod")["Amount"].sum()
    monthly_expenses = df[df["Type"] == "Expense"].groupby("MonthPeriod")["Amount"].sum()

    avg_monthly_income = float(monthly_incomes.mean()) if not monthly_incomes.empty else 0.0
    avg_monthly_expenses = float(monthly_expenses.mean()) if not monthly_expenses.empty else 0.0
    avg_monthly_surplus = avg_monthly_income - avg_monthly_expenses

    # Essential vs. Discretionary spending breakdown (Current Month or All-Time)
    active_expense_df = cur_expense_df if not cur_expense_df.empty else expense_df
    discretionary_amt = float(active_expense_df[active_expense_df["Category"].isin(DISCRETIONARY_CATEGORIES)]["Amount"].sum())
    essential_amt = float(active_expense_df[active_expense_df["Category"].isin(ESSENTIAL_CATEGORIES)]["Amount"].sum())
    active_tot_exp = float(active_expense_df["Amount"].sum()) if not active_expense_df.empty else 0.0
    disc_pct = (discretionary_amt / active_tot_exp * 100) if active_tot_exp > 0 else 0.0

    # Overall category spending breakdown (All-Time)
    category_spending = []
    highest_category = None
    if not expense_df.empty:
        cat_sums = expense_df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        for cat, amt in cat_sums.items():
            pct = (amt / total_expenses * 100) if total_expenses > 0 else 0.0
            category_spending.append({"category": str(cat), "amount": float(amt), "percent": pct})
        if category_spending:
            highest_category = category_spending[0]

    # Budget Analysis (Current Month)
    cur_spent_by_cat = cur_expense_df.groupby("Category")["Amount"].sum().to_dict() if not cur_expense_df.empty else {}
    budget_analysis = []
    for cat, limit in budgets:
        limit_val = float(limit)
        spent_val = float(cur_spent_by_cat.get(cat, 0.0))
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
    budget_analysis.sort(key=lambda x: x["percent_used"], reverse=True)

    # Savings Goals Analysis
    goals_analysis = []
    total_monthly_goal_demand = 0.0
    for goal_id, name, target, current, target_date in goals:
        target_val = float(target)
        current_val = float(current)
        plan = calculate_savings_goal_monthly_plan(target_val, current_val, target_date)
        req_month = plan["required_per_month"]
        if req_month:
            total_monthly_goal_demand += req_month
        goals_analysis.append({
            "id": goal_id,
            "name": name,
            "target": target_val,
            "current": current_val,
            "remaining": plan["remaining"],
            "target_date": plan["target_date"],
            "months_remaining": plan["months_remaining"],
            "required_per_month": req_month,
            "is_completed": current_val >= target_val and target_val > 0,
        })

    # Realistic Savings Capacity Estimation
    effective_surplus = cur_month_net if cur_month_income > 0 else max(0.0, avg_monthly_surplus)
    safe_surplus = max(0.0, effective_surplus)
    cons_save = safe_surplus * 0.50
    mod_save = safe_surplus * 0.75
    agg_save = safe_surplus * 0.90

    if effective_surplus <= 0:
        plan_feasibility = "deficit"
    elif total_monthly_goal_demand > 0 and effective_surplus < total_monthly_goal_demand:
        plan_feasibility = "tight"
    else:
        plan_feasibility = "comfortable"

    # Recent transactions (Last 8)
    recent_transactions = []
    recent_df = df.sort_values("Date", ascending=False).head(8)
    for _, row in recent_df.iterrows():
        recent_transactions.append({
            "date": row["Date"].strftime("%d %b %Y"),
            "type": row["Type"],
            "category": row["Category"],
            "amount": float(row["Amount"]),
            "description": str(row["Description"]) if row["Description"] else "—",
        })

    # ML Insights (Statistical / Heuristic)
    health = financial_health_score(transactions, budgets, goals)
    prediction = predict_next_month_expenses(transactions)
    anomalies_res = detect_expense_anomalies(transactions)

    # Clean MAD anomalies format
    clean_anomalies = []
    for anom in anomalies_res.get("anomalies", []):
        clean_anomalies.append({
            "date": anom.get("date") or anom.get("Date"),
            "category": anom.get("category") or anom.get("Category"),
            "amount": float(anom.get("amount") or anom.get("Amount") or 0.0),
            "reason": anom.get("reason") or anom.get("Reason", "Statistically high deviation"),
        })

    return {
        "has_data": True,
        "user_id": user_id,
        "curr": curr,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "balance": net_balance,
        "savings_rate": savings_rate,
        "current_month_name": cur_month_label,
        "current_month_income": cur_month_income,
        "current_month_expense": cur_month_expense,
        "current_month_net": cur_month_net,
        "current_month_savings_rate": cur_month_savings_rate,
        "current_month_categories": cur_month_categories,
        "current_month_top_category": cur_month_top_category,
        "mom_comparison": mom_comparison,
        "monthly_averages": {
            "recorded_months": recorded_months,
            "avg_income": avg_monthly_income,
            "avg_expense": avg_monthly_expenses,
            "avg_surplus": avg_monthly_surplus,
        },
        "essential_vs_discretionary": {
            "discretionary_amount": discretionary_amt,
            "essential_amount": essential_amt,
            "discretionary_pct": disc_pct,
        },
        "category_spending": category_spending,
        "highest_category": highest_category,
        "budget_analysis": budget_analysis,
        "has_budgets": bool(budgets),
        "savings_goals_analysis": goals_analysis,
        "has_goals": bool(goals),
        "realistic_savings_capacity": {
            "available_surplus": effective_surplus,
            "conservative": cons_save,
            "moderate": mod_save,
            "aggressive": agg_save,
            "total_goal_demand": total_monthly_goal_demand,
            "feasibility": plan_feasibility,
        },
        "recent_transactions": recent_transactions,
        "ml_insights": {
            "health_score": health.get("score"),
            "health_factors": health.get("factors", {}),
            "health_suggestions": health.get("suggestions", []),
            "forecast_status": prediction.get("status"),
            "forecast_amount": prediction.get("amount", 0.0),
            "forecast_month": prediction.get("month"),
            "forecast_categories": prediction.get("category_predictions", {}),
            "anomalies": clean_anomalies,
        },
    }


def format_context_for_prompt(ctx: dict[str, Any]) -> str:
    """
    Format the financial context dictionary into an unambiguous, structured prompt for Gemini.
    Provides complete facts to answer:
    1. "Analyze my spending this month"
    2. "Which category is costing me the most?"
    3. "Where can I reduce my expenses?"
    4. "Am I overspending compared with last month?"
    5. "How much can I realistically save next month?"
    6. "Which budgets are close to their limits?"
    7. "Suggest a savings plan based on my income and expenses"
    """
    curr = ctx.get("curr", "₹")
    if not ctx.get("has_data"):
        return f"User currency: {curr}. The user has zero recorded transactions currently."

    lines = [
        f"=== AUTHENTICATED USER FINANCIAL PROFILE (Currency: {curr}) ===",
        f"- All-Time Total Income: {format_currency(ctx['total_income'], curr)}",
        f"- All-Time Total Expenses: {format_currency(ctx['total_expenses'], curr)}",
        f"- Net Financial Balance: {format_currency(ctx['net_balance'], curr)}",
        f"- Overall Savings Rate: {ctx['savings_rate']:.1f}%",
        "",
        f"=== CURRENT MONTH PERFORMANCE ({ctx.get('current_month_name', 'This Month')}) ===",
        f"- Current Month Inflow (Income): {format_currency(ctx['current_month_income'], curr)}",
        f"- Current Month Outflow (Expenses): {format_currency(ctx['current_month_expense'], curr)}",
        f"- Current Month Net Surplus: {format_currency(ctx['current_month_net'], curr)}",
        f"- Current Month Savings Rate: {ctx['current_month_savings_rate']:.1f}%",
    ]

    # Current month ranked categories
    if ctx.get("current_month_categories"):
        lines.append("\nTop Categories This Month (Ranked):")
        for item in ctx["current_month_categories"]:
            lines.append(f"  • {item['category']}: {format_currency(item['amount'], curr)} ({item['percent']:.1f}% of month's spend)")
        if ctx.get("current_month_top_category"):
            top_m = ctx["current_month_top_category"]
            lines.append(f"Highest Spending Category This Month: '{top_m['category']}' ({format_currency(top_m['amount'], curr)})")
    else:
        lines.append("- No expense transactions recorded in the current month.")

    # Month-over-Month comparison
    lines.append("\n=== MONTH-OVER-MONTH (MoM) COMPARISON ===")
    mom = ctx.get("mom_comparison", {})
    if mom.get("available"):
        lines.append(f"Comparison: {mom['current_month_name']} vs. {mom['previous_month_name']}:")
        pct_str = f" ({mom['expense_pct_change']:+.1f}%)" if mom["expense_pct_change"] is not None else ""
        diff_str = f"+{format_currency(mom['expense_diff'], curr)}" if mom['expense_diff'] >= 0 else format_currency(mom['expense_diff'], curr)
        lines.append(f"- Expense Variance: {diff_str}{pct_str} (Prior month: {format_currency(mom['prev_expense'], curr)} -> Current: {format_currency(ctx['current_month_expense'], curr)})")
        lines.append(f"- Overspending Status: {'OVERSPENDING compared to prior month' if mom['is_overspending'] else 'SPENDING REDUCED compared to prior month'}")
        inc_diff_str = f"+{format_currency(mom['income_diff'], curr)}" if mom['income_diff'] >= 0 else format_currency(mom['income_diff'], curr)
        lines.append(f"- Income Variance: {inc_diff_str} (Prior month: {format_currency(mom['prev_income'], curr)} -> Current: {format_currency(ctx['current_month_income'], curr)})")
    else:
        lines.append(f"- MoM Variance Status: {mom.get('message', 'Data across multiple months needed')}")

    # Historical monthly baselines
    m_avg = ctx.get("monthly_averages", {})
    if m_avg.get("recorded_months", 0) > 0:
        lines.append(f"\n=== HISTORICAL BASELINES ({m_avg['recorded_months']} Distinct Recorded Month(s)) ===")
        lines.append(f"- Average Monthly Income: {format_currency(m_avg['avg_income'], curr)}")
        lines.append(f"- Average Monthly Expenses: {format_currency(m_avg['avg_expense'], curr)}")
        lines.append(f"- Average Monthly Net Surplus: {format_currency(m_avg['avg_surplus'], curr)}")

    # Essential vs. Discretionary spending
    evd = ctx.get("essential_vs_discretionary", {})
    lines.append("\n=== ESSENTIAL VS. DISCRETIONARY SPENDING ===")
    lines.append(f"- Discretionary Outflow (Shopping, Entertainment, Food/Dining, Travel): {format_currency(evd.get('discretionary_amount', 0.0), curr)} ({evd.get('discretionary_pct', 0.0):.1f}% of active spend)")
    lines.append(f"- Essential Outflow (Rent, Utilities/Bills, Healthcare, Education): {format_currency(evd.get('essential_amount', 0.0), curr)}")

    # Budgets & Utilization
    lines.append("\n=== CONFIGURED MONTHLY BUDGETS & ACTIVE UTILIZATION ===")
    if ctx.get("budget_analysis"):
        for b in ctx["budget_analysis"]:
            rem_str = f"Remaining cushion: {format_currency(b['remaining'], curr)}" if b['remaining'] >= 0 else f"OVER BUDGET by {format_currency(abs(b['remaining']), curr)}"
            lines.append(
                f"- Category '{b['category']}': Spent {format_currency(b['current_month_spent'], curr)} "
                f"of {format_currency(b['monthly_limit'], curr)} limit ({b['percent_used']:.1f}% used). {rem_str} [Status: {b['status'].upper()}]"
            )
        critical = [b for b in ctx["budget_analysis"] if b["status"] in ("over", "near")]
        if critical:
            lines.append(f"⚠️ Critical Budgets Requiring Attention: {', '.join([f'{c['category']} ({c['percent_used']:.1f}%)' for c in critical])}")
        else:
            lines.append("All category budgets are currently healthy (<75% utilized).")
    else:
        lines.append("No monthly category budgets configured yet by user.")

    # Savings goals & plan
    lines.append("\n=== SAVINGS GOALS & REQUIRED MONTHLY CONTRIBUTIONS ===")
    if ctx.get("savings_goals_analysis"):
        for g in ctx["savings_goals_analysis"]:
            if g.get("is_completed"):
                plan_str = "GOAL REACHED 🎉"
            elif g.get("required_per_month"):
                plan_str = f"Requires {format_currency(g['required_per_month'], curr)}/month over {g['months_remaining']} month(s)"
            else:
                plan_str = "No deadline date specified"
            lines.append(
                f"- Goal '{g['name']}': Saved {format_currency(g['current'], curr)} of {format_currency(g['target'], curr)} target. "
                f"Remaining: {format_currency(g['remaining'], curr)}. Target Date: {g['target_date'] or 'None'}. Plan: {plan_str}."
            )
    else:
        lines.append("No active savings milestones configured yet by user.")

    # Realistic savings capacity
    rsc = ctx.get("realistic_savings_capacity", {})
    lines.append("\n=== REALISTIC SAVINGS CAPACITY NEXT MONTH ===")
    lines.append(f"- Available Net Monthly Surplus: {format_currency(rsc.get('available_surplus', 0.0), curr)}")
    lines.append(f"- Total Required for Goals/Month: {format_currency(rsc.get('total_goal_demand', 0.0), curr)}")
    lines.append(f"- Recommended Savings Ranges:")
    lines.append(f"  * Conservative (50% of surplus): {format_currency(rsc.get('conservative', 0.0), curr)}")
    lines.append(f"  * Moderate / Target (75% of surplus): {format_currency(rsc.get('moderate', 0.0), curr)}")
    lines.append(f"  * Aggressive (90% of surplus): {format_currency(rsc.get('aggressive', 0.0), curr)}")
    lines.append(f"- Goal Affordability Feasibility: {rsc.get('feasibility', 'comfortable').upper()}")

    # Recent transactions
    if ctx.get("recent_transactions"):
        lines.append("\n=== RECENT TRANSACTIONS (Last 8 Entries) ===")
        for tx in ctx["recent_transactions"]:
            lines.append(f"- {tx['date']} | {tx['type']} | {tx['category']} | {format_currency(tx['amount'], curr)} | {tx['description']}")

    # ML Insights & Statistical Outliers
    ml = ctx.get("ml_insights", {})
    lines.append("\n=== STATISTICAL FORECASTS & DETECTED OUTLIERS (Estimates, not historical facts) ===")
    if ml.get("health_score") is not None:
        lines.append(f"- Financial Health Score: {ml['health_score']}/100")
        for sug in ml.get("health_suggestions", []):
            lines.append(f"  * Health Metric Suggestion: {sug}")

    if ml.get("forecast_status") == "ok":
        lines.append(f"- Next-Month Linear Forecast ({ml['forecast_month']}): Approx {format_currency(ml['forecast_amount'], curr)}")
        for cat, cat_amt in ml.get("forecast_categories", {}).items():
            lines.append(f"  * Forecasted {cat}: {format_currency(cat_amt, curr)}")
    else:
        lines.append("- Next-month trend forecast unavailable (at least 2 months of expense data required).")

    if ml.get("anomalies"):
        lines.append(f"- Detected Spending Spikes ({len(ml['anomalies'])} outlier(s) flagged by Median Absolute Deviation):")
        for anom in ml["anomalies"][:5]:
            lines.append(f"  * {anom.get('date')}: {anom.get('category')} - {format_currency(anom.get('amount', 0), curr)} ({anom.get('reason')})")
    else:
        lines.append("- No statistical spending anomalies detected.")

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
        f"2. Explicitly distinguish between:\n"
        f"   - ACTUAL historical facts (e.g. 'You spent {curr}12,000 this month')\n"
        f"   - DETERMINISTIC budget metrics (e.g. '{curr}2,000 remaining until limit')\n"
        f"   - STATISTICAL forecasts/estimates (e.g. 'Our trend model projects ~{curr}35,000 next month, which is an estimate')\n"
        f"   - YOUR recommendations.\n"
        f"3. Specific questions to answer with precise data:\n"
        f"   - 'Analyze my spending this month': State current month income, expenses, net surplus, and ranked categories.\n"
        f"   - 'Which category is costing me the most?': Cite the #1 category for current month and all-time with exact amounts and percentages.\n"
        f"   - 'Where can I reduce my expenses?': Examine discretionary spending (Shopping, Entertainment, Travel, Dining). Suggest a specific 10-20% trim with the exact monthly amount saved.\n"
        f"   - 'Am I overspending compared with last month?': Quote current vs previous month figures and percentage change. If multi-month data is unavailable, state clearly that historical data is needed.\n"
        f"   - 'How much can I realistically save next month?': Provide the recommended Moderate savings capacity (75% of surplus), reference the ML forecast, and explain why it is realistic.\n"
        f"   - 'Which budgets are close to their limits?': List categories with >=75% or >100% usage, citing current spend, monthly limit, and remaining cushion.\n"
        f"   - 'Suggest a savings plan based on my income and expenses': Compare total monthly goal requirements against the user's actual monthly surplus. State whether goals are comfortably funded or if a deficit exists.\n"
        f"4. If data is missing (e.g., no budgets set, no savings goals, or only 1 month of transactions), explicitly state what is missing and explain how the user can set it up in the app.\n"
        f"5. Do NOT promise financial returns or guarantee investment outcomes. Conclude major decisions with prudent financial warnings.\n"
        f"6. Keep responses well-structured with clear markdown headings, bullet points, and actionable next steps. Limit responses to under 280 words.\n\n"
        f"{data_summary}"
    )


def generate_advisor_reply(
    api_key: str,
    contents: list,
    system_instruction: str,
    model_name: str = DEFAULT_GEMINI_MODEL,
    max_retries: int = 2,
) -> tuple[str, str | None]:
    """
    Query Gemini via google-genai SDK with automatic retry for transient 503/server spikes.
    Returns (reply_text, error_message).
    Never logs or exposes the API key.
    """
    if not api_key:
        return "", "Missing Gemini API key. Configure GEMINI_API_KEY in .env, environment variable, or secrets.toml."

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "", "The 'google-genai' SDK is not installed. Please run 'pip install google-genai'."

    client = genai.Client(api_key=api_key)

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            if response and response.text:
                return response.text.strip(), None
            return "I analyzed your numbers, but could not produce a response. Please rephrase your question.", None
        except Exception as exc:
            last_err = exc
            err_str = str(exc)
            # If 503 or transient rate spike and retries remain, wait briefly and retry
            if ("503" in err_str or "UNAVAILABLE" in err_str.upper()) and attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            break

    # Format user-friendly error explanation without revealing secrets
    err_str = str(last_err)
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str.upper():
        msg = "⚠️ **Quota Limit Reached:** The Gemini API free-tier rate limit has been temporarily exceeded. Please wait a minute before sending your next inquiry."
    elif "404" in err_str:
        msg = f"⚠️ **Model Availability Error:** Model '{model_name}' was not found. Please verify that this model is accessible for your API key."
    elif "503" in err_str or "UNAVAILABLE" in err_str.upper():
        msg = "⚠️ **High Server Demand (503):** The Gemini model is experiencing temporary peak demand on Google's servers. Please try your question again in a moment."
    elif "API_KEY" in err_str.upper() or "403" in err_str or "UNAUTHENTICATED" in err_str.upper():
        msg = "⚠️ **Authentication Error:** The provided Gemini API key appears invalid or expired. Please check your key in `.env` or Google AI Studio."
    else:
        msg = f"⚠️ **Service Disruption:** Could not connect to Gemini ({type(last_err).__name__}). Your local financial data remains safe."

    return msg, str(last_err)
