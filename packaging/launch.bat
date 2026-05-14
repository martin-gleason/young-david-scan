@echo off
REM Court Document Cataloguer — portable launcher.
REM
REM Double-click this file from the USB drive. It points the app at a
REM "data" folder next to itself (so the database, archive, logs, and
REM keyfile all live on the same USB you launched from) and then runs
REM CourtDocCataloguer.exe.
REM
REM The %~dp0 trick gives the directory this .bat file is in, with a
REM trailing backslash. Quotes around the path tolerate spaces (e.g.
REM "E:\My Documents\CourtDocCataloguer\").

setlocal

set "COURT_DOC_DIR=%~dp0data"

REM Optional: shorter idle-lock timeout for kiosk-style USB use.
REM Uncomment to override the 10-minute default.
REM set "COURT_DOC_LOCK_MINUTES=5"

REM Optional: enable the Audit Log button for reviewers.
REM set "COURT_DOC_AUDIT=1"

if not exist "%COURT_DOC_DIR%" mkdir "%COURT_DOC_DIR%"

start "" "%~dp0CourtDocCataloguer\CourtDocCataloguer.exe"

endlocal
