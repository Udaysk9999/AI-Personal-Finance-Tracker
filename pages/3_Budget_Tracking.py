import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go

from auth import require_login
from database import (
    create_database,
    get_transactions,
    set_budget,
    get_budgets,
    delete_budget,
    get_savings_goals,
    get_user_profile,
)
from utils import (
    inject_css,
    page_header,
    section_divider,
    empty_state,
    format_currency,
    get_user_currency,
    apply_chart_theme,
    theme_chart_colors,
    EXPENSE_CATEGORIES,
)
from finance_tools import budget_alerts, build_report_pdf
from finance_ml import financial_health_score, predict_next_month_expenses

st.set_page_config(page_title="Budget Tracking", page_icon="🎯", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Budget Tracking & Alerts",
    "Set monthly expenditure thresholds per category, track progress in real-time, and download PDF reports.",
    badge_text="Budgets",
    icon="🎯",
)

if "budget_saved" not in st.session_state:
    st.session_state.budget_saved = False
if "budget_deleted" not in st.session_state:
    st.session_state.budget_deleted = False

if st.session_state.budget_saved:
    st.success("Budget limit saved successfully.")
    st.session_state.budget_saved = False
if st.session_state.budget_deleted:
    st.success("Budget limit removed.")
    st.session_state.budget_deleted = False

# ==================================================
# SET / UPDATE A BUDGET
# ==================================================

st.subheader("Set Category Budget Limit")

with st.form("set_budget_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        budget_category = st.selectbox("Category", EXPENSE_CATEGORIES)
    with col2:
        budget_limit = st.number_input(f"Monthly Limit ({curr})", min_value=0.0, step=500.0, format="%.2f")

    submitted = st.form_submit_button("Save Budget Limit", type="primary")

    if submitted:
        if budget_limit <= 0:
            st.error(f"Please enter a limit greater than {curr}0.00.")
        else:
            set_budget(user_id, budget_category, budget_limit)
            st.session_state.budget_saved = True
            st.rerun()

section_divider()

# ==================================================
# CURRENT MONTH BUDGET STATUS
# ==================================================

today = date.today()
month_label = today.strftime("%B %Y")
st.subheader(f"Current Month Progress — {month_label}")

budgets = get_budgets(user_id)
transactions = get_transactions(user_id)
goals = get_savings_goals(user_id)
alerts = budget_alerts(budgets, transactions, warning_threshold=0.80)

# Budget alerts banner
if alerts:
    for alert in alerts:
        is_over = alert["level"] == "over"
        pct_display = f"{alert['percent'] * 100:.0f}%"
        if is_over:
            st.error(
                f"🚨 **{alert['category']}** is over budget! "
                f"Spent: {format_currency(alert['spent'])} of {format_currency(alert['limit'])} limit ({pct_display} used, over by {format_currency(alert.get('over_by', alert['spent'] - alert['limit']))})"
            )
        else:
            st.warning(
                f"⚠️ **{alert['category']}** is approaching limit ({pct_display} used)! "
                f"Spent: {format_currency(alert['spent'])} of {format_currency(alert['limit'])} — {format_currency(alert.get('remaining', alert['limit'] - alert['spent']))} cushion remaining."
            )

# Monthly PDF Export & Report Download
profile = get_user_profile(user_id)
health = financial_health_score(transactions, budgets, goals)
prediction = predict_next_month_expenses(transactions)
report = build_report_pdf(profile["username"], transactions, budgets, goals, health, prediction, alerts, currency=curr)

st.download_button(
    "📄 Download Monthly PDF Financial Report",
    report,
    f"finance_report_{today.isoformat()}.pdf",
    "application/pdf",
)

if not budgets:
    empty_state(
        "No Active Budgets",
        "Set monthly limits on your spending categories above to begin tracking and receiving threshold alerts.",
        icon="🎯",
    )
else:
    df = pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"]) if transactions else pd.DataFrame(columns=["ID", "Date", "Type", "Category", "Amount", "Description"])

    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
        this_month = df[
            (df["Type"] == "Expense")
            & (df["Date"].dt.year == today.year)
            & (df["Date"].dt.month == today.month)
        ]
        spent_by_category = this_month.groupby("Category")["Amount"].sum().to_dict()
    else:
        spent_by_category = {}

    # --- Interactive Budget vs Actual Comparison Chart ---
    chart_data = []
    for category, limit in budgets:
        spent = float(spent_by_category.get(category, 0.0))
        chart_data.append({
            "Category": category,
            "Limit": limit,
            "Spent": spent,
            "Over": spent > limit,
        })
    chart_df = pd.DataFrame(chart_data)

    if not chart_df.empty:
        fig_budget = go.Figure()
        fig_budget.add_trace(
            go.Bar(
                y=chart_df["Category"],
                x=chart_df["Limit"],
                name="Budgeted Limit",
                orientation="h",
                marker_color="rgba(99, 102, 241, 0.45)",
                marker_line_color="#6366f1",
                marker_line_width=1.5,
                hovertemplate="<b>%{y}</b><br>Budget Limit: " + curr + "%{x:,.2f}<extra></extra>",
            )
        )
        spent_colors = ["#f43f5e" if row["Over"] else "#10b981" for _, row in chart_df.iterrows()]
        fig_budget.add_trace(
            go.Bar(
                y=chart_df["Category"],
                x=chart_df["Spent"],
                name="Actual Spent",
                orientation="h",
                marker_color=spent_colors,
                marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Actual Spent: " + curr + "%{x:,.2f}<extra></extra>",
            )
        )
        apply_chart_theme(
            fig_budget,
            height=max(220, len(chart_df) * 45 + 90),
            title=f"Budget Limit vs. Actual Spend ({month_label})",
            x_title=f"Amount ({curr})",
            barmode="group",
        )
        st.plotly_chart(fig_budget, use_container_width=True)

    st.markdown("### Category Budget Status & Utilization")

    for category, limit in budgets:
        spent = float(spent_by_category.get(category, 0.0))
        pct = min(spent / limit, 1.0) if limit > 0 else 0.0
        over = spent > limit

        if over:
            badge_html = '<span class="pft-badge pft-badge-rose">Over Budget</span>'
        elif pct >= 0.80:
            badge_html = '<span class="pft-badge pft-badge-amber">Near Limit</span>'
        else:
            badge_html = '<span class="pft-badge pft-badge-emerald">On Track</span>'

        col_a, col_b = st.columns([5, 1])

        with col_a:
            over_text = f" — <span style='color: #f43f5e; font-weight: 600;'>over by {format_currency(spent - limit)}</span>" if over else f" — {format_currency(limit - spent)} remaining"
            st.markdown(
                f"""
                <div style="margin-bottom: 6px;">
                    <span style="font-weight: 700; font-size: 1.05rem;">{category}</span> &nbsp; {badge_html}
                    <div style="font-size: 0.88rem; color: var(--pft-text-secondary); margin-top: 2px;">
                        {format_currency(spent)} spent of {format_currency(limit)} budgeted ({pct * 100:.1f}%){over_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(pct)

        with col_b:
            st.write("")
            if st.button("Remove", key=f"remove_budget_{category}", help=f"Delete {category} budget"):
                delete_budget(user_id, category)
                st.session_state.budget_deleted = True
                st.rerun()

        st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px solid var(--pft-border);' />", unsafe_allow_html=True)
