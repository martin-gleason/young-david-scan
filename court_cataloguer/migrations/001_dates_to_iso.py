"""Rewrite `cases.case_date` rows from MM/DD/YYYY to ISO `YYYY-MM-DD`.

Idempotent — ISO rows are left untouched. If a row's date can't be parsed we
log it (without the value, in case it accidentally carries PII) and leave the
row alone, so a single bad row can't block the whole migration.

Runs inside a transaction supplied by the caller.
"""

from __future__ import annotations

import sqlite3

from ..dates import DateParseError, is_iso_date, parse_us_date
from ..logging_setup import get_logger

log = get_logger(__name__)


def run(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT id, case_date FROM cases").fetchall()

    changed = 0
    already_iso = 0
    unparseable = 0

    for row in rows:
        case_id = row["id"] if hasattr(row, "keys") else row[0]
        current = row["case_date"] if hasattr(row, "keys") else row[1]

        if is_iso_date(current):
            already_iso += 1
            continue

        try:
            iso = parse_us_date(current)
        except DateParseError:
            log.warning(
                "Migration 001: case id=%s has unparseable case_date; leaving as-is", case_id
            )
            unparseable += 1
            continue

        conn.execute("UPDATE cases SET case_date = ? WHERE id = ?", (iso, case_id))
        changed += 1

    return {
        "examined": len(rows),
        "changed": changed,
        "already_iso": already_iso,
        "unparseable": unparseable,
    }
