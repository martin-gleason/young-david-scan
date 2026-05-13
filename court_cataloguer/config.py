# All paths and constants live here.
# Override the data directory at runtime with COURT_DOC_DIR env var
# (useful for tests and for dev work on non-Windows machines).

import os
from pathlib import Path

# ── Application Data Directory ────────────────────────────────────────────────
# All data (database, archived PDFs, exports) live here.
# This folder is created automatically on first run.
APP_DATA_DIR = Path(os.environ.get("COURT_DOC_DIR", "C:/CourtDocCataloguer"))
ARCHIVE_DIR = APP_DATA_DIR / "archive"
EXPORTS_DIR = APP_DATA_DIR / "exports"
LOGS_DIR = APP_DATA_DIR / "logs"
DB_PATH = APP_DATA_DIR / "cataloguer.db"
KEYFILE_PATH = APP_DATA_DIR / "keyfile.json"
MASTER_XLSX = EXPORTS_DIR / "master_catalogue.xlsx"

# Idle auto-lock: minutes of no input before the app returns to the
# passphrase screen. Override with COURT_DOC_LOCK_MINUTES (useful for
# kiosk-like deployments or for testing the lock-out path quickly).
LOCK_TIMEOUT_MIN = int(os.environ.get("COURT_DOC_LOCK_MINUTES", "10"))

# ── Application Info ──────────────────────────────────────────────────────────
APP_TITLE = "Court Document Cataloguer"
APP_VERSION = "1.0.0"
WINDOW_SIZE = "1280x800"
MIN_WIDTH = 1100
MIN_HEIGHT = 700

# ── Petition Types (edit this list to add/remove options) ────────────────────
PETITION_TYPES = [
    "Petition for Adjudication — Neglect",
    "Petition for Adjudication — Dependency",
    "Supplemental Petition",
    "Motion to Modify",
    "Emergency Motion",
    "Other",
]

# ── Courtrooms (edit this list to add/remove options) ────────────────────────
COURTROOMS = [
    "Courtroom 1",
    "Courtroom 2",
    "Courtroom 3",
    "Courtroom 4",
    "Courtroom 5",
    "Courtroom 6",
    "Other",
]

# ── UI Palette ────────────────────────────────────────────────────────────────
C_PRIMARY = "#1a3a5c"  # Navy  — header bars, buttons
C_ACCENT = "#c8a84b"  # Gold  — highlights, secondary buttons
C_BG = "#f0f2f5"  # Light gray — main background
C_WHITE = "#ffffff"
C_TEXT = "#1a1a1a"
C_MUTED = "#666666"
C_SUCCESS = "#2e7d32"  # Green
C_WARNING = "#f57f17"  # Amber
C_DANGER = "#c62828"  # Red
C_PENDING = "#e65100"  # Orange
C_ROW_ALT = "#eaf0f8"  # Alternating row fill

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_H2 = ("Segoe UI", 13, "bold")
FONT_BODY = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 10)
