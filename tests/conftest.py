# Redirect APP_DATA_DIR to a tmp path for the whole test run so we never
# touch the real C:\CourtDocCataloguer\ during testing.
#
# We set COURT_DOC_DIR *before* importing court_cataloguer.config so the
# module-level Path() picks it up.

import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="court-cataloguer-test-"))
os.environ["COURT_DOC_DIR"] = str(_TMP_ROOT)

# Make sure the project root is on sys.path so `import court_cataloguer` works
# even when running pytest from inside the tests/ dir.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# Deterministic 32-byte test key. Real launches derive via PBKDF2; tests
# bypass that to keep test runs fast (PBKDF2 at 600k iters is ~250ms each).
TEST_MASTER_KEY = b"\x42" * 32


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Per-test isolated *encrypted* DB. Sets a deterministic master key."""
    from court_cataloguer import config

    monkeypatch.setattr(config, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(config, "KEYFILE_PATH", tmp_path / "keyfile.json")
    monkeypatch.setattr(config, "MASTER_XLSX", tmp_path / "exports" / "master_catalogue.xlsx")

    from court_cataloguer import database

    monkeypatch.setattr(database, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "cataloguer.db")

    database.set_master_key(TEST_MASTER_KEY)
    database.init_db()
    yield tmp_path
    database.clear_master_key()
