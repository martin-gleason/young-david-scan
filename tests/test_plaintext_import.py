"""Plaintext → encrypted migration on first launch with a pre-Phase-3 DB."""

import sqlite3
from pathlib import Path

import pytest

from court_cataloguer import auth, crypto, database


@pytest.fixture
def seeded_plaintext_dir(tmp_path, monkeypatch):
    """Set up a data dir with a plaintext DB containing one case row."""
    from court_cataloguer import config

    monkeypatch.setattr(config, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(config, "KEYFILE_PATH", tmp_path / "keyfile.json")
    monkeypatch.setattr(database, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(auth, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(auth, "KEYFILE_PATH", tmp_path / "keyfile.json")

    # Build a plaintext SQLite DB the old (Phase 1/2) way.
    db_path = tmp_path / "cataloguer.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE cases (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                last_name     TEXT NOT NULL,
                courtroom     TEXT NOT NULL,
                docket_number TEXT NOT NULL UNIQUE,
                case_date     TEXT NOT NULL,
                notes         TEXT NOT NULL DEFAULT '',
                created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute(
            "INSERT INTO cases (last_name, courtroom, docket_number, case_date) "
            "VALUES (?, ?, ?, ?)",
            ("Legacy", "Courtroom 1", "LEG-1", "2024-01-15"),
        )
        conn.commit()

    yield tmp_path
    database.clear_master_key()


def test_detection_recognises_plaintext(seeded_plaintext_dir):
    assert auth.is_plaintext_sqlite(seeded_plaintext_dir / "cataloguer.db")


def test_detection_rejects_missing(tmp_path):
    assert not auth.is_plaintext_sqlite(tmp_path / "nope.db")


def test_startup_mode_picks_import_plaintext(seeded_plaintext_dir):
    assert auth.determine_startup_mode() == auth.StartupMode.IMPORT_PLAINTEXT


def test_import_preserves_data_and_writes_backup(seeded_plaintext_dir):
    db_path: Path = seeded_plaintext_dir / "cataloguer.db"
    keyfile_path: Path = seeded_plaintext_dir / "keyfile.json"

    backup = auth.import_plaintext("a-secure-passphrase-please")

    # Backup created with the original plaintext content intact.
    assert backup.exists()
    assert backup.name == "cataloguer.db.pre-phase3.bak"
    with sqlite3.connect(str(backup)) as conn:
        rows = conn.execute("SELECT last_name FROM cases").fetchall()
    assert rows == [("Legacy",)]

    # Keyfile written.
    assert keyfile_path.exists()
    kf = crypto.load_keyfile(keyfile_path)
    assert kf.version == crypto.KEYFILE_VERSION

    # New DB is encrypted — plain sqlite3 can't read it.
    with sqlite3.connect(str(db_path)) as conn, pytest.raises(sqlite3.DatabaseError):
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()

    # And the data is accessible through the keyed connection.
    case = database.get_case_by_docket("LEG-1")
    assert case is not None
    assert case["last_name"] == "Legacy"


def test_import_refuses_when_db_is_already_encrypted(seeded_plaintext_dir, monkeypatch):
    # Encrypt it first.
    auth.import_plaintext("first-pass-phrase-here")
    # Now try to import again — should refuse.
    with pytest.raises(RuntimeError, match="does not look like plaintext"):
        auth.import_plaintext("second-pass-phrase-here")
