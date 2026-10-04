"""SQLite tenant store. One row per provisioned customer."""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "tenants.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                pack TEXT NOT NULL,
                inbox_id TEXT,
                inbox_email TEXT,
                phone TEXT,
                agentphone_agent_id TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        # migration for DBs created before the AgentPhone switch
        cols = [r[1] for r in c.execute("PRAGMA table_info(tenants)").fetchall()]
        if "agentphone_agent_id" not in cols:
            c.execute("ALTER TABLE tenants ADD COLUMN agentphone_agent_id TEXT")


def save(tenant: dict):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tenants VALUES "
            "(:id, :name, :email, :pack, :inbox_id, :inbox_email, :phone, :created_at)",
            tenant,
        )


def get(tenant_id: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        return dict(row) if row else None


def list_all():
    with _conn() as c:
        rows = c.execute("SELECT * FROM tenants ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def now():
    return int(time.time())
