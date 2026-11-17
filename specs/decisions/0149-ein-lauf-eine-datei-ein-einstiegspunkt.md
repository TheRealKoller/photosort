# 0149 - Ein Lauf, eine Datei; ein Paket, ein Einstiegspunkt

**Status:** Accepted
**Datum:** 2026-11-17
**Bezug:** Issue [#647](https://github.com/TheRealKoller/photosort/issues/647), Story „Jeder Lauf hat seine eigene Datei"

## Kontext

`photosort.worker` und `photosort.api.photos` sind je eine Datei mit rund 5.000 bzw. 3.400
Zeilen. 39 Module importieren `worker`, acht `api.photos`; dazu kommen 54 Monkeypatch-Ziele
und sieben strukturelle Wächter, die beide Dateien als Quelltext lesen. Eine Aufteilung in
Untermodule berührt deshalb drei Dinge auf einmal: den Importpfad der Aufrufer, das Ziel jedes
Patches und den Dateischlüssel jedes Wächters. Ohne Regel für diese drei Stellen entsteht beim
ersten Untermodul eine zweite Konvention.

## Entscheidung

### 1. Paket mit genau einem Einstiegspunkt
`worker.py` und `api/photos.py` werden zu Paketen. `worker/__init__.py` und
`api/photos/__init__.py` tragen die heutige Namensmenge in einem ausdrücklichen `__all__`.
Niemand außerhalb des Pakets importiert ein Untermodul; die Untermodule sind privat (`_runs`)
oder thematisch benannt, nie ein zweiter Einstiegspunkt.

### 2. Gemeinsame Schicht, qualifiziert angesprochen
Geteiltes Laufverhalten (Phase setzen, Abbruch prüfen, Fehlschlag melden, Lauf beenden,
Cloud-Kosten/-fehler verbuchen, Logger, Zeitquelle) liegt in `worker/_runs.py`. Angesprochen
wird sie ausschließlich qualifiziert: `import photosort.worker._runs as runs` und
`runs._set_phase(...)`. Kein `from … import` für geteilte Namen an einer **Aufrufstelle**, keine
relativen Importe. `worker/__init__.py` bindet die Namen für die Außenseite (Punkt 1) und ruft
selbst nichts Geteiltes über diese Bindung auf; ein Patch auf dem Paket erreicht deshalb keinen
Aufrufer.

### 3. Patch-Ziel ist die Nachschlagestelle
Ein Monkeypatch trifft das Modul, in dem der Name zur Laufzeit nachgeschlagen wird — nicht den
Einstiegspunkt. Punkt 2 macht das für die gemeinsame Schicht zu genau einer Stelle: ein Patch
auf `_runs` erreicht jeden Aufrufer.

### 4. Fester Loggername
Alle Module des Worker-Pakets loggen auf `photosort.worker`. Der Logger wird in `_runs.py` mit
diesem Namen erzeugt; Untermodule verwenden `runs.logger`, erzeugen keinen eigenen.

### 5. Lauf-Dateien ohne Ringe, eine Verkettung
Je Lauf genau eine Datei; keine Lauf-Datei importiert eine andere. Die einzige Ausnahme ist die
Verkettung des Klassifizierungs-Jobs (`classification.py` → Kriterien-Lauf,
Remote-Kategorien, Eye-Phase) und steht an genau einer Stelle.

### 6. Modellsatz als einziger Einhängepunkt
Die Modelle eines Kriterien-Laufs werden in einem `ModelSet` gebündelt und den Phasen
übergeben. Jede Phase baut nur ihre eigenen Modelle. Ein zusätzliches Modell ist ein Feld plus
seine Verwendung in seiner Phase; keine Phasensignatur ändert sich.

### 7. Phaseneinheiten sind private Module
Die Phasen der Kriterien-Bewertung liegen als benannte Einheiten in `worker/_criterion/`. Der
Lauf selbst (Reihenfolge, Phasenwechsel, Abbruch-/Fehlschlag-Semantik) bleibt im
Orchestrierungsmodul des Laufs.

### 8. Endpunktgruppen an einem Router ohne `dependencies`
Die Themengruppen der Foto-Endpunkte sind je ein `APIRouter()` ohne routerweite
`dependencies`; jeder Endpunkt trägt seine Absicherung ausgeschrieben. Ein Aggregat-Router
unter `photos/__init__.py` bindet sie in fester Reihenfolge ein.

### 9. Wächter lesen paketweit
Strukturelle Wächter, die etwas **verbieten**, lesen den Quelltext des ganzen Pakets; Wächter,
die etwas **erlauben** (Schreibstellen, erlaubte Leser), nennen die neue Datei und den
Funktionsnamen. Kein Wächter wird weiter gefasst als heute.

## Begründung

Punkt 1 hält die Zusage „öffentliche Schnittstelle wächst nicht" prüfbar: Aufrufer und Tests
sehen weiter nur `photosort.worker` bzw. `photosort.api.photos`. Punkt 3 macht die
54 Patch-Ziele zu einer ableitbaren Regel statt zu 54 Einzelfallentscheidungen. Punkt 5
verhindert, dass die Lauf-Dateien untereinander ein zweites Geflecht bilden, das die Aufteilung
nur verschiebt. Punkt 6 ist die einzige Stelle, an der die Story „ein zusätzliches Modell an
genau einer Stelle eingehängt" prüfbar einlöst. Punkt 9 schließt die Lücke, die eine Aufteilung
sonst öffnet: ein Verbot, das nur eine Datei liest, verliert mit dem Umzug seinen Griff.

## Konsequenzen

- Tests, die einen Namen aus dem Paket lesen, bleiben unverändert; Tests, die einen Namen
  patchen, nennen das Untermodul. Wo ein Test die Ablage als Dateischlüssel führt, folgt der
  Schlüssel der neuen Datei, die Aussage bleibt wortgleich.
- Neue Lauf-Dateien und Phasen-Module sind erst erreichbar, wenn `worker/__init__.py` sie
  einbindet; die Importkette des Pakets ist damit die einzige Stelle, die neue Untermodule
  sichtbar macht.
- Ein Wächter, der heute `worker.py` liest, muss auf die Menge der Paketdateien umgestellt
  werden — einmalig, mit unverändertem Prädikat und unveränderten Zählungen.
- Lebende Doku nennt die neuen Ablagen; abgeschlossene Specs, ADRs und CHANGELOG bleiben, wie
  sie sind.
