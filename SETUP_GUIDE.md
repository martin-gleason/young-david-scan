# Setup & Build Guide
## Court Document Cataloguer — Dependency/Neglect Court

> **Are you a beta tester?** This guide is the long version intended for whoever builds and deploys the app. If you just got handed a USB drive and want to know how to run it, read **`BETA_TEST.md`** instead.

---

## What This App Does

A local Windows desktop application for scanning, cataloguing, and searching dependency/neglect court petition documents. All data stays on the workstation — no internet, no cloud, no AI.

---

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer (only needed for development/building — not on staff machines)

---

## Step 1 — Install Python (development machine only)

Download from: https://www.python.org/downloads/

During install: **check "Add Python to PATH"**

Verify in Command Prompt:
```
python --version
```

---

## Step 2 — Install Dependencies

Open Command Prompt in the project folder:

```
cd C:\path\to\court_doc_cataloguer
pip install -r requirements.txt
```

---

## Step 3 — Run the App (development / testing)

```
python main.py
```

The app will:
- Create `C:\CourtDocCataloguer\` on first run
- Create the database automatically
- Open the main window

---

## Step 4 — Build the .exe (for deployment to staff machines)

Run this once from the project folder:

```
pyinstaller packaging\CourtDocCataloguer.spec --clean --noconfirm
```

The spec file (`packaging/CourtDocCataloguer.spec`) is configured for a **single-file** PyInstaller build: it produces one `CourtDocCataloguer.exe` containing the bundled Python runtime, statically-linked SQLCipher, PyMuPDF, and tkinter. No `_internal/` folder, no launcher batch file. Drop the .exe on a USB drive and it will self-locate — the data directory defaults to a `data\` folder next to wherever the .exe lives.

After building, verify the bundle locally:

```
dist\CourtDocCataloguer.exe --selftest
```

Should exit 0 and print `court_cataloguer self-test passed`. The CI build runs this automatically on every push.

For the automated build, see `.github/workflows/build-release.yml` — every push to `main` triggers a Windows-runner build that uploads the zip as an Actions artifact. Tagged pushes (`v1.2.0` etc.) also create a GitHub Release with the zip attached.

The finished executable appears at:
```
dist\CourtDocCataloguer.exe
```

---

## Step 5 — Deploy to a Staff Machine

1. Copy `CourtDocCataloguer.exe` to the staff machine — on a USB drive for portable mode, or anywhere on `C:\` for a fixed install.
2. (Optional) Right-click → **Create shortcut** → drag shortcut to desktop.
3. Double-click the .exe (or shortcut) to launch.

**No Python install needed on staff machines.** The .exe is self-contained — Python, tkinter, sqlcipher3, and pymupdf are all bundled in.

The .exe self-locates its data directory: a `data\` folder is created next to the .exe on first launch. To force a specific location, set `COURT_DOC_DIR=<path>` before launching.

---

## Data Location

The data directory defaults depend on how the app is launched:

| Launch mode | Default data dir |
|---|---|
| Run from the built `.exe` (portable USB) | `<exe-dir>\data\` — the folder right next to the .exe |
| Run from source (`python main.py` during development) | `C:\CourtDocCataloguer\` |
| Override either case | Set `COURT_DOC_DIR=<path>` before launch |

Inside that directory:

| Path | Contents |
|---|---|
| `cataloguer.db` | All case and document records (SQLCipher encrypted) |
| `keyfile.json` | KDF parameters needed to re-derive the master key |
| `archive\<YYYY-MM-DD>\` | Imported PDFs organised by date |
| `exports\master_catalogue.xlsx` | Master spreadsheet |
| `logs\app.log` | Rotating PII-redacted log |

**Backup recommendation:** Copy the entire data folder (or the USB drive) to a network drive or external drive weekly. The `cataloguer.db` file is encrypted — backups are safe to store on a less-trusted drive, but **the backup is only useful if you still know the passphrase**.

---

## The Passphrase — read this first

Starting with v1.1, every case record is encrypted on disk with a passphrase you set the first time you launch the app.

- **Choose a passphrase you will not forget.** Write it on paper and store it somewhere only you can reach (locked desk drawer, home safe).
- **There is no recovery, no reset, no backdoor.** If you lose the passphrase, every record in `cataloguer.db` is permanently unreadable. Even the application authors cannot recover it.
- **Minimum length: 12 characters.** Longer is better. A short memorable phrase ("blue October chair") is stronger and easier to remember than a short complex one ("X4!9bQ").
- The first time you launch v1.1 with an older (pre-encryption) database, the app will detect it, ask you to set a passphrase, encrypt the data, and keep a `cataloguer.db.pre-phase3.bak` rollback file. Don't delete that file until you've successfully opened the app a few times with the new passphrase.

The app also **auto-locks after 10 minutes of inactivity**. You'll be asked for the passphrase again to continue. If you walk away from your desk, the data is protected. You can change the timeout by setting the `COURT_DOC_LOCK_MINUTES` environment variable.

---

## The Audit Log

Starting with v1.2, the app keeps a tamper-evident record of every consequential action — case creation, document import, PDF opens, Excel exports, sign-ins, idle-locks. Each entry is cryptographically signed so that anyone editing the database file directly (with a text editor or SQL tool) will break the signature chain and `Verify Chain` in the app will surface exactly which row was altered.

The audit log is **not visible in the normal UI** — you'd never need it for daily work. To inspect it, set the environment variable `COURT_DOC_AUDIT=1` before launching the app. An "Audit Log" button will appear on the Home screen. The screen shows the latest 500 events and has a `Verify Chain` button.

What the audit log proves: every recorded action happened under your passphrase. What it does NOT prove: the actual content of cases or PDFs (those are in the regular tables). Like the catalogue itself, the audit log is encrypted with your passphrase — losing the passphrase loses both.

---

## Daily Workflow (for staff)

1. Scan petitions at the Toshiba/Xerox machine → save to USB drive
2. Plug USB into PC and open CourtDocCataloguer
3. Click **Import from USB** → Scan → Import All
4. Unplug USB
5. Click **Open Processing Queue**
6. Work through the queue: review each PDF, fill in the form, click **Save & Next**
7. When done, click **Export to Excel** from the home screen

---

## Customising Courtrooms or Petition Types

Open `config.py` in Notepad and edit the lists:

```python
COURTROOMS = [
    "Courtroom 1",
    "Courtroom 2",
    ...
]

PETITION_TYPES = [
    "Petition for Adjudication — Neglect",
    ...
]
```

After editing, re-run `pyinstaller` to rebuild the .exe.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "No removable drives found" | Try unplugging and re-inserting the USB, then click Scan again |
| "Cannot open PDF" | The PDF may be corrupt. Skip it and note the filename. |
| "master_catalogue.xlsx is open in Excel" | Close the file in Excel, then click Export again |
| App won't start | Check that `C:\CourtDocCataloguer\` exists and is writable |
| "Incorrect passphrase" | Try again. After 5 wrong attempts the app quits to slow guessing — re-launch and try again. Caps lock? |
| Forgot passphrase | There is no recovery. The data is gone. Set a new passphrase on a fresh data dir and start over. |
| App locked itself while you were on a break | Expected behaviour at 10 min idle. Re-enter your passphrase to continue. Override with `COURT_DOC_LOCK_MINUTES`. |
| Lost data | Restore `cataloguer.db` AND `keyfile.json` together from a backup. Restoring one without the other is useless. |

---

## Project File Overview

| File | Purpose |
|---|---|
| `main.py` | Entry point — creates the app window |
| `config.py` | All constants, paths, and dropdown lists |
| `database.py` | All SQLite database operations |
| `utils.py` | USB detection, file import, Excel export |
| `pdf_viewer.py` | PDF display widget |
| `screens.py` | All five application screens |
| `requirements.txt` | Python package dependencies |

---

-----
2026-05-12

#AI/Claude
