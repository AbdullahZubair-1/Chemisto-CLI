"""Intentionally failing test used only to demo /run diagnosing a failure.

This lives under examples/ (not tests/) so it never affects the real
automated test suite's pass/fail status.
"""
import sqlite3

from examples.auth import hash_password, login


def test_login_succeeds_with_correct_password():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE users (username TEXT, password_hash TEXT)")
    connection.execute(
        "INSERT INTO users VALUES (?, ?)", ("alice", hash_password("correct-password"))
    )

    assert login(connection, "alice", "wrong-password") is True
