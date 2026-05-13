"""Migration tests — both 001 (dates) and 002 (FK), plus apply_all idempotency."""

import pytest
from sqlcipher3 import dbapi2 as sqlite

from court_cataloguer import database as db
from court_cataloguer.migrations import apply_all
from tests.conftest import TEST_MASTER_KEY


def _raw_conn(path):
    """Open a SQLCipher connection directly with the deterministic test key.

    Used to seed rows that bypass the normal app validation (e.g. planting
    MM/DD/YYYY rows that the new validator would reject).
    """
    conn = sqlite.connect(str(path))
    conn.row_factory = sqlite.Row
    conn.execute(f"PRAGMA key = \"x'{TEST_MASTER_KEY.hex()}'\"")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_001_rewrites_us_dates_to_iso(fresh_db, monkeypatch):
    # Seed two cases bypassing the normal API so we can plant a MM/DD/YYYY date
    # (the API would reject it post-Phase-2). Direct SQL is fine for fixtures.
    with _raw_conn(fresh_db / "cataloguer.db") as conn:
        conn.execute(
            "INSERT INTO cases (last_name, courtroom, docket_number, case_date) "
            "VALUES (?, ?, ?, ?)",
            ("Old", "Courtroom 1", "OLD-1", "12/15/2023"),
        )
        conn.execute(
            "INSERT INTO cases (last_name, courtroom, docket_number, case_date) "
            "VALUES (?, ?, ?, ?)",
            ("New", "Courtroom 1", "NEW-1", "2024-01-15"),
        )
        conn.commit()

    # Run the migrations.
    with db._connect() as conn:
        apply_all(conn, fresh_db / "cataloguer.db")
        conn.commit()

    cases = sorted(db.get_all_cases(), key=lambda r: r["docket_number"])
    by_docket = {c["docket_number"]: c for c in cases}
    assert by_docket["OLD-1"]["case_date"] == "2023-12-15"
    assert by_docket["NEW-1"]["case_date"] == "2024-01-15"


def test_001_idempotent(fresh_db):
    # First run is implicit in fresh_db (init_db already invoked apply_all).
    # Add a row, then re-run apply_all — nothing should change.
    db.create_case("Solo", "Courtroom 1", "SOLO-1", "2024-07-04")

    with db._connect() as conn:
        apply_all(conn, fresh_db / "cataloguer.db")
        conn.commit()

    case = db.get_case_by_docket("SOLO-1")
    assert case["case_date"] == "2024-07-04"


def test_002_documents_has_on_delete_restrict(fresh_db):
    with _raw_conn(fresh_db / "cataloguer.db") as conn:
        fks = conn.execute("PRAGMA foreign_key_list(documents)").fetchall()
    relevant = [fk for fk in fks if fk["from"] == "case_id"]
    assert len(relevant) == 1
    assert relevant[0]["on_delete"].upper() == "RESTRICT"


def test_002_blocks_deletion_of_case_with_documents(fresh_db):
    case_id = db.create_case("Doe", "Courtroom 1", "FK-1", "2024-05-12")
    db.add_document("foo.pdf", "/tmp/foo.pdf")
    # Link the doc to the case.
    with db._connect() as conn:
        conn.execute("UPDATE documents SET case_id = ? WHERE id = 1", (case_id,))
        conn.commit()

    # Now try to delete the case — FK RESTRICT should forbid it.
    with pytest.raises(sqlite.IntegrityError), db._connect() as conn:
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        conn.commit()
