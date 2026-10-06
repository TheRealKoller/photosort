# 0135 - Ein einzelner Ortsausreißer trennt nicht, und ein unbestätigter Sehenswürdigkeitsname entfällt

**Status:** Accepted
**Datum:** 2026-10-06
**Teilweise abgelöst:** ADR
[`0123`](./0123-der-sehenswuerdigkeitsname-wird-lokal-verortet-und-am-event-geprueft.md) Punkt 2
Zustand (1) („der Name wird behandelt wie vor dieser Entscheidung"), Punkt 3 vollständig und Punkt 4
der Satz „Hat das Event keine einzige gemessene Zelle, findet keine Prüfung statt und der Name
bleibt". Punkt 1, die Dreiwertigkeit der **Ablage** aus Punkt 2 und Punkt 5 gelten unverändert.
ADR 0118 und 0119 gelten vollständig weiter.
**Bezug:** Issue #584

## Kontext

Zwei Befunde aus Projekt 7:

- **„Tower of London" über Fotos in Schottland.** `_landmark_name_is_plausible` lässt einen Namen
  in drei von fünf Zweigen ungeprüft stehen: ohne Auskunft, ohne gemessene Zelle, ohne
  Auskunftszeile zum Namen. Der Worker übergibt nie `None`; wirksam sind also die beiden letzten
  — der zweite Auszug fehlt auf dem Volume (dann entsteht nie eine Zeile), oder das Event trägt
  nur übernommene Koordinaten. Daniel hat entschieden: Was sich nicht über den Aufnahmeort
  bestätigen lässt, entfällt.
- **Ein Foto zerlegt ein Erlebnis in drei Events** (01.06.2022, 18:04 / 18:06 / 18:07–19:33).
  Ein Namenswechsel ist seit ADR 0118 **kein** Trennsignal mehr; die Ortsnamen sind Folge, nicht
  Ursache der Zerlegung. Bei Abständen von ein bis zwei Minuten kann nur `schritt` bzw.
  `ausdehnung` getrennt haben: Ein Foto liegt weit neben den übrigen. Stufe 3 heilt das nicht —
  die Ausdehnungsgrenze für das Zusammenlegen (`MERGE_EXTENT_MAX_METERS`) sperrt beide Kanten
  des Einzelfotos, und das Foto davor bleibt ebenfalls allein.

## Entscheidung

### 1. Ein Ortsausreißer ist eine eigene Vorstufe, kein weiteres Signal

Vor dem Durchlauf über die Signale bestimmt die neue reine Funktion `events.py::location_excursions`
über die sortierte Folge die Fotos, deren Ort als **Ausreißer** gilt — Muster
`motif_change_starts` (ADR 0109): eine Segmentierung über die ganze Folge mit
Bestätigungsfenster, die das vorwärts entscheidende `BoundarySignal`-Protokoll nicht ausdrücken
kann.

**Ausreißer** ist eine zusammenhängende Folge von weniger als
`LOCATION_CHANGE_CONFIRMING_PHOTOS` (= 2, unkalibriert, Testaussage nur `>= 2`) Fotos mit
**gemessener** Koordinate (`measured_position`), deren jede weiter als `EVENT_STEP_MAX_METERS` vom
Bezug liegt, wobei das nächste Foto mit gemessener Koordinate danach **wieder** innerhalb von
`EVENT_STEP_MAX_METERS` am Bezug liegt. Bezug ist die letzte gemessene Koordinate vor der Folge,
die selbst kein Ausreißer ist. Fotos ohne gemessene Koordinate unterbrechen die Folge nicht und
zählen **nie** mit — weder für den Ausreißer noch für die Bestätigung. Sonst bestätigte ein Foto,
das über `infer_locations` die Koordinate des Ausreißers übernommen hat, den Wechsel, und die
Regel griffe gerade im häufigen Fall nicht.

Zum Ausreißer gehören außerdem alle Fotos **ohne** gemessene Koordinate zwischen dem Bezugsfoto
und dem Rückkehrfoto, deren wirksame (übernommene) Koordinate weiter als
`EVENT_STEP_MAX_METERS` vom Bezug liegt. Sie haben ihren Ort vom Ausreißer und verlieren ihn mit
ihm.

Ein Ortswechsel **ohne Rückkehr** oder mit mindestens zwei Fotos am neuen Ort ist bestätigt und
trennt wie bisher. Die Zeitlücke bleibt unberührt: Liegt zwischen Bezug und Rückkehr eine Grenze
von `zeitluecke`/`dauer`, trennt diese ohnehin.

### 2. Ein Ausreißer verliert seinen Ort für die ganze Bildung, nicht seine Mitgliedschaft

Für den Durchlauf, Stufe 3 und `_built` geht jedes Foto des Ausreißers als Kandidat **ohne** Ort ein
(`location`, `gps_lat`, `gps_lon` auf `None`, an genau einer Stelle in `explain_events`). Er
gehört damit zum umgebenden Event, verschiebt weder Schritt noch Ausdehnung, speist keine Zelle,
keinen Ortsnamen und keine Plausibilitätsprüfung. Persistiert wird an den Fotos nichts anders.

Der Ort nur aus den Signalen zu nehmen, ihn aber in `_cells_of` zu lassen, ist verworfen: Das
Event trüge zwei Zellen verschiedener Orte, `locality_of_event` fände keinen eindeutigen Ort, und
das wieder vereinte Erlebnis hieße nur nach der Zeit.

### 3. Die Ortsplausibilität ist fail-closed

`_landmark_name_is_plausible` ist nur noch wahr, wenn eine Auskunftszeile mit Punkten vorliegt
und mindestens ein Punkt einer gemessenen Zelle näher liegt als
`LANDMARK_PLAUSIBILITY_RADIUS_METERS`. Keine Auskunft, keine gemessene Zelle, keine Zeile und
leere Punktmenge ergeben je **falsch**. Die Ablage in `landmark_place_lookups` bleibt dreiwertig
(eine fehlende Zeile wird beim nächsten Lauf mit vorhandenem Auszug nachgeschlagen); nur ihre
Auswertung am Event fällt für „nie nachgeschlagen" jetzt wie „ohne Fund" aus.

## Konsequenzen

- **Fehlt der Sehenswürdigkeitsauszug, trägt kein Event eines Laufs einen Sehenswürdigkeitsnamen**
  — der in ADR 0123 Punkt 3 ausgeschlossene Betriebszustand ist jetzt gewollt. Die Events heißen
  nach Ort bzw. Zeit, nie gar nicht (ADR 0120 Punkt 2). Dasselbe gilt im Request-Pfad
  (`rebuild_run_grouping`, keine Fabrik) für jeden Namen, der noch keine Zeile hat.
- **Events nur mit übernommenen Koordinaten verlieren ihren Namen.** Das ist die wörtliche
  Produktentscheidung, kein Nebeneffekt.
- **Ein kurzer echter Abstecher mit einem einzigen Foto wird nicht mehr abgetrennt** und gibt
  dem Event weder Zelle noch Namen. Das ist die Kehrseite der Zusage „ein abweichendes Foto
  trennt nie", dieselbe wie beim Motivwechsel.
- **Keine Migration, kein Backfill, kein Cache.** Gliederung und Namen entstehen bei jedem Lauf
  und jeder Neuberechnung aus den persistierten Werten neu; Trennursachen werden nicht abgelegt
  (ADR 0117 Punkt 4).
- Das Sicherheitskonzept (Ankerzeile zum zweiten Auszug, Fortschreibung Spec 0529 S4),
  `docs/setup.md` und `docs/architecture.md` beschreiben fail-open und ziehen im selben Pull
  Request nach.
