"""Tests for user isolation: two users should never see each other's data."""

import os
import tempfile
from pathlib import Path

import database


def setup_module():
    """Point the database at a temporary file for this test module."""
    global _tmp_dir
    _tmp_dir = tempfile.mkdtemp()
    database.DB_NAME = str(Path(_tmp_dir) / "test_isolation.db")
    database.create_database()


def teardown_module():
    """Clean up the temporary database."""
    import shutil
    shutil.rmtree(_tmp_dir, ignore_errors=True)


def test_user_creation_and_auth():
    alice = database.create_user("alice", "alice-password")
    bob = database.create_user("bob", "bob-password")
    assert alice != bob
    assert database.verify_user("alice", "alice-password")["id"] == alice
    assert database.verify_user("alice", "wrong-password") is None
    assert database.verify_user("bob", "bob-password")["id"] == bob


def test_transaction_isolation():
    alice = database.create_user("alice_txn", "alice-password")
    bob = database.create_user("bob_txn", "bob-password")

    database.add_transaction(alice, "2026-09-01", "Income", "Salary", 100000, "Alice salary")
    database.add_transaction(bob, "2026-09-01", "Income", "Salary", 50000, "Bob salary")

    assert len(database.get_transactions(alice)) == 1
    assert database.get_transactions(alice)[0][-1] == "Alice salary"
    assert len(database.get_transactions(bob)) == 1
    assert database.get_transactions(bob)[0][-1] == "Bob salary"


def test_budget_isolation():
    alice = database.create_user("alice_bgt", "alice-password")
    bob = database.create_user("bob_bgt", "bob-password")

    database.set_budget(alice, "Food", 10000)
    database.set_budget(bob, "Food", 5000)

    assert database.get_budgets(alice) == [("Food", 10000.0)]
    assert database.get_budgets(bob) == [("Food", 5000.0)]


def test_savings_goal_isolation():
    alice = database.create_user("alice_goal", "alice-password")
    bob = database.create_user("bob_goal", "bob-password")

    database.add_savings_goal(alice, "Emergency Fund", 200000, "2027-01-01")
    database.add_savings_goal(bob, "Vacation", 80000, "2027-06-01")

    assert database.get_savings_goals(alice)[0][1] == "Emergency Fund"
    assert database.get_savings_goals(bob)[0][1] == "Vacation"


def test_cross_user_operations_are_noop():
    alice = database.create_user("alice_cross", "alice-password")
    bob = database.create_user("bob_cross", "bob-password")

    database.add_transaction(alice, "2026-09-01", "Income", "Salary", 100000, "Alice salary")
    database.set_budget(alice, "Food", 10000)
    database.add_savings_goal(alice, "Emergency Fund", 200000, "2027-01-01")
    alice_goal_id = database.get_savings_goals(alice)[0][0]
    alice_txn_id = database.get_transactions(alice)[0][0]

    # Bob tries to delete/update Alice's data — should be no-ops
    database.delete_transaction(bob, alice_txn_id)
    database.delete_budget(bob, "Food")
    database.update_savings_goal_amount(bob, alice_goal_id, 999999)
    database.delete_savings_goal(bob, alice_goal_id)

    # Alice's data should be unchanged
    assert len(database.get_transactions(alice)) == 1
    assert database.get_budgets(alice) == [("Food", 10000.0)]
    assert database.get_savings_goals(alice)[0][3] == 0.0  # current_amount unchanged
    assert len(database.get_savings_goals(alice)) == 1


def test_transaction_update_and_isolation():
    alice = database.create_user("alice_update", "alice-password")
    bob = database.create_user("bob_update", "bob-password")

    database.add_transaction(alice, "2026-09-01", "Expense", "Food", 500.0, "Alice lunch")
    alice_txn = database.get_transactions(alice)[0]
    alice_txn_id = alice_txn[0]

    # Alice successfully updates her transaction
    updated = database.update_transaction(alice, alice_txn_id, "2026-09-02", "Expense", "Groceries", 650.0, "Alice dinner")
    assert updated is True
    alice_updated_txns = database.get_transactions(alice)
    assert len(alice_updated_txns) == 1
    assert alice_updated_txns[0][1] == "2026-09-02"
    assert alice_updated_txns[0][2] == "Expense"
    assert alice_updated_txns[0][3] == "Groceries"
    assert alice_updated_txns[0][4] == 650.0
    assert alice_updated_txns[0][5] == "Alice dinner"

    # Bob tries to maliciously edit Alice's transaction - must fail and be no-op
    bob_attempt = database.update_transaction(bob, alice_txn_id, "2026-09-03", "Income", "Salary", 999999.0, "Hacked")
    assert bob_attempt is False
    # Verify Alice's transaction was not changed
    alice_verify = database.get_transactions(alice)[0]
    assert alice_verify[4] == 650.0
    assert alice_verify[5] == "Alice dinner"

