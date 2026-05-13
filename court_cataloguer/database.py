# All SQLite operations. Nothing here touches the UI.
#
# Uses sqlcipher3 (statically-linked SQLCipher 4) so every connection
# is keyed via PRAGMA key. The 32-byte raw master key lives in a module
# global, set once by the auth flow before any DB call.
#
# DO NOT log, print, repr, or otherwise externalise the master key or
# raise it inside an exception message.

from sqlcipher3 import dbapi2 as sqlite

from .config import APP_DATA_DIR, DB_PATH

# ── Key state ─────────────────────────────────────────────────────────────────

_master_key: bytes | None = None


class WrongPassphraseError(Exception):
    """Raised when PRAGMA key probe fails — either wrong key or corrupt DB."""


def set_master_key(key: bytes) -> None:
    """Install the master key used for every subsequent _connect(). Do not log."""
    global _master_key
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("master key must be exactly 32 bytes")
    _master_key = key


def clear_master_key() -> None:
    """Drop the master key from memory (called on idle-lock or quit)."""
    global _master_key
    _master_key = None


def has_master_key() -> bool:
    return _master_key is not None


# ── Connection ────────────────────────────────────────────────────────────────


def _connect() -> sqlite.Connection:
    """Open a keyed connection with Row factory and FK support.

    Raises WrongPassphraseError if PRAGMA key fails on the first real read.
    """
    if _master_key is None:
        raise RuntimeError("database.set_master_key() must be called before opening a connection")
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite.connect(str(DB_PATH))
    conn.row_factory = sqlite.Row
    conn.execute(f"PRAGMA key = \"x'{_master_key.hex()}'\"")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite.DatabaseError as exc:
        conn.close()
        # Don't include the key or path in the message.
        raise WrongPassphraseError("wrong passphrase or corrupt database") from exc
    return conn


def rekey(new_key: bytes) -> None:
    """Change the master key on the existing DB.

    The current master key (set via set_master_key) must already be valid;
    we verify with a probe read, then run PRAGMA rekey, then update the
    in-memory key. PRAGMA rekey rewrites every page — slow on large DBs.
    """
    if not isinstance(new_key, bytes) or len(new_key) != 32:
        raise ValueError("new key must be exactly 32 bytes")
    conn = _connect()  # raises WrongPassphraseError if current key is wrong
    try:
        conn.execute(f"PRAGMA rekey = \"x'{new_key.hex()}'\"")
    finally:
        conn.close()
    set_master_key(new_key)


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
