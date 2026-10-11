import streamlit as st
from datetime import date
import pandas as pd
import plotly.graph_objects as go

from auth import require_login
from database import (
    create_database,
    add_savings_goal,
    get_savings_goals,
    update_savings_goal_amount,
    delete_savings_goal,
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
    metric_card,
)

st.set_page_config(page_title="Savings Goals", page_icon="🏦", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Savings Goals & Milestones",
    "Define your target milestones, allocate savings, track completion velocity, and stay on schedule.",
    badge_text="Goals",
    icon="🏦",
)

if "goal_added" not in st.session_state:
    st.session_state.goal_added = False
if "goal_updated" not in st.session_state:
    st.session_state.goal_updated = False
if "goal_deleted" not in st.session_state:
    st.session_state.goal_deleted = False

if st.session_state.goal_added:
    st.success("Savings goal created successfully.")
    st.session_state.goal_added = False
if st.session_state.goal_updated:
    st.success("Goal progress updated.")
    st.session_state.goal_updated = False
if st.session_state.goal_deleted:
    st.success("Savings goal removed.")
    st.session_state.goal_deleted = False

# ==================================================
# CREATE A GOAL
# ==================================================

st.subheader("Create a New Milestone Goal")

with st.form("add_goal_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        goal_name = st.text_input("Goal Name", placeholder="e.g. Emergency Fund, New Car...")
    with col2:
        goal_target = st.number_input(f"Target Amount ({curr})", min_value=0.0, step=1000.0, format="%.2f")
    with col3:
        goal_date = st.date_input("Target Date", value=date.today())

    submitted = st.form_submit_button("Create Goal", type="primary")

    if submitted:
        if not goal_name.strip():
            st.error("Please enter a name for your goal.")
        elif goal_target <= 0:
            st.error(f"Please enter a target amount greater than {curr}0.00.")
        else:
            add_savings_goal(user_id, goal_name.strip(), goal_target, str(goal_date))
            st.session_state.goal_added = True
            st.rerun()

section_divider()

# ==================================================
# TRACK PROGRESS & VISUALIZE MILESTONES
# ==================================================

st.subheader("Active Savings Milestones")

goals = get_savings_goals(user_id)

if not goals:
    empty_state(
        "No Savings Goals Created",
        "Set up an emergency reserve, dream vacation, or big purchase goal above to track your savings trajectory.",
        icon="🏦",
    )
else:
    total_target = sum(g[2] for g in goals)
    total_saved = sum(g[3] for g in goals)
    overall_pct = (total_saved / total_target * 100) if total_target > 0 else 0.0

    # Summary strip for all goals
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        metric_card("Total Cumulative Target", format_currency(total_target), accent="indigo", icon="🎯")
    with m_col2:
        metric_card("Total Amount Saved", format_currency(total_saved), accent="emerald", icon="💰")
    with m_col3:
        metric_card("Overall Progress", f"{overall_pct:.1f}%", accent="cyan" if overall_pct >= 50 else "amber", icon="🏁")

    # --- Interactive Horizontal Bar Chart Comparing Saved vs Target ---
    chart_names = [g[1] for g in goals]
    chart_targets = [g[2] for g in goals]
    chart_saved = [g[3] for g in goals]

    fig_goals = go.Figure()
    fig_goals.add_trace(
        go.Bar(
            y=chart_names,
            x=chart_targets,
            name="Target Amount",
            orientation="h",
            marker_color="rgba(99, 102, 241, 0.4)",
            marker_line_color="#6366f1",
            marker_line_width=1.5,
            hovertemplate="<b>%{y}</b><br>Target: " + curr + "%{x:,.2f}<extra></extra>",
        )
    )
    saved_bar_colors = ["#10b981" if s >= t and t > 0 else "#6366f1" for s, t in zip(chart_saved, chart_targets)]
    fig_goals.add_trace(
        go.Bar(
            y=chart_names,
            x=chart_saved,
            name="Current Saved",
            orientation="h",
            marker_color=saved_bar_colors,
            marker_line_width=0,
            hovertemplate="<b>%{y}</b><br>Saved: " + curr + "%{x:,.2f}<extra></extra>",
        )
    )
    apply_chart_theme(
        fig_goals,
        height=max(220, len(goals) * 45 + 90),
        title="Savings Goals: Target vs. Current Saved",
        x_title=f"Amount ({curr})",
        barmode="group",
    )
    st.plotly_chart(fig_goals, use_container_width=True)

    # ==================================================
    # SMART SAVINGS PLANNER & FEASIBILITY ANALYSIS
    # ==================================================
    from database import get_transactions
    from finance_ml import calculate_savings_plan

    user_transactions = get_transactions(user_id)
    plan = calculate_savings_plan(user_transactions, goals)

    with st.expander("📊 Smart Monthly Savings Planner & Feasibility Analysis", expanded=True):
        st.caption("Data-grounded projections based on your actual income, regular living expenses, and active goals.")

        if plan["status"] == "ok":
            p_col1, p_col2, p_col3 = st.columns(3)
            with p_col1:
                metric_card(
                    "Estimated Monthly Surplus",
                    format_currency(plan["baseline_surplus"], curr),
                    accent="indigo" if plan["baseline_surplus"] >= 0 else "rose",
                    icon="💵",
                    help_text="net disposable cash flow",
                )
            with p_col2:
                metric_card(
                    "Recommended Monthly Savings",
                    format_currency(plan["realistic_monthly_target"], curr),
                    accent="emerald" if plan["realistic_monthly_target"] > 0 else "amber",
                    icon="🎯",
                    help_text="70% of safe surplus",
                )
            with p_col3:
                metric_card(
                    "Total Goals Monthly Demand",
                    format_currency(plan["total_monthly_demand"], curr),
                    accent="cyan" if plan["total_monthly_demand"] <= plan["realistic_monthly_target"] else "rose",
                    icon="⏳",
                    help_text="sum of deadline targets",
                )

            # Feasibility recommendation banner
            if plan["feasibility"] == "deficit":
                st.error(f"⚠️ **Cash Flow Advisory:** {plan['target_message']}")
            elif plan["total_monthly_demand"] > plan["realistic_monthly_target"]:
                st.warning(
                    f"⚠️ **Tight Savings Schedule:** Your active milestones require {format_currency(plan['total_monthly_demand'], curr)}/month, "
                    f"which exceeds your recommended safe monthly savings rate ({format_currency(plan['realistic_monthly_target'], curr)}/month). "
                    "Consider extending target dates or reducing discretionary category spending."
                )
            else:
                st.success(
                    f"✅ **Goals Are Fully Feasible:** Your recommended savings capacity of {format_currency(plan['realistic_monthly_target'], curr)}/month "
                    f"comfortably covers all active milestone deadlines ({format_currency(plan['total_monthly_demand'], curr)}/month)."
                )

            # Capacity ranges table
            if plan["realistic_monthly_target"] > 0:
                st.markdown(
                    f'<div style="font-size: 0.88rem; color: var(--pft-text-secondary); margin: 8px 0 12px 0;">'
                    f'<strong>Savings Capacity Range:</strong> '
                    f'&nbsp;•&nbsp; <strong>Conservative (50%):</strong> {format_currency(plan["conservative_target"], curr)}/mo '
                    f'&nbsp;•&nbsp; <strong>Moderate / Target (70%):</strong> {format_currency(plan["realistic_monthly_target"], curr)}/mo '
                    f'&nbsp;•&nbsp; <strong>Aggressive (85%):</strong> {format_currency(plan["aggressive_target"], curr)}/mo'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Goal-by-goal feasibility projections
            if plan["goals_plan"]:
                st.markdown("##### Milestone Feasibility & Estimated Timelines")
                for gp in plan["goals_plan"]:
                    status_lbl = gp["status"]
                    if status_lbl == "completed":
                        b_html = '<span class="pft-badge pft-badge-emerald">Completed 🎉</span>'
                        t_text = "Milestone achieved!"
                    elif status_lbl == "on_track":
                        b_html = '<span class="pft-badge pft-badge-emerald">On Schedule</span>'
                        t_text = f"Requires {format_currency(gp['required_per_month'], curr)}/mo over {gp['months_to_deadline']} month(s)"
                    elif status_lbl == "tight":
                        b_html = '<span class="pft-badge pft-badge-amber">Tight Schedule</span>'
                        t_text = f"Requires {format_currency(gp['required_per_month'], curr)}/mo over {gp['months_to_deadline']} month(s) — close to maximum surplus"
                    elif status_lbl == "extended_timeline_needed":
                        b_html = '<span class="pft-badge pft-badge-rose">Extend Deadline</span>'
                        t_text = f"Requires {format_currency(gp['required_per_month'], curr)}/mo, but safe capacity is {format_currency(plan['realistic_monthly_target'], curr)}/mo"
                    elif status_lbl == "deficit":
                        b_html = '<span class="pft-badge pft-badge-rose">Deficit</span>'
                        t_text = "Cannot project timeline while cash flow is negative"
                    else:
                        b_html = '<span class="pft-badge pft-badge-neutral">Open-Ended</span>'
                        est_m = gp.get("estimated_months_at_target")
                        t_text = f"~{est_m} month(s) to reach target at recommended savings rate" if est_m else "No deadline set"

                    st.markdown(
                        f'<div style="padding: 6px 0; border-bottom: 1px solid var(--pft-border);">'
                        f'<strong>{gp["name"]}</strong> &nbsp; {b_html}'
                        f'<div style="font-size: 0.85rem; color: var(--pft-text-secondary); margin-top: 2px;">'
                        f'{format_currency(gp["remaining"], curr)} remaining &nbsp;•&nbsp; {t_text}'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.caption(f"ℹ️ {plan['assumptions']}")
        else:
            st.info(plan["message"])

    st.markdown("### Milestone Details & Contributions")

    for goal_id, name, target, current, target_date in goals:
        pct = min(current / target, 1.0) if target > 0 else 0.0
        remaining = max(target - current, 0.0)
        is_completed = current >= target and target > 0

        if is_completed:
            status_badge = '<span class="pft-badge pft-badge-emerald">Goal Reached 🎉</span>'
        elif pct >= 0.5:
            status_badge = f'<span class="pft-badge pft-badge-indigo">{pct * 100:.0f}% Achieved</span>'
        else:
            status_badge = f'<span class="pft-badge pft-badge-neutral">{pct * 100:.0f}% In Progress</span>'

        st.markdown(
            f"""
            <div style="margin-bottom: 6px;">
                <span style="font-weight: 700; font-size: 1.1rem;">{name}</span> &nbsp; {status_badge}
                <div style="font-size: 0.88rem; color: var(--pft-text-secondary); margin-top: 3px;">
                    {format_currency(current)} saved of {format_currency(target)}
                    &nbsp;•&nbsp; Target date: <strong>{target_date or 'Not specified'}</strong>
                    &nbsp;•&nbsp; <strong>{format_currency(remaining)}</strong> remaining
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(pct)

        col_a, col_b, col_c = st.columns([2.5, 1, 1])

        with col_a:
            new_amount = st.number_input(
                f"Update Saved Amount ({curr})",
                min_value=0.0,
                value=float(current),
                step=500.0,
                format="%.2f",
                key=f"goal_amount_{goal_id}",
            )

        with col_b:
            st.write("")
            st.write("")
            if st.button("Save Progress", key=f"update_goal_{goal_id}"):
                update_savings_goal_amount(user_id, goal_id, new_amount)
                st.session_state.goal_updated = True
                st.rerun()

        with col_c:
            st.write("")
            st.write("")
            if st.button("Delete Goal", key=f"delete_goal_{goal_id}", help="Delete this savings milestone"):
                delete_savings_goal(user_id, goal_id)
                st.session_state.goal_deleted = True
                st.rerun()

        st.markdown("<hr style='margin: 16px 0; border: none; border-top: 1px solid var(--pft-border);' />", unsafe_allow_html=True)