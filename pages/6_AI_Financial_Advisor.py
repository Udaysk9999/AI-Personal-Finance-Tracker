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
)
from advisor_engine import (
    load_gemini_api_key,
    build_financial_context,
    format_context_for_prompt,
    get_advisor_system_instruction,
)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

st.set_page_config(page_title="AI Financial Advisor", page_icon="🤖", layout="wide")
inject_css()

create_database()
user_id, username = require_login()
curr = get_user_currency()

page_header(
    "AI Financial Advisor",
    "Personalized, cautious financial intelligence and budget optimization grounded in your real numbers.",
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
# BUILD FINANCIAL CONTEXT & SUMMARY
# ==================================================

ctx = build_financial_context(user_id, curr=curr)

if not ctx.get("has_data"):
    empty_state(
        "No Transactions Recorded Yet",
        "Record income or expenses on the Transaction Management page first so the advisor has data to evaluate.",
        icon="💳",
    )
    st.stop()

data_summary = format_context_for_prompt(ctx)
system_instruction = get_advisor_system_instruction(curr=curr, data_summary=data_summary)

with st.expander("🔍 View deterministic financial data supplied to the advisor", expanded=False):
    st.markdown("```text\n" + data_summary + "\n```")

# ==================================================
# CHAT INTERFACE & CONVERSATION HISTORY
# ==================================================

section_divider()
st.subheader("💬 Ask Your Financial Advisor")

history_key = f"advisor_messages_{user_id}"
if history_key not in st.session_state:
    st.session_state[history_key] = []

# Display conversation history
for msg in st.session_state[history_key]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Quick example question pills grounded in core advisor capabilities
st.caption("Common inquiries:")
q_cols = st.columns(5)
questions = [
    "Where am I spending the most?",
    "Which expenses could I reduce?",
    "Which category is closest to its budget limit?",
    f"How can I save {curr}2,000 next month?",
    "How much should I save monthly for my goals?",
]
clicked_question = None
for col, q_text in zip(q_cols, questions):
    if col.button(q_text, key=f"q_btn_{q_text}", use_container_width=True):
        clicked_question = q_text

user_input = st.chat_input("Ask about your spending, budget warnings, goal planning, or savings...")
prompt = clicked_question or user_input

if prompt:
    # Append user turn
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
        placeholder = st.empty()
        with st.spinner("Analyzing your finances with AI..."):
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=DEFAULT_GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                    ),
                )
                reply_text = response.text.strip() if (response and response.text) else "I reviewed your figures, but could not produce a response. Please try rephrasing your question."
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str.upper():
                    reply_text = "⚠️ **Quota Limit Reached:** The Gemini API free-tier rate limit has been temporarily reached. Please wait a minute before sending your next inquiry."
                elif "404" in err_str:
                    reply_text = f"⚠️ **Model Availability Error:** {err_str}. Please verify that '{DEFAULT_GEMINI_MODEL}' is accessible for your API key."
                elif "503" in err_str or "UNAVAILABLE" in err_str.upper():
                    reply_text = "⚠️ **High Server Demand (503):** The Gemini model is currently experiencing high temporary demand on Google's servers. Please try sending your inquiry again in a few moments."
                elif "API_KEY" in err_str.upper() or "403" in err_str or "UNAUTHENTICATED" in err_str.upper():
                    reply_text = "⚠️ **Authentication Error:** The provided Gemini API key appears invalid or expired. Please check your key in `.env` or Google AI Studio."
                else:
                    reply_text = f"⚠️ **Service Disruption:** Could not reach the Gemini API at this time ({err_str}). Your underlying financial data remains safe."

        placeholder.markdown(reply_text)

    # Append assistant turn
    st.session_state[history_key].append({"role": "assistant", "content": reply_text})

if st.session_state[history_key]:
    st.write("")
    if st.button("🗑️ Clear Conversation History", help="Reset chat memory for this account"):
        st.session_state[history_key] = []
        st.rerun()