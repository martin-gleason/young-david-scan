# Phase 4 — Audit & Integrity

**Status:** Implementation on this branch.
**Depends on:** Phase 3 ✅ (encryption + auth).
**Blocks:** anything else that wants to record "who did what when".

---

## Problem

Phase 3 made the data unreadable without a passphrase. It didn't give us a tamper-evident record of who accessed or changed it. For court records, that gap is significant — if the navigator (or someone with the passphrase) is subpoenaed or under suspicion, "what was opened, when?" must be answerable.

This PR adds:

1. A keyed-HMAC-chained `audit_log` table that records consequential actions.
2. Per-PDF SHA-256 integrity verification — set on import, verified on open.
3. A hidden Audit Log screen (env-gated) with a Verify Chain button.

---

## What gets audited

High-signal actions only. Search/read of cases or documents is NOT audited — it'd swamp the log.

- **Auth**: `auth.first_run`, `auth.unlock_success`, `auth.locked`, `auth.rekey`.
- **Case writes**: `case.create`.
- **Document writes**: `doc.import`, `doc.complete`, `doc.skip`.
- **Document reads (exfiltration boundary)**: `doc.open`.
- **Export**: `export.excel`.
- **Integrity**: `integrity.mismatch`.

Wrong-passphrase failures can't sign a row (no key in memory yet) — they go to `app.log` only. Documented gap.

## Crypto

`court_cataloguer/crypto.py` gets one new function:

```python
def derive_audit_key(master_key: bytes) -> bytes:
    """HKDF-Expand-SHA256(master_key, info='audit-hmac-v1') → 32 bytes."""
```

Uses `cryptography.hazmat.primitives.kdf.hkdf.HKDFExpand` (already in deps from Phase 1).

## Schema (migrations 003 + 004)

```sql
-- 003_add_audit_log.py
CREATE TABLE audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc        TEXT    NOT NULL,
    actor         TEXT    NOT NULL,
    machine       TEXT    NOT NULL,
    action        TEXT    NOT NULL,
    target_table  TEXT,
    target_id     INTEGER,
    details_json  TEXT    NOT NULL DEFAULT '{}',
    prev_hmac     TEXT    NOT NULL DEFAULT '',
    this_hmac     TEXT    NOT NULL
);
CREATE INDEX idx_audit_log_ts_utc ON audit_log(ts_utc);

-- 004_add_document_provenance.py
ALTER TABLE documents ADD COLUMN sha256          TEXT;
ALTER TABLE documents ADD COLUMN imported_by     TEXT;
ALTER TABLE documents ADD COLUMN import_machine  TEXT;
```

Existing rows get NULL — `sha256` is lazily backfilled on first open.

## HMAC chain

Canonical row form: JSON with sorted keys, no whitespace, includes `id` and `prev_hmac`. INSERT-then-UPDATE pattern because we need the autoincrement id before signing:

1. INSERT with empty `this_hmac`.
2. Fetch `lastrowid`.
3. Compute canonical JSON + HMAC.
4. UPDATE that row's `this_hmac`.

All four statements inside the caller's existing transaction so a rollback affects both the wrapped write and the audit row atomically.

`verify_chain()` walks the table in id order, recomputes each HMAC, returns the id of the first row that fails (or None).

## PDF SHA-256

- `utils.sha256_file(path)` streams the file in 64 KB chunks.
- `import_pdfs` stores `sha256`, `imported_by` (`USERNAME` env), `import_machine` (`platform.node()`).
- On open (entry-screen viewer + search-popup open-pdf): compute current hash; compare to stored; if mismatch → audit row + override modal. If stored is NULL (pre-Phase-4 doc), compute and backfill.

Override on mismatch is intentional — legitimate re-scans of court records happen and we want to record the event, not block work.

## AuditLogScreen

Gated by `COURT_DOC_AUDIT=1`. HomeScreen shows an "Audit Log" button only when the env is set. The screen displays the rows with a Verify Chain button that surfaces tamper at a specific row id.

## Critical files

**Created**:
- `court_cataloguer/audit.py`
- `court_cataloguer/screens/audit_log.py`
- `court_cataloguer/migrations/003_add_audit_log.py`
- `court_cataloguer/migrations/004_add_document_provenance.py`
- `tests/test_audit.py`, `tests/test_audit_hookpoints.py`, `tests/test_document_integrity.py`

**Modified**:
- `court_cataloguer/crypto.py` (HKDF helper)
- `court_cataloguer/database.py` (audit hookpoints, sha256 setter, add_document signature)
- `court_cataloguer/auth.py` (audit hookpoints)
- `court_cataloguer/app.py` (audit `auth.locked`)
- `court_cataloguer/utils.py` (sha256_file, import_pdfs adds provenance)
- `court_cataloguer/screens/{home,search,entry}.py` (export + open audit + integrity check)
- `court_cataloguer/screens/__init__.py` (register AuditLogScreen)
- `CLAUDE.md`, `SETUP_GUIDE.md`

## Reuse patterns preserved

- `database._connect()` chokepoint untouched — audit appends happen inside the same `with _connect() as conn` block.
- Migrations follow the Phase 2 filename-ordered self-skipping pattern.
- `screens/_shared.py` factories build AuditLogScreen.
- `crypto.py` extended (one new function), not refactored.

## Verification

- `pytest` — 64 existing + ~20 new = ~85 total green.
- `ruff check . && ruff format --check .` clean.
- End-to-end on a fresh data dir: first-run produces an `auth.first_run` row; chain verifies; tampering a row breaks the chain and Verify Chain reports the broken id; modifying a stored PDF on disk produces an `integrity.mismatch` audit + override modal.

## Risks

- Per-write extra INSERT+UPDATE: sub-ms; not a concern.
- HMAC includes `id` so we need INSERT-then-UPDATE; clean but verbose. Worth it for reorder-detection.
- Audit log encrypted with the same key — losing the passphrase loses the audit log too. Documented.

## Out of scope

- Audit log export to a separate signed file (court IT handoff).
- Per-row signed entries from external identities.
- Audit on read of cases (only `doc.open` is audited).
- Rekey UI.
