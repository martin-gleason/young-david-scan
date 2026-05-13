# Setup & Build Guide
## Court Document Cataloguer — Dependency/Neglect Court

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
pyinstaller --onefile --windowed --name "CourtDocCataloguer" main.py
```

The finished executable appears at:
```
dist\CourtDocCataloguer.exe
```

---

## Step 5 — Deploy to a Staff Machine

1. Copy `CourtDocCataloguer.exe` to the staff machine (USB or network share)
2. Place it anywhere — suggest `C:\CourtDocCataloguer\CourtDocCataloguer.exe`
3. Right-click → **Create shortcut** → drag shortcut to desktop
4. Double-click the shortcut to launch

**No Python install needed on staff machines.** The .exe is self-contained.

---

## Data Location (on every machine)

| Path | Contents |
|---|---|
| `C:\CourtDocCataloguer\cataloguer.db` | All case and document records |
| `C:\CourtDocCataloguer\archive\` | Imported PDFs organised by date |
| `C:\CourtDocCataloguer\exports\master_catalogue.xlsx` | Master spreadsheet |

**Backup recommendation:** Copy `C:\CourtDocCataloguer\` to a network drive or external drive weekly.

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
| Lost data | Restore `cataloguer.db` from your most recent backup |

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
