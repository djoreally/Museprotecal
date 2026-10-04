"""Tenant store. Postgres when DATABASE_URL is set, SQLite fallback for local dev."""
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "tenants.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    pack TEXT NOT NULL,
    inbox_id TEXT,
    inbox_email TEXT,
    phone TEXT,
    agentphone_agent_id TEXT,
    created_at BIGINT NOT NULL
)
"""

PG_SCHEMA = SCHEMA  # identical DDL works on both


def _pg_url():
    return os.environ.get("DATABASE_URL", "")


_BACKEND = None  # "pg" or "sqlite", resolved once


def _resolve_backend():
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    if _pg_url():
        try:
            import psycopg

            conn = psycopg.connect(_pg_url(), connect_timeout=5)
            conn.close()
            _BACKEND = "pg"
        except Exception as e:
            print(f"WARNING: Postgres unreachable ({str(e)[:80]}), using SQLite fallback")
            _BACKEND = "sqlite"
    else:
        _BACKEND = "sqlite"
    return _BACKEND


class _Conn:
    """Tiny wrapper so the rest of the code doesn't care which DB it is."""

    def __init__(self):
        self.is_pg = _resolve_backend() == "pg"
        if self.is_pg:
            import psycopg

            self.conn = psycopg.connect(_pg_url(), connect_timeout=10)
        else:
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            if exc[0] is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()

    def _q(self, sql):
        return sql.replace("?", "%s") if self.is_pg else sql

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(self._q(sql), params)
        return cur

    def fetchone(self, sql, params=()):
        cur = self.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        if self.is_pg:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        return dict(row)

    def fetchall(self, sql, params=()):
        cur = self.execute(sql, params)
        rows = cur.fetchall()
        if self.is_pg:
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
        return [dict(r) for r in rows]


def init():
    with _Conn() as c:
        c.execute(PG_SCHEMA if c.is_pg else SCHEMA)
        if not c.is_pg:
            cols = [r[1] for r in c.execute("PRAGMA table_info(tenants)").fetchall()]
            if "agentphone_agent_id" not in cols:
                c.execute("ALTER TABLE tenants ADD COLUMN agentphone_agent_id TEXT")


def save(tenant: dict):
    cols = "(id, name, email, pack, inbox_id, inbox_email, phone, agentphone_agent_id, created_at)"
    with _Conn() as c:
        c.execute(
            f"INSERT INTO tenants {cols} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET "
            "name=EXCLUDED.name, email=EXCLUDED.email, pack=EXCLUDED.pack,"
            " inbox_id=EXCLUDED.inbox_id, inbox_email=EXCLUDED.inbox_email,"
            " phone=EXCLUDED.phone, agentphone_agent_id=EXCLUDED.agentphone_agent_id,"
            " created_at=EXCLUDED.created_at"
            if c.is_pg
            else f"INSERT OR REPLACE INTO tenants {cols} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant["id"],
                tenant["name"],
                tenant["email"],
                tenant["pack"],
                tenant.get("inbox_id"),
                tenant.get("inbox_email"),
                tenant.get("phone"),
                tenant.get("agentphone_agent_id"),
                tenant["created_at"],
            ),
        )


def get(tenant_id: str):
    with _Conn() as c:
        return c.fetchone("SELECT * FROM tenants WHERE id = ?", (tenant_id,))


def list_all():
    with _Conn() as c:
        return c.fetchall("SELECT * FROM tenants ORDER BY created_at DESC")


def now():
    return int(time.time())
