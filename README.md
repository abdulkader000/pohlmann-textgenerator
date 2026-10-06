# Windows delivery update

The existing project supports a manual GitHub Actions Windows build; no Windows EXE has yet been built or tested in the current macOS session. Real generation remains untested because the user reported `credit_balance_exhausted / insufficient_quota`.

## Manual GitHub Actions build

See [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) for repository setup, exact user-run push commands, official Action documentation and the subsequent CLI-only build/download procedure. The user has authorized a public repository on `abdulkader000`; the workflow supports public or private repositories. It runs only through `workflow_dispatch` on `windows-latest` with Python 3.12, runs `build_windows.py`, stops on failures and uploads only the validated recipient ZIP as `TextGenerator-Windows`. No OpenAI API secret is needed or used.

## Build on Windows

Install Python 3.10 or newer with the Python launcher. Unzip the source folder and double-click `BUILD_WINDOWS.bat`. The script creates a dedicated build environment, installs dependencies, runs offline tests, builds a console-free EXE and creates `release/TextGenerator_Windows.zip`. Build errors stop packaging.

The delivery ZIP contains exactly TextGenerator.exe, .env with a placeholder key, and ANLEITUNG.txt at its root. The build generates fixed placeholder configuration and never copies local `.env` or `.env.example`. The responsible person configures `.env` only locally beside the extracted EXE, using a locally supplied key. Keep the delivery archive's placeholder; do not repackage a configured `.env`. The instructions mark delivery as provisional until the live test succeeds. See `PRUEFBERICHT.md` for the tests actually performed in the current session. Successful CI compilation does not replace testing the EXE on a Windows computer.

On Windows verify: opening from a path with spaces, automatic browser launch, a demo run via `TextGenerator.exe --demo`, HTML/TXT download, the Program beenden button, and a real API run after credit is available. The browser must stay open until the Program beenden button is used; closing only the browser leaves the local process running.

The EXE is unsigned. Actual startup and any Windows prompts must be checked on the delivery computer. Restart after any change to `.env`.

## macOS test with an older system Python

Use Python 3.10+ explicitly when creating the environment; the system `python3` may be too old. For the already installed Homebrew Python 3.13:

```bash
"$(brew --prefix python@3.13)/bin/python3.13" -m venv .venv313
source .venv313/bin/activate
python -m pip install -r requirements.txt
python app.py --demo
```

## Existing functionality and background

# Pohlmann Textgenerator

Überarbeitete Fassung des vorhandenen lokalen Python/Flask-Tools. Läuft aus dem Quellcode auf macOS, Linux und Windows; eine Windows-EXE ist dafür nicht erforderlich.

## Auftrag

Neue Kombinationen aus Linktext und URL eingeben; pro Generierung einen anders formulierten deutschen Artikel mit ungefähr 800 Wörtern erzeugen. Frau Witzgall soll das Tool bedienen können. Die neue Linkliste und das Betriebssystem von Frau Witzgall sind im Auftrag noch nicht angegeben.

## macOS / Linux: Installation und Offline-Test

Python 3.10 oder neuer ist erforderlich. Im Terminal in diesen entpackten Ordner wechseln:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py --demo
```

Die Oberfläche öffnet sich im Browser. Falls sie nicht automatisch öffnet, die im Terminal angezeigte Adresse öffnen. „Eigene Linkliste“ wählen und zum Beispiel eingeben:

```text
IT-Sicherheit, https://it-sicherheit.de/
Phishing, https://norbert-pohlmann.com/glossar-cyber-sicherheit/phishing/
```

Generieren und HTML-/Text-Download prüfen. Demo-Ergebnisse sind sichtbar als DEMO markiert, repetitiv und nicht zur Veröffentlichung gedacht. Der Demo-Modus ist kein Test der KI-Qualität. Beenden mit Strg+C im Terminal.

## Echte KI-Texte

```bash
cp .env.example .env
```

In `.env` einen gültigen, vom Institut bereitgestellten API-Schlüssel eintragen. `.env` liegt direkt neben `app.py`. Den Schlüssel nicht in Chat, Git oder Code einfügen. Alte Schlüssel aus den Originalarchiven müssen vom Schlüsselinhaber widerrufen werden; die gelieferten alten Schlüssel wurden nicht verwendet oder übernommen.

`OPENAI_MODEL=gpt-4` übernimmt den Modellnamen des bisherigen Hauptprogramms. Bei fehlendem Modellzugriff einen vom API-Konto unterstützten Chat-Completions-Modellnamen konfigurieren. Live-Zugriff und Kosten wurden hier nicht geprüft. Eine Generierung kann bis zu drei API-Anfragen verursachen; sichtbare Wortzahl und vollständige Verlinkung werden geprüft. Die URLs werden nicht abgerufen. Der Inhalt der verlinkten Webseiten wird daher nicht als Quelle ausgewertet.

```bash
python app.py
```

Zielwortzahl: standardmäßig 800; erfolgreich sind 720–880 Wörter. Andere Ziele zwischen 200 und 2000 sind einstellbar. Wortzahl zählt den sichtbaren Artikeltext ohne HTML. Unterschiedliche Texte werden angefordert; mathematisch garantierte Einzigartigkeit gibt es nicht. Fachliche Aussagen vor Veröffentlichung prüfen.

## Bedienung für Frau Witzgall

1. Programm starten und Browser öffnen.
2. „Eigene Linkliste“ oder eine der vorhandenen Vorlagen wählen.
3. Thema und gewünschte Wortzahl setzen.
4. Linkpaare eingeben oder Vorlage bearbeiten: eine Zeile je Paar, `Linktext, URL`.
5. „Neuen Text generieren“ drücken; Ergebnis lesen und herunterladen.
6. Für einen weiteren Text erneut generieren.

Die Vorlagen wurden aus der neueren Originalfassung übernommen. Ihre Zieladressen sind nicht auf Aktualität geprüft; beispielsweise verweist „Kritische Infrastruktur“ im Original auf eine Privatsphäre-Seite. Bitte die freigegebene aktuelle Linkliste verwenden. Gelöschte Vorlageneinträge werden nicht wieder hinzugefügt. Linktexte mit Komma können als CSV in geraden doppelten Anführungszeichen oder mit Tab vor der URL eingegeben werden.

Ergebnisse liegen im Ordner `outputs` neben dem Programm, als HTML mit Links und TXT ohne HTML. Ordner muss beschreibbar sein. Der Server lauscht ausschließlich auf `127.0.0.1`, ohne Debug-Modus; kein öffentliches Hosting eingerichtet.

## Windows / EXE

Zum Starten aus Quellcode:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py --demo
```

Eine neue Windows-EXE **auf Windows** bauen und anschließend dort testen:

```powershell
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller --clean app.spec
```

Ergebnis: `dist\TextGenerator.exe`. Für den echten Betrieb `.env` neben die EXE legen. Keine Schlüssel in die EXE bündeln. Die vorhandenen Archive enthalten keine EXE-Datei. Eine Windows-EXE wurde in dieser Linux-Umgebung nicht gebaut oder getestet.

## Prüfung

```bash
python -m unittest discover -s tests -v
```

Automatisierte Offline-Prüfungen: Eingabevalidierung, Linkerstellung und Escaping, fehlende/überlappende Begriffe, Wiederholungsversuche und Wortgrenzen mit simulierter API, Oberfläche, fehlender Schlüssel, Demo und Downloads. Keine echte OpenAI-Anfrage durchgeführt. macOS-/Windows-Lauf und echte Artikelqualität müssen noch lokal geprüft werden.

## Änderungen gegenüber den Archiven

- Neuere `app.py` als funktionale Grundlage; vorhandene Website-Vorlagen unverändert als JSON ausgelagert.
- Fehlenden `templates`-Ordner am Programmroot wiederhergestellt.
- Eingabefeld ist maßgebliche Linkliste; entfernte Vorlagenlinks werden nicht wieder eingeschleust.
- Wortziel 800 statt des in der neueren Version fest eingebauten 1000–1200-Ziels.
- Verlinkung über escaped Text statt fehleranfälliger globaler HTML-Ersetzung; keine Modell-HTML-Ausführung.
- Fehlende Begriffe und falsche Länge lösen begrenzte Überarbeitung aus; kein erfolgreiches Ergebnis vortäuschen.
- Programm-/Ressourcenpfade unabhängig vom Terminal-Arbeitsordner; zufälliger Port erst gebunden, dann Browser geöffnet.
- Lesbare API-Fehler, sichere Dateinamen und eindeutige Ergebnisnamen.
- Alte `.env`, eingebettete Schlüssel, IDE-Dateien und alte Ergebnisse nicht übernommen.

Weitere Übergabe an Codex: `CODEX_PROMPT.md`.
