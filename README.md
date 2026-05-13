# Court Document Cataloguer

A local Windows desktop app for cataloguing scanned petition PDFs in dependency / neglect court. Single-user, offline, encrypted-at-rest (Phase 3+).

## Where to start

- **Setting up or deploying?** Read `SETUP_GUIDE.md`.
- **Working on the code?** Read `CLAUDE.md` first — it covers architecture, conventions, threat model, and what NOT to do.

## Quick commands

```bash
pip install -e .[dev]
python main.py            # run the app

pytest                    # tests
ruff check .              # lint
mypy court_cataloguer     # types
```

For a custom data directory (e.g. when testing), set `COURT_DOC_DIR=/tmp/court-test` before running.
