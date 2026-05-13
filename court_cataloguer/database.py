# All SQLite operations. Nothing here touches the UI.

import sqlite3

from .config import APP_DATA_DIR, DB_PATH

# ── Connection ────────────────────────────────────────────────────────────────


def _connect() -> sqlite3.Connection:
    """Open a connection with Row factory and foreign key support."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────


def init_db() -> None:
    """Create tables if they don't exist, then apply any pending migrations.
    Safe to call on every launch.
    """
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                last_name      TEXT    NOT NULL,
                courtroom      TEXT    NOT NULL,
                docket_number  TEXT    NOT NULL UNIQUE,
                case_date      TEXT    NOT NULL,
                notes          TEXT    NOT NULL DEFAULT '',
                created_at     TEXT    NOT NULL
                                   DEFAULT (datetime('now','localtime')),
                updated_at     TEXT    NOT NULL
                                   DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
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
        """)
        conn.commit()

    # Migrations are imported here (not at module top) to avoid a circular
    # import: migrations modules import from .dates / .logging_setup which
    # are fine, but downstream code may import this database module before
    # the migrations package is importable in test fixtures.
    from . import migrations

    with _connect() as conn:
        migrations.apply_all(conn, DB_PATH)
        conn.commit()


# ── Case Operations ───────────────────────────────────────────────────────────


def create_case(
    last_name: str, courtroom: str, docket_number: str, case_date: str, notes: str = ""
) -> int:
    """Insert a new case. Returns the new case id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO cases (last_name, courtroom, docket_number,
                                  case_date, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (last_name.strip(), courtroom.strip(), docket_number.strip(), case_date, notes.strip()),
        )
        conn.commit()
        return cur.lastrowid


def get_case_by_id(case_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return dict(row) if row else None


def get_case_by_docket(docket_number: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE docket_number = ?",
            (docket_number.strip(),),
        ).fetchone()
        return dict(row) if row else None


def search_cases(
    last_name: str = "",
    docket: str = "",
    courtroom: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict]:
    """Flexible case search — all parameters optional."""
    sql = "SELECT * FROM cases WHERE 1=1"
    params: list = []
    if last_name:
        sql += " AND last_name LIKE ?"
        params.append(f"%{last_name}%")
    if docket:
        sql += " AND docket_number LIKE ?"
        params.append(f"%{docket}%")
    if courtroom:
        sql += " AND courtroom LIKE ?"
        params.append(f"%{courtroom}%")
    if date_from:
        sql += " AND case_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND case_date <= ?"
        params.append(date_to)
    sql += " ORDER BY last_name ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_all_cases() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY last_name ASC").fetchall()
        return [dict(r) for r in rows]


# ── Document Operations ───────────────────────────────────────────────────────


def add_document(original_filename: str, stored_path: str, status: str = "pending") -> int:
    """Register a newly imported PDF. Returns the new document id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO documents (original_filename, stored_path, status)
               VALUES (?, ?, ?)""",
            (original_filename, str(stored_path), status),
        )
        conn.commit()
        return cur.lastrowid


def complete_document(doc_id: int, case_id: int, petition_type: str) -> None:
    """Mark a document as complete and link it to a case."""
    with _connect() as conn:
        conn.execute(
            """UPDATE documents
               SET case_id = ?, petition_type = ?, status = 'complete'
               WHERE id = ?""",
            (case_id, petition_type, doc_id),
        )
        conn.commit()


def skip_document(doc_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE documents SET status = 'skipped' WHERE id = ?",
            (doc_id,),
        )
        conn.commit()


def get_pending_documents() -> list[dict]:
    """All documents with status='pending', oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT d.*, c.last_name, c.docket_number
               FROM documents d
               LEFT JOIN cases c ON d.case_id = c.id
               WHERE d.status = 'pending'
               ORDER BY d.imported_at ASC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_documents_for_case(case_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM documents WHERE case_id = ?
               ORDER BY imported_at ASC""",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_documents() -> list[dict]:
    """All documents joined with their case data, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT d.*, c.last_name, c.courtroom,
                      c.docket_number, c.case_date
               FROM documents d
               LEFT JOIN cases c ON d.case_id = c.id
               ORDER BY d.imported_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_pending_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'pending'").fetchone()
        return row[0]


def get_queue_summary() -> dict:
    """Return counts of pending / complete / skipped / total documents."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM documents GROUP BY status"
        ).fetchall()
    summary = {"pending": 0, "complete": 0, "skipped": 0, "total": 0}
    for row in rows:
        status = row["status"]
        count = row["cnt"]
        if status in summary:
            summary[status] = count
        summary["total"] += count
    return summary
