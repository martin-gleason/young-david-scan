# PyInstaller spec for the Court Document Cataloguer.
#
# Build with:
#   pyinstaller packaging/CourtDocCataloguer.spec --clean --noconfirm
#
# Produces a SINGLE-FILE executable at dist/CourtDocCataloguer.exe. The .exe
# is self-locating: at runtime it reads sys.executable, treats the directory
# the .exe lives in as the install root, and creates a "data/" folder next
# to itself for the database, archive, audit log, etc. (see
# court_cataloguer/config._default_data_dir).
#
# Trade-offs accepted by going single-file:
#   - First-launch cost: ~2–3 s while the PyInstaller bootloader unpacks the
#     bundle to %TEMP%\_MEIxxxx and starts the bundled Python interpreter.
#     Subsequent launches in the same session reuse the unpack.
#   - AV heuristics flag single-file PyInstaller bundles more often than
#     onedir bundles. We mitigate with: no UPX, no console window, a build
#     produced by a clean CI runner. Code-signing certificate is the real
#     fix and is on the Phase 7 roadmap.
#   - Harder to inspect when something goes wrong — the bundle is opaque
#     until it unpacks. Acceptable cost for "one file on a USB drive."
#
# The CLAUDE.md guidance previously documented the onedir choice; that
# write-up is now stale and is updated in the same change as this spec.

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

# sqlcipher3-wheels statically links SQLCipher + OpenSSL into the
# sqlcipher3 native extension. collect_dynamic_libs pulls the .pyd in;
# collect_submodules picks up dbapi2 etc.
binaries = collect_dynamic_libs("sqlcipher3")
hiddenimports = collect_submodules("sqlcipher3")

# PyMuPDF (fitz) loads its native lib at import time; same treatment.
binaries += collect_dynamic_libs("fitz")
hiddenimports += collect_submodules("fitz")

# court_cataloguer.migrations — submodules are loaded dynamically by
# importlib.import_module(f"...{name}") from migrations/__init__.py, so
# PyInstaller's static-import analyzer can't see them. We can't use
# collect_submodules() here for two reasons: (a) the project isn't on
# sys.path during spec processing unless we add it, and (b) the names
# start with digits (001_dates_to_iso etc.) which collect_submodules
# filters out as invalid Python identifiers. So glob the .py files
# directly — this is build-time only, doesn't require the package to
# be importable, and handles digit-prefixed names fine.
from pathlib import Path as _Path

# SPECPATH is a PyInstaller-injected global — the directory containing
# this spec file. __file__ is NOT defined in PyInstaller's spec exec
# context (we tried; the build errored with NameError).
_PROJECT_ROOT = _Path(SPECPATH).parent  # noqa: F821 — SPECPATH is injected
_MIG_DIR = _PROJECT_ROOT / "court_cataloguer" / "migrations"
hiddenimports += [
    f"court_cataloguer.migrations.{p.stem}"
    for p in sorted(_MIG_DIR.glob("[0-9][0-9][0-9]_*.py"))
]
# Also force the package itself + its __init__ into the bundle.
hiddenimports += ["court_cataloguer.migrations"]

block_cipher = None


a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=binaries,
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Shave bundle size — none of these are used at runtime.
        "tkinter.test",
        "test",
        "unittest",
        "pytest",
        "ruff",
        "mypy",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file build: binaries, zipfiles, and datas go straight into the EXE
# (no separate COLLECT step). exclude_binaries defaults to False here.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CourtDocCataloguer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX trips antivirus; not worth the size savings
    upx_exclude=[],
    runtime_tmpdir=None,  # Use the OS default (%TEMP%) for bundle unpack
    console=False,        # GUI app — no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
