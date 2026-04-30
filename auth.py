"""
Zarządzanie użytkownikami.

Lokalnie: SQLite (users.db)
Streamlit Cloud: PostgreSQL przez zmienną DATABASE_URL (np. Supabase free tier)
"""
import hashlib
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

_SQLITE_PATH = Path(__file__).parent / "users.db"

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id      TEXT PRIMARY KEY,
        email   TEXT UNIQUE NOT NULL,
        pw_hash TEXT NOT NULL,
        salt    TEXT NOT NULL,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def _is_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL", ""))


@contextmanager
def _conn():
    """Zwraca (connection, placeholder) dla aktywnego silnika."""
    if _is_postgres():
        import psycopg2
        url = os.environ["DATABASE_URL"]
        if "sslmode" not in url:
            url += "?sslmode=require"
        conn = psycopg2.connect(url)
        try:
            yield conn, "%s"
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(_SQLITE_PATH)
        try:
            yield conn, "?"
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _init_table() -> None:
    with _conn() as (conn, _ph):
        conn.execute(_CREATE_TABLE)


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()


def register(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub komunikat błędu)."""
    _init_table()
    salt = os.urandom(32).hex()
    uid  = str(uuid.uuid4())
    try:
        with _conn() as (conn, ph):
            conn.execute(
                f"INSERT INTO users (id, email, pw_hash, salt) VALUES ({ph},{ph},{ph},{ph})",
                (uid, email.lower().strip(), _hash(password, salt), salt),
            )
        return True, uid
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            return False, "Ten adres email jest już zarejestrowany."
        return False, str(exc)


def login(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub komunikat błędu)."""
    _init_table()
    with _conn() as (conn, ph):
        row = conn.execute(
            f"SELECT id, pw_hash, salt FROM users WHERE email = {ph}",
            (email.lower().strip(),),
        ).fetchone()
    if not row:
        return False, "Nieprawidłowy email lub hasło."
    uid, stored, salt = row
    if _hash(password, salt) == stored:
        return True, uid
    return False, "Nieprawidłowy email lub hasło."
