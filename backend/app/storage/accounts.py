"""本地账号和可撤销的登录会话。"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from time import time
from uuid import uuid4

from app.config import get_settings
from app.storage.persistence import data_dir

_USERNAME = re.compile(r"[a-z0-9][a-z0-9_.-]{2,63}")


@dataclass(frozen=True)
class Account:
    id: str
    username: str


def normalize_username(username: str) -> str:
    return username.strip().lower()


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(root / "accounts.sqlite3")) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash BLOB PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            )
        """)
        with db:
            yield db


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=3, maxmem=64 * 1024**2)


def create_account(username: str, password: str) -> Account:
    username = normalize_username(username)
    if not _USERNAME.fullmatch(username):
        raise ValueError("账号需为 3–64 位字母、数字、点、下划线或连字符，以字母或数字开头")
    if not 12 <= len(password) <= 128:
        raise ValueError("密码长度需为 12–128 个字符")
    account = Account(uuid4().hex, username)
    salt = secrets.token_bytes(16)
    try:
        with _database() as db:
            db.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?)",
                (account.id, account.username, salt, _password_hash(password, salt)),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("该账号已存在") from exc
    return account


def find_account(username: str) -> Account | None:
    with _database() as db:
        row = db.execute(
            "SELECT id, username FROM accounts WHERE username = ?", (normalize_username(username),)
        ).fetchone()
    return Account(*row) if row else None


def authenticate(username: str, password: str) -> Account | None:
    with _database() as db:
        row = db.execute(
            "SELECT id, username, salt, password_hash FROM accounts WHERE username = ?",
            (normalize_username(username),),
        ).fetchone()
    if row is None:
        _password_hash(password, bytes(16))
        return None
    account_id, username, salt, expected = row
    if hmac.compare_digest(_password_hash(password, salt), expected):
        return Account(account_id, username)
    return None


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def create_session(account: Account, previous_token: str | None) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time())
    with _database() as db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        if previous_token:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(previous_token),))
        db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            (_token_hash(token), account.id, now + get_settings().auth_session_seconds),
        )
    return token


def session_account(token: str) -> Account | None:
    with _database() as db:
        row = db.execute(
            """
            SELECT accounts.id, accounts.username
            FROM sessions JOIN accounts ON accounts.id = sessions.account_id
            WHERE token_hash = ? AND expires_at > ?
            """,
            (_token_hash(token), int(time())),
        ).fetchone()
    return Account(*row) if row else None


def revoke_session(token: str) -> None:
    with _database() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


@contextmanager
def legacy_adoption(account: Account) -> Iterator[bool]:
    """保存唯一归属，再串行执行可续跑的一次性迁移。"""
    with _database() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS legacy_adoption (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                account_id TEXT NOT NULL REFERENCES accounts(id),
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execute(
            "INSERT INTO legacy_adoption (id, account_id) VALUES (1, ?) ON CONFLICT(id) DO NOTHING",
            (account.id,),
        )
        (owner,) = db.execute("SELECT account_id FROM legacy_adoption WHERE id = 1").fetchone()
        if owner != account.id:
            raise ValueError("旧知识库已归属其他账号")

    # 归属单独提交。即使复制中途失败，下次也只能继续给同一个账号。
    with _database() as db:
        db.execute("BEGIN IMMEDIATE")
        (completed,) = db.execute("SELECT completed FROM legacy_adoption WHERE id = 1").fetchone()
        yield not completed
        if not completed:
            db.execute("UPDATE legacy_adoption SET completed = 1 WHERE id = 1")
