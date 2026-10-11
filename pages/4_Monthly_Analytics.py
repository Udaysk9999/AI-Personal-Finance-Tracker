import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from auth import require_login
from database import create_database, get_transactions
from utils import (
    inject_css,
    page_header,
    section_divider,
    metric_card,
    empty_state,
    format_currency,
    get_user_currency,
    theme_chart_colors,
)

st.set_page_config(page_title="Monthly Analytics", page_icon="📈", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Monthly Analytics & Trends",
    "Track cash flow trajectory, month-over-month variances, and historical income/expense records.",
    badge_text="Trends",
    icon="📈",
)

transactions = get_transactions(user_id)

if not transactions:
    empty_state(
        "No Transactions Recorded",
        "Add transactions across multiple months in Transaction Management to generate multi-month analytics.",
        icon="📈",
    )
    st.stop()

df = pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"])
df["Date"] = pd.to_datetime(df["Date"])
chart_colors = theme_chart_colors()
df["Month"] = df["Date"].dt.to_period("M").astype(str)

monthly = (
    df.groupby(["Month", "Type"])["Amount"].sum().unstack(fill_value=0).reset_index()
)
for col in ["Income", "Expense"]:
    if col not in monthly.columns:
        monthly[col] = 0.0
monthly = monthly.sort_values("Month")
monthly["Net"] = monthly["Income"] - monthly["Expense"]

# ==================================================
# TREND CHART
# ==================================================

st.subheader("Cash Flow Trajectory (Income vs. Expenses)")

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=monthly["Month"],
        y=monthly["Income"],
        name="Income",
        mode="lines+markers",
        line=dict(color="#10b981", width=3),
        marker=dict(size=7),
    )
)
fig.add_trace(
    go.Scatter(
        x=monthly["Month"],
        y=monthly["Expense"],
        name="Expense",
        mode="lines+markers",
        line=dict(color="#f43f5e", width=3),
        marker=dict(size=7),
    )
)

fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=chart_colors["font"]),
    xaxis=dict(title="Month", showgrid=False, color=chart_colors["axis"]),
    yaxis=dict(title=f"Amount ({curr})", gridcolor=chart_colors["grid"], color=chart_colors["axis"]),
    legend=dict(font=dict(color=chart_colors["legend"])),
    margin=dict(l=20, r=20, t=30, b=20),
)

st.plotly_chart(fig, use_container_width=True)

# ==================================================
# MONTH-OVER-MONTH COMPARISON
# ==================================================

section_divider()
st.subheader("Month-over-Month Variance")

if len(monthly) < 2:
    st.info("💡 Record transactions across at least two distinct months to unlock month-over-month percentage comparisons.")
else:
    current = monthly.iloc[-1]
    previous = monthly.iloc[-2]

    def pct_change(curr_val, prev_val):
        if prev_val == 0:
            return None
        return ((curr_val - prev_val) / prev_val) * 100

    income_change = pct_change(current["Income"], previous["Income"])
    expense_change = pct_change(current["Expense"], previous["Expense"])
    net_val = current["Net"]

    col1, col2, col3 = st.columns(3)

    with col1:
        delta_str = f"{income_change:+.1f}%" if income_change is not None else None
        metric_card(
            f"Income ({current['Month']})",
            format_currency(current["Income"]),
            delta=delta_str,
            accent="emerald",
            icon="📈",
            help_text="vs prior month",
        )

    with col2:
        delta_str = f"{expense_change:+.1f}%" if expense_change is not None else None
        metric_card(
            f"Expenses ({current['Month']})",
            format_currency(current["Expense"]),
            delta=delta_str,
            accent="rose",
            icon="📉",
            help_text="vs prior month",
        )

    with col3:
        metric_card(
            f"Net Savings ({current['Month']})",
            format_currency(net_val),
            accent="indigo" if net_val >= 0 else "rose",
            icon="💳",
            help_text="monthly surplus",
        )

    if expense_change is not None:
        if expense_change > 0:
            st.warning(
                f"**Spending Alert:** Your expenses increased by **{expense_change:.1f}%** in {current['Month']} compared to {previous['Month']}."
            )
        else:
            st.success(
                f"**Great Job:** Your expenses decreased by **{abs(expense_change):.1f}%** in {current['Month']} compared to {previous['Month']}."
            )

# ==================================================
# MONTHLY BREAKDOWN TABLE
# ==================================================

section_divider()
st.subheader("Monthly Historical Breakdown")

display_monthly = monthly.copy()
display_monthly["Income"] = display_monthly["Income"].apply(format_currency)
display_monthly["Expense"] = display_monthly["Expense"].apply(format_currency)
display_monthly["Net"] = display_monthly["Net"].apply(format_currency)

st.dataframe(
    display_monthly.rename(columns={"Month": "Billing Period"}),
    use_container_width=True,
    hide_index=True,
)
