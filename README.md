# Personal Finance Tracker

A multi-page Streamlit app for tracking personal income and expenses, with budgets, monthly analytics, savings goals, and an AI financial advisor — backed by a local SQLite database.

## Features

- **Transaction Management** — add, edit, search, filter by date/type/category, delete, and export transactions to CSV, with intelligent category auto-suggestions.
- **Statement Import** — upload bank statements in CSV or Excel format with smart auto-categorization review before batch importing.
- **Financial Dashboard** — income/expense summary, balance, savings rate, category breakdown charts, and smart spending insights.
- **Budget Tracking & PDF Export** — set monthly spending limits per category, track progress bars with real-time alerts, and download comprehensive monthly PDF financial reports.
- **Monthly Analytics** — income vs. expenses trend chart over time, month-over-month comparison, spending breakdown, expense forecasts with reliability badges, and anomaly detection.
- **Savings Goals & Planning** — create savings goals with target amounts and dates, track visual progress, and calculate required monthly contributions with feasibility indicators.
- **AI Financial Advisor** — intelligent multi-turn chat powered by Google Gemini (`gemini-3.8-flash`), grounded in user-scoped financial summaries with privacy-safe redactions and quick action prompt chips.
- **Profile & Settings** — manage user profile, switch display currency (₹ INR, $ USD, € EUR, £ GBP, ¥ JPY, C$ CAD, A$ AUD, ₣ CHF), change password, export full data, or permanently delete account with cascade cleanup.
- **Multi-Currency Support** — select your preferred currency in Profile & Settings or quick sidebar toggle; all dashboards, reports, and PDFs format dynamically.
- **Financial Health Score** — deterministic 0–100 score based on savings rate, expense ratio, budget adherence, goal progress, and consistency.

## Multi-user accounts

The app supports independent accounts with Register, Log In, and Log out controls. Each account receives a unique user ID, and transactions, budgets, savings goals, dashboard calculations, analytics, and AI Advisor summaries are strictly filtered to that authenticated user. Ownership checks are applied to every update and delete operation.

Users must choose a username and a password of at least eight characters. Newly registered accounts always start with empty financial data. If an existing single-user `finance_tracker.db` is present, the first startup migrates its old rows under an inaccessible legacy owner instead of exposing them to a new account.

### Gmail password recovery setup

Registration requires an email address so that the Forgot Password flow can deliver a one-time verification code. Password recovery uses Gmail SMTP with a Gmail **App Password**, not a normal Gmail password. Add these values to `.env` or Streamlit Secrets in `.streamlit/secrets.toml`:

```toml
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USERNAME = "your-gmail-address@gmail.com"
SMTP_APP_PASSWORD = "your-16-character-gmail-app-password"
SMTP_FROM_EMAIL = "your-gmail-address@gmail.com"
```

`SMTP_HOST` and `SMTP_PORT` default to Gmail's `smtp.gmail.com` and `587`; `SMTP_USERNAME`, `SMTP_APP_PASSWORD`, and optionally `SMTP_FROM_EMAIL` are the important account settings. Enable two-step verification on the Gmail account before creating the App Password. Never commit `.env` or `.streamlit/secrets.toml` or expose these values in the UI.

## Project structure

```
Personal-Finance-Tracker/
├── app.py                          # Home page: quick add + at-a-glance summary + quick stats
├── database.py                     # SQLite setup, user auth, and CRUD for transactions, budgets, goals, currency
├── utils.py                        # Shared CSS, category lists, currency formatting helpers, color palettes
├── finance_ml.py                   # User-scoped prediction, anomaly detection, categorization, scoring, and simulation logic
├── finance_tools.py                # Bank statement parsing (CSV/Excel), budget alerts, and PDF report generation
├── pages/
│   ├── 1_Transaction_Management.py # Transaction CRUD, filtering, CSV/Excel statement import
│   ├── 2_Financial_Dashboard.py    # Metric cards, donut breakdown, recent activity, financial health
│   ├── 3_Budget_Tracking.py        # Category budget limits, alerts, monthly PDF export
│   ├── 4_Monthly_Analytics.py      # Trends, MoM comparisons, forecasts, anomaly reviews
│   ├── 5_Savings_Goals.py          # Goals tracking, contributions, monthly savings planner
│   ├── 6_AI_Financial_Advisor.py   # Gemini chat advisor, privacy drawer, prompt chips, conversation reset
│   └── 7_Profile_Settings.py       # Currency preference, password change, account deletion
├── tests/                          # 46 comprehensive unit and integration tests
├── requirements.txt                # Python package dependencies
├── .env                            # Local environment variables (GEMINI_API_KEY, SMTP)
└── README.md
```

Streamlit automatically builds the sidebar navigation from the `pages/` folder — no extra routing code needed.

## Requirements

- Python 3.9+
- streamlit
- pandas
- plotly
- google-genai (for the AI Financial Advisor)
- scikit-learn (used by forecasting and ML models)
- reportlab (for monthly PDF reports)
- openpyxl (for Excel statement imports)
- python-dotenv (for loading environment variables from `.env`)

## Setup

1. Clone or download this project, keeping the folder structure above intact.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your Gemini API key for the AI Financial Advisor page. You can add it to a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your-gemini-api-key-here
   ```
   Or inside `.streamlit/secrets.toml`:
   ```toml
   GEMINI_API_KEY = "your-gemini-api-key-here"
   ```
   Get a free key (no credit card required) at https://aistudio.google.com/app/apikey. Keep `.env` and `.streamlit/secrets.toml` out of version control (both are listed in `.gitignore`). Without a key, every other page still works — only the advisor page requires a key.
4. Run the app:
   ```bash
   streamlit run app.py
   ```
5. Open the URL Streamlit prints (usually `http://localhost:8501`).

A file named `finance_tracker.db` will be created automatically the first time you run the app. It is ignored by Git to keep your financial data private.

## Usage

1. **Home** — register or log in, quickly add a transaction, or check your total income/expenses/balance.
2. **Transaction Management** — full transaction log with date/type/category filters, per-row edit and delete, CSV export, and CSV/Excel statement imports.
3. **Financial Dashboard** — charts, savings rate, and financial health score based on all your data.
4. **Budget Tracking** — set monthly category limits, review alerts, and download a Monthly PDF Financial Report.
5. **Monthly Analytics** — spot trends across months, compare month-over-month spending, review linear regression forecasts with reliability badges, and check anomaly detection.
6. **Savings Goals** — set savings targets, track progress, and calculate required monthly contributions with feasibility indicators.
7. **AI Financial Advisor** — chat with Gemini grounded in your actual financial metrics; reset conversation or use starter prompts anytime.
8. **Profile & Settings** — switch display currency (₹, $, €, £, ¥, etc.), update password, or delete your account.

## Privacy & Security

- All financial records are strictly tied to `user_id` and enforced with parameterized queries.
- Cross-user database operations are rejected at the query level (`WHERE id = ? AND user_id = ?`).
- The AI Advisor receives structured summary totals and metrics, never raw transaction lists or personally identifiable credentials.
- Secrets, databases (`*.db`), `.env`, and cache directories are excluded via `.gitignore`.

