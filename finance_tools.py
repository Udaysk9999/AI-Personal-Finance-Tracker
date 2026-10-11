from __future__ import annotations

import io
from datetime import date
from typing import Any

import pandas as pd


def parse_statement(uploaded_file, user_transactions: list | None = None) -> pd.DataFrame:
    """
    Parse uploaded bank statements (CSV/Excel).
    Automatically suggests initial categories based on transaction descriptions
    so users don't get all unmapped rows as 'Other'.
    """
    from finance_ml import suggest_category

    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        raw = pd.read_csv(uploaded_file)
    elif name.endswith((".xlsx", ".xls")):
        raw = pd.read_excel(uploaded_file)
    else:
        raise ValueError("Upload a CSV or Excel file.")

    if raw.empty:
        raise ValueError("The uploaded file is empty.")

    columns = {str(col).strip().lower(): col for col in raw.columns}

    def find(*names):
        for n in names:
            if n in columns:
                return columns[n]
        return None

    date_col = find("date", "transaction date", "value date")
    amount_col = find("amount", "transaction amount", "debit", "credit")
    type_col = find("type", "transaction type", "debit/credit")
    category_col = find("category", "categories")
    desc_col = find("description", "merchant", "narration", "details", "particulars")

    if date_col is None or amount_col is None:
        raise ValueError("The file must contain Date and Amount columns.")

    result = pd.DataFrame()
    result["Date"] = pd.to_datetime(raw[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    result["Amount"] = pd.to_numeric(raw[amount_col], errors="coerce")

    if type_col:
        result["Type"] = (
            raw[type_col]
            .astype(str)
            .str.strip()
            .str.title()
            .replace({"Debit": "Expense", "Credit": "Income"})
        )
    else:
        result["Type"] = "Expense"

    # Category handling: if provided in file, use it; otherwise suggest based on description
    if category_col:
        raw_cats = raw[category_col].fillna("").astype(str).str.strip()
    else:
        raw_cats = pd.Series([""] * len(raw))

    descriptions = (
        raw[desc_col].fillna("").astype(str).str.strip()
        if desc_col
        else pd.Series(["Imported transaction"] * len(raw))
    )
    result["Description"] = descriptions

    # Smart category assignment if missing or generic
    assigned_cats = []
    for cat, desc, tx_type in zip(raw_cats, descriptions, result["Type"]):
        if cat and cat.lower() not in ("", "other", "uncategorized", "nan"):
            assigned_cats.append(cat)
        else:
            suggestion = suggest_category(
                desc,
                tx_type=tx_type,
                user_transactions=user_transactions,
                fallback=True,
            )
            assigned_cats.append(suggestion["category"] if suggestion else "Other Expense")

    result["Category"] = assigned_cats

    result = result.dropna(subset=["Date", "Amount"])
    result = result[result["Amount"] > 0]
    result.loc[~result["Type"].isin(["Income", "Expense"]), "Type"] = "Expense"

    if result.empty:
        raise ValueError("No valid transactions were found.")

    return result.reset_index(drop=True)


def export_transactions(transactions) -> pd.DataFrame:
    return pd.DataFrame(
        transactions,
        columns=["ID", "Date", "Type", "Category", "Amount", "Description"],
    )


def budget_alerts(
    budgets: list[tuple[str, float]],
    transactions: list,
    warning_threshold: float = 0.80,
) -> list[dict[str, Any]]:
    """
    Proactively identify budgets approaching limits or over budget.
    - Uses 80% threshold for approaching limits (customizable).
    - Prevents duplicate or contradictory alerts (each category gets one alert: 'over' or 'warning').
    - Handles zero/negative budgets safely without DivisionByZero.
    - Provides spent, limit, remaining, over_by, utilization percentage, and status.
    """
    if not budgets or not transactions:
        return []

    df = export_transactions(transactions)
    if df.empty:
        return []

    df["Date"] = pd.to_datetime(df["Date"])
    today = date.today()
    current = df[
        (df["Type"] == "Expense")
        & (df["Date"].dt.year == today.year)
        & (df["Date"].dt.month == today.month)
    ]
    spent = current.groupby("Category")["Amount"].sum().to_dict() if not current.empty else {}

    alerts = []
    for category, limit in budgets:
        limit_val = float(limit)
        amount = float(spent.get(category, 0.0))

        # Safe zero budget handling
        if limit_val <= 0:
            if amount > 0:
                alerts.append({
                    "category": category,
                    "spent": amount,
                    "limit": limit_val,
                    "remaining": 0.0,
                    "over_by": amount,
                    "percent": 1.0,
                    "level": "over",
                    "status": "over",
                    "message": f"Zero budget allocated; total recorded spend is {amount:,.2f}.",
                })
            continue

        pct = amount / limit_val
        remaining = max(0.0, limit_val - amount)
        over_by = max(0.0, amount - limit_val)

        if pct >= 1.0:
            alerts.append({
                "category": category,
                "spent": amount,
                "limit": limit_val,
                "remaining": 0.0,
                "over_by": over_by,
                "percent": pct,
                "level": "over",
                "status": "over",
                "message": f"Over budget by {over_by:,.2f} ({pct * 100:.1f}% used).",
            })
        elif pct >= warning_threshold:
            alerts.append({
                "category": category,
                "spent": amount,
                "limit": limit_val,
                "remaining": remaining,
                "over_by": 0.0,
                "percent": pct,
                "level": "warning",
                "status": "approaching",
                "message": f"Approaching limit: {remaining:,.2f} cushion remaining ({pct * 100:.1f}% used).",
            })

    # Sort critical first (highest percentage used)
    alerts.sort(key=lambda a: a["percent"], reverse=True)
    return alerts


def build_report_pdf(username, transactions, budgets, goals, health, prediction, alerts):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8))
    story = [
        Paragraph("Personal Finance Report", styles["Title"]),
        Paragraph(f"Prepared for {username} · {date.today().isoformat()}", styles["Normal"]),
        Spacer(1, 16),
    ]
    df = export_transactions(transactions)
    income = float(df.loc[df["Type"] == "Income", "Amount"].sum()) if not df.empty else 0
    expenses = float(df.loc[df["Type"] == "Expense", "Amount"].sum()) if not df.empty else 0
    story.append(
        Paragraph(
            f"<b>Summary</b><br/>Income: ₹{income:,.2f}<br/>Expenses: ₹{expenses:,.2f}<br/>Balance: ₹{income-expenses:,.2f}",
            styles["Heading2"],
        )
    )
    if health.get("score") is not None:
        story.append(Paragraph(f"Financial Health Score: {health['score']}/100", styles["Heading2"]))
    if prediction.get("status") == "ok":
        story.append(Paragraph(f"Predicted next-month expenses: ₹{prediction['amount']:,.2f}", styles["Normal"]))
    if alerts:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Budget Alerts", styles["Heading2"]))
        data = [["Category", "Spent", "Limit", "Usage"]] + [
            [a["category"], f"₹{a['spent']:,.2f}", f"₹{a['limit']:,.2f}", f"{a['percent']*100:.0f}%"]
            for a in alerts
        ]
        table = Table(data, colWidths=[2.2 * inch, 1.2 * inch, 1.2 * inch, 0.8 * inch])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6C63FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ])
        )
        story.append(table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Recent Transactions", styles["Heading2"]))
    if not df.empty:
        data = [["Date", "Type", "Category", "Amount"]] + [
            [str(r["Date"]), r["Type"], r["Category"], f"₹{r['Amount']:,.2f}"]
            for _, r in df.head(20).iterrows()
        ]
        table = Table(data, repeatRows=1, colWidths=[1.2 * inch, 1.0 * inch, 1.7 * inch, 1.2 * inch])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6C63FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ])
        )
        story.append(table)
    doc.build(story)
    return output.getvalue()
