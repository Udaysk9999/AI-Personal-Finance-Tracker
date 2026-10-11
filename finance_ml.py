"""Explainable data features for the logged-in user's finance data only.

The functions in this module accept already-filtered transaction/budget/goal data;
they never query the database or use data from another user.
"""
from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

import numpy as np
import pandas as pd


EXPENSE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Food": (
        "food", "grocery", "groceries", "swiggy", "zomato", "restaurant",
        "cafe", "lunch", "dinner", "breakfast", "snacks", "supermarket",
        "bakery", "mcdonald", "starbucks", "domino", "pizza", "burger",
        "subway", "kfc", "blinkit", "zepto", "instamart", "bigbasket",
        "dmart", "dunzo", "eatfit", "dining", "chai", "coffee",
    ),
    "Bills": (
        "electricity", "water bill", "internet", "wifi", "broadband",
        "mobile bill", "phone bill", "utility", "bill", "recharge",
        "airtel", "jio", "vi ", "vodafone", "tata power", "bescom",
        "gas", "lpg", "cylinder", "postpaid", "dth", "cable",
        "maintenance", "sewage",
    ),
    "Travel": (
        "uber", "ola", "taxi", "cab", "flight", "airline", "indigo",
        "air india", "train", "irctc", "railway", "bus", "redbus",
        "metro", "fuel", "petrol", "diesel", "cng", "parking",
        "toll", "fastag", "travel", "auto", "rapido", "commute", "fare",
    ),
    "Rent": (
        "rent", "lease", "landlord", "flat rent", "house rent", "room rent",
        "deposit", "accommodation", "society maintenance",
    ),
    "Shopping": (
        "amazon", "flipkart", "shopping", "clothes", "fashion", "mall",
        "myntra", "zara", "h&m", "ajio", "meesho", "retail", "store",
        "electronics", "shoes", "apparel", "footwear", "nike", "adidas",
        "puma", "uniqlo", "nykaa", "croma", "reliance digital",
    ),
    "Entertainment": (
        "netflix", "spotify", "movie", "cinema", "prime video", "game",
        "entertainment", "theatre", "pvr", "inox", "bookmyshow",
        "hotstar", "disney", "youtube premium", "playstation", "xbox",
        "steam", "concert", "amusement", "bowling",
    ),
    "Healthcare": (
        "doctor", "hospital", "medicine", "pharmacy", "health", "clinic",
        "dental", "dentist", "apollo", "medplus", "1mg", "pharmeasy",
        "pathology", "diagnostic", "blood test", "gym", "fitness",
        "cult.fit", "therapy", "consultation", "optician", "spectacles",
    ),
    "Education": (
        "course", "college", "school", "book", "tuition", "education",
        "udemy", "coursera", "university", "academy", "training",
        "fee", "exam", "stationary", "kindle", "textbook",
    ),
}

INCOME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Salary": (
        "salary", "payroll", "wages", "stipend", "paycheck",
        "employer", "monthly pay", "salary credit",
    ),
    "Freelance": (
        "freelance", "upwork", "fiverr", "client", "consulting",
        "contract", "gig", "project fee", "invoice payment",
    ),
    "Investment": (
        "dividend", "interest", "stock", "mutual fund", "zerodha",
        "groww", "capital gain", "crypto", "fd interest", "yield",
        "shares", "equity",
    ),
    "Bonus": (
        "bonus", "incentive", "appraisal", "reward", "commission",
        "performance pay", "ex-gratia",
    ),
    "Rental": (
        "rent received", "tenant", "rental income", "sublet",
    ),
}

ESSENTIAL_CATEGORIES = {"Rent", "Bills", "Healthcare", "Education"}
DISCRETIONARY_CATEGORIES = {"Food", "Shopping", "Entertainment", "Travel", "Other Expense"}


def transactions_frame(transactions) -> pd.DataFrame:
    columns = ["ID", "Date", "Type", "Category", "Amount", "Description"]
    frame = pd.DataFrame(transactions, columns=columns)
    if not frame.empty:
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame["Amount"] = pd.to_numeric(frame["Amount"], errors="coerce").fillna(0.0)
    return frame


def suggest_expense_category(
    description: str,
    user_transactions: list | None = None,
    fallback: bool = False,
) -> dict[str, str] | None:
    """
    Suggest an expense category using keyword matching, historical transactions,
    and a safe fallback when requested.
    """
    text = (description or "").strip().lower()
    if not text:
        return None

    # 1. Match against the user's historical transactions if provided
    if user_transactions:
        # Check exact or strong merchant match from user's own past logs
        for tx in user_transactions:
            # tx: (id, date, type, category, amount, description)
            if len(tx) >= 6 and str(tx[2]).lower() == "expense":
                past_desc = str(tx[5] or "").strip().lower()
                past_cat = str(tx[3] or "").strip()
                if past_desc and past_cat:
                    if text == past_desc:
                        return {
                            "category": past_cat,
                            "reason": f"Matched previous transaction with description '{tx[5]}'.",
                            "confidence": "high",
                        }
                    # Substring match if merchant name is distinct (>= 4 chars)
                    if len(past_desc) >= 4 and (past_desc in text or text in past_desc):
                        return {
                            "category": past_cat,
                            "reason": f"Similar to your past '{tx[5]}' expense.",
                            "confidence": "moderate",
                        }

    # 2. Match predefined keyword dictionary
    for category, keywords in EXPENSE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return {
                    "category": category,
                    "reason": f"Matched the description to keyword '{keyword}'.",
                    "confidence": "keyword",
                }

    # 3. Fallback if requested
    if fallback:
        return {
            "category": "Other Expense",
            "reason": "No keyword or transaction history pattern matched. Defaulted to 'Other Expense' for review.",
            "confidence": "fallback",
        }

    return None


def suggest_income_category(
    description: str,
    user_transactions: list | None = None,
    fallback: bool = False,
) -> dict[str, str] | None:
    """
    Suggest an income category using keyword matching, historical transactions,
    and a safe fallback when requested.
    """
    text = (description or "").strip().lower()
    if not text:
        return None

    # 1. Match against the user's historical income
    if user_transactions:
        for tx in user_transactions:
            if len(tx) >= 6 and str(tx[2]).lower() == "income":
                past_desc = str(tx[5] or "").strip().lower()
                past_cat = str(tx[3] or "").strip()
                if past_desc and past_cat:
                    if text == past_desc or (len(past_desc) >= 4 and past_desc in text):
                        return {
                            "category": past_cat,
                            "reason": f"Matched previous income record '{tx[5]}'.",
                            "confidence": "high",
                        }

    # 2. Match income keywords
    for category, keywords in INCOME_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return {
                    "category": category,
                    "reason": f"Matched the description to keyword '{keyword}'.",
                    "confidence": "keyword",
                }

    # 3. Fallback
    if fallback:
        return {
            "category": "Other Income",
            "reason": "No keyword or history pattern matched. Defaulted to 'Other Income' for review.",
            "confidence": "fallback",
        }

    return None


def suggest_category(
    description: str,
    tx_type: str = "Expense",
    user_transactions: list | None = None,
    fallback: bool = True,
) -> dict[str, str] | None:
    """
    Unified category suggestion for either Expense or Income.
    """
    if str(tx_type).lower() == "income":
        return suggest_income_category(description, user_transactions=user_transactions, fallback=fallback)
    return suggest_expense_category(description, user_transactions=user_transactions, fallback=fallback)


def predict_next_month_expenses(transactions) -> dict[str, Any]:
    """
    Predict next month's expenses using a trend regression over monthly totals.
    Provides clear explainability and highlights when data history is limited.
    """
    frame = transactions_frame(transactions)
    expenses = frame[frame["Type"] == "Expense"].copy()
    if expenses.empty:
        return {
            "status": "insufficient",
            "message": "Add expense transactions to generate a prediction.",
            "is_estimate": True,
        }

    monthly = (
        expenses.assign(Month=expenses["Date"].dt.to_period("M"))
        .groupby("Month")["Amount"]
        .sum()
        .sort_index()
    )

    if len(monthly) < 2:
        return {
            "status": "insufficient",
            "message": "At least two distinct billing months of expense history are needed for a trend prediction.",
            "is_estimate": True,
        }

    from sklearn.linear_model import LinearRegression

    x = np.arange(len(monthly), dtype=float).reshape(-1, 1)
    y = monthly.to_numpy(dtype=float)
    model = LinearRegression().fit(x, y)

    # Protect against negative predictions and runaway extrapolation
    raw_prediction = float(model.predict([[len(monthly)]])[0])
    max_observed = float(monthly.max())
    min_observed = float(monthly.min())
    # Cap between 0 and 2.5x max observed month to prevent runaway regression lines on 2-3 points
    prediction = max(0.0, min(raw_prediction, max(max_observed * 2.2, max_observed + 5000.0)))

    mae = None
    if len(monthly) >= 3:
        holdout = LinearRegression().fit(x[:-1], y[:-1]).predict([[len(monthly) - 1]])[0]
        mae = abs(float(y[-1] - holdout))

    # Reliability rating
    if len(monthly) == 2:
        reliability = "low"
        reliability_message = (
            "Early trend estimate based on only 2 recorded months. "
            "Predictions become more reliable as you record 3 or more months."
        )
    elif len(monthly) >= 5:
        reliability = "high"
        reliability_message = f"Based on {len(monthly)} consecutive recorded months of expense history."
    else:
        reliability = "moderate"
        reliability_message = f"Based on {len(monthly)} recorded months of expense history."

    category_predictions = {}
    if len(monthly) >= 3:
        category_monthly = (
            expenses.assign(Month=expenses["Date"].dt.to_period("M"))
            .pivot_table(index="Month", columns="Category", values="Amount", aggfunc="sum", fill_value=0)
            .sort_index()
        )
        for category in category_monthly.columns:
            values = category_monthly[category].to_numpy(dtype=float)
            if len(values) >= 3 and values.sum() > 0:
                category_model = LinearRegression().fit(
                    np.arange(len(values), dtype=float).reshape(-1, 1), values
                )
                cat_pred = float(category_model.predict([[len(values)]])[0])
                cat_max = float(values.max())
                category_predictions[category] = max(0.0, min(cat_pred, max(cat_max * 2.0, cat_max + 2000.0)))

    next_month = (monthly.index[-1] + 1).strftime("%B %Y")
    return {
        "status": "ok",
        "amount": round(prediction, 2),
        "month": next_month,
        "history_months": len(monthly),
        "mae": round(mae, 2) if mae is not None else None,
        "reliability": reliability,
        "reliability_message": reliability_message,
        "category_predictions": category_predictions,
        "is_estimate": True,
        "explanation": (
            "A linear trend regression was fitted to your monthly expense totals. "
            "This figure is a statistical projection, not a guaranteed forecast."
        ),
    }


def detect_expense_anomalies(transactions) -> dict[str, Any]:
    """
    Flag unusually high expenses for user review using robust per-category
    Median Absolute Deviation (MAD) thresholds.
    These flags are highlighted for review, not classified as fraud.
    """
    frame = transactions_frame(transactions)
    expenses = frame[frame["Type"] == "Expense"].copy()
    if len(expenses) < 5:
        return {
            "status": "insufficient",
            "message": "At least five expense transactions are needed for statistical anomaly detection.",
            "anomalies": [],
        }

    anomalies = []

    # Category-level outlier detection
    for category, group in expenses.groupby("Category"):
        values = group["Amount"]
        # Require at least 3 transactions in this category to establish a reliable category baseline
        if len(group) >= 3:
            median = float(values.median())
            mad = float((values - median).abs().median())
            # Minimum threshold cushion so normal small expenses are never flagged
            threshold = median + max(3.0 * mad, median * 0.75, 150.0)
            for _, row in group[group["Amount"] > threshold].iterrows():
                amt = float(row["Amount"])
                multiple = (amt / median) if median > 0 else 1.0
                anomalies.append({
                    "date": row["Date"].strftime("%d %b %Y"),
                    "category": str(category),
                    "amount": amt,
                    "reason": (
                        f"Flagged for review: {amt:,.2f} is unusually high for {category} "
                        f"(category median: {median:,.2f}, review threshold: {threshold:,.2f}, {multiple:.1f}x typical)."
                    ),
                    "severity": "high" if amt > threshold * 1.5 else "moderate",
                })
        else:
            # For categories with fewer than 3 transactions, check against overall expense distribution
            all_median = float(expenses["Amount"].median())
            all_mad = float((expenses["Amount"] - all_median).abs().median())
            global_threshold = all_median + max(3.5 * all_mad, all_median * 1.5, 500.0)
            for _, row in group[group["Amount"] > global_threshold].iterrows():
                amt = float(row["Amount"])
                anomalies.append({
                    "date": row["Date"].strftime("%d %b %Y"),
                    "category": str(category),
                    "amount": amt,
                    "reason": (
                        f"Flagged for review: {amt:,.2f} in {category} is an overall high-value transaction "
                        f"relative to account median ({all_median:,.2f})."
                    ),
                    "severity": "moderate",
                })

    anomalies.sort(key=lambda item: item["amount"], reverse=True)
    return {
        "status": "ok",
        "anomalies": anomalies,
        "explanation": (
            "Unusual transactions are flagged for your review to verify accuracy or unexpected price spikes; "
            "they are not classified as fraud."
        ),
    }


def calculate_savings_plan(transactions, goals, budgets=None) -> dict[str, Any]:
    """
    Calculate a realistic, data-grounded monthly savings plan for the authenticated user.
    - Uses actual income and expense baselines.
    - Handles irregular income and negative cash flow safely without misleading targets.
    - Clearly documents assumptions behind projections.
    """
    frame = transactions_frame(transactions)
    today = date.today()

    if frame.empty:
        return {
            "status": "insufficient",
            "message": "Add income and expense transactions to generate a personalized savings plan.",
            "realistic_monthly_target": 0.0,
            "conservative_target": 0.0,
            "aggressive_target": 0.0,
            "baseline_surplus": 0.0,
            "is_irregular_income": False,
            "goals_plan": [],
            "assumptions": "No financial history available.",
            "is_projection": True,
        }

    frame["Month"] = frame["Date"].dt.to_period("M")
    n_months = int(frame["Month"].nunique())

    monthly_income = frame[frame["Type"] == "Income"].groupby("Month")["Amount"].sum()
    monthly_expense = frame[frame["Type"] == "Expense"].groupby("Month")["Amount"].sum()

    total_income = float(monthly_income.sum()) if not monthly_income.empty else 0.0
    total_expense = float(monthly_expense.sum()) if not monthly_expense.empty else 0.0

    mean_income = float(monthly_income.mean()) if not monthly_income.empty else 0.0
    median_income = float(monthly_income.median()) if not monthly_income.empty else 0.0
    mean_expense = float(monthly_expense.mean()) if not monthly_expense.empty else 0.0
    median_expense = float(monthly_expense.median()) if not monthly_expense.empty else 0.0

    # Irregular income detection: coefficient of variation > 0.35 across 2+ months
    is_irregular_income = False
    if len(monthly_income) >= 2 and mean_income > 0:
        income_cv = float(monthly_income.std()) / mean_income
        if income_cv > 0.35:
            is_irregular_income = True

    # Conservative baseline: if income is volatile, use median to prevent over-committing
    baseline_income = min(median_income, mean_income) if is_irregular_income else mean_income
    baseline_expense = max(median_expense, mean_expense) if is_irregular_income else mean_expense
    baseline_surplus = baseline_income - baseline_expense

    # Realistic savings targets (Moderate = 70% of safe surplus, Conservative = 50%, Aggressive = 85%)
    if baseline_surplus <= 0:
        conservative = 0.0
        moderate = 0.0
        aggressive = 0.0
        feasibility = "deficit"
        target_message = (
            "Monthly expenses currently equal or exceed income. "
            "Focus on trimming discretionary expenses to restore positive cash flow before committing to new savings targets."
        )
    else:
        conservative = round(baseline_surplus * 0.50, 2)
        moderate = round(baseline_surplus * 0.70, 2)
        aggressive = round(baseline_surplus * 0.85, 2)
        feasibility = "positive"
        target_message = (
            f"Recommended target is ~{moderate:,.2f}/month (70% of regular net surplus), "
            f"preserving a 30% cushion ({baseline_surplus * 0.30:,.2f}) for unforeseen expenses."
        )

    # Goal feasibility and timelines
    goals_plan = []
    total_monthly_demand = 0.0

    for goal in (goals or []):
        # goal: (id, name, target, current, target_date)
        goal_id, name, target, current, target_date = goal[:5]
        target_val = float(target)
        current_val = float(current)
        remaining = max(0.0, target_val - current_val)

        months_remaining = None
        required_per_month = None

        if target_date:
            try:
                target_dt = datetime.strptime(str(target_date).strip(), "%Y-%m-%d").date()
                year_diff = target_dt.year - today.year
                month_diff = target_dt.month - today.month
                total_m = year_diff * 12 + month_diff
                if target_dt.day < today.day and total_m > 0:
                    total_m = max(1, total_m - 1)
                months_remaining = max(1, total_m) if total_m > 0 else 1
                required_per_month = round(remaining / months_remaining, 2)
                total_monthly_demand += required_per_month
            except Exception:
                months_remaining = None
                required_per_month = None

        # Estimated months at realistic savings rate
        if remaining == 0:
            status = "completed"
            months_at_target = 0
        elif moderate <= 0:
            status = "deficit"
            months_at_target = None
        else:
            months_at_target = max(1, int(np.ceil(remaining / moderate)))
            if required_per_month is not None:
                if required_per_month <= moderate:
                    status = "on_track"
                elif required_per_month <= baseline_surplus * 0.90:
                    status = "tight"
                else:
                    status = "extended_timeline_needed"
            else:
                status = "open_ended"

        goals_plan.append({
            "id": goal_id,
            "name": name,
            "target": target_val,
            "current": current_val,
            "remaining": remaining,
            "target_date": target_date,
            "months_to_deadline": months_remaining,
            "required_per_month": required_per_month,
            "estimated_months_at_target": months_at_target,
            "status": status,
        })

    assumptions = (
        f"Assumptions: Baseline regular monthly income of ~{baseline_income:,.2f}, "
        f"living expenses of ~{baseline_expense:,.2f}, and an allocation of 70% of estimated net surplus. "
        f"{'Caution: Irregular income detected; conservative median applied. ' if is_irregular_income else ''}"
        "All calculations are projections based on historical data and do not guarantee future performance."
    )

    return {
        "status": "ok",
        "feasibility": feasibility,
        "n_months": n_months,
        "mean_income": round(mean_income, 2),
        "mean_expense": round(mean_expense, 2),
        "baseline_surplus": round(baseline_surplus, 2),
        "realistic_monthly_target": moderate,
        "conservative_target": conservative,
        "aggressive_target": aggressive,
        "target_message": target_message,
        "is_irregular_income": is_irregular_income,
        "total_monthly_demand": round(total_monthly_demand, 2),
        "goals_plan": goals_plan,
        "assumptions": assumptions,
        "is_projection": True,
    }


def financial_health_score(transactions, budgets, goals) -> dict[str, Any]:
    """Calculate a deterministic 0-100 score from five explainable factors."""
    frame = transactions_frame(transactions)
    income = float(frame.loc[frame["Type"] == "Income", "Amount"].sum()) if not frame.empty else 0.0
    expense = float(frame.loc[frame["Type"] == "Expense", "Amount"].sum()) if not frame.empty else 0.0
    if income <= 0 and expense <= 0:
        return {"score": None, "message": "Add income and expense transactions to calculate your financial health score."}

    savings_rate = max(-1.0, min(1.0, (income - expense) / income)) if income else -1.0
    savings_factor = max(0.0, min(25.0, savings_rate * 25.0))
    ratio_factor = max(0.0, min(25.0, (1.0 - (expense / income if income else 2.0)) * 25.0))

    monthly_budget_rows = []
    for category, limit in budgets:
        category_spend = float(frame.loc[(frame["Type"] == "Expense") & (frame["Category"] == category), "Amount"].sum())
        monthly_budget_rows.append(min(1.0, float(limit) / max(category_spend, float(limit))))
    budget_factor = (sum(monthly_budget_rows) / len(monthly_budget_rows) * 20.0) if monthly_budget_rows else 10.0

    goal_progress = [min(1.0, float(current) / float(target)) for _, _, target, current, _ in goals if float(target) > 0]
    goal_factor = (sum(goal_progress) / len(goal_progress) * 15.0) if goal_progress else 7.5

    months = frame["Date"].dt.to_period("M").nunique() if not frame.empty else 0
    consistency_factor = min(15.0, months * 3.0)
    score = round(max(0.0, min(100.0, savings_factor + ratio_factor + budget_factor + goal_factor + consistency_factor)))
    factors = {
        "Savings rate": round(savings_factor, 1),
        "Expense-to-income ratio": round(ratio_factor, 1),
        "Budget adherence": round(budget_factor, 1),
        "Savings-goal progress": round(goal_factor, 1),
        "Saving consistency": round(consistency_factor, 1),
    }
    suggestions = []
    if savings_rate < 0: suggestions.append("Reduce discretionary expenses so monthly cash flow becomes positive.")
    elif savings_rate < 0.2: suggestions.append("Try to build the savings rate toward 20% of income.")
    if budget_factor < 14: suggestions.append("Review categories that are close to or above their budgets.")
    if not goals: suggestions.append("Create a savings goal to give your surplus a measurable purpose.")
    return {"score": score, "factors": factors, "suggestions": suggestions or ["Your indicators are balanced; keep reviewing them monthly."], "explanation": "The score is the sum of five weighted indicators: savings rate (25), expense ratio (25), budget adherence (20), goal progress (15), and month-to-month consistency (15)."}


def simulate_finances(transactions, goals, extra_monthly_saving=0.0, category_reduction=None, reduction_percent=0.0) -> dict[str, Any]:
    frame = transactions_frame(transactions)
    if frame.empty:
        baseline_income = baseline_expenses = 0.0
    else:
        frame["Month"] = frame["Date"].dt.to_period("M")
        months = max(1, int(frame["Month"].nunique()))
        baseline_income = float(frame.loc[frame["Type"] == "Income", "Amount"].sum()) / months
        baseline_expenses = float(frame.loc[frame["Type"] == "Expense", "Amount"].sum()) / months

    current_surplus = baseline_income - baseline_expenses

    category_savings = 0.0
    if category_reduction and not frame.empty:
        cat_total = float(frame.loc[(frame["Type"] == "Expense") & (frame["Category"] == category_reduction), "Amount"].sum())
        monthly_cat_expense = cat_total / max(1, int(frame["Month"].nunique()))
        category_savings = monthly_cat_expense * max(0.0, min(100.0, float(reduction_percent))) / 100.0

    simulated_expenses = max(0.0, baseline_expenses - category_savings)
    simulated_surplus = baseline_income - simulated_expenses + max(0.0, float(extra_monthly_saving))
    difference = simulated_surplus - current_surplus

    goal_estimates = []
    for _, name, target, current, _ in goals:
        remaining = max(0.0, float(target) - float(current))
        months = None if simulated_surplus <= 0 else int((remaining + simulated_surplus - 1) // simulated_surplus)
        goal_estimates.append({"name": name, "remaining": remaining, "months": months})

    return {
        "current_surplus": current_surplus,
        "simulated_surplus": simulated_surplus,
        "difference": difference,
        "goal_estimates": goal_estimates,
    }
