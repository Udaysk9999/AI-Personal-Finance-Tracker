import streamlit as st
import pandas as pd
import os

from auth import require_login
from database import create_database, get_transactions, get_budgets, get_savings_goals
from utils import (
    inject_css,
    page_header,
    section_divider,
    empty_state,
    format_currency,
    get_user_currency,
)

st.set_page_config(page_title="AI Financial Advisor", page_icon="🤖", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "AI Financial Advisor",
    "Personalized, cautious financial intelligence and spending optimization powered by Google Gemini.",
    badge_text="Gemini 2.0",
    icon="🤖",
)

st.markdown(
    """<div class="ai-disclaimer">
        <strong>🛡️ AI Advisory & Privacy Notice:</strong> This feature uses Google's Gemini API to analyze
        aggregated financial summaries of your data. It provides practical suggestions grounded strictly
        in your recorded numbers, not licensed financial or investment advice. Only anonymized category
        totals are sent — never your raw identity or individual account lists.
    </div>""",
    unsafe_allow_html=True,
)

# ==================================================
# API KEY CHECK
# ==================================================

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key and hasattr(st, "secrets"):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

if not api_key:
    st.warning(
        "No Gemini API key found. Set the `GEMINI_API_KEY` environment variable "
        "(or configure `.streamlit/secrets.toml` with `GEMINI_API_KEY = \"...\"`) to enable this page.\n\n"
        "Obtain a free key at https://aistudio.google.com/app/apikey"
    )
    st.stop()

try:
    from google import genai
except ImportError:
    st.error(
        "The `google-genai` package is not installed. Run `pip install google-genai`."
    )
    st.stop()

# ==================================================
# BUILD FINANCIAL DATA SUMMARY
# ==================================================

transactions = get_transactions(user_id)

if not transactions:
    empty_state(
        "No Transactions to Analyze",
        "Add transactions in Transaction Management first so the AI Advisor has numbers to review.",
        icon="💳",
    )
    st.stop()

df = pd.DataFrame(transactions, columns=["ID", "Date", "Type", "Category", "Amount", "Description"])
df["Date"] = pd.to_datetime(df["Date"])

total_income = float(df[df["Type"] == "Income"]["Amount"].sum())
total_expenses = float(df[df["Type"] == "Expense"]["Amount"].sum())
balance = total_income - total_expenses

expense_by_category = (
    df[df["Type"] == "Expense"].groupby("Category")["Amount"].sum().sort_values(ascending=False)
)

budgets = get_budgets(user_id)
goals = get_savings_goals(user_id)

summary_lines = [
    f"Active Currency: {curr}",
    f"Total recorded income: {format_currency(total_income)}",
    f"Total recorded expenses: {format_currency(total_expenses)}",
    f"Current available balance: {format_currency(balance)}",
    "Expense breakdown by category:",
]
for category, amount in expense_by_category.items():
    summary_lines.append(f"  - {category}: {format_currency(amount)}")

if budgets:
    summary_lines.append("Active monthly budget limits:")
    for category, limit in budgets:
        spent = expense_by_category.get(category, 0.0)
        summary_lines.append(f"  - {category}: {format_currency(spent)} spent of {format_currency(limit)} limit")

if goals:
    summary_lines.append("Savings goals progress:")
    for _, name, target, current, target_date in goals:
        summary_lines.append(f"  - {name}: {format_currency(current)} saved of {format_currency(target)} target (target date: {target_date or 'not specified'})")

data_summary = "\n".join(summary_lines)

with st.expander("🔍 View aggregated numbers provided to the advisor"):
    st.text(data_summary)

# ==================================================
# CONVERSATIONAL CHAT INTERFACE
# ==================================================

section_divider()
st.subheader("💬 Ask Your Advisor")

if f"advisor_messages_{user_id}" not in st.session_state:
    st.session_state[f"advisor_messages_{user_id}"] = []

for msg in st.session_state[f"advisor_messages_{user_id}"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Suggestion pills
st.caption("Prompt ideas:")
suggested = st.columns(3)
suggestion_texts = [
    "Where can I realistically cut back discretionary spending?",
    "Am I saving an adequate percentage given my current income?",
    "How should I prioritize my monthly budget limits?",
]
clicked_suggestion = None
for col, text in zip(suggested, suggestion_texts):
    if col.button(text, key=f"suggestion_{text}", use_container_width=True):
        clicked_suggestion = text

user_input = st.chat_input("Ask a question about your spending, budget optimization, or savings...")
prompt = clicked_suggestion or user_input

if prompt:
    st.session_state[f"advisor_messages_{user_id}"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    system_prompt = (
        f"You are a cautious, practical personal finance assistant embedded in a budgeting app. "
        f"The user operates in currency {curr}. You are given an accurate summary of their real "
        f"transaction numbers. Give concise, actionable, and grounded suggestions based strictly "
        f"on the provided figures. Do not invent numbers that are not provided. Keep responses under "
        f"220 words. You are not a licensed financial advisor, so avoid absolute declarations on "
        f"investments, taxes, or legal matters."
    )

    system_instruction = (
        f"{system_prompt}\n\n"
        f"Here is a summary of the user's financial data:\n\n{data_summary}"
    )

    # Build multi-turn conversation history using google-genai types.
    from google.genai import types

    contents = []
    for msg in st.session_state[f"advisor_messages_{user_id}"]:
        contents.append(
            types.Content(
                role=msg["role"] if msg["role"] == "user" else "model",
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )

    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            reply_text = response.text
        except Exception as e:
            reply_text = f"Sorry, I couldn't reach the AI advisor right now ({e})."

        placeholder.markdown(reply_text)

    st.session_state[f"advisor_messages_{user_id}"].append({"role": "assistant", "content": reply_text})

if st.session_state[f"advisor_messages_{user_id}"]:
    if st.button("🗑️ Clear Conversation History"):
        st.session_state[f"advisor_messages_{user_id}"] = []
        st.rerun()