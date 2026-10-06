# Prüfbericht vom 6. Oktober 2026 – vorläufiger Stand

## Projekt und Umgebung

Das vorhandene Projekt unter `/Users/abdulkaderalamin/Documents/Code/pohlmann-textgenerator` wurde vor Änderungen byteweise mit `Pohlmann_Textgenerator_Windows_Build.zip` verglichen: alle 15 Dateien identisch. Keine Neuimplementierung, keine Git-Pushes und keine Veröffentlichung.

Diese Sitzung läuft auf macOS (Darwin), nicht auf Windows. Das Standard-Python ist 3.9.18; für die Prüfungen wurde das verfügbare Python 3.12.14 verwendet. Die festgelegten Abhängigkeiten aus `requirements.txt` wurden in `.venv` installiert. `pip check` meldet keine defekten Abhängigkeiten.

`build_windows.py` wurde mit Python 3.12 gestartet. Tatsächliches Ergebnis: Abbruch mit „Die Windows-EXE muss auf Windows gebaut werden.“ Eine nutzbare Windows-VM wurde nicht gefunden; der vorhandene VBoxManage-Verweis zeigt auf eine fehlende VirtualBox-Installation. Kein Windows-PyInstaller-Lauf und keine EXE wurden erzeugt. Es gibt deshalb keinen nachgewiesenen Windows-Buildfehler zu beheben.

## Tatsächlich ausgeführte Prüfungen

`.venv/bin/python -m unittest discover -s tests -v`: alle sechs vorhandenen Tests erfolgreich.

- CSV und frei editierbare Linkpaare: Validierung erfolgreich.
- Verlinkung einschließlich überlappender Begriffe, HTML-Escaping und fehlender Linktexte: erfolgreich.
- Wortzahl und Wiederholungsversuche mit simulierter Modellantwort: erfolgreich.
- Fehlender Zugang, Demo und HTML-/TXT-Downloads: erfolgreich.
- Simulierte HTTP-429-Fehler `credit_balance_exhausted` und `insufficient_quota`: deutsche Guthabenmeldung, Eingaben erhalten, keine Ergebnisdateien gespeichert.
- Schutz des Beenden-Endpunkts durch Sitzungstoken: erfolgreich.

Zusätzlich wurde der unveränderte Quellcode über echtes lokales HTTP auf macOS geprüft, in einer temporären Projektkopie mit Leerzeichen im Pfad und mit Arbeitsverzeichnis außerhalb des Programmordners. Zwei vollständige Durchläufe bestanden: Start, Standardwert 800, Demo mit 800 Wörtern, beide eingegebenen Linktexte als Links im HTML, HTML-/TXT-Download als Datei, Beenden über `/stop` mit Prozessende und Neustart mit neuen Ergebnisdateien.

Der zeitgesteuerte Aufruf von `webbrowser.open` wurde durch einen Testersatz abgefangen und geprüft. Das Öffnen eines echten Browserfensters wurde damit nicht getestet. Es wurden keine API-Aufrufe und keine Abrufe eingegebener Link-URLs vorgenommen. Demo-Ausgaben wurden ausschließlich im temporären Testordner erzeugt und nicht als echte Artikel bewertet.

Statische Prüfung von `app.spec`: `console=False`; eingebundene Daten sind ausschließlich `templates` und `site_data.json`. Das bestätigt die Build-Konfiguration, nicht das Verhalten einer Windows-EXE.

## Zugang und Änderungen

Keine lokale `.env` wurde bereitgestellt. `.env.example` enthält den vorgesehenen Platzhalter. Kein echter Schlüssel wurde übernommen oder verwendet. Der konfigurierte Modellname wurde nicht geändert.

Die Empfängeranleitung kennzeichnet die Lieferung als vorläufig und erläutert die lokale Konfiguration. Build-Abschlussmeldung und README fordern nicht mehr dazu auf, eine lokal mit Schlüssel konfigurierte `.env` erneut zu verpacken. Anwendung, Artikelgenerierung und bestehende Architektur wurden nicht geändert.

## Offen vor Fertigstellung

1. Build auf Windows mit Python >=3.10.
2. EXE auf Windows einschließlich Pfad mit Leerzeichen, tatsächlichem automatischem Browserstart und fehlender Terminal-Konsole prüfen.
3. Demo, beide Downloads, Programm beenden und Neustart mit dieser EXE prüfen.
4. Nach verfügbarem Guthaben und lokal bereitgestelltem Schlüssel zwei echte Artikel generieren und jeweils 720–880 Wörter bei Ziel 800, alle Links, Lesbarkeit und Variation prüfen. Das vom Nutzer berichtete Guthabenproblem wurde hier nicht erneut live abgefragt; kein Live-Test gilt als bestanden.
5. Empfänger-ZIP mit ausschließlich `TextGenerator.exe`, `.env` mit Platzhalter und `ANLEITUNG.txt` prüfen.

## ZIP-Status

Eine fertige Empfänger-ZIP existiert noch nicht. Der vom vorhandenen Windows-Build vorgesehene absolute Zielpfad lautet:

`/Users/abdulkaderalamin/Documents/Code/pohlmann-textgenerator/release/TextGenerator_Windows.zip`

Dieser Pfad ist nur das geplante Ausgabeziel; er bezeichnet keine erzeugte oder getestete Lieferung. Nach Übertragung auf einen Windows-Rechner ergibt sich dessen tatsächlicher absoluter ZIP-Pfad aus dem dortigen Projektordner.

## Ergänzung: manuelle GitHub-Actions-Vorbereitung

Auf ausdrücklichen Nutzerauftrag wurde `.github/workflows/windows-build.yml` ergänzt: ausschließlich `workflow_dispatch`, `windows-latest`, Python 3.12 x64, privates Repository erforderlich, `contents: read`, keine API-Secrets. Checkout, Python-Setup und Artifact-Upload verwenden v7; die verwendeten Versionen und Eingaben wurden anhand der offiziellen GitHub-Repositories und `action.yml`-Dateien geprüft. Quellen und genaue CLI-Befehle stehen in `GITHUB_ACTIONS.md`.

`build_windows.py` nutzt weiterhin die vorhandenen Installations-, Test- und PyInstaller-Schritte mit `check=True`. Die Verpackung schreibt jetzt eine feste `.env` mit Platzhalter und unverändertem Modell `gpt-4`, ohne lokale Konfigurationsdateien zu kopieren. ZIP enthält ausschließlich die drei vorgesehenen Dateien im Wurzelverzeichnis. Vor Abschluss werden Dateiliste, Integrität, exakte Platzhalter-Konfiguration und MZ-Dateikopf der EXE geprüft; die Header-Prüfung ersetzt keinen Laufzeittest.

Neun Offline-Tests bestanden auf macOS: die ursprünglichen sechs und drei neue Tests für Verpackung, Zurückweisung zusätzlicher Dateien/falscher Konfiguration/nicht als EXE erkennbarer Dateien und Abbruch vor Verpackung bei simuliertem Installations-, Test- oder Buildfehler. Die EXE in den Verpackungstests ist ausdrücklich nur eine Testdatei mit MZ-Header.

YAML wurde lokal geparst und auf manuellen Trigger, Windows-Runner, Python-Version, Action-Versionen, begrenzte Upload-Datei und unverfälschte Fehlerweitergabe geprüft. `.gitignore` wurde mit Git in einem temporären Repository überprüft: 20 Pfade für Konfiguration, Schlüssel, Python-Umgebungen und erzeugte Dateien ausgeschlossen; sechs benötigte Projektpfade inklusive `.env.example` und Workflow bleiben einschließbar. In den Projektdateien wurden keine typischen OpenAI-Schlüsselwerte gefunden; die Vorlage enthält weiterhin den vorgesehenen Platzhalter.

Der Projektordner ist noch kein Git-Repository und hat keinen Remote. `gh` war hier nicht installiert. Es wurde kein Repository erstellt, kein Commit oder Push ausgeführt und kein GitHub-Workflow gestartet. Die Empfänger-ZIP ist weiterhin nicht vorhanden. Nach Nutzerbestätigung des Pushs erfolgen CI-Lauf, Ergebnisprüfung und Download über CLI; Windows-UI-Test und echte Artikel nach verfügbarem Guthaben bleiben eigenständige offene Prüfungen.

Nachfolgende Nutzerfreigabe: Ein öffentliches Repository auf `abdulkader000` ist ausdrücklich erlaubt. Der bisherige Privat-Repository-Check wurde deshalb entfernt; Geheimnis-Ausschlüsse und feste Platzhalter-Konfiguration bleiben bestehen. Die Anleitung enthält aktualisierte Public-Repository-Befehle und die Anmeldung, die der Nutzer selbst im Browser durchführen kann. `gh` ist inzwischen als Version 2.102.0 installiert; der geprüfte Anmeldestatus war noch nicht angemeldet. Weiterhin kein Repository, Push oder CI-Lauf durch Codex.
