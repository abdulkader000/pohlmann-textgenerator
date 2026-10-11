# Windows-Testversion — noch nicht durchgeführt

Ein erfolgreicher Build ist keine Laufzeit- oder Inhaltsfreigabe. Ergebnisse sind Entwürfe und müssen vor Veröffentlichung von einer Person geprüft werden. Echte Generierung kostet API-Guthaben und erfolgt erst nach ausdrücklicher Freigabe des Testumfangs.

- [ ] **Start und Browser:** ZIP vollständig in einen beschreibbaren Ordner mit Leerzeichen entpacken, EXE per Doppelklick starten. Browser öffnet automatisch; im Normalbetrieb keine Terminalkonsole. `.env` liegt neben der EXE, lokal eingerichteter Schlüssel, sichtbares Modell `gpt-4.1`. Alte `.env` und geerbtes `OPENAI_MODEL=gpt-4` ausschließen. Auch Demo starten.
- [ ] **Generierung und Korrektur:** Vollständige Vorlage sowie drei Links, Ziel 800, akzeptiert 720–880. Falls eine Korrektur nötig ist: passende Absätze werden bearbeitet, Unterlänge verteilt erweitert, übrige Absätze und vorhandene Links bleiben erhalten. Höchstens drei Anfragen pro normaler Generierung; bei API-Fehler kein Modellwechsel. Bei Ablehnung keine erfolgreiche Ergebnisdatei; Eingaben bleiben erhalten. Sprache, Fakten und Zusicherungen gesondert prüfen.
- [ ] **Links:** Alle verlangten Begriffe bzw. ausdrücklich erlaubten Formen führen zur eingegebenen URL; Überlappungen und Bindestrichgrenzen prüfen. Keine künstliche Linkliste. Die Anwendung ruft die Linkziele nicht zum Generieren ab.
- [ ] **Downloads:** HTML und TXT herunterladen und öffnen. Beide enthalten denselben Artikelkörper; HTML enthält korrekte Links und den Entwurfshinweis. Dateinamen beginnen mit `ENTWURF_` (Demo: `DEMO_`). TXT bleibt reiner Artikeltext; der Hinweis zählt nicht zur Wortzahl.
- [ ] **Beenden und Neustart:** „Programm beenden“ beendet den lokalen Prozess. Anschließend erneut per Doppelklick starten und beide Downloads erneut prüfen. Nach Änderungen an `.env` neu starten; nur das Browserfenster zu schließen beendet die Anwendung nicht.

Keine der Checkboxen wurde durch die lokalen Mock-Tests als Windows-Test bestanden markiert. Die letzte echte Drei-Link-Generierung ergab 715 Wörter und war nicht akzeptiert; die Offline-Erweiterung ist kein neuer Live-Nachweis.
