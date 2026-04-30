"""
Zarządzanie użytkownikami — SQLite, rejestracja, logowanie.
"""
import hashlib
import os
import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id      TEXT PRIMARY KEY,
                email   TEXT UNIQUE NOT NULL,
                pw_hash TEXT NOT NULL,
                salt    TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()


def register(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub komunikat błędu)."""
    _init_db()
    salt = os.urandom(32).hex()
    uid = str(uuid.uuid4())
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (id, email, pw_hash, salt) VALUES (?,?,?,?)",
                (uid, email.lower().strip(), _hash(password, salt), salt),
            )
        return True, uid
    except sqlite3.IntegrityError:
        return False, "Ten adres email jest już zarejestrowany."
    except Exception as exc:
        return False, str(exc)


def login(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub komunikat błędu)."""
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, pw_hash, salt FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    if not row:
        return False, "Nieprawidłowy email lub hasło."
    uid, stored, salt = row
    if _hash(password, salt) == stored:
        return True, uid
    return False, "Nieprawidłowy email lub hasło."
