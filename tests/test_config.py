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
