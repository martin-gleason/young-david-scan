"""Rebuild the `documents` table with `case_id ON DELETE RESTRICT`.

SQLite cannot add ON DELETE clauses to existing foreign keys via ALTER TABLE,
so we use the standard recreate pattern: create the new table, copy rows
over, drop the old, rename the new. Indexes and triggers (currently none)
would need to be recreated here too.

Idempotent — checks the existing FK clause via `PRAGMA foreign_key_list` and
no-ops if it's already RESTRICT.
"""

from __future__ import annotations

import sqlite3

from ..logging_setup import get_logger

log = get_logger(__name__)

NEW_DOCUMENTS_SQL = """
    CREATE TABLE documents_new (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id           INTEGER,
        original_filename TEXT    NOT NULL,
        stored_path       TEXT    NOT NULL,
        petition_type     TEXT    NOT NULL DEFAULT '',
        status            TEXT    NOT NULL DEFAULT 'pending',
        imported_at       TEXT    NOT NULL
                              DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT
    )
"""


def _existing_on_delete(conn: sqlite3.Connection) -> str:
    """Return the current ON DELETE clause for the documents.case_id FK, or ''."""
    fks = conn.execute("PRAGMA foreign_key_list(documents)").fetchall()
    for fk in fks:
        # PRAGMA returns rows with columns: id, seq, table, from, to, on_update, on_delete, match
        if (fk["from"] if hasattr(fk, "keys") else fk[3]) == "case_id":
            return (fk["on_delete"] if hasattr(fk, "keys") else fk[6]) or ""
    return ""


def run(conn: sqlite3.Connection) -> dict[str, int | str]:
    on_delete = _existing_on_delete(conn)
    if on_delete.upper() == "RESTRICT":
        return {"status": "already_restrict", "rows_copied": 0}

    # SQLite requires foreign_keys OFF during the rebuild so we don't trip our
    # own FK while moving rows. Save + restore.
    fk_was_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    if fk_was_on:
        conn.execute("PRAGMA foreign_keys = OFF")

    try:
        conn.execute(NEW_DOCUMENTS_SQL)
        conn.execute("""
            INSERT INTO documents_new (id, case_id, original_filename, stored_path,
                                       petition_type, status, imported_at)
            SELECT id, case_id, original_filename, stored_path,
                   petition_type, status, imported_at
            FROM documents
        """)
        rows = conn.execute("SELECT COUNT(*) FROM documents_new").fetchone()[0]
        conn.execute("DROP TABLE documents")
        conn.execute("ALTER TABLE documents_new RENAME TO documents")

        # Sanity check: no orphan case_id values that would violate the new FK.
        violations = conn.execute("PRAGMA foreign_key_check(documents)").fetchall()
        if violations:
            # Roll back happens at the apply_all level; raise so the caller does it.
            raise RuntimeError(
                f"foreign_key_check found {len(violations)} violation(s) "
                "after rebuilding documents — aborting migration 002"
            )
    finally:
        if fk_was_on:
            conn.execute("PRAGMA foreign_keys = ON")

    return {"status": "rebuilt", "rows_copied": rows}
