"""Tests for password reset database operations."""

import tempfile
from pathlib import Path

import database


def setup_module():
    global _tmp_dir
    _tmp_dir = tempfile.mkdtemp()
    database.DB_NAME = str(Path(_tmp_dir) / "test_reset.db")
    database.create_database()


def teardown_module():
    import shutil
    shutil.rmtree(_tmp_dir, ignore_errors=True)


def test_password_reset_flow():
    user_id = database.create_user("recoverme", "old-password", "recoverme@example.com")

    # Verify the user can be found by email (case-insensitive)
    found = database.get_user_by_email("RECOVERME@example.com")
    assert found is not None
    assert found["id"] == user_id

    # Verify old password works
    assert database.verify_user("recoverme", "old-password")["id"] == user_id

    # Reset the password
    assert database.reset_user_password(user_id, "new-password") is True

    # Old password should no longer work
    assert database.verify_user("recoverme", "old-password") is None

    # New password should work
    assert database.verify_user("recoverme", "new-password")["id"] == user_id
