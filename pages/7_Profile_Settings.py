import streamlit as st

from auth import require_login
from database import (
    create_database,
    delete_user_account,
    get_user_profile,
    update_user_profile,
    get_transactions,
)
from utils import inject_css, page_header, section_divider, metric_card

st.set_page_config(page_title="Profile & Preferences", page_icon="⚙️", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
profile = get_user_profile(user_id)

page_header(
    "Profile & Preferences",
    "Manage your personal identity, select your preferred currency, and manage account security.",
    badge_text="Settings",
    icon="⚙️",
)

# Overview metrics
tx_count = len(get_transactions(user_id))
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    metric_card("Username", profile["username"], accent="indigo", icon="👤")
with m_col2:
    metric_card("Active Currency", profile["currency"], accent="emerald", icon="💱")
with m_col3:
    metric_card("Total Records", f"{tx_count} transactions", accent="cyan", icon="📊")

section_divider()

# Profile edit form
st.subheader("Edit Profile & Currency")

currency_choices = ["₹", "$", "€", "£", "¥", "C$", "A$"]
current_currency = profile["currency"] if profile["currency"] in currency_choices else "₹"

with st.form("profile_settings_form"):
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("Username", value=profile["username"])
        new_email = st.text_input("Email address", value=profile["email"] or "")
    with col2:
        currency = st.selectbox(
            "Preferred Currency Symbol",
            currency_choices,
            index=currency_choices.index(current_currency),
            help="This currency will be used dynamically throughout all charts, cards, reports, and calculations.",
        )

    save_clicked = st.form_submit_button("Save Changes", type="primary")
    if save_clicked:
        try:
            update_user_profile(user_id, new_username, new_email, currency)
            st.session_state["username"] = new_username.strip()
            st.session_state["user_currency"] = currency
            st.success("Profile and currency settings updated successfully!")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

section_divider()

# Danger Zone
st.subheader("⚠️ Account Security & Danger Zone")
st.caption(f"Account created on: {profile['created_at']}")

with st.expander("Delete Account", expanded=False):
    st.error(
        "Permanent Action: Deleting your account will immediately remove all your personal transactions, "
        "budgets, savings goals, and profile data from the database. This action cannot be reversed."
    )
    confirm = st.checkbox("I understand that deleting my account is irreversible and permanently purges all my data.")
    if st.button("Delete My Entire Account", type="primary", disabled=not confirm):
        delete_user_account(user_id)
        for key in ("user_id", "username", "user_currency"):
            st.session_state.pop(key, None)
        for key in list(st.session_state):
            if key.startswith("advisor_messages_"):
                st.session_state.pop(key, None)
        st.success("Your account and all associated financial records were permanently deleted.")
        st.rerun()
