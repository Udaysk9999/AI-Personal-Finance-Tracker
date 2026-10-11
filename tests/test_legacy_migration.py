"""Tests for legacy single-user database migration."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

import database


def test_legacy_migration():
    """A pre-existing single-user database should be migrated safely.

    Old rows end up under an inaccessible legacy owner, and a newly
    registered user starts with empty data.
    """
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(tmp_dir) / "legacy.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT
            );
            CREATE TABLE budgets (
                category TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE savings_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_amount REAL NOT NULL,
                current_amount REAL NOT NULL DEFAULT 0,
                target_date TEXT,
                created_at TEXT NOT NULL
            );
            INSERT INTO transactions (date, type, category, amount, description)
                VALUES ('2026-01-01', 'Income', 'Salary', 1000, 'legacy');
            INSERT INTO budgets (category, monthly_limit, updated_at)
                VALUES ('Food', 200, '2026-01-01');
            INSERT INTO savings_goals (name, target_amount, current_amount, target_date, created_at)
                VALUES ('Old goal', 500, 10, '2027-01-01', '2026-01-01');
        """)
        conn.commit()
        conn.close()

        # Point database module at the legacy db and run migration
        database.DB_NAME = str(db_path)
        database.create_database()

        # A new user should start with empty data
        new_user = database.create_user("newuser_legacy", "newuser-password")
        assert database.get_transactions(new_user) == []
        assert database.get_budgets(new_user) == []
        assert database.get_savings_goals(new_user) == []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
