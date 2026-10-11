import streamlit as st
from datetime import date
import pandas as pd
import json

from auth import require_login
from database import (
    create_database,
    get_transactions,
    delete_transaction,
    add_transaction,
    get_budgets,
    get_savings_goals,
    set_budget,
    add_savings_goal,
    update_savings_goal_amount,
    get_user_profile,
)
from utils import (
    inject_css,
    page_header,
    section_divider,
    empty_state,
    format_currency,
    get_user_currency,
    INCOME_CATEGORIES,
    EXPENSE_CATEGORIES,
)
from finance_ml import suggest_expense_category
from finance_tools import parse_statement, export_transactions

st.set_page_config(page_title="Transaction Management", page_icon="💵", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "Transaction Management",
    "Record new transactions, search & filter past activity, and import bank statements.",
    badge_text="Transactions",
    icon="💵",
)

# Toast notifications
if "show_success" not in st.session_state:
    st.session_state.show_success = False
if "show_delete_success" not in st.session_state:
    st.session_state.show_delete_success = False

if st.session_state.show_success:
    st.success("Transaction added successfully.")
    st.session_state.show_success = False

if st.session_state.show_delete_success:
    st.success("Transaction deleted successfully.")
    st.session_state.show_delete_success = False

# Quick tabs for actions
action_tab1, action_tab2, action_tab3 = st.tabs(["➕ Add Transaction", "📥 Import Statement", "💾 Backup & Restore"])

with action_tab1:
    t_type = st.selectbox("Transaction Type", ["Expense", "Income"], key="tm_type")
    cat_options = EXPENSE_CATEGORIES if t_type == "Expense" else INCOME_CATEGORIES
    suggested_category = st.session_state.get("suggested_expense_category")
    if suggested_category in cat_options:
        st.info(f"💡 AI Suggested Category: **{suggested_category}** (can be changed below).")

    with st.form("add_transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_date = st.date_input("Date", date.today(), key="tm_date")
            category_idx = cat_options.index(suggested_category) if suggested_category in cat_options else 0
            category = st.selectbox("Category", cat_options, index=category_idx, key="tm_category")
        with col2:
            amount = st.number_input(f"Amount ({curr})", min_value=0.0, step=100.0, format="%.2f", key="tm_amount")
            description = st.text_input("Description / Merchant", placeholder="e.g. Netflix subscription, Grocery mart", key="tm_desc")

        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            submitted = st.form_submit_button("Add Transaction", type="primary", use_container_width=True)
        with btn_col2:
            suggest_clicked = st.form_submit_button("🤖 Auto-Suggest Category", use_container_width=True) if t_type == "Expense" else False

        if suggest_clicked:
            suggestion = suggest_expense_category(description)
            if suggestion:
                st.session_state["suggested_expense_category"] = suggestion["category"]
                st.rerun()
            else:
                st.warning("No confident category match found. Please select a category manually.")

        if submitted:
            if amount <= 0:
                st.error(f"Please enter an amount greater than {curr}0.00.")
            else:
                add_transaction(user_id, str(t_date), t_type, category, amount, description.strip())
                st.session_state.pop("suggested_expense_category", None)
                st.session_state.show_success = True
                st.rerun()

with action_tab2:
    st.caption("Upload your bank statement in CSV or Excel format. Required columns: `Date`, `Amount`, and optionally `Type`, `Category`, `Description`.")
    uploaded = st.file_uploader("Choose statement file", type=["csv", "xlsx", "xls"], key="statement_upload")
    if uploaded is not None:
        try:
            imported = parse_statement(uploaded)
            st.write(f"Preview of parsed rows ({len(imported)} total):")
            st.dataframe(imported.head(15), use_container_width=True, hide_index=True)
            if st.button("Import All Parsed Transactions", type="primary"):
                for row in imported.itertuples(index=False):
                    add_transaction(user_id, row.Date, row.Type, row.Category, float(row.Amount), row.Description)
                st.success(f"Successfully imported {len(imported)} transaction(s) into your account.")
                st.rerun()
        except ValueError as exc:
            st.error(f"Failed to parse statement: {exc}")

with action_tab3:
    profile = get_user_profile(user_id)
    backup_data = {
        "version": 1,
        "profile": {"username": profile["username"], "email": profile["email"], "currency": profile["currency"]},
        "transactions": export_transactions(get_transactions(user_id)).to_dict("records"),
        "budgets": [{"category": c, "monthly_limit": l} for c, l in get_budgets(user_id)],
        "savings_goals": [{"name": n, "target_amount": t, "current_amount": c, "target_date": d} for _, n, t, c, d in get_savings_goals(user_id)],
    }
    st.download_button(
        "📥 Download Full Account JSON Backup",
        json.dumps(backup_data, default=str, indent=2),
        f"finance_backup_{date.today().isoformat()}.json",
        "application/json",
        use_container_width=True,
    )
    st.markdown("---")
    restore_file = st.file_uploader("Upload JSON backup file to restore", type=["json"], key="restore_backup")
    if restore_file is not None and st.button("Restore Backup into Account", type="primary"):
        try:
            payload = json.load(restore_file)
            rows = payload.get("transactions", [])
            for row in rows:
                add_transaction(user_id, row["Date"], row["Type"], row["Category"], float(row["Amount"]), row.get("Description", ""))
            for row in payload.get("budgets", []):
                set_budget(user_id, row["category"], float(row["monthly_limit"]))
            for row in payload.get("savings_goals", []):
                add_savings_goal(user_id, row["name"], float(row["target_amount"]), row.get("target_date"))
                created_goal = get_savings_goals(user_id)[0]
                update_savings_goal_amount(user_id, created_goal[0], float(row.get("current_amount", 0)))
            st.success(f"Restored {len(rows)} transaction(s), budgets, and savings goals.")
            st.rerun()
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            st.error(f"Could not restore backup: {exc}")

section_divider()

# ==================================================
# TRANSACTION HISTORY & FILTERS
# ==================================================

st.header("Transaction History")

transactions = get_transactions(user_id)

if not transactions:
    empty_state(
        "No Transactions Found",
        "You haven't recorded any transactions yet. Use the 'Add Transaction' tab above or upload a statement to get started.",
        icon="💳",
    )
else:
    df = pd.DataFrame(
        transactions,
        columns=["ID", "Date", "Type", "Category", "Amount", "Description"]
    )
    df["Date"] = pd.to_datetime(df["Date"])

    # Filter Bar
    f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1, 1.5])
    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()

    with f_col1:
        date_from = st.date_input("From Date", value=min_date, min_value=min_date, max_value=max_date, key="filter_from")
    with f_col2:
        date_to = st.date_input("To Date", value=max_date, min_value=min_date, max_value=max_date, key="filter_to")
    with f_col3:
        type_filter = st.selectbox("Type Filter", ["All", "Expense", "Income"], key="filter_type")
    with f_col4:
        search_term = st.text_input("Search Description / Category", placeholder="Search by text...", key="filter_search")

    filtered_df = df.copy()

    if date_from > date_to:
        st.warning("'From Date' cannot be after 'To Date'.")
        filtered_df = filtered_df.iloc[0:0]
    else:
        filtered_df = filtered_df[
            (filtered_df["Date"].dt.date >= date_from) & (filtered_df["Date"].dt.date <= date_to)
        ]

    if type_filter != "All":
        filtered_df = filtered_df[filtered_df["Type"] == type_filter]

    if search_term.strip():
        term = search_term.strip().lower()
        filtered_df = filtered_df[
            filtered_df["Category"].str.lower().str.contains(term, na=False)
            | filtered_df["Description"].fillna("").str.lower().str.contains(term, na=False)
        ]

    st.caption(f"Showing **{len(filtered_df)}** of **{len(df)}** transaction(s).")

    # CSV Download Button
    if not filtered_df.empty:
        export_df = filtered_df.copy()
        export_df["Date"] = export_df["Date"].dt.strftime("%Y-%m-%d")
        st.download_button(
            label="📥 Export Filtered Transactions (CSV)",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=f"transactions_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

    if filtered_df.empty:
        empty_state("No Matching Transactions", "Try broadening your search term or date range filter.", icon="🔍")
    else:
        header_cols = st.columns([0.8, 1.2, 1.1, 1.4, 1.4, 2.4, 0.7])
        labels = ["ID", "Date", "Type", "Category", "Amount", "Description", "Action"]
        for col, label in zip(header_cols, labels):
            col.markdown(f"**{label}**")

        for _, row in filtered_df.iterrows():
            row_cols = st.columns([0.8, 1.2, 1.1, 1.4, 1.4, 2.4, 0.7])
            is_inc = row["Type"] == "Income"
            amt_color = "#10b981" if is_inc else "#f43f5e"
            type_badge = f"<span class='pft-badge {'pft-badge-emerald' if is_inc else 'pft-badge-rose'}'>{row['Type']}</span>"

            row_cols[0].write(f"#{int(row['ID'])}")
            row_cols[1].write(row["Date"].strftime("%d %b %Y"))
            row_cols[2].markdown(type_badge, unsafe_allow_html=True)
            row_cols[3].write(row["Category"])
            row_cols[4].markdown(f"<span style='color:{amt_color}; font-weight:700;'>{format_currency(row['Amount'])}</span>", unsafe_allow_html=True)
            row_cols[5].write(row["Description"] if row["Description"] else "—")

            if row_cols[6].button("🗑️", key=f"del_{row['ID']}", help="Delete transaction"):
                delete_transaction(user_id, int(row["ID"]))
                st.session_state.show_delete_success = True
                st.rerun()
