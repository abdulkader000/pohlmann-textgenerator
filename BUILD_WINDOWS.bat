@echo off
setlocal
cd /d "%~dp0"
py -3 build_windows.py
if errorlevel 1 (
  echo Build fehlgeschlagen. Bitte die Meldung oben pruefen.
  pause
  exit /b 1
)
echo Build abgeschlossen. Ergebnis im Ordner release.
pause
