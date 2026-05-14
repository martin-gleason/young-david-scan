# PyInstaller spec for the Court Document Cataloguer beta build.
#
# Build with:
#   pyinstaller packaging/CourtDocCataloguer.spec
#
# Produces dist/CourtDocCataloguer/CourtDocCataloguer.exe plus the runtime
# directory next to it. We deliberately do NOT use --onefile because
# unpacking sqlcipher3's native extension to a temp dir on every launch
# slows first-run by 2-3s and can trip antivirus heuristics. The
# multi-file build also makes incident response easier (the navigator can
# zip the whole folder if something goes wrong without picking files
# out of an opaque single-file archive).

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

# sqlcipher3-wheels statically links SQLCipher + OpenSSL into the
# sqlcipher3 native extension. --collect-binaries / collect_dynamic_libs
# pulls the .pyd in. --collect-submodules picks up dbapi2 etc.
binaries = collect_dynamic_libs("sqlcipher3")
hiddenimports = collect_submodules("sqlcipher3")

# PyMuPDF (fitz) loads its native lib at import time; same treatment.
binaries += collect_dynamic_libs("fitz")
hiddenimports += collect_submodules("fitz")

# Pillow / openpyxl are pure-Python at the surface; PyInstaller's dep
# walker handles them. Listed here for documentation.

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
        # Pull these out of the bundle to shave size — we don't use any of them.
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CourtDocCataloguer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX trips antivirus; not worth the size savings
    console=False,          # GUI app — no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CourtDocCataloguer",
)
