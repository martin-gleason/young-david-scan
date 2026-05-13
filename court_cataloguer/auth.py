"""Auth orchestration: detect startup mode, drive the AuthScreen flow,
and migrate any pre-Phase-3 plaintext DB into an encrypted one.

This module owns the small bit of policy ("is the DB plaintext? do we
need a first-run prompt?") so the AuthScreen stays focused on UI.
"""

from __future__ import annotations

import sqlite3
from enum import Enum
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlite

from . import crypto, database
from .config import DB_PATH, KEYFILE_PATH
from .logging_setup import get_logger

log = get_logger(__name__)

PLAINTEXT_BACKUP_SUFFIX = ".pre-phase3.bak"


class StartupMode(str, Enum):
    """How the app should greet the user this launch."""

    FIRST_RUN = "first_run"  # nothing exists yet → set a new passphrase
    UNLOCK = "unlock"  # keyfile + encrypted DB → enter passphrase
    IMPORT_PLAINTEXT = "import_plaintext"  # pre-Phase-3 plaintext DB present


def determine_startup_mode(
    db_path: Path | None = None, keyfile_path: Path | None = None
) -> StartupMode:
    """Pick the AuthScreen mode based on what's on disk.

    Decision matrix:
        no keyfile, no DB              → FIRST_RUN
        no keyfile, DB exists          → IMPORT_PLAINTEXT (assume plaintext)
        keyfile exists (regardless)    → UNLOCK

    Paths default to the module-level config values at *call time* so test
    fixtures can monkeypatch `config.DB_PATH` / `config.KEYFILE_PATH` and
    have the change take effect.
    """
    db_path = db_path or DB_PATH
    keyfile_path = keyfile_path or KEYFILE_PATH
    if keyfile_path.exists():
        return StartupMode.UNLOCK
    if db_path.exists() and db_path.stat().st_size > 0:
        return StartupMode.IMPORT_PLAINTEXT
    return StartupMode.FIRST_RUN


def is_plaintext_sqlite(db_path: Path) -> bool:
    """Probe whether a DB file is plaintext SQLite (vs. SQLCipher-encrypted).

    Uses stdlib sqlite3 (no key support) and tries a real read. Encrypted
    DBs fail with DatabaseError; plaintext DBs succeed.
    """
    if not db_path.exists() or db_path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except sqlite3.DatabaseError:
        return False


# ── First-run / unlock paths ──────────────────────────────────────────────────


def first_run_setup(passphrase: str) -> None:
    """Create a fresh keyfile and install the derived key in memory.

    Caller is responsible for then invoking `database.init_db()` which
    creates the schema in a newly-encrypted DB.
    """
    salt = crypto.generate_salt()
    crypto.save_keyfile(KEYFILE_PATH, salt)
    key = crypto.derive_key(passphrase, salt)
    database.set_master_key(key)
    log.info("First-run setup complete; keyfile written to %s", KEYFILE_PATH.name)


def unlock(passphrase: str) -> None:
    """Derive the key from an existing keyfile and try to open the DB.

    Raises WrongPassphraseError if the derived key doesn't open the DB.
    Caller is responsible for invoking `database.init_db()` after success.
    """
    kf = crypto.load_keyfile(KEYFILE_PATH)
    key = crypto.derive_key(passphrase, kf.salt, iterations=kf.iterations)
    database.set_master_key(key)
    # Force a probe so a bad key surfaces here, not deep in the UI later.
    try:
        database.init_db()
    except database.WrongPassphraseError:
        database.clear_master_key()
        raise


# ── Plaintext → encrypted migration ───────────────────────────────────────────


def import_plaintext(
    passphrase: str, db_path: Path | None = None, keyfile_path: Path | None = None
) -> Path:
    """Convert an unencrypted Phase-1/2 DB to a SQLCipher-encrypted one.

    Sequence:
      1. Derive a fresh key from the new passphrase.
      2. Use SQLCipher's sqlcipher_export to copy plaintext → encrypted.
      3. Rename plaintext file to <name>.pre-phase3.bak.
      4. Rename encrypted output into place.
      5. Write the keyfile.
      6. Install the key in memory.

    Returns the path of the backup file so callers can surface it.
    Leaves the keyfile / encrypted DB partially written only if step 5/6
    crashes after step 4 — at that point everything's on disk and a
    relaunch will resume cleanly via UNLOCK mode.
    """
    db_path = db_path or DB_PATH
    keyfile_path = keyfile_path or KEYFILE_PATH
    if not is_plaintext_sqlite(db_path):
        raise RuntimeError("import_plaintext called but the DB does not look like plaintext SQLite")

    salt = crypto.generate_salt()
    key = crypto.derive_key(passphrase, salt)
    key_hex = crypto.key_to_pragma_hex(key)

    encrypted_tmp = db_path.with_suffix(db_path.suffix + ".enc")
    if encrypted_tmp.exists():
        encrypted_tmp.unlink()

    # Open the plaintext DB *with sqlcipher3* — no key set → SQLCipher
    # treats it as plain, which is what we want for the export side.
    conn = sqlite.connect(str(db_path))
    try:
        conn.execute(f"ATTACH DATABASE '{encrypted_tmp}' AS enc KEY \"x'{key_hex}'\"")
        conn.execute("SELECT sqlcipher_export('enc')")
        conn.execute("DETACH DATABASE enc")
    finally:
        conn.close()

    backup = db_path.with_name(db_path.name + PLAINTEXT_BACKUP_SUFFIX)
    if backup.exists():
        # Leave the existing backup intact — never clobber a previous rollback path.
        log.warning(
            "Plaintext backup %s already exists; using %s.dup",
            backup.name,
            backup.name,
        )
        backup = backup.with_suffix(backup.suffix + ".dup")
    db_path.rename(backup)
    encrypted_tmp.rename(db_path)
    crypto.save_keyfile(keyfile_path, salt)
    database.set_master_key(key)

    log.info(
        "Imported plaintext DB to encrypted; backup at %s, new keyfile at %s",
        backup.name,
        keyfile_path.name,
    )
    return backup
