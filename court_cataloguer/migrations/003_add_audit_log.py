"""Create the audit_log table.

Idempotent — `CREATE TABLE IF NOT EXISTS` is safe to call repeatedly.
No data is migrated; this just adds an empty table.
"""

from __future__ import annotations

import sqlite3

from ..logging_setup import get_logger

log = get_logger(__name__)


def run(conn: sqlite3.Connection) -> dict[str, int | str]:
    existed = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone()
    if existed:
        return {"status": "already_present"}

    conn.execute("""
        CREATE TABLE audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc        TEXT    NOT NULL,
            actor         TEXT    NOT NULL,
            machine       TEXT    NOT NULL,
            action        TEXT    NOT NULL,
            target_table  TEXT,
            target_id     INTEGER,
            details_json  TEXT    NOT NULL DEFAULT '{}',
            prev_hmac     TEXT    NOT NULL DEFAULT '',
            this_hmac     TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX idx_audit_log_ts_utc ON audit_log(ts_utc)")
    log.info("Created audit_log table + index")
    return {"status": "created"}
