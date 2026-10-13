# Pohlmann Textgenerator — Windows-Testversion

Vorhandenes Python/Flask-Tool für deutsche Artikelentwürfe mit anklickbaren Links. Diese Version ist zum Testen bestimmt, nicht zur Lieferung oder automatischen Veröffentlichung freigegeben. Vollständige Linkabdeckung ist keine Inhaltsfreigabe; die Wortzahl ist ungefähr. Sprache und fachliche Aussagen müssen vor Veröffentlichung geprüft werden.

## Verhalten

- Standardziel ungefähr 800 Wörter; weitere Schreibziele 200–2000. Die Artikellänge verhindert weder Speichern noch Download. Unter 87,5 % des Ziels erscheint ein Hinweis (bei Ziel 800: unter 700), ohne Text zu kürzen.
- Frei editierbare Linkliste; URLs werden nicht zum Generieren abgerufen.
- Explizite grammatische Varianten mit festen URL-Zuordnungen; strikte Wort- und Bindestrichgrenzen sowie unabhängige Abdeckung überlappender Begriffe. In den ausdrücklich erfassten Zusammensetzungen `eIDAS-Verordnung`, `Malware-Anhang` und `TLS-geschützte` wird nur der Grundbegriff verlinkt; der sichtbare Text bleibt erhalten. Diese Erkennung erweitert nicht die Schreibformen im Modellauftrag.
- Themenplanung passend zu den tatsächlichen Begriffen. Nur fehlende Links veranlassen gezielte Absatzkorrekturen; andere Absätze und vorhandene Links bleiben geschützt. Die Wortzahl ist kein Auswahl- oder Verbesserungsmaß für eine Korrektur. Bestehende Links mit ihren zulässigen Formen werden je Passage im Korrekturauftrag genannt.
- Bei vollständigen Links sofort speichern, ohne Längen-Korrektur. Normaler Lauf: höchstens drei Anfragen insgesamt, bei API-Fehler sofort stoppen, kein Modell-Fallback.
- Bleiben Links offen, erscheinen ihre Namen und die beste Fassung wird als **Unvollständiger Entwurf** herunterladbar. Nur vorhandene Begriffe werden verlinkt, keine angehängte Linkliste oder falsche Vollständigkeitsmeldung.
- Vollständige Dateinamen beginnen mit ENTWURF_, unvollständige mit UNVOLLSTAENDIGER_ENTWURF_. HTML enthält Status und Prüfhinweise außerhalb des Artikelkörpers. Vollständige TXT bleibt reiner Artikeltext; unvollständige TXT erhält einen Statusheader vor dem unveränderten Text.

Die Vorlage korrigiert den dokumentierten Schreibfehler IT-Sicherheitszahler zu IT-Sicherheitszahlen; die zugehörige URL bleibt unverändert.

Die Überarbeitung der zweiten Vorlage ist in [NORBERT_TEMPLATE_REVIEW.md](NORBERT_TEMPLATE_REVIEW.md) dokumentiert: geprüfte Originalquellen, korrigierter KRITIS-Link, eigene Themenplanung nur für diese Vorlage und begrenzte grammatische Varianten. Ein begrenzter echter Test der Standardliste mit Ziel 700 erreichte nach zwei Anfragen 718 Wörter und 38/38 Links; die Inhaltsprüfung fand weiterhin Mängel. Das ist keine Inhaltsfreigabe und kein Windows-Nachweis. Die zweite Vorlage muss in der neuen Windows-Testversion erneut geprüft werden. Vorläufig ist die vom Nutzer erfolgreich getestete erste Vorlage mit Ziel 800 der empfohlene Weg.

Fehlgeschlagene Generierungen zeigen die Namen der fehlenden Linktexte und speichern die beste abgelehnte Fassung samt tatsächlichen Eingaben, Modellen und Korrekturgründen lokal unter diagnostics/. Keine Schlüssel oder .env; SDK-Fehlertexte werden nicht gespeichert. Diagnosen bleiben außerhalb von Git, EXE und ZIP. Zusätzlich bleibt die unvollständige Fassung über die normalen Downloadrouten zugänglich.

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

Der Nutzer hat die bisherige EXE auf Windows geprüft: automatischer Browserstart ohne Konsole, Beenden und Neustart sowie Speichern im Ausgabeordner funktionieren. Drei Links wurden erfolgreich generiert und im HTML geprüft. Die vollständige Vorlage wurde nach drei Versuchen mit 882 Wörtern, ohne fehlende Linktexte oder Formatprobleme, wegen der alten Obergrenze 880 abgelehnt. Die aktuelle Version verwendet keine Längengrenze für die Annahme; die vollständige Vorlage muss mit der neuen EXE erneut getestet werden. Lokale Mock-Tests sind kein Nachweis für die Qualität neuer Artikel; keine Weitergabe als freigegebene Version.
