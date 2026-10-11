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
    '<div class="ai-disclaimer">'
    '<strong>🛡️ Privacy & Reliability Notice:</strong> The advisor operates strictly on aggregated summaries '
    'of your real transactions, budgets, and savings targets (no account numbers or personal identities). '
    'Calculations for balances, limits, and timelines are computed deterministically before reaching the AI. '
    'Gemini is used to synthesize insights, explain trade-offs, and generate actionable recommendations.'
    '</div>',
    unsafe_allow_html=True,
)

# ==================================================
# API KEY RESOLUTION
# ==================================================

api_key = load_gemini_api_key()

if not api_key:
    st.markdown("### 🔑 Connect Your Gemini API Key")
    st.info(
        "To enable your personalized AI Financial Advisor, please connect your Google Gemini API key. "
        "You can enter it directly below for this session, or configure it permanently in your deployment settings."
    )

    with st.container():
        st.markdown("**Enter Gemini API Key for this Session:**")
        key_col, btn_col = st.columns([3, 1])
        with key_col:
            user_input_key = st.text_input(
                "Gemini API Key",
                type="password",
                placeholder="Paste your Gemini API key (e.g. AQ... or AIza...)",
                label_visibility="collapsed",
                key="inline_gemini_key_input",
            )
        with btn_col:
            connect_btn = st.button("🚀 Connect Advisor", type="primary", use_container_width=True)

        if connect_btn and user_input_key.strip():
            cleaned = user_input_key.strip().strip("'\"")
            st.session_state["gemini_api_key"] = cleaned
            os.environ["GEMINI_API_KEY"] = cleaned
            try:
                from pathlib import Path
                secrets_dir = Path(".streamlit")
                secrets_dir.mkdir(parents=True, exist_ok=True)
                secrets_path = secrets_dir / "secrets.toml"
                secrets_path.write_text(f'GEMINI_API_KEY = "{cleaned}"\n', encoding="utf-8")
            except Exception:
                pass
            st.success("✅ Gemini API Key connected! Initializing your advisor...")
            st.rerun()

    with st.expander("☁️ Setting up permanently on Streamlit Community Cloud (Advanced Settings)", expanded=True):
        st.markdown(
            """
            If you deployed this app to **Streamlit Community Cloud**, configure your secret in the cloud dashboard:

            1. Go to your app dashboard at [share.streamlit.io](https://share.streamlit.io)
            2. Click the **3 dots (`⋮`)** next to your app → **Settings** → **Secrets** (or in **Advanced Settings** when deploying)
            3. Paste the following exact TOML format (make sure to include `GEMINI_API_KEY = ` and quotes):
            ```toml
            GEMINI_API_KEY = "your_actual_api_key_here"
            ```
            > ⚠️ **Common Mistake:** Do not just paste the bare key by itself without `GEMINI_API_KEY = "..."`! TOML format requires the variable name and quotation marks.
            4. Click **Save**, then click **Reboot App** if the app does not reload automatically.

            👉 You can get a free Gemini API key anytime at [Google AI Studio](https://aistudio.google.com/app/apikey).
            """
        )
    st.stop()

# Add sidebar indicator and management for active key
with st.sidebar.expander("⚙️ Gemini AI Advisor", expanded=False):
    st.markdown("🟢 **Status:** Connected")
    masked = "••••••••" + (api_key[-4:] if len(api_key) > 4 else "")
    st.caption(f"Key: `{masked}`")
    st.caption(f"Model: `{DEFAULT_GEMINI_MODEL}`")
    if st.button("Change / Disconnect Key", key="disconnect_key_btn", use_container_width=True):
        st.session_state.pop("gemini_api_key", None)
        st.session_state.pop("GEMINI_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        st.rerun()

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
has_data = ctx.get("has_data", False)

data_summary = format_context_for_prompt(ctx)
system_instruction = get_advisor_system_instruction(curr=curr, data_summary=data_summary)

if has_data:
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
else:
    st.info(
        "💡 **General Financial Advisory Mode:** No transactions are recorded yet in this account. "
        "You can chat with your AI Advisor below for general financial guidance, budgeting rules (like 50/30/20), "
        "and savings advice! Once you record transactions in **Transaction Management**, the advisor will automatically "
        "tailor recommendations to your exact spending and income."
    )

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
if has_data:
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
else:
    q_rows = [
        [
            "How does the 50/30/20 budgeting rule work?",
            "How should I build an emergency fund?",
            "What are effective tips to cut down daily expenses?",
        ],
        [
            "How much of my income should I aim to save?",
            "What is the difference between essential and discretionary expenses?",
            "How do I set realistic financial goals?",
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
        text_content = str(msg.get("content", "")).strip()
        if text_content:
            contents.append(
                types.Content(
                    role=role_tag,
                    parts=[types.Part.from_text(text=text_content)],
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
        display_reply = reply_text.strip() if reply_text and reply_text.strip() else (
            f"⚠️ **Could not generate response:** {err}" if err else "I was unable to analyze your request. Please try asking again."
        )
        st.markdown(display_reply)

    # Append assistant turn to session history
    st.session_state[history_key].append({"role": "assistant", "content": display_reply})
    st.rerun()