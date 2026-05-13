"""Confirm the DB on disk is genuinely SQLCipher-encrypted, not plain SQLite."""

import sqlite3

import pytest

from court_cataloguer import database as db


def test_db_unreadable_as_plain_sqlite(fresh_db):
    # Sanity: data round-trips fine via the keyed connection.
    db.create_case("Doe", "Courtroom 1", "ENC-1", "2024-05-12")
    fetched = db.get_case_by_docket("ENC-1")
    assert fetched is not None

    # But the file on disk is not readable as plain SQLite.
    db_path = fresh_db / "cataloguer.db"
    assert db_path.exists()
    assert db_path.stat().st_size > 0
    with sqlite3.connect(str(db_path)) as conn, pytest.raises(sqlite3.DatabaseError):
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()


def test_no_master_key_blocks_connection(fresh_db, monkeypatch):
    # Clear the key the fixture installed; any DB call should now raise.
    db.clear_master_key()
    with pytest.raises(RuntimeError, match="set_master_key"):
        db.get_pending_count()


def test_wrong_master_key_raises_wrong_passphrase(fresh_db):
    # Reach in and swap the key for a wrong one. _connect should refuse.
    db.set_master_key(b"\x99" * 32)
    with pytest.raises(db.WrongPassphraseError):
        db.get_pending_count()


def test_rekey_changes_working_key(fresh_db):
    # Insert with current key.
    db.create_case("Doe", "Courtroom 1", "REKEY-1", "2024-05-12")

    new_key = b"\x77" * 32
    db.rekey(new_key)

    # The new key works.
    assert db.get_case_by_docket("REKEY-1") is not None

    # The old key (from the fixture) no longer works.
    from tests.conftest import TEST_MASTER_KEY

    db.set_master_key(TEST_MASTER_KEY)
    with pytest.raises(db.WrongPassphraseError):
        db.get_pending_count()

    # Put the new key back so fixture teardown doesn't trip.
    db.set_master_key(new_key)
