import streamlit as st
import pandas as pd
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
    "Deep-dive spending analysis, AI-powered forecasting, anomaly detection, and financial simulations.",
    badge_text="Analytics",
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
chart_colors = theme_chart_colors()

total_income = float(df[df["Type"] == "Income"]["Amount"].sum())
total_expenses = float(df[df["Type"] == "Expense"]["Amount"].sum())
balance = total_income - total_expenses
expense_df = df[df["Type"] == "Expense"]

# ==================================================
# FINANCIAL SUMMARY
# ==================================================

st.subheader("Financial Summary")

sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
with sum_col1:
    metric_card("Total Income", format_currency(total_income), accent="emerald", icon="📈")
with sum_col2:
    metric_card("Total Expenses", format_currency(total_expenses), accent="rose", icon="📉")
with sum_col3:
    metric_card(
        "Current Balance",
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
        help_text="of income spent",
    )

section_divider()

# ==================================================
# SPENDING ANALYSIS
# ==================================================

st.subheader("Spending Analysis")

if expense_df.empty:
    st.info("Add an expense transaction to view category distribution and breakdown charts.")
else:
    col1, col2 = st.columns(2)

    category_expenses = (
        expense_df.groupby("Category")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
    )

    with col1:
        fig_category = px.pie(
            category_expenses,
            names="Category",
            values="Amount",
            title="Expense Distribution by Category",
            color_discrete_sequence=FINANCE_COLOR_SEQUENCE,
            hole=0.55,
        )
        fig_category.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=chart_colors["font"]),
            title_font=dict(size=16, color=chart_colors["title"]),
            legend=dict(font=dict(color=chart_colors["legend"])),
            margin=dict(l=20, r=20, t=60, b=20),
        )
        fig_category.update_traces(
            textposition="inside",
            textinfo="percent",
            marker=dict(line=dict(color=chart_colors["marker_line"], width=2)),
        )
        st.plotly_chart(fig_category, use_container_width=True)

    with col2:
        fig_bar = px.bar(
            category_expenses,
            x="Category",
            y="Amount",
            color="Category",
            title="Total Spend per Category",
            color_discrete_sequence=FINANCE_COLOR_SEQUENCE,
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=chart_colors["font"]),
            title_font=dict(size=16, color=chart_colors["title"]),
            xaxis=dict(title="Category", showgrid=False, color=chart_colors["axis"]),
            yaxis=dict(title=f"Amount ({curr})", gridcolor=chart_colors["grid"], color=chart_colors["axis"]),
            showlegend=False,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        fig_bar.update_traces(marker_line_width=0)
        st.plotly_chart(fig_bar, use_container_width=True)

# ==================================================
# SMART FINANCIAL INSIGHTS & BENCHMARKS
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
            help_text="of total income consumed",
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
            help_text="remaining after expenses",
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
st.caption("Heuristics and statistical models executed locally on your authenticated data.")

budgets = get_budgets(user_id)
goals = get_savings_goals(user_id)

prediction = predict_next_month_expenses(transactions)
health = financial_health_score(transactions, budgets, goals)
anomalies = detect_expense_anomalies(transactions)

tool_col1, tool_col2 = st.columns(2)

with tool_col1:
    st.subheader("🔮 Next-Month Expense Forecasting")
    if prediction["status"] == "ok":
        metric_card(
            f"Forecasted Total ({prediction['month']})",
            format_currency(prediction["amount"]),
            accent="indigo",
            icon="📈",
        )
        st.caption(f"ℹ️ {prediction['explanation']}")
        if prediction.get("mae") is not None:
            st.caption(f"Model holdout Mean Absolute Error: ~{format_currency(prediction['mae'])}.")
        if prediction.get("category_predictions"):
            with st.expander("Category-wise Forecast Breakdown"):
                for category, amount in prediction["category_predictions"].items():
                    st.write(f"• **{category}:** {format_currency(amount)}")
    else:
        st.info(prediction["message"])

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
    st.warning(f"Detected **{len(anomalies['anomalies'])}** statistically unusual transaction(s) using Median Absolute Deviation (MAD).")
    st.caption(anomalies["explanation"])
    st.dataframe(pd.DataFrame(anomalies["anomalies"]), use_container_width=True, hide_index=True)
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
    metric_card("Current Monthly Baseline Surplus", format_currency(simulation["current_surplus"]), accent="indigo")
with sim_metric_col2:
    diff_val = simulation["difference"]
    metric_card(
        "Simulated Monthly Surplus",
        format_currency(simulation["simulated_surplus"]),
        delta=f"+{format_currency(diff_val)}" if diff_val > 0 else None,
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
