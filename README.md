# Indikationscodes Onkologie & Hämatologie

Arbeitshilfe für Chemotherapie-Verordnungen: alle onkologischen und hämatologischen
Arzneimittel der BAG-Spezialitätenliste (SL), die einen **Indikationscode** verlangen,
mit Code und Kurztext der Indikation.

Seit 1. Juli 2026 muss der Indikationscode bei Arzneimitteln mit Preismodell auf jeder
Verordnung und Rechnung übermittelt werden; ab 1. Januar 2027 dürfen Versicherer Rechnungen
ohne Code zurückweisen.

**Webseite:** siehe GitHub Pages dieses Repositorys (Suche, Excel-Download, Änderungen).

## Woher kommen die Daten?

- Quelle ist der öffentliche FHIR-Export der SL des BAG (ePL, Lizenz CC0).
- Der **Indikationscode** wird unverändert aus den BAG-Daten übernommen – keine KI, keine
  Rekonstruktion.
- Der **Kurztext** ist eine gekürzte Fassung des Limitationstexts: entweder automatisch
  (Titel des Limitationstexts) oder mit KI erstellt. Er ist erst nach fachlicher Prüfung
  verlässlich. Der vollständige BAG-Text ist auf der Webseite bei jedem Code aufklappbar.
- Massgebend bleibt immer die Spezialitätenliste unter <https://sl.bag.admin.ch/sl>.

## Welche Präparate gelten als Onkologie/Hämatologie?

Auswahl über den ATC-Code, festgelegt in `scripts/config.py` (z.B. L01 Antineoplastika,
L02 endokrine Tumortherapie, B02/B03 Hämatologie). Die Liste kann vom Onkologie-Team
angepasst werden; alle übrigen Präparate mit Code bleiben auf der Webseite unter
„Alle Präparate“ auffindbar.

## Aktualisierung

Eine GitHub Action (`.github/workflows/update.yml`) lädt am 2. jedes Monats die aktuelle SL,
erstellt Liste, Excel und Änderungsübersicht neu und veröffentlicht sie. Manuell auslösbar
unter *Actions → Monatliche Aktualisierung → Run workflow*.

Optional: Mit einem Repository-Secret `ANTHROPIC_API_KEY` werden Kurztexte für neue Codes
mit Claude erstellt (Kosten: wenige Rappen pro Monat). Ohne Schlüssel wird automatisch gekürzt.

## Kurztexte als geprüft markieren

In `data/shorttexts.json` beim betreffenden Eintrag `"status": "geprüft"` setzen (und den
Kurztext bei Bedarf anpassen). Geprüfte Texte bleiben erhalten, solange das BAG den
Limitationstext nicht ändert, und erscheinen auf der Webseite mit ✓.

## Lokal ausführen

```
pip install openpyxl
python scripts/build.py                    # lädt die SL (ca. 90 MB) und baut alles neu
python scripts/build.py --input sl.ndjson  # mit bereits heruntergeladener Datei
```
