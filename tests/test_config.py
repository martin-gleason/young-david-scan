"""COURT_DOC_DIR env var must be honoured so tests can redirect the data path."""

import os
import sys
from pathlib import Path


def test_court_doc_dir_env_var_redirects_app_data():
    expected = Path(os.environ["COURT_DOC_DIR"])

    # Force a fresh import so the module-level Path() evaluates against the env.
    sys.modules.pop("court_cataloguer.config", None)
    from court_cataloguer import config

    assert config.APP_DATA_DIR == expected
    assert config.DB_PATH == expected / "cataloguer.db"
    assert config.ARCHIVE_DIR == expected / "archive"
    assert config.EXPORTS_DIR == expected / "exports"
    assert config.LOGS_DIR == expected / "logs"


def test_default_data_dir_is_exe_dir_when_frozen(monkeypatch, tmp_path):
    """A PyInstaller-frozen .exe must default the data dir to its own folder.

    Drives the "drop the .exe on a USB drive and run" promise — without
    this, a portable build would silently write the database to whatever
    machine it's plugged into.
    """
    sys.modules.pop("court_cataloguer.config", None)
    from court_cataloguer.config import _default_data_dir

    fake_exe = tmp_path / "CourtDocCataloguer.exe"
    fake_exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert _default_data_dir() == tmp_path / "data"


def test_default_data_dir_is_windows_path_when_not_frozen(monkeypatch):
    """From source, default falls back to C:/CourtDocCataloguer for dev parity."""
    sys.modules.pop("court_cataloguer.config", None)
    from court_cataloguer.config import _default_data_dir

    # sys.frozen should be absent in a normal pytest run; delete defensively.
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert _default_data_dir() == Path("C:/CourtDocCataloguer")
