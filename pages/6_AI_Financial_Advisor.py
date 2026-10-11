import streamlit as st
import pandas as pd
import os

from auth import require_login
from database import create_database
from utils import (
    inject_css,
    page_header,
    section_divider,
    empty_state,
    format_currency,
    get_user_currency,
    metric_card,
)
from advisor_engine import (
    load_gemini_api_key,
    build_financial_context,
    format_context_for_prompt,
    get_advisor_system_instruction,
    generate_advisor_reply,
    DEFAULT_GEMINI_MODEL,
)

st.set_page_config(page_title="AI Financial Advisor", page_icon="🤖", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "AI Financial Advisor",
    "Personalized, accurate, and actionable financial guidance grounded in your real financial data.",
    badge_text="Gemini 3.8",
    icon="🤖",
)

st.markdown(
    """<div class="ai-disclaimer">
        <strong>🛡️ Privacy & Reliability Notice:</strong> The advisor operates strictly on aggregated summaries
        of your real transactions, budgets, and savings targets (no account numbers or personal identities).
        Calculations for balances, limits, and timelines are computed deterministically before reaching the AI.
        Gemini is used to synthesize insights, explain trade-offs, and generate actionable recommendations.
    </div>""",
    unsafe_allow_html=True,
)

# ==================================================
# API KEY RESOLUTION
# ==================================================

api_key = load_gemini_api_key()

if not api_key:
    st.warning(
        "**Gemini API Key Required**\n\n"
        "To enable your AI Financial Advisor, please configure your API key by doing one of the following:\n"
        "- Add `GEMINI_API_KEY=\"your_key_here\"` to the `.env` file in the project root.\n"
        "- Or set the `GEMINI_API_KEY` environment variable in your terminal.\n"
        "- Or add `GEMINI_API_KEY = \"...\"` to `.streamlit/secrets.toml`.\n\n"
        "👉 You can obtain a free Gemini API key (no credit card required) at [Google AI Studio](https://aistudio.google.com/app/apikey)."
    )
    st.stop()

try:
    from google import genai
    from google.genai import types
except ImportError:
    st.error(
        "The `google-genai` SDK is not installed in the active environment. "
        "Please run `pip install google-genai`."
    )
    st.stop()

# ==================================================
# BUILD REAL FINANCIAL DATA SNAPSHOT
# ==================================================

ctx = build_financial_context(user_id, curr=curr)

if not ctx.get("has_data"):
    empty_state(
        "No Transactions Recorded Yet",
        "Record income or expenses on the Transaction Management page first so the advisor has real numbers to evaluate.",
        icon="💳",
    )
    st.stop()

data_summary = format_context_for_prompt(ctx)
system_instruction = get_advisor_system_instruction(curr=curr, data_summary=data_summary)

# Display deterministic financial summary cards
st.subheader("Financial Snapshot Grounding the Advisor")
sn_col1, sn_col2, sn_col3, sn_col4 = st.columns(4)
with sn_col1:
    metric_card(
        "Total Income",
        format_currency(ctx["total_income"], curr),
        accent="emerald",
        icon="📈",
        help_text=f"Month: {format_currency(ctx['current_month_income'], curr)}",
    )
with sn_col2:
    metric_card(
        "Total Expenses",
        format_currency(ctx["total_expenses"], curr),
        accent="rose",
        icon="📉",
        help_text=f"Month: {format_currency(ctx['current_month_expense'], curr)}",
    )
with sn_col3:
    metric_card(
        "Net Balance",
        format_currency(ctx["net_balance"], curr),
        accent="indigo" if ctx["net_balance"] >= 0 else "rose",
        icon="💳",
        help_text=f"Month Surplus: {format_currency(ctx['current_month_net'], curr)}",
    )
with sn_col4:
    metric_card(
        "Savings Rate",
        f"{ctx['savings_rate']:.1f}%",
        accent="cyan" if ctx["savings_rate"] >= 20 else "amber",
        icon="🎯",
        help_text=f"This Month: {ctx['current_month_savings_rate']:.1f}%",
    )

with st.expander("🔍 View deterministic financial data supplied to the advisor", expanded=False):
    st.markdown("```text\n" + data_summary + "\n```")

# ==================================================
# CHAT INTERFACE & CONVERSATION HISTORY
# ==================================================

section_divider()

chat_hdr_col1, chat_hdr_col2 = st.columns([3, 1])
with chat_hdr_col1:
    st.subheader("💬 Ask Your Financial Advisor")
with chat_hdr_col2:
    history_key = f"advisor_messages_{user_id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []
    if st.session_state[history_key]:
        if st.button("🔄 Start New Conversation", key="clear_chat_top", use_container_width=True):
            st.session_state[history_key] = []
            st.rerun()

# Display conversation history
for msg in st.session_state[history_key]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Quick example question pills grounded in core advisor capabilities
st.caption("Common inquiries (click to ask):")
q_rows = [
    [
        "Analyze my spending this month.",
        "Which category is costing me the most?",
        "Where can I reduce my expenses?",
    ],
    [
        "Am I overspending compared with last month?",
        "How much can I realistically save next month?",
        "Which budgets are close to their limits?",
        "Suggest a savings plan based on my income and expenses.",
    ],
]

clicked_question = None
for row_questions in q_rows:
    cols = st.columns(len(row_questions))
    for col, q_text in zip(cols, row_questions):
        if col.button(q_text, key=f"q_btn_{q_text}", use_container_width=True):
            clicked_question = q_text

user_input = st.chat_input("Ask about your spending, budget warnings, goal planning, or savings...")
prompt = (clicked_question or user_input or "").strip()

if prompt:
    # Append user turn to session history
    st.session_state[history_key].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build multi-turn Content list with a sliding window (last 10 messages = 5 turns)
    recent_messages = st.session_state[history_key][-10:]
    contents = []
    for msg in recent_messages:
        role_tag = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role_tag,
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )

    with st.chat_message("assistant"):
        with st.spinner("Analyzing your finances with AI..."):
            reply_text, err = generate_advisor_reply(
                api_key=api_key,
                contents=contents,
                system_instruction=system_instruction,
                model_name=DEFAULT_GEMINI_MODEL,
                max_retries=2,
            )
        st.markdown(reply_text)

    # Append assistant turn to session history
    st.session_state[history_key].append({"role": "assistant", "content": reply_text})
    st.rerun()