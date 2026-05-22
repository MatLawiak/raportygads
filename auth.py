"""
Zarządzanie użytkownikami + szyfrowanie danych per konto.

Lokalnie  : SQLite (users.db), brak szyfrowania
Streamlit Cloud: Supabase SDK przez HTTPS, dane szyfrowane Fernet (AES-128-CBC)
"""
import hashlib
import os
import uuid
from pathlib import Path

_SQLITE_PATH = Path(__file__).parent / "users.db"


# ── Szyfrowanie ───────────────────────────────────────────────────────────────

def _enc_key() -> bytes | None:
    raw = os.environ.get("ENCRYPTION_KEY", "")
    if not raw:
        return None
    return raw.encode()


def _encrypt(text: str) -> str:
    key = _enc_key()
    if not key or not text:
        return text
    from cryptography.fernet import Fernet
    return Fernet(key).encrypt(text.encode()).decode()


def _decrypt(token: str) -> str:
    key = _enc_key()
    if not key or not token:
        return token
    try:
        from cryptography.fernet import Fernet
        return Fernet(key).decrypt(token.encode()).decode()
    except Exception:
        return ""


# ── Backend selection ─────────────────────────────────────────────────────────

def _use_supabase() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _sb():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


# ── SQLite init ───────────────────────────────────────────────────────────────

def _sqlite_init():
    import sqlite3
    with sqlite3.connect(_SQLITE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                pw_hash TEXT NOT NULL, salt TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ── Hashing ───────────────────────────────────────────────────────────────────

def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()


# ── Rejestracja / logowanie ───────────────────────────────────────────────────

def register(email: str, password: str) -> tuple[bool, str]:
    """Zwraca (ok, user_id lub błąd)."""
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
    """Zwraca (ok, user_id lub błąd)."""
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


# ── Dane użytkownika (szyfrowane) ─────────────────────────────────────────────

def save_user_data(user_id: str, fields: dict) -> bool:
    """
    Zapisuje podane pola w tabeli user_data (upsert).
    Wartości są szyfrowane przed zapisem.
    fields: {"openai_key": "...", "gads_yaml": "...", ...}
    """
    if not _use_supabase():
        return False
    try:
        encrypted = {k: _encrypt(v) for k, v in fields.items() if v is not None}
        encrypted["user_id"] = user_id
        _sb().table("user_data").upsert(encrypted).execute()
        return True
    except Exception:
        return False


def load_user_data(user_id: str) -> dict:
    """
    Wczytuje i odszyfrowuje dane użytkownika.
    Zwraca dict z kluczami: openai_key, gads_yaml, ga4_json, config_json, meta_token.
    """
    if not _use_supabase():
        return {}
    try:
        res = _sb().table("user_data").select("*").eq("user_id", user_id).execute()
        if not res.data:
            return {}
        row = res.data[0]
        return {
            field: _decrypt(row.get(field, "") or "")
            for field in ("openai_key", "gads_yaml", "ga4_json", "config_json", "meta_token")
        }
    except Exception:
        return {}


def delete_account(user_id: str) -> tuple[bool, str]:
    """
    Trwale usuwa konto i wszystkie dane użytkownika (RODO art. 17).
    """
    if not _use_supabase():
        return False, "Brak połączenia z bazą danych."
    try:
        _sb().table("user_data").delete().eq("user_id", user_id).execute()
        _sb().table("users").delete().eq("id", user_id).execute()
        return True, "Konto i wszystkie dane zostały trwale usunięte."
    except Exception as exc:
        return False, str(exc)
