import streamlit as st
from datetime import date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from auth import require_login
from database import (
    create_database,
    add_transaction,
    get_transactions,
    get_budgets,
    get_savings_goals,
)
from utils import (
    inject_css,
    page_header,
    section_divider,
    metric_card,
    empty_state,
    format_currency,
    get_user_currency,
    INCOME_CATEGORIES,
    EXPENSE_CATEGORIES,
    FINANCE_COLOR_SEQUENCE,
    theme_chart_colors,
)
from finance_tools import budget_alerts
from finance_ml import suggest_expense_category

st.set_page_config(
    page_title="AI-Powered Personal Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    title="Financial Overview",
    subtitle=f"Welcome back, {username}. Here is your real-time financial health, budget progress, and spending trends.",
    badge_text="Live Dashboard",
    icon="📊",
)

# Fetch user data
transactions = get_transactions(user_id)
budgets = get_budgets(user_id)
goals = get_savings_goals(user_id)
chart_colors = theme_chart_colors()

# ==================================================
# FINANCIAL SUMMARY METRICS
# ==================================================

if transactions:
    df = pd.DataFrame(
        transactions,
        columns=["ID", "Date", "Type", "Category", "Amount", "Description"],
    )
    df["Date"] = pd.to_datetime(df["Date"])

    total_income = float(df[df["Type"] == "Income"]["Amount"].sum())
    total_expenses = float(df[df["Type"] == "Expense"]["Amount"].sum())
    balance = total_income - total_expenses
    savings_rate = ((balance / total_income) * 100) if total_income > 0 else 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total Income", format_currency(total_income), accent="emerald", icon="📈")
    with col2:
        metric_card("Total Expenses", format_currency(total_expenses), accent="rose", icon="📉")
    with col3:
        metric_card(
            "Current Balance",
            format_currency(balance),
            accent="indigo" if balance >= 0 else "rose",
            icon="💳",
        )
    with col4:
        savings_delta = f"{savings_rate:.1f}%" if total_income > 0 else "0.0%"
        metric_card(
            "Savings Rate",
            savings_delta,
            delta=f"{savings_rate:+.1f}%" if total_income > 0 else None,
            accent="cyan" if savings_rate >= 20 else "amber",
            icon="🎯",
            help_text="of total income",
        )
else:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total Income", format_currency(0), accent="emerald", icon="📈")
    with col2:
        metric_card("Total Expenses", format_currency(0), accent="rose", icon="📉")
    with col3:
        metric_card("Current Balance", format_currency(0), accent="indigo", icon="💳")
    with col4:
        metric_card("Savings Rate", "0.0%", accent="cyan", icon="🎯")

# ==================================================
# QUICK ACTIONS
# ==================================================

with st.expander("⚡ Quick Add Transaction", expanded=False):
    t_type = st.selectbox("Transaction Type", ["Expense", "Income"], key="quick_t_type")
    cat_options = EXPENSE_CATEGORIES if t_type == "Expense" else INCOME_CATEGORIES
    
    with st.form("quick_add_form", clear_on_submit=True):
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            q_date = st.date_input("Date", date.today(), key="quick_date")
            q_category = st.selectbox("Category", cat_options, key="quick_cat")
        with q_col2:
            q_amount = st.number_input(f"Amount ({curr})", min_value=0.0, step=100.0, format="%.2f", key="quick_amt")
            q_desc = st.text_input("Description", placeholder="e.g. Grocery run, Freelance project...", key="quick_desc")

        q_submit = st.form_submit_button("Save Transaction", type="primary")
        if q_submit:
            if q_amount <= 0:
                st.error(f"Please enter an amount greater than {curr}0.00")
            else:
                add_transaction(user_id, str(q_date), t_type, q_category, q_amount, q_desc.strip())
                st.success("Transaction recorded successfully!")
                st.rerun()

section_divider()

# ==================================================
# VISUAL ANALYTICS: TRENDS & BREAKDOWN
# ==================================================

if transactions:
    st.subheader("Financial Analytics & Breakdown")
    chart_col1, chart_col2 = st.columns([1.2, 1])

    with chart_col1:
        # Monthly spending and income trends
        df["Month"] = df["Date"].dt.to_period("M").astype(str)
        monthly_summary = (
            df.groupby(["Month", "Type"])["Amount"].sum().unstack(fill_value=0).reset_index()
        )
        for col_name in ["Income", "Expense"]:
            if col_name not in monthly_summary.columns:
                monthly_summary[col_name] = 0.0
        monthly_summary = monthly_summary.sort_values("Month")

        fig_trend = go.Figure()
        fig_trend.add_trace(
            go.Bar(
                x=monthly_summary["Month"],
                y=monthly_summary["Income"],
                name="Income",
                marker_color="#10b981",
            )
        )
        fig_trend.add_trace(
            go.Bar(
                x=monthly_summary["Month"],
                y=monthly_summary["Expense"],
                name="Expense",
                marker_color="#f43f5e",
            )
        )
        fig_trend.update_layout(
            title="Monthly Cash Flow (Income vs. Expense)",
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=chart_colors["font"]),
            xaxis=dict(title="Month", showgrid=False, color=chart_colors["axis"]),
            yaxis=dict(title=f"Amount ({curr})", gridcolor=chart_colors["grid"], color=chart_colors["axis"]),
            legend=dict(font=dict(color=chart_colors["legend"])),
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with chart_col2:
        # Expense category distribution
        expense_df = df[df["Type"] == "Expense"]
        if not expense_df.empty:
            cat_totals = (
                expense_df.groupby("Category")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
            )
            fig_pie = px.pie(
                cat_totals,
                names="Category",
                values="Amount",
                title="Expense Distribution by Category",
                color_discrete_sequence=FINANCE_COLOR_SEQUENCE,
                hole=0.55,
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=chart_colors["font"]),
                title_font=dict(size=16, color=chart_colors["title"]),
                legend=dict(font=dict(color=chart_colors["legend"])),
                margin=dict(l=20, r=20, t=50, b=20),
            )
            fig_pie.update_traces(
                textposition="inside",
                textinfo="percent",
                marker=dict(line=dict(color=chart_colors["marker_line"], width=2)),
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense transactions recorded yet to display category breakdown.")

    section_divider()

# ==================================================
# BUDGETS & SAVINGS GOALS PROGRESS
# ==================================================

b_col, g_col = st.columns(2)

with b_col:
    st.subheader("🎯 Monthly Budget Tracking")
    today = date.today()
    if budgets:
        alerts = budget_alerts(budgets, transactions)
        if alerts:
            for alert in alerts:
                if alert["level"] == "over":
                    st.error(f"⚠️ **{alert['category']}** is over budget! ({format_currency(alert['spent'])} of {format_currency(alert['limit'])})")
                else:
                    st.warning(f"⚡ **{alert['category']}** is at {alert['percent']*100:.0f}% of budget limit.")

        # Calculate spending for this month per budget category
        if transactions:
            cur_month_expenses = df[
                (df["Type"] == "Expense")
                & (df["Date"].dt.year == today.year)
                & (df["Date"].dt.month == today.month)
            ]
            spent_map = cur_month_expenses.groupby("Category")["Amount"].sum().to_dict()
        else:
            spent_map = {}

        for category, limit in budgets:
            spent = float(spent_map.get(category, 0.0))
            pct = min(spent / limit, 1.0) if limit > 0 else 0.0
            over = spent > limit
            
            status_text = "Over Budget" if over else ("Near Limit" if pct >= 0.75 else "Healthy")
            st.markdown(
                f"**{category}** — {format_currency(spent)} / {format_currency(limit)} "
                f"<span style='float: right; font-size: 0.85rem; font-weight: 600; color: {'#f43f5e' if over else ('#f59e0b' if pct >= 0.75 else '#10b981')}'>{status_text}</span>",
                unsafe_allow_html=True,
            )
            st.progress(pct)
            st.caption(f"{pct * 100:.1f}% utilized{' — over by ' + format_currency(spent - limit) if over else ''}")
    else:
        empty_state(
            "No Budgets Set",
            "Set monthly spending limits on the Budget Tracking page to monitor expenses and prevent overspending.",
            icon="🎯",
        )

with g_col:
    st.subheader("🏦 Savings Goals Progress")
    if goals:
        for goal_id, name, target, current, target_date in goals:
            pct = min(current / target, 1.0) if target > 0 else 0.0
            remaining = max(target - current, 0.0)
            target_str = f"Target date: {target_date}" if target_date else "No date set"
            
            st.markdown(
                f"**{name}** — {format_currency(current)} / {format_currency(target)} "
                f"<span style='float: right; font-size: 0.85rem; color: var(--pft-text-muted);'>{target_str}</span>",
                unsafe_allow_html=True,
            )
            st.progress(pct)
            st.caption(f"{pct * 100:.1f}% reached • {format_currency(remaining)} remaining")
    else:
        empty_state(
            "No Savings Goals",
            "Define your financial milestones on the Savings Goals page to track progress toward your dreams.",
            icon="🏦",
        )

section_divider()

# ==================================================
# RECENT TRANSACTIONS FEED
# ==================================================

st.subheader("🕒 Recent Transactions")

if transactions:
    recent_df = df.head(5).copy()
    
    # Styled table display
    for _, row in recent_df.iterrows():
        r_col1, r_col2, r_col3, r_col4 = st.columns([1.2, 1.5, 2.5, 1.5])
        is_income = row["Type"] == "Income"
        amt_color = "#10b981" if is_income else "#f43f5e"
        sign = "+" if is_income else "-"
        
        with r_col1:
            st.write(f"📅 {row['Date'].strftime('%d %b %Y')}")
        with r_col2:
            st.markdown(f"**{row['Category']}**")
        with r_col3:
            st.write(row["Description"] if row["Description"] else "—")
        with r_col4:
            st.markdown(
                f"<div style='text-align: right; font-weight: 700; color: {amt_color};'>"
                f"{sign}{format_currency(row['Amount'])}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid var(--pft-border);' />", unsafe_allow_html=True)

    st.caption("Showing 5 most recent transactions. Navigate to Transaction Management for full search, filters, import, and editing.")
else:
    empty_state(
        "No Transactions Yet",
        "Record your first income or expense above or import your bank statement in Transaction Management.",
        icon="💳",
    )