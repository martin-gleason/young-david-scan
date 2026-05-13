"""Tamper-evident audit log.

Every consequential action appends a row to `audit_log`. Each row carries
an HMAC-SHA256 over its own contents plus the previous row's HMAC, so
a single mutation breaks the chain at that point and everything after.

The audit key is derived from the master encryption key via HKDF (see
crypto.derive_audit_key). This module reads the master key from the
database module's in-memory state — set_master_key must already have
been called.

NEVER put PII into `details`. The schema is intentionally narrow:
`target_table` + `target_id` reference the real row; `details` is for
non-PII metadata only (status transitions, counts, sha256 prefixes).
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import crypto, database
from .logging_setup import get_logger

log = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def actor() -> str:
    """Identity of whoever is operating the app right now.

    Uses the OS-level user name. For a single-user side-project deployment
    this is always the navigator; the field is recorded anyway so future
    multi-user installs don't need a schema change.
    """
    # Prefer USERNAME (Windows) → USER (POSIX) → getpass fallback → 'unknown'.
    return os.environ.get("USERNAME") or os.environ.get("USER") or _safe_getpass() or "unknown"


def _safe_getpass() -> str | None:
    try:
        return getpass.getuser()
    except Exception:
        return None


def machine() -> str:
    """Hostname of the workstation. Falls back to 'unknown' if it raises."""
    try:
        return platform.node() or "unknown"
    except Exception:
        return "unknown"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _audit_key() -> bytes:
    """Derive (and re-derive on each call — cheap) the audit HMAC key."""
    if database._master_key is None:
        raise RuntimeError("audit requires the master key to be installed first")
    return crypto.derive_audit_key(database._master_key)


def _canonical(row: dict[str, Any]) -> bytes:
    """Stable byte form for hashing — sorted keys, no whitespace."""
    return json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hmac_row(audit_key: bytes, row: dict[str, Any]) -> str:
    return hmac.new(audit_key, _canonical(row), hashlib.sha256).hexdigest()


# ── Append ────────────────────────────────────────────────────────────────────


def append(
    conn,
    action: str,
    *,
    target_table: str | None = None,
    target_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Append an audit row inside the caller's open transaction.

    INSERT then UPDATE — we need AUTOINCREMENT id in the signed bytes,
    so we write the row with empty hmacs, fetch the id, compute, then
    UPDATE this_hmac. All inside the caller's transaction.

    Returns the row id.
    """
    audit_key = _audit_key()
    ts = _now_utc_iso()
    details_json = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))

    prev = conn.execute("SELECT this_hmac FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hmac = prev[0] if prev is not None else ""

    cur = conn.execute(
        """INSERT INTO audit_log
              (ts_utc, actor, machine, action, target_table, target_id,
               details_json, prev_hmac, this_hmac)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts, actor(), machine(), action, target_table, target_id, details_json, prev_hmac, ""),
    )
    new_id = cur.lastrowid

    signed = {
        "id": new_id,
        "ts_utc": ts,
        "actor": actor(),
        "machine": machine(),
        "action": action,
        "target_table": target_table,
        "target_id": target_id,
        "details_json": details_json,
        "prev_hmac": prev_hmac,
    }
    this_hmac = _hmac_row(audit_key, signed)
    conn.execute("UPDATE audit_log SET this_hmac = ? WHERE id = ?", (this_hmac, new_id))
    return new_id


# ── Verify ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChainVerification:
    ok: bool
    row_count: int
    first_broken_id: int | None = None
    reason: str = ""


def verify_chain() -> ChainVerification:
    """Walk audit_log in id order, recompute every HMAC, return the first failure."""
    audit_key = _audit_key()
    with database._connect() as conn:
        rows = conn.execute(
            """SELECT id, ts_utc, actor, machine, action, target_table,
                      target_id, details_json, prev_hmac, this_hmac
               FROM audit_log
               ORDER BY id ASC"""
        ).fetchall()

    prev_hmac = ""
    for row in rows:
        signed = {
            "id": row["id"],
            "ts_utc": row["ts_utc"],
            "actor": row["actor"],
            "machine": row["machine"],
            "action": row["action"],
            "target_table": row["target_table"],
            "target_id": row["target_id"],
            "details_json": row["details_json"],
            "prev_hmac": prev_hmac,
        }
        expected = _hmac_row(audit_key, signed)
        if not hmac.compare_digest(expected, row["this_hmac"]):
            return ChainVerification(
                ok=False,
                row_count=len(rows),
                first_broken_id=row["id"],
                reason=f"HMAC mismatch at id={row['id']}",
            )
        prev_hmac = row["this_hmac"]
    return ChainVerification(ok=True, row_count=len(rows))


# ── Convenience for callers without an open conn ──────────────────────────────


def append_standalone(
    action: str,
    *,
    target_table: str | None = None,
    target_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Open a fresh conn, append, commit. For non-DB call sites (auth/app lock)."""
    with database._connect() as conn:
        row_id = append(
            conn, action, target_table=target_table, target_id=target_id, details=details
        )
        conn.commit()
    return row_id
