# CLAUDE.md — Court Document Cataloguer

This file is the guide for any future Claude session working in this repo. Read it before doing anything beyond a trivial edit.

---

## What this is

A local Windows desktop app (Tkinter + SQLite) that helps **one court navigator at Cook County Juvenile Court (dependency/neglect division)** catalogue scanned petition PDFs from a USB drive. The navigator scans documents on a court copier, plugs the USB into a workstation, runs this app, fills in case metadata, and produces an indexed archive plus a master Excel export.

**Deployment context** (this is load-bearing — don't lose it):

- Real production juvenile-court PII. Much of it is sealed by statute in Illinois.
- Single user, single workstation. No network, no multi-tenant, no shared install.
- This is a **side project** the navigator builds and maintains on top of regular duties — not a Cook County IT-deployed system. Court IT is not in the loop and there is no formal compliance review.
- Implication: rigorous on data handling, lightweight on enterprise process. We optimise for "if the laptop is stolen or borrowed, the data does not leak" and "if the navigator makes a clerical mistake, it is recoverable."

---

## Threat model (concise)

**In scope** — design against these:

1. Stolen / borrowed / lost laptop.
2. Over-the-shoulder viewing in a public courthouse corridor.
3. Accidental over-sharing via the Excel export (emailing the wrong file).
4. Data corruption from malformed input (e.g. wrong-format dates breaking search).
5. Orphaned PDFs after a mid-import crash.
6. PDF integrity — was the archived copy silently swapped or corrupted?

**Out of scope** — note them, but don't design against them in v1:

1. Targeted nation-state attacker with physical-keylogger access.
2. Live forensic RAM analysis while the app is unlocked.
3. PyPI supply-chain compromise (we mitigate only by pinning + occasional manual review).

**Load-bearing controls** in the design:

- Encryption at rest (SQLCipher) gated by a passphrase that derives the key. → Phase 3.
- Append-only HMAC-chained audit log of every read/write. → Phase 4.
- Date storage in ISO format so search actually works. → Phase 2.
- PDF SHA-256 captured on import, verified on display. → Phase 4.

---

## Architecture map

```
young-david-scan/
├── main.py                    Thin launcher → court_cataloguer.app:main
├── CLAUDE.md                  ← you are here
├── SETUP_GUIDE.md             Staff-facing setup notes (update on deploy-relevant changes)
├── README.md                  One-screen orientation; points at CLAUDE + SETUP
├── pyproject.toml             Package + tooling config; deps pinned exactly
├── requirements.txt           Runtime pins (regenerated from pyproject)
├── requirements-dev.txt       Dev tooling (ruff, mypy, pytest)
├── .gitignore                 Block *.db, *.pdf, dist/, build/, .venv/
├── .python-version            3.11 pin
├── court_cataloguer/          The package
│   ├── __init__.py
│   ├── app.py                 CourtDocApp + main() entry point
│   ├── config.py              All constants + paths. Honours COURT_DOC_DIR env var.
│   ├── database.py            ALL SQLite operations. Never write SQL anywhere else.
│   ├── utils.py               USB detection, PDF import, Excel export. No UI here.
│   ├── pdf_viewer.py          Reusable Tk widget that renders PDFs via PyMuPDF.
│   ├── logging_setup.py       get_logger() — rotating files + PII redaction filter.
│   └── screens/
│       ├── _shared.py         Widget factories: make_header, btn, field_row, entry, combo.
│       ├── home.py            Landing screen, pending badge, action buttons.
│       ├── import_.py         USB scan + PDF copy → archive.
│       ├── queue.py           List of pending documents.
│       ├── entry.py           Split-pane PDF viewer + case-info form. Main work surface.
│       └── search.py          Case lookup + per-case document popup.
└── tests/
    ├── conftest.py            tmp-path COURT_DOC_DIR fixture
    ├── test_database.py
    ├── test_utils.py
    └── test_config.py
```

**Key reuse boundaries** (don't violate without a strong reason):

- DB ops live in `court_cataloguer/database.py`. Never write SQL elsewhere. Never import `sqlite3` outside this module.
- All logging goes through `court_cataloguer.logging_setup.get_logger(__name__)`. Never `print()` in non-test code.
- All shared widget factories live in `court_cataloguer/screens/_shared.py`. Reuse `btn`, `field_row`, `entry`, `combo` instead of building widgets from scratch.
- All paths come from `court_cataloguer.config`. Never hard-code `C:/CourtDocCataloguer` anywhere else — that one constant honours `COURT_DOC_DIR` so tests can redirect it.
- Screen navigation uses `app.show_screen(name, **kwargs)`; each screen optionally defines `refresh(**kwargs)`. Preserve this pattern.

---

## Conventions

- **Python 3.11**. PEP 585 generics only: `list[X]`, `dict[str, int]`, `dict | None`. **Never** `typing.List`, `typing.Optional`, `typing.Dict`.
- **No bare `except:`** and **no `except Exception: pass`**. Minimum acceptable handler is `log.exception("…")`. Bare swallows have already cost us debugging time once.
- **No `print()`** in non-test code. Use the module logger.
- **All DB writes are parameterised**. Never interpolate user data into SQL with f-strings.
- **All dates persisted as `YYYY-MM-DD`** (ISO 8601). MM/DD/YYYY is a UI-boundary concern only. Parse/format helpers live in `court_cataloguer/dates.py` — use `parse_us_date` and `format_us_date`, don't reinvent.
- **PRAGMA `foreign_keys = ON`** is always set on connect. Never disable it.

---

## Security do's and don'ts

DON'T:

- Log PII. The redacting filter in `logging_setup.py` strips known patterns, but it's belt-and-suspenders — don't deliberately log `last_name`, `notes`, full filenames containing names, or full docket numbers. Use IDs.
- Write the passphrase or derived key to any file, log, exception message, or `repr`. Treat them like passwords — because they are.
- Commit `*.db`, `*.pdf`, `*.xlsx`, `.env`, `dist/`, `build/`, or anything under `C:\CourtDocCataloguer\`. `.gitignore` enforces this but `git add -A` can still slip past.
- Disable `PRAGMA foreign_keys`.
- Introduce **any** outbound network call. The app is, by design, offline. CI assertion lands in Phase 7.
- Add a new dependency without checking it against the threat model and pinning it exactly.
- Change the data-directory layout. Existing installs have data at `C:\CourtDocCataloguer\` — moving it loses the user's data without a migration.
- Modify DB schema without a migration script. Even adding a column.

DO:

- Use `log = get_logger(__name__)` at the top of every module that needs logging.
- Validate user input at the UI boundary. Trust the DB layer's input only after that boundary.
- Prefer `Path` over string paths; pass `str(path)` only to libraries that demand it (sqlite3, openpyxl).
- Write a test for any new DB query.

---

## Run / build / test

```bash
# Install for development (editable):
pip install -e .[dev]

# Run the app (data lives at COURT_DOC_DIR or default C:\CourtDocCataloguer):
python main.py

# Run with a temp data directory + debug logging to console:
COURT_DOC_DIR=/tmp/court-test COURT_DOC_DEBUG=1 python main.py

# Tests:
pytest

# Lint:
ruff check .
ruff format --check .

# Types:
mypy court_cataloguer

# Build .exe for staff machine. Uses the checked-in spec file at
# packaging/CourtDocCataloguer.spec — produces a single-file
# CourtDocCataloguer.exe with the bundled Python runtime, SQLCipher,
# PyMuPDF, and tkinter. The .exe is self-locating: its data dir
# defaults to a `data/` folder next to the .exe, so dropping it on a
# USB drive gives a portable install with no launcher script.
pyinstaller packaging\CourtDocCataloguer.spec --clean --noconfirm

# Smoke-test the produced .exe (CI does this automatically):
dist\CourtDocCataloguer.exe --selftest
```

---

## Phase plan

See `/home/marty/.claude/plans/cheeky-seeking-rainbow.md` for the full plan. Summary:

1. **Phase 1 — Scaffolding + this file.** ✅ landed.
2. **Phase 2 — Data integrity.** ✅ landed. ISO date storage + migration + foreign-key cascade + atomic import. Notes for future sessions: migrations live in `court_cataloguer/migrations/` and are filename-ordered + self-skipping (no versions table); `documents.case_id` is now `ON DELETE RESTRICT` so any future case-delete UI must explicitly handle orphan documents.
3. **Phase 3 — Encryption + auth.** ✅ landed. SQLCipher via `sqlcipher3-wheels`; passphrase → PBKDF2-HMAC-SHA256 (600k iters, 16-byte salt) → 32-byte raw key fed to `PRAGMA key = "x'<hex>'"`. First-run sets passphrase; idle auto-lock (default 10 min, `COURT_DOC_LOCK_MINUTES` override). A pre-Phase-3 plaintext DB is auto-migrated on first launch and the original preserved as `cataloguer.db.pre-phase3.bak`. **Losing the passphrase loses the data** — no recovery.
4. **Phase 4 — Audit + integrity.** ✅ landed. `audit_log` table with HMAC-chained rows (audit key = HKDF-Expand-SHA256 of the master key). Audited actions: `auth.first_run`, `auth.unlock_success`, `auth.locked`, `auth.rekey`, `case.create`, `doc.import`, `doc.complete`, `doc.skip`, `doc.open`, `export.excel`, `integrity.mismatch`. Wrong-passphrase attempts go to the file log only (no key → no signature possible). `documents` gained `sha256` / `imported_by` / `import_machine` columns. PDFs are hashed on import and verified on open; mismatch is logged + audited + presents an override modal (re-scans happen — we record the event, don't block work). Audit log review is gated behind `COURT_DOC_AUDIT=1`. **Audit log shares the master key**, so losing the passphrase loses the audit trail too. Acceptable per threat model.
4. **Phase 4 — Audit + integrity.** HMAC-chained `audit_log` table; per-document SHA-256; chain-of-custody fields.
5. **Phase 5 — Workflow + UI.** Edit completed records, un-skip flow, multi-line notes, Courtroom blank default, skip confirmation, threading for long ops, keyboard shortcuts.
6. **Phase 6 — Idiomatic cleanup.** Mostly done in Phase 1; remainder is opportunistic.
7. **Phase 7 — Deployment hardening.** Code signing, encrypted backups, no-network startup assertion, BitLocker as deploy precondition.

---

## What lives in the data directory

Default location depends on launch mode (see `court_cataloguer.config._default_data_dir`):

- **Frozen `.exe`** (the portable build): `<exe-dir>\data\` — next to the .exe on the USB drive.
- **Source / dev** (`python main.py`): `C:\CourtDocCataloguer\` — preserves the pre-portable default.
- **Either case, override:** `$COURT_DOC_DIR` always wins.

Whichever path is in use holds:

- `cataloguer.db` — SQLCipher-encrypted SQLite. Unreadable without the passphrase. **No recovery if the passphrase is lost.**
- `keyfile.json` — NON-secret KDF parameters (version, kdf name, iter count, base64 salt). Used to re-derive the key from the passphrase. Required to unlock. If you lose this file but still have the passphrase, you've lost the data anyway because re-deriving without the original salt produces a different key.
- `cataloguer.db.pre-phase3.bak` — rollback copy of the pre-encryption plaintext DB, written automatically the first time a Phase-2 DB is auto-migrated. Safe to delete once you're confident the migration worked.
- `cataloguer.db.pre-migrations.bak` — rollback before Phase-2-style migrations ran (created from the first-launch state).
- `archive/<YYYY-MM-DD>/*.pdf` — imported PDFs. NOT encrypted today — document BitLocker or a separately-encrypted folder as deployment guidance.
- `exports/master_catalogue.xlsx` — last Excel export. Plaintext.
- `logs/app.log` — rotating log (5 MB × 5). PII redaction filter applied; still, don't hand the log to anyone outside court staff.
- `audit_log` (inside `cataloguer.db`) — HMAC-chained tamper-evident record of consequential actions. Read via the AuditLog screen (set `COURT_DOC_AUDIT=1` to reveal the button). The chain re-anchors at every `auth.rekey` — `verify_chain()` is meaningful within an epoch between rekeys.

## What NOT to do without asking

These changes require explicit user buy-in before touching:

- **Schema change** — anything that alters `cases` or `documents` tables. Even adding a column needs a migration.
- **New dependency** — every package is a supply-chain risk. Justify it.
- **Data directory layout change** — migrating the user's existing data is a one-shot operation that can lose data if wrong.
- **Any outbound network call** — including telemetry, crash reporting, update checks. The app is offline by design.
- **Removing or weakening encryption / auth** controls once Phase 3 lands.
- **Deleting `*.db` files** during automated cleanup. Always ask.

---

## Open questions / known gaps

- **Passphrase recovery**: there is none. Losing the passphrase loses the data. SETUP_GUIDE will document this — but think about whether a sealed paper "break glass" passphrase escrow is appropriate.
- **PDF archive encryption**: deferred. Currently relies on SQLCipher for the index + (planned) BitLocker for files on disk. Revisit after Phase 3.
- **Audit log review UI**: only an env-flag-gated screen in Phase 4. If audit volume grows, build a real reviewer.
