# Centralised logging. All modules: `log = get_logger(__name__)`.
# Writes rotating files to APP_DATA_DIR/logs/. PII redaction filter is
# applied to all handlers so we don't leak names / docket numbers.

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from .config import LOGS_DIR

_CONFIGURED = False
_DEFAULT_LEVEL = logging.INFO
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 5

# Patterns that look enough like PII to redact. Conservative — we'd rather
# over-redact than leak. Expanded in Phase 4 with live DB-row matching.
_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    # docket numbers like "2024-JA-001234" or "24JA1234"
    re.compile(r"\b\d{2,4}[- ]?[A-Z]{2,4}[- ]?\d{3,8}\b"),
    # filenames that look like LastName_FirstName_*.pdf
    re.compile(r"\b[A-Z][a-z]{2,}[_ ][A-Z][a-z]{2,}(?=[._ ])"),
)


class PiiRedactingFilter(logging.Filter):
    """Replace matches of known PII patterns in the formatted message."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for pat in _PII_PATTERNS:
            msg = pat.sub("[REDACTED]", msg)
        # Overwrite both the cached message and the raw args so reformat
        # doesn't reintroduce the original.
        record.msg = msg
        record.args = ()
        return True


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "app.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redactor = PiiRedactingFilter()

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(redactor)

    root = logging.getLogger("court_cataloguer")
    root.setLevel(_DEFAULT_LEVEL)
    root.addHandler(file_handler)
    root.propagate = False

    if os.environ.get("COURT_DOC_DEBUG") == "1":
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        console.addFilter(redactor)
        root.addHandler(console)
        root.setLevel(logging.DEBUG)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Module-level entry point. Idempotent; safe to call from any import."""
    _configure()
    return logging.getLogger(name)
