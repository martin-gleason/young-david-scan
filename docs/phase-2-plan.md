# Phase 2 — Data Integrity

**Status:** Planning. No implementation yet on this branch — this file is the spec the PR opens against.

**Owner:** —
**Estimated effort:** 1 focused session (≈2–3 hrs)
**Depends on:** Phase 1 (scaffolding + CLAUDE.md). ← merged.
**Blocks:** Phase 3 (encryption). Migrating bad date strings inside an encrypted DB is harder than migrating them in plaintext, so this MUST land first.

---

## Problem statement

The current schema stores `cases.case_date` as a free-text string. The UI label says `MM/DD/YYYY` but nothing validates it. The search code then compares those strings with `>=` / `<=` in SQL:

```python
# court_cataloguer/database.py — search_cases
if date_from:
    sql += " AND case_date >= ?"
    params.append(date_from)
```

SQLite compares strings lexicographically. So with MM/DD/YYYY data:

- `"12/01/2023" > "01/01/2024"` → True (wrong; Dec 2023 is before Jan 2024)
- A date-range search returns garbage and the navigator may not notice.

This silently corrupts the catalogue's most important navigation surface. We fix it before encryption goes in, because untangling bad-date data on an encrypted DB is painful (no `sqlite3` CLI without the key, harder to inspect).

Additionally, while we're touching the data layer:

- The `documents.case_id → cases.id` foreign key has no `ON DELETE` clause. We need an explicit decision before Phase 4 adds case-deletion UI.
- `utils.import_pdfs` does `shutil.copy2` then `db.add_document`. If the DB insert fails after the copy, the file is orphaned. Make the pair atomic.

---

## Scope of this PR

### In scope

1. **Switch `case_date` storage to ISO `YYYY-MM-DD`.**
   - Parse `MM/DD/YYYY` (and a few common typos: `M/D/YYYY`, leading/trailing whitespace) at the UI boundary.
   - Display as `MM/DD/YYYY` to the navigator; store and search as ISO.
   - Reject unparseable dates in `EntryScreen._validate` with a field-level error.

2. **One-shot data migration.**
   - New module `court_cataloguer/migrations/001_dates_to_iso.py`.
   - Detects rows whose `case_date` matches the MM/DD/YYYY pattern and rewrites them to ISO.
   - Idempotent: re-running is a no-op (rows already in `YYYY-MM-DD` are skipped).
   - Logs counts: examined / rewritten / skipped / unparseable.
   - Called once from `database.init_db()` after table creation. Wrapped in a transaction so a partial run rolls back.
   - Pre-migration backup: copy `cataloguer.db` → `cataloguer.db.pre-001.bak` before running. Keep one generation; this is single-user.

3. **Foreign-key cascade decision: `ON DELETE RESTRICT`.**
   - `documents.case_id REFERENCES cases(id) ON DELETE RESTRICT`.
   - Court records: we never want to silently lose a document's case link. If a case has documents, deletion must be refused at the DB level.
   - Schema change requires a migration step (SQLite can't alter FK after creation): `002_fk_restrict.py` rebuilds the `documents` table with the new constraint via the standard `PRAGMA legacy_alter_table=OFF; CREATE TABLE new; INSERT SELECT; DROP old; ALTER RENAME` pattern.

4. **Atomic PDF import.**
   - In `utils.import_pdfs`, wrap the `_safe_copy` + `db.add_document` pair so a DB insert failure rolls back the file copy.
   - Implementation: copy first, register second; if register raises, `dest.unlink(missing_ok=True)` and re-raise.
   - Log the orphan-cleanup path explicitly.

5. **Tests.**
   - `tests/test_dates.py`: `parse_us_date` / `format_us_date` round-trip, rejection of garbage, edge cases (leading zeros, single-digit month).
   - `tests/test_migrations.py`: seed DB with mixed MM/DD/YYYY + ISO rows, run migration, assert all rows end up ISO; assert idempotency on second run.
   - `tests/test_atomic_import.py`: monkeypatch `db.add_document` to raise, assert the dest file is gone.
   - `tests/test_database.py`: add a search-range test that previously would have failed (`"12/15/2023"` < `"01/15/2024"`).

6. **Update `CLAUDE.md` conventions section** to remove "currently violated by existing data" caveat once landed.

### Out of scope

- ❌ Encryption. That's Phase 3.
- ❌ Schema additions for audit log, SHA-256, chain-of-custody. Phase 4.
- ❌ Edit-completed-record workflow. Phase 5.
- ❌ UI: replacing the Entry-screen Notes widget. Phase 5.
- ❌ Adding any new dependency.

---

## Critical files to be modified

- `court_cataloguer/database.py` — new module-level migration entry point called from `init_db`; FK constraint changes.
- `court_cataloguer/utils.py` — atomic `import_pdfs` rewrite.
- `court_cataloguer/screens/entry.py` — `_validate` rejects unparseable dates; date round-trip via new helper.
- `court_cataloguer/dates.py` — **new**. Pure parse/format helpers; no I/O.
- `court_cataloguer/migrations/__init__.py` — **new**.
- `court_cataloguer/migrations/001_dates_to_iso.py` — **new**.
- `court_cataloguer/migrations/002_fk_restrict.py` — **new**.
- `tests/test_dates.py`, `tests/test_migrations.py`, `tests/test_atomic_import.py` — **new**.
- `tests/test_database.py` — extend with date-range search regression.

## Reuse from existing code

- `court_cataloguer.database._connect()` is the right boundary for migrations to acquire connections through — they should not open their own SQLite connections.
- `court_cataloguer.logging_setup.get_logger(__name__)` for all migration logs.
- The existing `EntryScreen._validate()` pattern (return bool, set `_error_var`) — extend, don't rewrite.

## Design notes / open decisions

- **Migration tracking table?** For a single-user side project with a known small set of migrations we don't need a full `alembic`-style versions table. Each migration file is idempotent and self-skipping. If Phase 4+ grows the migration count, revisit then.
- **Date format input flexibility:** accept `MM/DD/YYYY`, `M/D/YYYY`, `MM/DD/YY` (→ `20YY` for 00–69, `19YY` for 70–99 — the navigator may type 2-digit years). Reject everything else with a clear error. **Open question:** should we also accept `YYYY-MM-DD` directly for power users / paste-from-other-systems? Leaning yes; minor.
- **Pre-migration backup:** simple `shutil.copy2`. Skip backup if the DB is empty (first-run case). Naming: `cataloguer.db.pre-001.bak`. Phase 3 will revisit when encryption lands (backup of encrypted DB needs the same key to read; that's fine).

---

## Verification

1. `pytest` — all new tests + existing 6 still pass.
2. `ruff check . && ruff format --check .` — clean.
3. Manual: with a real DB containing MM/DD/YYYY rows, launch the app once → confirm:
   - Backup file `cataloguer.db.pre-001.bak` exists.
   - `sqlite3 cataloguer.db "SELECT case_date FROM cases"` returns ISO format only.
   - Date-range search in the UI now returns sensible results across month/year boundaries.
4. Re-launch a second time → no re-migration, no second backup file (idempotency).
5. Manual: edit a case via the entry screen with a deliberately bad date (`13/45/2024`) → error message shown, case not saved.

---

## Risk + rollback

- **Risk:** migration corrupts data.
  - **Mitigation:** transactional run; pre-migration `.bak` copy; idempotent.
  - **Rollback:** copy `cataloguer.db.pre-001.bak` back over `cataloguer.db`. Document this in CLAUDE.md.
- **Risk:** FK `ON DELETE RESTRICT` change breaks existing rows (unlikely — current code never deletes cases, but worth a test).
  - **Mitigation:** migration runs `PRAGMA foreign_key_check` after the rebuild; logs any violations.
