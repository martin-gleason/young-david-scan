# Beta Test — Court Document Cataloguer

Hi David! This is the portable build of the cataloguer for you to try out before we ship a permanent install. It runs straight from a USB drive — no installation, no admin rights, no IT ticket.

---

## Before you start

**Read this part carefully.** It's the only thing in this guide that's actually scary.

The app encrypts every case record with a passphrase you set the first time you launch it. **There is no recovery if you forget the passphrase.** No "click here to reset", no support email that can restore it, no backdoor. The cryptographic design means even the people who wrote the app can't get the data back. Treat this passphrase like the key to a safe — write it on paper and put it somewhere only you can reach.

A 12-character minimum is enforced. Longer phrases ("blue October chair house") are stronger AND easier to remember than short complex ones ("X4!9bQ"). You'll be asked to type it twice on the first launch to make sure you typed what you meant.

---

## Step 1 — Get the build

1. Go to https://github.com/martin-gleason/young-david-scan/actions
2. Click the most recent green run of **"Build portable Windows .exe"**
3. Scroll to the bottom of that page and download **`CourtDocCataloguer-portable.zip`** under "Artifacts"

(If you're doing this without a GitHub login, ask me — I can also send the zip directly.)

---

## Step 2 — Put it on a USB drive

1. Plug an empty USB drive into your work computer. **2 GB or more.** A smaller drive will work for a few weeks; you'll want headroom for the PDF archive as you process more cases.
2. Unzip `CourtDocCataloguer-portable.zip` onto the USB drive. You should see exactly two files:

```
E:\
├── CourtDocCataloguer.exe
└── README.txt
```

(Drive letter will vary — E:, F:, G: depending on what's plugged in.)

3. **Double-click `CourtDocCataloguer.exe`.** Windows takes about 2–3 seconds on the first launch while it unpacks the bundled Python runtime into a temporary folder (normal — happens once per session). The app then creates a `data\` folder right next to the .exe and puts everything in it — database, archived PDFs, the audit trail — so it all stays on the USB drive. The .exe knows where it is and points itself at the USB automatically; no launcher batch file required.

---

## Step 3 — First run

The app opens to a "Welcome — set a passphrase" screen. Type your passphrase twice and click **Create passphrase**. Takes about a second (it's running 600,000 rounds of PBKDF2 in the background to derive the encryption key — you'll see a "Deriving key…" status).

The home screen appears with four buttons. You're in.

---

## Step 4 — Things to try

Pick a quiet ten minutes and run through this whole list. Anything that surprises you or breaks, write down (or screenshot) and send it back.

### Workflow we'd actually use

1. **Scan a few test PDFs** to a different USB drive. Use throw-away petitions or whatever you have lying around — please don't put real case data on the beta yet (see "What about real data?" below).
2. **Plug in the scan USB.** Don't unplug the beta USB.
3. Click **Import from USB** → **Scan for USB Drives** → **Import All PDFs**.
4. Unplug the scan USB. The PDFs are now copied into `data\archive\<today>\` on the beta USB.
5. Click **Open Processing Queue**. The imported PDFs are listed.
6. Double-click one. The PDF viewer + the case-info form appears side by side.
7. Fill in the form — last name, courtroom, docket #, case date (MM/DD/YYYY), petition type, notes. Click **Save & Next**.
8. Work through three or four documents. Try skipping one. Try saving with a bad date like `13/45/2024` — the app should reject it with a clear message.
9. Go back to **Home** → **Search Cases**. Search by last name. Search by date range across a year boundary (`12/01/2023` → `02/01/2024`) and confirm results look right.
10. **Export to Excel.** A `master_catalogue.xlsx` appears in `data\exports\`. Open it in Excel.

### Things to try just to test the safety net

11. **Walk away for 10+ minutes.** Come back and try to do anything. The app should ask for your passphrase again — this is the idle auto-lock.
12. **Quit the app entirely** (close the window). Re-launch from the USB. Type the wrong passphrase. The app says "Incorrect passphrase. N attempt(s) remaining." After 5 wrong attempts it quits.
13. **Try opening the same `cataloguer.db` file with a free SQLite viewer** (DB Browser for SQLite, for example). It should fail — the file is encrypted. This is the test that matters: anyone who picks up your USB without your passphrase sees ciphertext.

---

## Step 5 — When you're done testing

1. **Don't delete the USB yet** — the data is encrypted but I'd like to confirm the file structure looks right before we wipe.
2. Send me a quick note about anything that:
   - Crashed or hung
   - Looked broken
   - Felt confusing
   - You wished worked differently
3. If you want to keep using it for real work after the beta, we can — but read the next section first.

---

## What about real case data?

You can use real data, but think about these risks first:

- **Losing the USB.** The data is encrypted with your passphrase, so a stolen or lost USB is effectively a brick to anyone else. But losing it still costs you the data — same as today if your laptop died with `C:\CourtDocCataloguer\` on it. **Make a backup** by copying the `data\` folder somewhere safe (encrypted external drive, or your existing backup spot) at least weekly.
- **Losing the passphrase.** Already covered above. There is no recovery.
- **Wearing out the USB.** Cheap flash drives die unpredictably. If you use this for real work, get a name-brand drive (SanDisk Ultra, Samsung Bar Plus, Kingston) — they last years; bargain-bin drives last weeks.
- **The audit log lives in the same encrypted DB.** To see what's there, open Command Prompt on the USB drive and run `set COURT_DOC_AUDIT=1 && CourtDocCataloguer.exe` — an Audit Log button appears on the Home screen. Future versions will surface it without the env-var hop.

---

## What's new in this build

Compared to anything you've used before:

- **Encrypted at rest.** Every case record is AES-256-encrypted with a key derived from your passphrase (SQLCipher 4 + PBKDF2 600k iters).
- **Auto-locks after 10 min idle.** Walks away, can't read your screen.
- **Tamper-evident audit log.** Every case create, document import, PDF open, export, and sign-in is HMAC-signed. If anyone (including someone with your passphrase) edits the database directly with another tool, the chain breaks visibly.
- **Per-PDF integrity.** Each PDF's SHA-256 is recorded on import and checked every time you open it. If a file on disk changes for any reason, you get a warning — and the warning itself is logged.
- **ISO date storage under the hood.** You still type MM/DD/YYYY; the app stores ISO. Date-range searches now work correctly across year boundaries (this was actually broken in the older version).

---

## Quick help

| Problem | What to do |
|---|---|
| "Incorrect passphrase" again and again | Caps Lock? After 5 attempts the app quits — re-launch and try once more, calmly. |
| App won't start | Wait 5 seconds — the first launch unpacks the bundled Python runtime to a temp folder, which takes a moment. If still nothing, see "Antivirus quarantined the .exe" below. |
| Windows SmartScreen warning | Click "More info" → "Run anyway". The build is unsigned for now — that's a paid certificate I haven't bought yet. |
| Antivirus quarantined the .exe | Add the USB drive (or the .exe itself) to your AV allowlist. Single-file PyInstaller bundles trigger heuristics more often than installed apps — code-signing fixes this for real but isn't in yet. |
| "Idle lock" annoys you | Set the environment variable `COURT_DOC_LOCK_MINUTES=20` (or whatever) before launching. The fastest way: Command Prompt → `cd` to the USB → `set COURT_DOC_LOCK_MINUTES=20` → `CourtDocCataloguer.exe`. |
| Lost the USB | If it had encrypted data on it: you're fine, the finder can't read it. If it had a paper note with your passphrase: now the finder CAN read it. Don't keep the passphrase on/near the USB. |
| Forgot the passphrase | Sorry — the data is gone. Set a new passphrase on a fresh USB and start over. |

---

Thanks for trying this. The whole point of the beta is to find the rough edges before this is anything you depend on for real work. Be merciless with the feedback.

— Marty
