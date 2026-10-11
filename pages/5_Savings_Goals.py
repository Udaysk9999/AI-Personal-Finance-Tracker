import streamlit as st
from datetime import date

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
)

st.set_page_config(page_title="Savings Goals", page_icon="🏦", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Savings Goals & Milestones",
    "Define your target milestones, allocate savings, and track your completion progress.",
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
# TRACK PROGRESS
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
        st.progress(pct, text=f"{pct * 100:.1f}% completed")

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