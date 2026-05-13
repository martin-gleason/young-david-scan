"""Add sha256 + imported_by + import_machine columns to documents.

`ALTER TABLE ADD COLUMN` is idempotent only at the SQL-statement level
if the column doesn't already exist — SQLite raises on duplicate add.
We inspect PRAGMA table_info first and skip columns that are already
present, so re-running the migration after a partial failure is safe.
"""

from __future__ import annotations

import sqlite3

from ..logging_setup import get_logger

log = get_logger(__name__)

NEW_COLUMNS = (
    ("sha256", "TEXT"),
    ("imported_by", "TEXT"),
    ("import_machine", "TEXT"),
)


def run(conn: sqlite3.Connection) -> dict[str, int | str | list[str]]:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}

    added: list[str] = []
    for name, sql_type in NEW_COLUMNS:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE documents ADD COLUMN {name} {sql_type}")
        added.append(name)

    if not added:
        return {"status": "already_present", "added": []}
    log.info("Added documents columns: %s", ", ".join(added))
    return {"status": "added_columns", "added": added}
