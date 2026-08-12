"""Toy authentication module used to demo Chemisto's /file context command."""
import hashlib
import sqlite3


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


def get_user(connection: sqlite3.Connection, username: str):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor = connection.execute(query)
    return cursor.fetchone()


def login(connection: sqlite3.Connection, username: str, password: str) -> bool:
    user = get_user(connection, username)
    if user is None:
        return False
    return user["password_hash"] == hash_password(password)
