"""
Zarządzanie użytkownikami.

Lokalnie  : SQLite (users.db)
Streamlit Cloud: Supabase przez SDK (SUPABASE_URL + SUPABASE_SERVICE_KEY)
"""
import hashlib
import os
import uuid
from pathlib import Path

_SQLITE_PATH = Path(__file__).parent / "users.db"


# ── helpers ──────────────────────────────────────────────────────────────────

def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()


def _use_supabase() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _sb():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _sqlite_init():
    import sqlite3
    with sqlite3.connect(_SQLITE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id      TEXT PRIMARY KEY,
                email   TEXT UNIQUE NOT NULL,
                pw_hash TEXT NOT NULL,
                salt    TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ── public API ────────────────────────────────────────────────────────────────

def register(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub komunikat błędu)."""
    salt = os.urandom(32).hex()
    uid  = str(uuid.uuid4())
    pw_h = _hash(password, salt)
    row  = {"id": uid, "email": email.lower().strip(), "pw_hash": pw_h, "salt": salt}

    if _use_supabase():
        try:
            _sb().table("users").insert(row).execute()
            return True, uid
        except Exception as exc:
            msg = str(exc).lower()
            if "unique" in msg or "duplicate" in msg or "23505" in msg:
                return False, "Ten adres email jest już zarejestrowany."
            return False, str(exc)
    else:
        import sqlite3
        _sqlite_init()
        try:
            with sqlite3.connect(_SQLITE_PATH) as conn:
                conn.execute(
                    "INSERT INTO users (id, email, pw_hash, salt) VALUES (?,?,?,?)",
                    (uid, row["email"], pw_h, salt),
                )
            return True, uid
        except sqlite3.IntegrityError:
            return False, "Ten adres email jest już zarejestrowany."
        except Exception as exc:
            return False, str(exc)


def login(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub komunikat błędu)."""
    if _use_supabase():
        try:
            res = _sb().table("users").select("id,pw_hash,salt").eq(
                "email", email.lower().strip()
            ).execute()
            if not res.data:
                return False, "Nieprawidłowy email lub hasło."
            r = res.data[0]
            if _hash(password, r["salt"]) == r["pw_hash"]:
                return True, r["id"]
            return False, "Nieprawidłowy email lub hasło."
        except Exception as exc:
            return False, str(exc)
    else:
        import sqlite3
        _sqlite_init()
        with sqlite3.connect(_SQLITE_PATH) as conn:
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
