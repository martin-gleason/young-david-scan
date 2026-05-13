# Phase 3 — Encryption + Authentication

**Status:** Implementation in progress on this branch.
**Depends on:** Phase 2 ✅
**Blocks:** Phase 4 (audit log HMAC uses the master key).

---

## Problem statement

After Phase 2 the DB is a clean plaintext SQLite file at `C:\CourtDocCataloguer\cataloguer.db`. The threat model in CLAUDE.md identifies the load-bearing controls as **encryption at rest** + **audit log**. This PR delivers the encryption half and the auth gate that makes it usable.

If the laptop is stolen, borrowed, or seized today, every line of dependency/neglect PII is readable with a free SQLite viewer. After this PR, the same scenario yields ciphertext.

---

## Approach

User decisions locked from the Phase 1 planning interview: passphrase at launch → PBKDF2-HMAC-SHA256 (600k iters) → 32-byte key → SQLCipher's `PRAGMA key = "x'<hex>'"`. We bypass SQLCipher's own KDF (we did our own).

### Library choice

**`sqlcipher3-wheels` 0.5.7** (laggykiller fork). As of Jan 2026 it's the only PyPI package shipping Windows wheels for Python 3.11+, statically linked with SQLCipher 4 + OpenSSL. Imports as `from sqlcipher3 import dbapi2 as sqlite` — drop-in for stdlib `sqlite3` (Row, executemany, context manager, PRAGMAs all work). `pysqlcipher3` is abandoned; `sqlcipher3-binary` is currently Linux-only.

### New modules

```
court_cataloguer/
├── crypto.py          PBKDF2 derive, salt gen, keyfile read/write. Pure functions.
├── auth.py            Orchestrator: detect startup mode, run plaintext-import flow.
├── idle.py            IdleLock — Tk event-bound inactivity timer.
└── screens/
    └── auth.py        AuthScreen — first_run / unlock / locked modes.
```

### `database.py` change (minimal)

```python
from sqlcipher3 import dbapi2 as sqlite   # was: import sqlite3

_master_key: bytes | None = None

def set_master_key(key: bytes) -> None: ...
def clear_master_key() -> None: ...

def _connect() -> sqlite.Connection:
    if _master_key is None:
        raise RuntimeError("set_master_key() must be called before opening a DB connection")
    conn = sqlite.connect(str(DB_PATH))
    conn.row_factory = sqlite.Row
    conn.execute(f'PRAGMA key = "x\'{_master_key.hex()}\'"')
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite.DatabaseError as exc:
        conn.close()
        raise WrongPassphraseError(str(exc)) from exc
    return conn
```

No screen code or migration code changes — all 6 modules that import `database` call high-level functions (`db.create_case`, etc.), not `_connect()` directly.

### Startup flow

`CourtDocApp.__init__` no longer calls `init_db()` directly. Sequence:

1. Build all screens (incl. AuthScreen). No DB calls in screen `__init__`s.
2. Detect startup state:
   - **no keyfile, no DB** → `first_run` (set a passphrase).
   - **no keyfile, plaintext DB exists** → `import_plaintext` (auto-migrate, see below).
   - **keyfile + DB** → `unlock` (enter passphrase).
3. `show_screen("AuthScreen", mode=...)`.
4. On success, AuthScreen calls `database.set_master_key(key)` → `database.init_db()` → `app.show_screen("HomeScreen")`. The IdleLock timer arms here.

### Plaintext → encrypted auto-migration

The user has been running this on real Cook County data. Plaintext DBs created in Phases 1/2 must auto-migrate, not strand the user.

Detection: open with stdlib `sqlite3.connect(path)` and run `SELECT count(*) FROM sqlite_master`. If it succeeds, the file is plaintext.

Migration (in `auth.py`):
1. UI prompt: "An unencrypted database was detected. Set a passphrase to encrypt it."
2. Derive key, generate salt.
3. Open the plaintext DB with sqlcipher3 (it'll open without a key); ATTACH a new keyed DB; `SELECT sqlcipher_export('encrypted')`; DETACH.
4. Rename old → `cataloguer.db.pre-phase3.bak`.
5. Rename new → `cataloguer.db`.
6. Write `keyfile.json`.

The `.pre-phase3.bak` file is rollback. CLAUDE.md documents what it is.

### AuthScreen modes

One class. `refresh(mode=...)` picks behaviour:

- **`first_run`**: two `show="•"` fields; warning: "Losing this passphrase loses your data. There is no recovery."
- **`unlock`**: one field; on `WrongPassphraseError` increment retry counter; after 5 attempts, `self.quit()`.
- **`locked`**: same as unlock but title indicates inactivity-driven lock; unlock returns to HomeScreen (not the previous screen — safer default).

### Idle lock

`IdleLock` binds `<Any-Key>`, `<Button>`, `<Motion>` at the Tk root. Any event resets a `tk.after()` timer. Default 10 minutes, overridable via `COURT_DOC_LOCK_MINUTES`. Fire → clear master key, blank form `StringVar`s, `show_screen("AuthScreen", mode="locked")`.

### Test fixture change

`tests/conftest.py` `fresh_db` fixture calls `database.set_master_key(b"\x00" * 32)` before `init_db()`. All Phase 1+2 tests continue to work.

---

## Critical files

**Created**: `court_cataloguer/{crypto,auth,idle}.py`, `court_cataloguer/screens/auth.py`, `tests/test_{crypto,database_encrypted,auth_flow,plaintext_import}.py`, `docs/phase-3-plan.md`.

**Modified**: `pyproject.toml`, `requirements.txt`, `court_cataloguer/{config,database,app}.py`, `court_cataloguer/screens/__init__.py`, `tests/conftest.py`, `CLAUDE.md`, `SETUP_GUIDE.md`.

## Reuse / patterns to preserve

- `database._connect()` remains the single chokepoint for DB access.
- `screens/_shared.py` factories build AuthScreen.
- `app.show_screen(name, **kwargs)` + per-screen `refresh(**kwargs)` pattern unchanged.
- `logging_setup.get_logger(__name__)` used in all new modules. Never log the passphrase or key bytes.

## Verification

1. `pytest` — existing 34 + new ~15 tests green.
2. `ruff check . && ruff format --check .` clean.
3. End-to-end on a fresh data dir:
   - First-run → set passphrase → DB created encrypted.
   - Quit, relaunch → unlock prompt → correct passphrase → app opens.
   - `sqlite3 cataloguer.db ".tables"` fails (file is encrypted).
   - Plaintext-import path: seed a Phase-2 plaintext DB → launch → migration runs → `.pre-phase3.bak` exists → data preserved.
   - `COURT_DOC_LOCK_MINUTES=1` + idle → returns to AuthScreen.

## Risks / one-way pitfalls

- **Lose passphrase → lose data.** No backdoor. Bake into onboarding text + SETUP_GUIDE.
- **`PRAGMA rekey` is not atomic** — flagged; rekey API exists in this PR but no UI yet.
- **`sqlcipher3-wheels` is a community fork.** Pinned exactly to avoid surprise.

## Out of scope for this PR

- Rekey UI screen (API only; UI deferred).
- PDF archive encryption (cheap path: BitLocker; per-file DEK deferred).
- Audit log (Phase 4).
