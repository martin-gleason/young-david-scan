"""One-shot DB migrations.

Each migration module exposes a `run(conn: sqlite3.Connection) -> dict` function
that performs an idempotent schema/data change and returns a small stats dict
(at minimum `{"changed": int, "skipped": int}`) for logging.

Migrations are applied in the order listed in `MIGRATIONS` below. They run
inside a single transaction per migration so a partial run rolls back cleanly.

There is no migration-versions table — each migration is self-skipping. If we
ever outgrow this (Phase 4+), introduce a `schema_migrations(name, applied_at)`
table at that point. For now (single-user, handful of migrations) the
self-skip property is enough.

Why an explicit MIGRATIONS list instead of pkgutil discovery: in a PyInstaller
`--onefile` bundle, the migration modules' bytecode lives inside the PYZ
archive, not as separate files on disk. `pkgutil.iter_modules` returns an
empty list there — a documented PyInstaller limitation — which caused first-
run audit-log creation to silently no-op and break the auth flow with
"no such table: audit_log". The test `test_migrations_list_matches_files`
guards against the list drifting from the files in this directory.
"""

from __future__ import annotations

import importlib
import shutil
import sqlite3
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger(__name__)

# Apply in this order. Add new migrations to the END of this tuple.
MIGRATIONS: tuple[str, ...] = (
    "001_dates_to_iso",
    "002_fk_restrict",
    "003_add_audit_log",
    "004_add_document_provenance",
)


def _backup(db_path: Path, tag: str) -> Path | None:
    """Copy db_path → db_path.with_suffix(f'.{tag}.bak'). No-op if DB empty/missing."""
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None
    bak = db_path.with_name(f"{db_path.name}.{tag}.bak")
    if bak.exists():
        # Keep one generation per tag. Don't clobber an existing pre-N backup
        # because that's the user's only rollback path if the previous run
        # half-finished.
        log.info("Backup already exists at %s — leaving it intact", bak.name)
        return bak
    shutil.copy2(db_path, bak)
    log.info("Created pre-migration backup: %s", bak.name)
    return bak


def apply_all(conn: sqlite3.Connection, db_path: Path) -> None:
    """Run every migration in order. Idempotent overall."""
    if not MIGRATIONS:
        return

    _backup(db_path, "pre-migrations")

    for name in MIGRATIONS:
        mod = importlib.import_module(f"{__name__}.{name}")
        if not hasattr(mod, "run"):
            log.warning("Migration %s has no run() — skipping", name)
            continue
        try:
            stats = mod.run(conn)
        except Exception:
            log.exception("Migration %s failed; rolling back its transaction", name)
            raise
        log.info("Migration %s: %s", name, stats)
