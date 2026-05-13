"""One-shot DB migrations.

Each migration module exposes a `run(conn: sqlite3.Connection) -> dict` function
that performs an idempotent schema/data change and returns a small stats dict
(at minimum `{"changed": int, "skipped": int}`) for logging.

Migrations are discovered and applied in lexical filename order by
`apply_all()`. They run inside a single transaction per migration so a partial
run rolls back cleanly.

There is no migration-versions table — each migration is self-skipping. If we
ever outgrow this (Phase 4+), introduce a `schema_migrations(name, applied_at)`
table at that point. For now (single-user, handful of migrations) the
self-skip property is enough.
"""

from __future__ import annotations

import importlib
import pkgutil
import shutil
import sqlite3
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger(__name__)


def _discover_migration_names() -> list[str]:
    """Return migration module names in lexical order (e.g. ['001_dates_to_iso'])."""
    pkg_path = Path(__file__).parent
    names: list[str] = []
    for mod in pkgutil.iter_modules([str(pkg_path)]):
        if mod.ispkg:
            continue
        # Migrations start with a 3-digit prefix. Everything else (this file,
        # any future helpers) is skipped.
        if len(mod.name) >= 3 and mod.name[:3].isdigit():
            names.append(mod.name)
    return sorted(names)


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
    """Run every discovered migration, in order. Idempotent overall."""
    names = _discover_migration_names()
    if not names:
        return

    _backup(db_path, "pre-migrations")

    for name in names:
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
