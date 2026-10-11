import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import html

from auth import require_login
from database import create_database, get_transactions, get_budgets, get_savings_goals
from utils import (
    inject_css,
    page_header,
    section_divider,
    metric_card,
    empty_state,
    format_currency,
    get_user_currency,
    FINANCE_COLOR_SEQUENCE,
    theme_chart_colors,
    apply_chart_theme,
)
from finance_ml import (
    detect_expense_anomalies,
    financial_health_score,
    predict_next_month_expenses,
    simulate_finances,
)

st.set_page_config(page_title="Financial Analytics & ML Insights", page_icon="📊", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Financial Dashboard & ML Insights",
    "Deep-dive spending analytics, machine learning forecasting, anomaly detection, and scenario simulation.",
    badge_text="Analytics & ML",
    icon="📊",
)

transactions = get_transactions(user_id)

if not transactions:
    empty_state(
        "No Transaction Data Available",
        "Add transactions in Transaction Management to generate spending reports, anomaly detection, and predictive models.",
        icon="📊",
    )
    st.stop()

df = pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"])
df["Date"] = pd.to_datetime(df["Date"])
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
chart_colors = theme_chart_colors()

total_income = float(df[df["Type"] == "Income"]["Amount"].sum())
total_expenses = float(df[df["Type"] == "Expense"]["Amount"].sum())
balance = total_income - total_expenses
expense_df = df[df["Type"] == "Expense"]

# ==================================================
# FINANCIAL SUMMARY METRICS
# ==================================================

st.subheader("Financial Summary")

sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
with sum_col1:
    metric_card("Total Income", format_currency(total_income), accent="emerald", icon="📈")
with sum_col2:
    metric_card("Total Expenses", format_currency(total_expenses), accent="rose", icon="📉")
with sum_col3:
    metric_card(
        "Current Net Balance",
        format_currency(balance),
        accent="indigo" if balance >= 0 else "rose",
        icon="💳",
    )
with sum_col4:
    expense_rate = (total_expenses / total_income * 100) if total_income > 0 else 0.0
    metric_card(
        "Spending Ratio",
        f"{expense_rate:.1f}%",
        accent="cyan" if expense_rate < 70 else "amber",
        icon="📊",
        help_text="of total earnings",
    )

section_divider()

# ==================================================
# SPENDING ANALYSIS & INTERACTIVE CHARTS
# ==================================================

st.subheader("Category Spending Analytics")

if expense_df.empty:
    st.info("Add an expense transaction to view category distribution and breakdown charts.")
else:
    col1, col2 = st.columns([1.1, 1.2])

    category_expenses = (
        expense_df.groupby("Category")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
    )

    with col1:
        # Donut Chart with Center Annotation
        fig_category = go.Figure(
            data=[
                go.Pie(
                    labels=category_expenses["Category"],
                    values=category_expenses["Amount"],
                    hole=0.6,
                    marker=dict(
                        colors=FINANCE_COLOR_SEQUENCE,
                        line=dict(color=chart_colors["marker_line"], width=2),
                    ),
                    textposition="inside",
                    textinfo="percent",
                    hovertemplate="<b>%{label}</b><br>Spent: " + curr + "%{value:,.2f}<br>Share: %{percent}<extra></extra>",
                )
            ]
        )
        fig_category.add_annotation(
            text=f"<b>{format_currency(total_expenses)}</b><br><span style='font-size:11px; color:{chart_colors['axis']};'>Total Outflow</span>",
            x=0.5,
            y=0.5,
            font=dict(size=14, color=chart_colors["font"]),
            showarrow=False,
        )
        apply_chart_theme(fig_category, height=360, title="Expense Distribution by Category")
        st.plotly_chart(fig_category, use_container_width=True)

    with col2:
        # Category Spend Horizontal/Vertical Bar Chart
        fig_bar = go.Figure(
            data=[
                go.Bar(
                    x=category_expenses["Category"],
                    y=category_expenses["Amount"],
                    marker=dict(
                        color=FINANCE_COLOR_SEQUENCE[: len(category_expenses)],
                        line=dict(width=0),
                    ),
                    hovertemplate="<b>%{x}</b><br>Total Spent: " + curr + "%{y:,.2f}<extra></extra>",
                )
            ]
        )
        apply_chart_theme(
            fig_bar,
            height=360,
            title="Total Spend per Category",
            x_title="Category",
            y_title=f"Amount ({curr})",
            show_legend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ==================================================
# SMART FINANCIAL BENCHMARKS & STATUS
# ==================================================

if total_income > 0:
    expense_percentage = (total_expenses / total_income) * 100

    if not expense_df.empty:
        category_sums = expense_df.groupby("Category")["Amount"].sum()
        highest_category = category_sums.idxmax()
        highest_amount = category_sums.max()
    else:
        highest_category = "None"
        highest_amount = 0.0

    st.subheader("💡 Financial Benchmarks & Status")
    ins_col1, ins_col2, ins_col3 = st.columns(3)

    with ins_col1:
        metric_card(
            "Expense Burn Rate",
            f"{expense_percentage:.1f}%",
            accent="cyan" if expense_percentage < 60 else "amber",
            icon="🔥",
            help_text="of income consumed",
        )
    with ins_col2:
        metric_card(
            "Top Spend Category",
            str(highest_category),
            accent="rose",
            icon="🏷️",
            help_text=f"{format_currency(highest_amount)} total",
        )
    with ins_col3:
        metric_card(
            "Net Surplus / Balance",
            format_currency(balance),
            accent="emerald" if balance >= 0 else "rose",
            icon="💰",
            help_text="remaining unspent",
        )

    # Contextual recommendation
    if expense_percentage < 40:
        rec_title = "Exceptional Cash Flow"
        rec_text = "Your spending is well below your income. You have substantial surplus capacity to accelerate savings goals or investments."
        rec_type = "success"
    elif expense_percentage < 70:
        rec_title = "Healthy & Balanced"
        rec_text = "Your expenses are in a balanced range. Review your top spending category to ensure it aligns with your long-term priorities."
        rec_type = "info"
    else:
        rec_title = "High Spending Advisory"
        rec_text = "Your expenses are consuming over 70% of your earnings. Consider setting strict category limits in Budget Tracking to curb discretionary outflows."
        rec_type = "warning"

    if rec_type == "success":
        st.success(f"**{rec_title}:** {rec_text}")
    elif rec_type == "warning":
        st.warning(f"**{rec_title}:** {rec_text}")
    else:
        st.info(f"**{rec_title}:** {rec_text}")

section_divider()

# ==================================================
# AI & ML FINANCIAL TOOLS
# ==================================================

st.header("🤖 Machine Learning & Predictive Insights")
st.caption("Explainable statistical models and deterministic heuristics computed locally on your authenticated data.")

budgets = get_budgets(user_id)
goals = get_savings_goals(user_id)

prediction = predict_next_month_expenses(transactions)
health = financial_health_score(transactions, budgets, goals)
anomalies = detect_expense_anomalies(transactions)

tool_col1, tool_col2 = st.columns(2)

with tool_col1:
    st.subheader("🔮 Next-Month Expense Forecasting")
    if prediction["status"] == "ok":
        rel = prediction.get("reliability", "moderate")
        if rel == "high":
            rel_badge = '<span class="pft-badge pft-badge-emerald">High Confidence</span>'
        elif rel == "low":
            rel_badge = '<span class="pft-badge pft-badge-amber">Low Confidence (Sparse Data)</span>'
        else:
            rel_badge = '<span class="pft-badge pft-badge-indigo">Moderate Confidence</span>'

        metric_card(
            f"Forecasted Total ({prediction['month']})",
            format_currency(prediction["amount"]),
            accent="indigo",
            icon="📈",
            help_text=f"{prediction.get('history_months', 0)} months analyzed",
        )
        st.markdown(f"<div style='margin: 6px 0;'>{rel_badge} &nbsp; <span style='font-size: 0.85rem; color: var(--pft-text-secondary);'>{prediction.get('reliability_message', '')}</span></div>", unsafe_allow_html=True)
        st.caption(f"ℹ️ {prediction['explanation']}")
        if prediction.get("mae") is not None:
            st.caption(f"Model holdout Mean Absolute Error: ~{format_currency(prediction['mae'])}.")
        if prediction.get("category_predictions"):
            with st.expander("Category-wise Forecast Breakdown", expanded=False):
                for category, amount in prediction["category_predictions"].items():
                    st.write(f"• **{category}:** {format_currency(amount)}")
    else:
        st.info(f"ℹ️ {prediction['message']}")

with tool_col2:
    st.subheader("🩺 Financial Health Score")
    if health.get("score") is None:
        st.info(health["message"])
    else:
        score_val = health["score"]
        score_accent = "emerald" if score_val >= 70 else ("amber" if score_val >= 40 else "rose")
        metric_card("Overall Health Score", f"{score_val} / 100", accent=score_accent, icon="🏆")
        with st.expander("Score Factors & Actionable Suggestions", expanded=True):
            for factor, points in health["factors"].items():
                st.write(f"• **{factor}:** {points} pts")
            st.caption(health["explanation"])
            for suggestion in health["suggestions"]:
                st.markdown(f"👉 *{suggestion}*")

section_divider()

# ==================================================
# ANOMALY DETECTION & WHAT-IF SIMULATOR
# ==================================================

st.subheader("⚠️ Unusual Spending Anomaly Detection")
if anomalies["status"] != "ok":
    st.info(anomalies["message"])
elif anomalies["anomalies"]:
    st.warning(
        f"Detected **{len(anomalies['anomalies'])}** statistically unusual transaction(s) using Median Absolute Deviation (MAD). "
        "These entries are flagged for your review to verify accuracy; they are not classified as fraud."
    )
    st.caption(anomalies["explanation"])
    anom_df = pd.DataFrame(anomalies["anomalies"])
    if "amount" in anom_df.columns:
        anom_df["amount"] = anom_df["amount"].apply(lambda v: format_currency(v, curr))
    rename_cols = {"date": "Date", "category": "Category", "amount": "Amount", "severity": "Severity", "reason": "Detection Rationale"}
    display_cols = [c for c in ["date", "category", "amount", "severity", "reason"] if c in anom_df.columns]
    st.dataframe(anom_df[display_cols].rename(columns=rename_cols), use_container_width=True, hide_index=True)
else:
    st.success("✅ No anomalous or irregular spending spikes detected in your categories.")

section_divider()

st.subheader("🎯 What-If Financial Scenario Simulator")
st.caption("Simulate how saving more or cutting discretionary categories would accelerate your surplus and goals.")

sim_col1, sim_col2 = st.columns(2)
with sim_col1:
    extra_saving = st.number_input(f"Additional monthly contribution ({curr})", min_value=0.0, value=0.0, step=500.0, format="%.2f")
    expense_categories = sorted({row["Category"] for row in pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"]).to_dict("records") if row["Type"] == "Expense"})
    reduction_category = st.selectbox("Category to cut back", ["None"] + expense_categories)
with sim_col2:
    reduction_percent = st.slider("Reduction percentage (%)", 0, 100, 0, 5)
    simulation = simulate_finances(
        transactions,
        goals,
        extra_monthly_saving=extra_saving,
        category_reduction=None if reduction_category == "None" else reduction_category,
        reduction_percent=reduction_percent,
    )

sim_metric_col1, sim_metric_col2 = st.columns(2)
with sim_metric_col1:
    metric_card("Current Monthly Baseline Surplus", format_currency(simulation["current_surplus"], curr), accent="indigo")
with sim_metric_col2:
    diff_val = simulation["difference"]
    metric_card(
        "Simulated Monthly Surplus",
        format_currency(simulation["simulated_surplus"], curr),
        delta=f"+{format_currency(diff_val, curr)}" if diff_val > 0 else None,
        accent="emerald",
        help_text="extra monthly gain",
    )

if simulation["goal_estimates"]:
    with st.expander("Impact on Your Savings Goals", expanded=True):
        for estimate in simulation["goal_estimates"]:
            if estimate["months"] is None:
                st.write(f"• **{estimate['name']}:** Cannot estimate while simulated surplus is zero or negative.")
            else:
                st.write(f"• **{estimate['name']}:** ~**{estimate['months']} month(s)** needed for {format_currency(estimate['remaining'])} remaining.")
