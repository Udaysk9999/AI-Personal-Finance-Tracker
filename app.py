import streamlit as st
from datetime import date
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

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
    format_currency,
    get_user_currency,
    metric_card,
    empty_state,
    badge,
    FINANCE_COLOR_SEQUENCE,
    theme_chart_colors,
    apply_chart_theme,
    INCOME_CATEGORIES,
    EXPENSE_CATEGORIES,
)
from finance_tools import budget_alerts
from finance_ml import financial_health_score

# === PAGE CONFIGURATION ===
st.set_page_config(
    page_title="AI-Powered Personal Expense Tracking & Budget Advisor",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
create_database()
user_id, username = require_login()
curr = get_user_currency()

# ==================================================
# MAIN CONTENT — Dashboard (Default Home)
# ==================================================

# Header
page_header(
    "Financial Overview",
    f"Welcome back, {username}. Here is your real-time financial health, cash flow, and budget analytics.",
    badge_text="Live Dashboard",
    icon="📊",
)

# Fetch user data
transactions = get_transactions(user_id)
budgets = get_budgets(user_id)
goals = get_savings_goals(user_id)
chart_colors = theme_chart_colors()

if transactions:
    df = pd.DataFrame(
        transactions,
        columns=["ID", "Date", "Type", "Category", "Amount", "Description"],
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)

    total_income = float(df[df["Type"] == "Income"]["Amount"].sum())
    total_expenses = float(df[df["Type"] == "Expense"]["Amount"].sum())
    balance = total_income - total_expenses
    savings_rate = ((balance / total_income) * 100) if total_income > 0 else 0.0
else:
    df = pd.DataFrame(columns=["ID", "Date", "Type", "Category", "Amount", "Description"])
    total_income = 0.0
    total_expenses = 0.0
    balance = 0.0
    savings_rate = 0.0

# --- Top Financial Summary Metrics ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    metric_card(
        "Current Net Balance",
        format_currency(balance),
        accent="indigo" if balance >= 0 else "rose",
        icon="💳",
        help_text="cumulative surplus",
    )
with col2:
    metric_card(
        "Total Inflow (Income)",
        format_currency(total_income),
        accent="emerald",
        icon="📈",
        help_text="all-time earned",
    )
with col3:
    metric_card(
        "Total Outflow (Expenses)",
        format_currency(total_expenses),
        accent="rose",
        icon="📉",
        help_text="all-time spent",
    )
with col4:
    savings_delta = f"{savings_rate:.1f}%" if total_income > 0 else "0.0%"
    metric_card(
        "Savings Rate",
        savings_delta,
        delta=f"{savings_rate:+.1f}%" if total_income > 0 else None,
        accent="cyan" if savings_rate >= 20 else "amber",
        icon="🎯",
        help_text="of total income saved",
    )

# --- Financial Health Summary Strip (ML Feature) ---
if transactions:
    health = financial_health_score(transactions, budgets, goals)
    if health.get("score") is not None:
        score = health["score"]
        score_color = "#10b981" if score >= 70 else ("#f59e0b" if score >= 40 else "#f43f5e")
        score_status = "Excellent" if score >= 70 else ("Balanced" if score >= 40 else "Needs Attention")
        suggestion = health["suggestions"][0] if health.get("suggestions") else "Maintain steady contributions to savings."

        st.markdown(
            f"""
            <div style="
                background: var(--pft-surface);
                border: 1px solid var(--pft-border);
                border-left: 4px solid {score_color};
                border-radius: 10px;
                padding: 12px 18px;
                margin: 16px 0 10px 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 12px;
                box-shadow: var(--pft-shadow-sm);
            ">
                <div style="display: flex; align-items: center; gap: 14px;">
                    <div style="font-size: 1.5rem;">🏆</div>
                    <div>
                        <div style="font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--pft-text-secondary);">
                            Financial Health Score
                        </div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: var(--pft-text-primary);">
                            <span style="color: {score_color};">{score} / 100</span> &nbsp;•&nbsp; <span style="font-size: 0.95rem; font-weight: 600; color: {score_color};">{score_status}</span>
                        </div>
                    </div>
                </div>
                <div style="font-size: 0.88rem; color: var(--pft-text-secondary); max-width: 580px;">
                    💡 <strong>Smart Advisory:</strong> {suggestion}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- Proactive Budget Alerts Banner ---
if budgets and transactions:
    active_alerts = budget_alerts(budgets, transactions, warning_threshold=0.80)
    if active_alerts:
        over_alerts = [a for a in active_alerts if a["level"] == "over"]
        near_alerts = [a for a in active_alerts if a["level"] == "warning"]
        if over_alerts:
            over_cats = ", ".join([f"**{a['category']}** ({format_currency(a['spent'], curr)} / {format_currency(a['limit'], curr)})" for a in over_alerts])
            st.error(f"🚨 **Budget Alert:** You are over budget in {over_cats}!")
        if near_alerts:
            near_cats = ", ".join([f"**{a['category']}** ({a['percent']*100:.0f}% used, {format_currency(a['remaining'], curr)} left)" for a in near_alerts])
            st.warning(f"⚠️ **Budget Caution:** Approaching monthly limit in {near_cats}.")

# --- Quick Add Transaction Expander ---
with st.expander("⚡ Quick Record New Transaction", expanded=False):
    from finance_ml import suggest_category

    t_type = st.selectbox("Transaction Type", ["Expense", "Income"], key="quick_t_type")
    cat_options = EXPENSE_CATEGORIES if t_type == "Expense" else INCOME_CATEGORIES
    quick_suggested = st.session_state.get("quick_suggested_cat")
    if quick_suggested in cat_options:
        st.info(f"💡 Suggested Category: **{quick_suggested}** (can be adjusted below before saving).")

    with st.form("quick_add_form", clear_on_submit=True):
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            q_date = st.date_input("Date", date.today(), key="quick_date")
            cat_idx = cat_options.index(quick_suggested) if quick_suggested in cat_options else 0
            q_category = st.selectbox("Category", cat_options, index=cat_idx, key="quick_cat")
        with q_col2:
            q_amount = st.number_input(f"Amount ({curr})", min_value=0.0, step=100.0, format="%.2f", key="quick_amt")
            q_desc = st.text_input("Description", placeholder="e.g. Grocery run, Freelance project...", key="quick_desc")

        btn1, btn2 = st.columns([1, 1])
        with btn1:
            q_submit = st.form_submit_button("Save Transaction", type="primary", use_container_width=True)
        with btn2:
            q_suggest = st.form_submit_button("🤖 Auto-Suggest Category", use_container_width=True)

        if q_suggest:
            sug = suggest_category(q_desc, tx_type=t_type, user_transactions=transactions, fallback=True)
            if sug:
                st.session_state["quick_suggested_cat"] = sug["category"]
                st.rerun()

        if q_submit:
            if q_amount <= 0:
                st.error(f"Please enter an amount greater than {curr}0.00")
            else:
                add_transaction(user_id, str(q_date), t_type, q_category, q_amount, q_desc.strip())
                st.session_state.pop("quick_suggested_cat", None)
                st.success("Transaction recorded successfully!")
                st.rerun()

section_divider()

# ==================================================
# VISUAL ANALYTICS: CHARTS & CASH FLOW
# ==================================================

if transactions:
    st.subheader("Financial Analytics & Cash Flow")
    chart_col1, chart_col2 = st.columns([1.25, 1.0])

    with chart_col1:
        # Grouped Monthly Cash Flow (Income vs Expenses)
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
                marker_line_width=0,
                hovertemplate="<b>Income</b><br>%{x}: " + curr + "%{y:,.2f}<extra></extra>",
            )
        )
        fig_trend.add_trace(
            go.Bar(
                x=monthly_summary["Month"],
                y=monthly_summary["Expense"],
                name="Expense",
                marker_color="#f43f5e",
                marker_line_width=0,
                hovertemplate="<b>Expense</b><br>%{x}: " + curr + "%{y:,.2f}<extra></extra>",
            )
        )
        apply_chart_theme(
            fig_trend,
            height=340,
            title="Monthly Cash Flow (Income vs. Expense)",
            y_title=f"Amount ({curr})",
            barmode="group",
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with chart_col2:
        # Interactive Donut Chart: Expense Category Breakdown
        expense_df = df[df["Type"] == "Expense"]
        if not expense_df.empty:
            cat_totals = (
                expense_df.groupby("Category")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
            )
            fig_pie = go.Figure(
                data=[
                    go.Pie(
                        labels=cat_totals["Category"],
                        values=cat_totals["Amount"],
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
            fig_pie.add_annotation(
                text=f"<b>{format_currency(total_expenses)}</b><br><span style='font-size:11px; color:{chart_colors['axis']};'>Total Spent</span>",
                x=0.5,
                y=0.5,
                font=dict(size=14, color=chart_colors["font"]),
                showarrow=False,
            )
            apply_chart_theme(fig_pie, height=340, title="Expense Distribution by Category")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense transactions recorded yet to display category breakdown.")

    # --- Second Chart Row: Spending Timeline & Monthly Net Savings ---
    sec_col1, sec_col2 = st.columns([1.1, 1.1])

    with sec_col1:
        # Daily Spending Trend (Area Chart)
        if not expense_df.empty:
            daily_spend = expense_df.groupby(expense_df["Date"].dt.date)["Amount"].sum().reset_index()
            daily_spend = daily_spend.sort_values("Date")

            fig_daily = go.Figure()
            fig_daily.add_trace(
                go.Scatter(
                    x=daily_spend["Date"],
                    y=daily_spend["Amount"],
                    mode="lines+markers",
                    fill="tozeroy",
                    fillcolor="rgba(244, 63, 94, 0.12)",
                    line=dict(color="#f43f5e", width=2.5),
                    marker=dict(size=6, color="#f43f5e"),
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>Daily Spend: " + curr + "%{y:,.2f}<extra></extra>",
                )
            )
            apply_chart_theme(
                fig_daily,
                height=310,
                title="Daily Spending Timeline",
                y_title=f"Spent ({curr})",
                show_legend=False,
            )
            st.plotly_chart(fig_daily, use_container_width=True)
        else:
            empty_state("No Expense History", "Add expense entries to visualize daily velocity.", icon="📈")

    with sec_col2:
        # Monthly Net Savings / Surplus (Bar Chart)
        monthly_summary["Net"] = monthly_summary["Income"] - monthly_summary["Expense"]
        net_colors = ["#10b981" if val >= 0 else "#f43f5e" for val in monthly_summary["Net"]]

        fig_net = go.Figure()
        fig_net.add_trace(
            go.Bar(
                x=monthly_summary["Month"],
                y=monthly_summary["Net"],
                marker_color=net_colors,
                marker_line_width=0,
                hovertemplate="<b>Net Savings</b><br>%{x}: " + curr + "%{y:,.2f}<extra></extra>",
            )
        )
        apply_chart_theme(
            fig_net,
            height=310,
            title="Monthly Net Savings / Surplus Trajectory",
            y_title=f"Net Surplus ({curr})",
            show_legend=False,
        )
        st.plotly_chart(fig_net, use_container_width=True)

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

            if over:
                status_badge = '<span class="pft-badge pft-badge-rose">Over Budget</span>'
                bar_color = "#f43f5e"
            elif pct >= 0.80:
                status_badge = '<span class="pft-badge pft-badge-amber">Near Limit</span>'
                bar_color = "#f59e0b"
            else:
                status_badge = '<span class="pft-badge pft-badge-emerald">On Track</span>'
                bar_color = "#10b981"

            remaining_txt = f"<span style='color: #f43f5e;'>over by {format_currency(spent - limit)}</span>" if over else f"{format_currency(limit - spent)} remaining"

            st.markdown(
                f"""
                <div style="margin-top: 10px; margin-bottom: 4px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; font-size: 0.95rem;">{category}</span>
                        {status_badge}
                    </div>
                    <div style="font-size: 0.85rem; color: var(--pft-text-secondary); margin-top: 2px;">
                        {format_currency(spent)} of {format_currency(limit)} &nbsp;•&nbsp; {pct * 100:.1f}% used &nbsp;•&nbsp; {remaining_txt}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(pct)
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
            is_done = current >= target and target > 0

            if is_done:
                g_badge = '<span class="pft-badge pft-badge-emerald">Completed 🎉</span>'
            elif pct >= 0.5:
                g_badge = f'<span class="pft-badge pft-badge-indigo">{pct * 100:.0f}% Achieved</span>'
            else:
                g_badge = f'<span class="pft-badge pft-badge-neutral">{pct * 100:.0f}% In Progress</span>'

            st.markdown(
                f"""
                <div style="margin-top: 10px; margin-bottom: 4px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; font-size: 0.95rem;">{name}</span>
                        {g_badge}
                    </div>
                    <div style="font-size: 0.85rem; color: var(--pft-text-secondary); margin-top: 2px;">
                        {format_currency(current)} of {format_currency(target)} &nbsp;•&nbsp; {target_str} &nbsp;•&nbsp; {format_currency(remaining)} to go
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(pct)
    else:
        empty_state(
            "No Savings Goals",
            "Define your financial milestones on the Savings Goals page to track progress toward your dreams.",
            icon="🏦",
        )

section_divider()

# ==================================================
# RECENT TRANSACTIONS FEED WITH FILTERS
# ==================================================

st.subheader("🕒 Recent Transactions")

if transactions:
    # Filter bar for recent feed
    rf_col1, rf_col2 = st.columns([1, 2])
    with rf_col1:
        feed_type = st.selectbox("Filter Type", ["All", "Expense", "Income"], key="home_feed_type")
    with rf_col2:
        feed_search = st.text_input("Quick Search", placeholder="Filter by category or merchant...", key="home_feed_search")

    feed_df = df.copy()
    if feed_type != "All":
        feed_df = feed_df[feed_df["Type"] == feed_type]
    if feed_search.strip():
        term = feed_search.strip().lower()
        feed_df = feed_df[
            feed_df["Category"].str.lower().str.contains(term, na=False)
            | feed_df["Description"].fillna("").str.lower().str.contains(term, na=False)
        ]

    feed_display = feed_df.head(6)

    if feed_display.empty:
        st.info("No transactions match the selected filter criteria.")
    else:
        for _, row in feed_display.iterrows():
            r_col1, r_col2, r_col3, r_col4 = st.columns([1.2, 1.5, 2.5, 1.5])
            is_income = row["Type"] == "Income"
            amt_color = "#10b981" if is_income else "#f43f5e"
            sign = "+" if is_income else "-"
            badge_class = "pft-badge-emerald" if is_income else "pft-badge-rose"

            with r_col1:
                st.write(f"📅 {row['Date'].strftime('%d %b %Y')}")
            with r_col2:
                st.markdown(f"<span class='pft-badge {badge_class}'>{row['Category']}</span>", unsafe_allow_html=True)
            with r_col3:
                st.write(row["Description"] if row["Description"] else "—")
            with r_col4:
                st.markdown(
                    f"<div style='text-align: right; font-weight: 700; color: {amt_color}; font-size: 1.02rem;'>"
                    f"{sign}{format_currency(row['Amount'])}</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid var(--pft-border);' />", unsafe_allow_html=True)

        st.caption("Showing most recent filtered transactions. Navigate to Transaction Management for full historical search, CSV export, and statement imports.")
else:
    empty_state(
        "No Transactions Yet",
        "Record your first income or expense above or import your bank statement in Transaction Management.",
        icon="💳",
    )