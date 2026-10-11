# Pohlmann Textgenerator — Windows-Testversion

Vorhandenes Python/Flask-Tool für deutsche Artikelentwürfe mit anklickbaren Links. Diese Version ist zum Testen bestimmt, nicht zur Lieferung oder automatischen Veröffentlichung freigegeben. Technischer Erfolg bei Wortzahl und Links ist keine Inhaltsfreigabe. Sprache und fachliche Aussagen müssen vor Veröffentlichung geprüft werden.

## Verhalten

- Standardziel 800 Wörter, technische Annahme 720–880; weitere Ziele 200–2000.
- Frei editierbare Linkliste; URLs werden nicht zum Generieren abgerufen.
- Explizite grammatische Varianten mit festen URL-Zuordnungen; strikte Wort- und Bindestrichgrenzen.
- Themenplanung passend zu den tatsächlichen Begriffen. Korrekturen bearbeiten passende Absätze; Unterlänge wird auf mehrere Absätze verteilt. Andere Absätze und vorhandene Links bleiben geschützt. Eine schlechtere Korrektur ersetzt nicht die beste Fassung.
- Normaler Lauf: höchstens drei Anfragen insgesamt, ohne Modell-Fallback bei API-Fehlern. Ein nicht passender Text wird nicht als erfolgreiche Ergebnisdatei gespeichert.
- Oberfläche und HTML nennen das Ergebnis Artikelentwurf. Dateinamen beginnen mit ENTWURF_; TXT enthält nur den Artikelkörper.

Die Vorlage korrigiert den dokumentierten Schreibfehler IT-Sicherheitszahler zu IT-Sicherheitszahlen; die zugehörige URL bleibt unverändert.

## Konfiguration

Die Testversion verwendet OPENAI_MODEL=gpt-4.1. Die Oberfläche zeigt das konfigurierte Modell. Eine alte .env oder eine geerbte Prozessvariable OPENAI_MODEL=gpt-4 kann weiterhin gpt-4 wählen; bereits gesetzte Prozessvariablen haben Vorrang vor .env. Nach Änderungen neu starten.

Der Schlüssel bleibt ausschließlich lokal in .env neben app.py bzw. der entpackten EXE. Nur einen lokal bereitgestellten Schlüssel verwenden, keine alten Archivschlüssel. .env und Schlüssel werden nicht in Git oder die EXE aufgenommen. .env.example enthält ausschließlich einen Platzhalter.

## Lokaler Offline-Test

Python 3.10 oder neuer verwenden. Abhängigkeiten aus requirements.txt installieren, dann:

```text
python -m unittest discover -s tests -v
python app.py --demo
```

Demo benötigt kein API-Guthaben und ist kein Qualitätsnachweis. Die versionierten Tests verwenden synthetische Daten und Mock-Antworten. Gespeicherte reale Antworten, Experimente und lokale Auswertungen bleiben außerhalb des veröffentlichten Quellcodes und der ZIP.

## Windows-Build

[GitHub Actions](GITHUB_ACTIONS.md) läuft manuell auf windows-latest mit Python 3.12. build_windows.py führt die Offline-Tests aus, baut die EXE ohne Terminalkonsole und validiert die ZIP. Jeder Fehler stoppt den Build. Der erfolgreiche Build ist kein Nachweis für den tatsächlichen EXE-Start auf Windows.

Die ZIP enthält genau:

```text
TextGenerator.exe
.env
ANLEITUNG.txt
```

Die feste .env enthält YOUR_API_KEY_HERE und OPENAI_MODEL=gpt-4.1. Der Build kopiert niemals die echte lokale .env oder eine bearbeitete .env.example. Keine OpenAI Secrets oder Generierungsanfragen in GitHub Actions.

## Windows-Prüfung

[WINDOWS_TEST_CHECKLIST.md](WINDOWS_TEST_CHECKLIST.md): Start aus einem Ordner mit Leerzeichen, automatischer Browserstart, Generierung und gegebenenfalls Korrektur, Links, HTML/TXT-Downloads, Beenden und Neustart. Auch Demo prüfen. Beim echten Test API-Kosten und Testumfang vorher festlegen. Das Browserfenster allein zu schließen beendet den Prozess nicht.

Die jüngste echte Drei-Link-Generierung hatte 715 Wörter und war nicht akzeptiert. Eine lokale Mock-Erweiterung prüft nur die Mechanik. Die Qualität neuer Artikel und der Windows-Lauf bleiben zu prüfen; keine Weitergabe als freigegebene Version.
