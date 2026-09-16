import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


class ConsoleDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), scenario TEXT, created_at TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _password(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
        return f"{salt.hex()}${digest.hex()}"

    def create_user(self, email: str, password: str) -> int:
        with self.connect() as db:
            try:
                cur = db.execute("INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)", (email.lower(), self._password(password), datetime.now(timezone.utc).isoformat()))
            except sqlite3.IntegrityError as error:
                raise ValueError("email already registered") from error
            return cur.lastrowid

    def authenticate(self, email: str, password: str) -> int | None:
        with self.connect() as db:
            row = db.execute("SELECT id,password_hash FROM users WHERE email=?", (email.lower(),)).fetchone()
        if not row:
            return None
        salt, expected = row["password_hash"].split("$", 1)
        actual = self._password(password, bytes.fromhex(salt)).split("$", 1)[1]
        return row["id"] if hmac.compare_digest(actual, expected) else None

    def session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user_id, expires.isoformat()))
        return token

    def user_for_token(self, token: str | None) -> int | None:
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("SELECT user_id,expires_at FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            return None
        return row["user_id"]

    def delete_session(self, token: str | None) -> None:
        if token:
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def claim_runs(self, user_id: int | None, run_ids: list[str], scenario: str) -> None:
        with self.connect() as db:
            db.executemany("INSERT OR REPLACE INTO runs VALUES(?,?,?,?)", [(run_id, user_id, scenario, datetime.now(timezone.utc).isoformat()) for run_id in run_ids])

    def owner(self, run_id: str) -> int | None:
        with self.connect() as db:
            row = db.execute("SELECT user_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return row["user_id"] if row else None
