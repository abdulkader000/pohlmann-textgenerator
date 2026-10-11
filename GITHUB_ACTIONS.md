# Windows-Testbuild über GitHub Actions

Workflow .github/workflows/windows-build.yml: manuelles workflow_dispatch, windows-latest, Python 3.12 x64. Der vorhandene build_windows.py führt Tests, PyInstaller, Verpackung und ZIP-Prüfung aus. Fehler stoppen den Job; danach wird ausschließlich release/TextGenerator_Windows.zip als Artifact TextGenerator-Windows hochgeladen. Keine OpenAI API-Anfragen und kein OpenAI Secret erforderlich.

## CLI-Ablauf

Nur nach Freigabe des Commits und Pushs:

```text
gh workflow run windows-build.yml --repo abdulkader000/pohlmann-textgenerator --ref main
gh run list --repo abdulkader000/pohlmann-textgenerator --workflow windows-build.yml --event workflow_dispatch --branch main --limit 5
gh run watch RUN_ID --repo abdulkader000/pohlmann-textgenerator --exit-status
gh run download RUN_ID --repo abdulkader000/pohlmann-textgenerator --name TextGenerator-Windows --dir release/windows-test-RUN_ID
```

Den neuen Run über die vollständige Commit-SHA zuordnen. Alte ZIP nicht überschreiben; die neue Datei erhält einen Namen mit Testversion, Datum und Commit. Keine öffentliche GitHub Release oder Empfänger-Nachricht erstellen.

## Inhalt und Schutz

ZIP ausschließlich TextGenerator.exe, .env, ANLEITUNG.txt im Wurzelverzeichnis. Die feste .env enthält nur OPENAI_API_KEY=YOUR_API_KEY_HERE und OPENAI_MODEL=gpt-4.1. Build und Prüfung verwenden keine echte lokale .env. Schlüssel, MZ-unabhängige Zusatzdateien, Quellen, Tests, Experimente und alte Artikel gehören nicht in die ZIP.

.gitignore schließt lokale Zugangsdaten, Python-Umgebungen, Builds, Outputs, Archive, Experimente und gespeicherte Antworten aus. Neue Dateien ausdrücklich auswählen, nicht git add . verwenden. Tests im Commit müssen ohne lokale Experimente und Rohantworten funktionieren.

## Offizielle Dokumentation

Die eingesetzten Versionen und Eingaben wurden anhand der offiziellen action.yml geprüft:

- [actions/checkout v7](https://github.com/actions/checkout/blob/v7/action.yml): persist-credentials=false, contents: read.
- [actions/setup-python v7](https://github.com/actions/setup-python/blob/v7/action.yml): python-version=3.12 und architecture=x64.
- [actions/upload-artifact v7](https://github.com/actions/upload-artifact/blob/v7/action.yml): name, path, if-no-files-found=error, compression-level=0, retention-days=14.
- [Manuelle Workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow), [gh workflow run](https://cli.github.com/manual/gh_workflow_run), [gh run watch](https://cli.github.com/manual/gh_run_watch), [gh run download](https://cli.github.com/manual/gh_run_download).

## Testgrenze

Build-Erfolg ist keine EXE-Laufzeit- oder Inhaltsfreigabe. Windows-Start und Bedienung gemäß WINDOWS_TEST_CHECKLIST.md prüfen. Die Anwendung erzeugt Entwürfe; Inhalte müssen vor Veröffentlichung geprüft werden. Es ist eine Testversion und keine Freigabe zum Versand.
