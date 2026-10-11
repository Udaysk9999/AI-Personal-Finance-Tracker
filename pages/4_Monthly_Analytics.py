import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

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
    apply_chart_theme,
    FINANCE_COLOR_SEQUENCE,
)

st.set_page_config(page_title="Monthly Analytics", page_icon="📈", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Monthly Analytics & Trends",
    "Track cash flow trajectory, month-over-month variances, category breakdowns, and historical records.",
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
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
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
# CASH FLOW TRAJECTORY CHART
# ==================================================

st.subheader("Cash Flow Trajectory (Income vs. Expenses)")

fig_flow = go.Figure()
fig_flow.add_trace(
    go.Scatter(
        x=monthly["Month"],
        y=monthly["Income"],
        name="Income",
        mode="lines+markers",
        line=dict(color="#10b981", width=3, shape="spline"),
        marker=dict(size=8, color="#10b981"),
        hovertemplate="<b>Income</b><br>%{x}: " + curr + "%{y:,.2f}<extra></extra>",
    )
)
fig_flow.add_trace(
    go.Scatter(
        x=monthly["Month"],
        y=monthly["Expense"],
        name="Expense",
        mode="lines+markers",
        line=dict(color="#f43f5e", width=3, shape="spline"),
        marker=dict(size=8, color="#f43f5e"),
        hovertemplate="<b>Expense</b><br>%{x}: " + curr + "%{y:,.2f}<extra></extra>",
    )
)
apply_chart_theme(
    fig_flow,
    height=340,
    title="Monthly Cash Flow Over Time",
    x_title="Billing Month",
    y_title=f"Amount ({curr})",
)
st.plotly_chart(fig_flow, use_container_width=True)

# ==================================================
# MONTH-OVER-MONTH VARIANCE METRICS
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

section_divider()

# ==================================================
# TWO-COLUMN ANALYTICS: NET SURPLUS & STACKED CATEGORIES
# ==================================================

st.subheader("Monthly Savings & Category Spending Breakdown")

c_col1, c_col2 = st.columns([1.1, 1.2])

with c_col1:
    # Monthly Net Savings / Deficit Bar Chart
    net_colors = ["#10b981" if val >= 0 else "#f43f5e" for val in monthly["Net"]]
    fig_net = go.Figure()
    fig_net.add_trace(
        go.Bar(
            x=monthly["Month"],
            y=monthly["Net"],
            marker_color=net_colors,
            marker_line_width=0,
            hovertemplate="<b>Net Savings</b><br>%{x}: " + curr + "%{y:,.2f}<extra></extra>",
        )
    )
    apply_chart_theme(
        fig_net,
        height=330,
        title="Monthly Net Savings / Surplus",
        x_title="Month",
        y_title=f"Net Surplus ({curr})",
        show_legend=False,
    )
    st.plotly_chart(fig_net, use_container_width=True)

with c_col2:
    # Stacked Monthly Category Spend
    expense_df = df[df["Type"] == "Expense"]
    if not expense_df.empty:
        cat_monthly = (
            expense_df.groupby(["Month", "Category"])["Amount"]
            .sum()
            .unstack(fill_value=0)
            .reset_index()
        )
        fig_stack = go.Figure()
        categories = [col for col in cat_monthly.columns if col != "Month"]
        for idx, cat in enumerate(categories):
            color = FINANCE_COLOR_SEQUENCE[idx % len(FINANCE_COLOR_SEQUENCE)]
            fig_stack.add_trace(
                go.Bar(
                    x=cat_monthly["Month"],
                    y=cat_monthly[cat],
                    name=cat,
                    marker_color=color,
                    hovertemplate=f"<b>{cat}</b><br>%{{x}}: " + curr + "%{y:,.2f}<extra></extra>",
                )
            )
        apply_chart_theme(
            fig_stack,
            height=330,
            title="Monthly Expense Breakdown by Category",
            x_title="Month",
            y_title=f"Spent ({curr})",
            barmode="stack",
        )
        st.plotly_chart(fig_stack, use_container_width=True)
    else:
        st.info("No expense data recorded to build category breakdown chart.")

section_divider()

# ==================================================
# MONTHLY BREAKDOWN TABLE
# ==================================================

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
