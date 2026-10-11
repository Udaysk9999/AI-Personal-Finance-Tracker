"""
Shared UI helpers, design system, and formatting utilities for the
AI-Powered Personal Expense Tracking & Budget Advisor.

Theme system:
- Light and Dark modes with curated fintech color palettes.
- Call inject_css() at the top of every page.
- Call theme_toggle() in the sidebar.
- Session-persisted theme and currency preferences.
"""

import streamlit as st
import html


# ==================================================
# CATEGORIES & DESIGN TOKENS
# ==================================================

INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Investments",
    "Gifts",
    "Other Income",
]

EXPENSE_CATEGORIES = [
    "Food",
    "Bills",
    "Travel",
    "Rent",
    "Shopping",
    "Entertainment",
    "Healthcare",
    "Education",
    "Other Expense",
]

# Curated fintech palette (high-contrast, accessible)
FINANCE_COLORS = {
    "income": "#10b981",    # Emerald
    "expense": "#f43f5e",   # Rose
    "balance": "#6366f1",   # Indigo
    "warning": "#f59e0b",   # Amber
    "teal": "#14b8a6",      # Cyan/Teal
    "sky": "#0284c7",       # Sky Blue
    "violet": "#8b5cf6",    # Violet
    "neutral": "#94a3b8",   # Slate neutral
}

FINANCE_COLOR_SEQUENCE = [
    "#6366f1",  # Indigo
    "#10b981",  # Emerald
    "#f43f5e",  # Rose
    "#f59e0b",  # Amber
    "#06b6d4",  # Cyan
    "#8b5cf6",  # Violet
    "#ec4899",  # Pink
    "#14b8a6",  # Teal
    "#3b82f6",  # Blue
]


# ==================================================
# CURRENCY & FORMATTING
# ==================================================

def get_user_currency() -> str:
    """Retrieve the active user's chosen currency symbol from session state, defaulting to ₹."""
    try:
        return st.session_state.get("user_currency", "₹")
    except Exception:
        return "₹"


def format_currency(amount, symbol: str = None) -> str:
    """
    Format a numeric amount with the user's active currency symbol.
    Correctly places negative sign before the symbol: '-$50.00' instead of '$-50.00'.
    """
    curr = symbol if symbol is not None else get_user_currency()
    try:
        val = float(amount)
        if val < 0:
            return f"-{curr}{abs(val):,.2f}"
        return f"{curr}{val:,.2f}"
    except (TypeError, ValueError):
        return f"{curr}0.00"


# ==================================================
# THEME CONFIGURATION
# ==================================================

def _current_theme() -> str:
    return st.session_state.get("pft_theme", "dark")


def theme_chart_colors() -> dict:
    """Return crisp Plotly colors for the active theme."""
    if _current_theme() == "light":
        return {
            "font": "#0f172a",
            "title": "#0f172a",
            "axis": "#64748b",
            "grid": "#e2e8f0",
            "legend": "#334155",
            "marker_line": "#ffffff",
        }
    return {
        "font": "#e2e8f0",
        "title": "#f8fafc",
        "axis": "#94a3b8",
        "grid": "#1e293b",
        "legend": "#cbd5e1",
        "marker_line": "#090d16",
    }


def theme_toggle(key: str = "pft_theme_toggle"):
    """Renders a sleek theme toggle button for the sidebar."""
    if "pft_theme" not in st.session_state:
        st.session_state.pft_theme = "dark"

    current = st.session_state.pft_theme
    label = "☀️ Switch to Light Mode" if current == "dark" else "🌙 Switch to Dark Mode"

    if st.button(label, key=key, use_container_width=True):
        st.session_state.pft_theme = "light" if current == "dark" else "dark"
        st.rerun()


# ==================================================
# CSS INJECTION — PREMIUM FINTECH DESIGN SYSTEM
# ==================================================

def inject_css():
    """Inject the comprehensive fintech design system CSS into the Streamlit app."""
    theme = _current_theme()

    if theme == "light":
        vars_css = """
            --pft-bg: #f8fafc;
            --pft-surface: #ffffff;
            --pft-surface-hover: #f1f5f9;
            --pft-surface-muted: #f1f5f9;
            --pft-border: rgba(15, 23, 42, 0.08);
            --pft-border-strong: rgba(15, 23, 42, 0.16);
            --pft-border-focus: #6366f1;
            
            --pft-text-primary: #0f172a;
            --pft-text-secondary: #475569;
            --pft-text-muted: #64748b;
            
            --pft-sidebar-bg: #ffffff;
            --pft-sidebar-border: rgba(15, 23, 42, 0.08);
            
            --pft-header-grad: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(16, 185, 129, 0.04));
            --pft-header-border: rgba(99, 102, 241, 0.12);
            --pft-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --pft-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.06), 0 2px 6px -2px rgba(15, 23, 42, 0.04);
            
            --pft-input-bg: #ffffff;
            --pft-input-border: #cbd5e1;
            --pft-input-text: #0f172a;
            
            --pft-btn-primary-bg: #4f46e5;
            --pft-btn-primary-hover: #4338ca;
            --pft-btn-primary-text: #ffffff;
            
            --pft-badge-bg: rgba(99, 102, 241, 0.08);
            --pft-badge-text: #4f46e5;
        """
    else:
        vars_css = """
            --pft-bg: #0b0f19;
            --pft-surface: #111827;
            --pft-surface-hover: #1f2937;
            --pft-surface-muted: #1e293b;
            --pft-border: rgba(255, 255, 255, 0.08);
            --pft-border-strong: rgba(255, 255, 255, 0.14);
            --pft-border-focus: #818cf8;
            
            --pft-text-primary: #f8fafc;
            --pft-text-secondary: #94a3b8;
            --pft-text-muted: #64748b;
            
            --pft-sidebar-bg: #0d121f;
            --pft-sidebar-border: rgba(255, 255, 255, 0.06);
            
            --pft-header-grad: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(16, 185, 129, 0.08));
            --pft-header-border: rgba(99, 102, 241, 0.20);
            --pft-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.2);
            --pft-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.35), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
            
            --pft-input-bg: #111827;
            --pft-input-border: #334155;
            --pft-input-text: #f8fafc;
            
            --pft-btn-primary-bg: #6366f1;
            --pft-btn-primary-hover: #4f46e5;
            --pft-btn-primary-text: #ffffff;
            
            --pft-badge-bg: rgba(99, 102, 241, 0.18);
            --pft-badge-text: #a5b4fc;
        """

    st.markdown(
        f"""
        <style>
        :root {{
            {vars_css}
        }}

        /* Global Typography & Background */
        html, body, [class*="css"] {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }}

        .stApp {{
            background-color: var(--pft-bg);
            color: var(--pft-text-primary);
        }}

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {{
            background-color: var(--pft-sidebar-bg) !important;
            border-right: 1px solid var(--pft-sidebar-border) !important;
        }}

        section[data-testid="stSidebar"] .stMarkdown p {{
            color: var(--pft-text-secondary);
        }}

        /* Headings */
        h1, h2, h3, h4 {{
            color: var(--pft-text-primary) !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }}

        h1 {{ font-size: 1.85rem !important; margin-bottom: 0.5rem !important; }}
        h2 {{ font-size: 1.35rem !important; margin-top: 1.25rem !important; margin-bottom: 0.5rem !important; }}
        h3 {{ font-size: 1.15rem !important; }}

        /* Text colors */
        p, span, label, div {{
            color: var(--pft-text-primary);
        }}
        .stCaption, [data-testid="stCaptionContainer"] p {{
            color: var(--pft-text-muted) !important;
            font-size: 0.85rem !important;
        }}

        /* Header Card */
        .pft-header {{
            padding: 22px 26px;
            margin-bottom: 22px;
            border-radius: 14px;
            background: var(--pft-header-grad);
            border: 1px solid var(--pft-header-border);
            box-shadow: var(--pft-shadow);
        }}
        .pft-header-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.65rem;
            font-weight: 700;
            color: var(--pft-text-primary);
            margin: 0;
            letter-spacing: -0.02em;
        }}
        .pft-header-sub {{
            margin: 6px 0 0 0;
            color: var(--pft-text-secondary);
            font-size: 0.95rem;
            line-height: 1.45;
        }}

        /* Metric / Stat Card */
        .pft-stat-card {{
            background: var(--pft-surface);
            border: 1px solid var(--pft-border);
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: var(--pft-shadow-sm);
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
            position: relative;
            overflow: hidden;
        }}
        .pft-stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--pft-shadow);
            border-color: var(--pft-border-strong);
        }}
        .pft-stat-card::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }}
        .pft-stat-card.accent-emerald::before {{ background: #10b981; }}
        .pft-stat-card.accent-rose::before    {{ background: #f43f5e; }}
        .pft-stat-card.accent-indigo::before  {{ background: #6366f1; }}
        .pft-stat-card.accent-amber::before   {{ background: #f59e0b; }}
        .pft-stat-card.accent-cyan::before    {{ background: #06b6d4; }}

        .pft-stat-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .pft-stat-label {{
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--pft-text-secondary);
        }}
        .pft-stat-icon {{
            font-size: 1.1rem;
            opacity: 0.85;
        }}
        .pft-stat-value {{
            font-size: 1.7rem;
            font-weight: 700;
            color: var(--pft-text-primary);
            letter-spacing: -0.02em;
            line-height: 1.2;
        }}
        .pft-stat-delta {{
            margin-top: 6px;
            font-size: 0.82rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .pft-delta-pos {{ color: #10b981; }}
        .pft-delta-neg {{ color: #f43f5e; }}
        .pft-delta-neutral {{ color: var(--pft-text-secondary); }}

        /* Card Container */
        .pft-card {{
            background: var(--pft-surface);
            border: 1px solid var(--pft-border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: var(--pft-shadow-sm);
            margin-bottom: 16px;
        }}

        /* Badges */
        .pft-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}
        .pft-badge-indigo  {{ background: rgba(99, 102, 241, 0.15); color: #818cf8; }}
        .pft-badge-emerald {{ background: rgba(16, 185, 129, 0.15); color: #10b981; }}
        .pft-badge-rose    {{ background: rgba(244, 63, 94, 0.15);  color: #f43f5e; }}
        .pft-badge-amber   {{ background: rgba(245, 158, 11, 0.15); color: #f59e0b; }}
        .pft-badge-neutral {{ background: rgba(148, 163, 184, 0.15); color: #94a3b8; }}

        /* Empty State */
        .pft-empty-state {{
            text-align: center;
            padding: 36px 20px;
            background: var(--pft-surface);
            border: 1px dashed var(--pft-border-strong);
            border-radius: 12px;
            margin: 16px 0;
        }}
        .pft-empty-icon {{
            font-size: 2.2rem;
            margin-bottom: 10px;
            opacity: 0.8;
        }}
        .pft-empty-title {{
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--pft-text-primary);
            margin-bottom: 4px;
        }}
        .pft-empty-desc {{
            font-size: 0.88rem;
            color: var(--pft-text-secondary);
            max-width: 440px;
            margin: 0 auto;
        }}

        /* Buttons */
        .stButton > button {{
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            padding: 0.45rem 1rem !important;
            transition: all 0.15s ease !important;
            border: 1px solid var(--pft-border-strong) !important;
        }}
        .stButton > button[kind="primary"] {{
            background-color: var(--pft-btn-primary-bg) !important;
            border: 1px solid var(--pft-btn-primary-bg) !important;
            color: var(--pft-btn-primary-text) !important;
        }}
        .stButton > button[kind="primary"]:hover {{
            background-color: var(--pft-btn-primary-hover) !important;
            border-color: var(--pft-btn-primary-hover) !important;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25) !important;
        }}
        .stButton > button[kind="secondary"]:hover {{
            border-color: var(--pft-border-focus) !important;
            color: var(--pft-border-focus) !important;
        }}

        /* Inputs & Selectboxes */
        input, textarea, select, [data-baseweb="select"] > div {{
            border-radius: 8px !important;
            border-color: var(--pft-input-border) !important;
        }}
        .stTextInput input, .stNumberInput input, .stDateInput input, [data-baseweb="input"] input {{
            background-color: var(--pft-input-bg) !important;
            color: var(--pft-input-text) !important;
            -webkit-text-fill-color: var(--pft-input-text) !important;
        }}

        /* Section Divider */
        .pft-divider {{
            height: 1px;
            margin: 24px 0;
            background: linear-gradient(90deg, transparent, var(--pft-border-strong), transparent);
            border: none;
        }}

        /* AI Disclaimer Box */
        .ai-disclaimer {{
            padding: 14px 18px;
            border-radius: 10px;
            background: rgba(99, 102, 241, 0.08);
            border: 1px solid rgba(99, 102, 241, 0.22);
            color: var(--pft-text-secondary);
            font-size: 0.88rem;
            line-height: 1.5;
            margin-bottom: 18px;
        }}

        /* Account Sidebar Badge */
        .pft-user-badge {{
            padding: 10px 14px;
            background: var(--pft-surface-muted);
            border: 1px solid var(--pft-border);
            border-radius: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
        }}
        .pft-user-avatar {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #6366f1;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
        }}
        .pft-user-info {{
            line-height: 1.25;
            overflow: hidden;
        }}
        .pft-user-name {{
            font-weight: 600;
            font-size: 0.9rem;
            color: var(--pft-text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .pft-user-role {{
            font-size: 0.75rem;
            color: var(--pft-text-muted);
        }}

        /* Responsive Layout Overrides */
        @media (max-width: 768px) {{
            .pft-header {{
                padding: 16px 18px;
            }}
            .pft-header-title {{
                font-size: 1.35rem;
            }}
            .pft-stat-value {{
                font-size: 1.4rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==================================================
# REUSABLE COMPONENTS
# ==================================================

def page_header(title: str, subtitle: str = "", badge_text: str = None, icon: str = None):
    """
    Renders a unified page header card with title, optional subtitle, and optional status badge.
    """
    badge_html = f'<span class="pft-badge pft-badge-indigo" style="margin-left: auto;">{badge_text}</span>' if badge_text else ""
    icon_prefix = f'<span style="opacity: 0.9;">{icon}</span> ' if icon else ""
    
    st.markdown(
        f"""
        <div class="pft-header">
            <div class="pft-header-title">
                {icon_prefix}{title}
                {badge_html}
            </div>
            {f'<p class="pft-header-sub">{subtitle}</p>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_divider():
    """Renders a sleek gradient section divider."""
    st.markdown('<hr class="pft-divider" />', unsafe_allow_html=True)


def metric_card(label: str, value: str, delta: str = None, accent: str = "indigo", icon: str = None, help_text: str = None):
    """
    Renders a fintech stat card.
    accent: "emerald" | "rose" | "indigo" | "amber" | "cyan"
    """
    delta_html = ""
    if delta is not None and str(delta).strip():
        delta_str = str(delta).strip()
        if delta_str.startswith("-"):
            cls = "pft-delta-neg"
            arrow = "↓ "
        elif delta_str.startswith("+"):
            cls = "pft-delta-pos"
            arrow = "↑ "
        else:
            cls = "pft-delta-neutral"
            arrow = ""
        sub = f" <span style='color: var(--pft-text-muted); font-weight: 400;'>{help_text}</span>" if help_text else ""
        delta_html = f'<div class="pft-stat-delta {cls}">{arrow}{delta_str}{sub}</div>'

    icon_html = f'<div class="pft-stat-icon">{icon}</div>' if icon else ""

    st.markdown(
        f"""
        <div class="pft-stat-card accent-{accent}">
            <div class="pft-stat-header">
                <span class="pft-stat-label">{html.escape(label)}</span>
                {icon_html}
            </div>
            <div class="pft-stat-value">{html.escape(str(value))}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, description: str, icon: str = "📊"):
    """Renders a clean empty-state message with guidance."""
    st.markdown(
        f"""
        <div class="pft-empty-state">
            <div class="pft-empty-icon">{icon}</div>
            <div class="pft-empty-title">{html.escape(title)}</div>
            <div class="pft-empty-desc">{html.escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "indigo"):
    """Small pill badge. kind: 'emerald' | 'rose' | 'amber' | 'indigo' | 'neutral'."""
    st.markdown(f'<span class="pft-badge pft-badge-{kind}">{html.escape(text)}</span>', unsafe_allow_html=True)


def card_start():
    """Open a card container."""
    st.markdown('<div class="pft-card">', unsafe_allow_html=True)


def card_end():
    """Close a card container."""
    st.markdown("</div>", unsafe_allow_html=True)
