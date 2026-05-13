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


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Per-test isolated DB. Patches the config module's path constants in place."""
    from court_cataloguer import config

    monkeypatch.setattr(config, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cataloguer.db")
    monkeypatch.setattr(config, "MASTER_XLSX", tmp_path / "exports" / "master_catalogue.xlsx")

    # database.py reads the path constants from config at call time, but it
    # already imported APP_DATA_DIR / DB_PATH by name — patch those too.
    from court_cataloguer import database

    monkeypatch.setattr(database, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "cataloguer.db")

    database.init_db()
    return tmp_path
