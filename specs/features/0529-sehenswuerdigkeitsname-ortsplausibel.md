# 0529 - Sehenswürdigkeit benennt ein Event nur bei passendem Aufnahmeort

**Status:** Implemented ([PR #530](https://github.com/TheRealKoller/photosort/pull/530))
**Erstellt:** 2026-09-24
**Bezug:** [Issue #529](https://github.com/TheRealKoller/photosort/issues/529)

## Ziel

Automatisch vergebene Eventnamen tragen heute einen Sehenswürdigkeitsnamen, den ein
Cloud-Bilderkennungsmodell aus den Fotos ableitet. Dieser Name kann geografisch völlig falsch sein:
Auf einer Schottlandreise hieß ein Cluster „Tower of London", obwohl die Aufnahmen weit entfernt von
London entstanden. Der Fehler steht am prominentesten Textelement eines Clusters und beschädigt das
Vertrauen in alle automatisch vergebenen Namen — der Nutzer kann nicht erkennen, welche stimmen.

Der Grundsatz „ein fehlender Name ist besser als ein falscher" wird heute nur gegen die Unsicherheit
des Modells durchgesetzt (Konfidenzgrenze, Mindestanteil), nicht gegen geografische Falschheit.
Diese Spec schließt die Lücke: Ein Sehenswürdigkeitsname erscheint nur noch, wenn er zum Aufnahmeort
passt.

## User Story

Als Nutzer, der seine Reisefotos durchsieht, möchte ich, dass ein Sehenswürdigkeitsname nur dann als
Eventname erscheint, wenn diese Sehenswürdigkeit auch tatsächlich am Aufnahmeort der Fotos liegt,
damit ich den Namen eines Clusters lesen kann, ohne jedes Mal selbst prüfen zu müssen, ob er
überhaupt zur Reise passt.

## Akzeptanzkriterien

- [ ] **Bestätigt heißt: ein Fundort, eine gemessene Zelle, unter der Grenze.** Liegt mindestens ein
      Fundort des gefalteten Namens **näher als** `LANDMARK_PLAUSIBILITY_RADIUS_METERS` an mindestens
      einer gemessenen Zelle des Events, benennt der Name das Event unverändert (`landmark_name`
      gesetzt, `place_kind == "landmark"`). Die Richtung ist strikt: ein Fundort **genau auf** der
      Grenze bestätigt **nicht**.
- [ ] **Fundorte vorhanden, keiner im Umkreis: der Name fällt weg, der Ort trägt den Cluster.** Liegt
      eine Auskunft mit Fundorten vor und liegt **keiner** davon unter der Grenze an **irgendeiner**
      gemessenen Zelle, ist `landmark_name is None`, und `place_kind`/`place_lat`/`place_lon`
      entstehen allein aus den gemessenen Zellen. Nachzuweisen an einem Namen mit **mehreren**
      Fundorten (Homonym), von denen der entfernte zuerst geprüft würde.
- [ ] **Nachgeschlagen ohne Fund verwirft.** Eine Zeile mit **leerer** Punktmenge führt zum selben
      Ausgang wie das vorige Kriterium, ohne dass eine Entfernung gerechnet wird.
- [ ] **Ohne gemessene Zelle findet keine Prüfung statt, und das schlägt das vorige Kriterium.** Hat
      das Event keine einzige gemessene Zelle (`_cells_of` leer), bleibt der Name **auch dann**, wenn
      eine Zeile mit leerer Punktmenge vorliegt. Der Fall „keine Zelle **und** leere Punktmenge" ist
      ein eigener Pflichtfall.
- [ ] **Die drei Zustände der Auskunft fallen nicht zusammen.** Bei identischer Kandidatenlage müssen
      sich drei Ausgänge unterscheiden lassen: **keine Auskunft** (kein Eintrag zum Namen bzw. `None`
      als Ganzes) → Name bleibt; **leere Punktmenge** → Name fällt; **Punkte im Umkreis** → Name
      bleibt. Zustand 1 und 3 sind am Ergebnis gleich und laufen trotzdem nicht über denselben Zweig
      — der Unterschied wird an der Abwesenheit des Eintrags festgemacht, nicht am Event.
- [ ] **Nach dem Verwerfen ist das Event von einem nie benannten ununterscheidbar.** Ein Event,
      dessen Name an der Ortsplausibilität scheitert, trägt exakt dieselben Werte in `place_kind`,
      `place_lat`, `place_lon`, `place_cells`, `photo_ids`, `started_at`, `ended_at` wie dasselbe
      Event mit von vornherein namenlosen Kandidaten. Insbesondere entsteht **nie** ein Cluster ohne
      jede Benennung, wo vorher einer mit Ortsbezug stand.
- [ ] **Die Prüfung sitzt hinter den bestehenden Regeln und rückt nichts nach.** Ein Name, der
      bereits an `LANDMARK_MIN_SHARE` oder `LANDMARK_CONFIDENCE_THRESHOLD` scheitert, erreicht die
      Ortsprüfung nicht. Scheitert der Mehrheitsname an der Ortsplausibilität, rückt der zweitbeste
      Name **nicht** nach — nachzuweisen an einer Lage, in der ein zweiter Name vorhanden ist, dessen
      Fundorte im Umkreis lägen.
- [ ] **Nachvollziehbar ist der Verwurf über die abgelegte Zeile, sonst nirgends.** Zu einem
      verworfenen Namen existiert eine Zeile in `landmark_place_lookups` mit gefaltetem Namen,
      Fundortmenge und Zeitpunkt, projektgebunden. Gegenanzeige: **kein** Logeintrag des Laufs trägt
      den Namen, eine Koordinate oder eine Entfernung (geprüft über `getMessage()` **und**
      `record.args`), und **keine** API-Antwort und **kein** Feld an `events` kommt hinzu.
- [ ] **Ohne Auszug verwirft nichts.** Fehlt der Sehenswürdigkeits-Auszug oder weicht er von seinem
      Hash ab, entsteht kein Durchgang und keine Zeile; jeder Name bleibt; eine Logzeile mit festem
      Grund-Token wird geschrieben; der Lauf bleibt `SUCCESS`. Die Ortsauflösung bleibt davon
      unberührt — ein fehlender Sehenswürdigkeits-Auszug kostet keine Ortsnamen.
- [ ] **Der Request-Pfad schlägt nichts nach.** `rebuild_run_grouping` liest die abgelegte Auskunft
      und löst keinen Dateidurchgang aus; ein dort unbekannter Name behält seinen Namen (Zustand 1).
- [ ] **Der zweite Auszug verhält sich wie die Rohdatei und lässt den ersten unverändert.** Für
      dieselbe Eingabe liefert ein Durchgang über den Auszug dasselbe Ergebnis wie über die Rohdatei;
      der Ortsauszug (`P`+`A`) ist zeichengleich zum Stand vor dieser Spec; beide Dateien tragen je
      ihre eigene `*.sha256` und entstehen aus einem Kommandoaufruf.
- [ ] **Die Migration ist additiv.** Sie legt ausschließlich `landmark_place_lookups` an, verändert
      kein bestehendes Feld und füllt nichts nach; bestehende Läufe behalten ihre Namen bis zur
      Neuberechnung.

## Datenmodell-Bezug

Neue Tabelle `landmark_place_lookups` (`models.py::LandmarkPlaceLookup`): `project_id` als echter
Fremdschlüssel `NOT NULL`, `folded_name` (je Projekt eindeutig), die Fundorte als JSON-Liste von
`[lat, lon]` — **nicht nullbar, leer erlaubt** —, `looked_up_at`. Muster und Lebensdauer wie
`landmark_names`. Migration additiv, `down_revision` auf dem heutigen Kopf `c5bc9a02c3c2`, kein
Backfill. `events` bekommt kein neues Feld; keine bestehende Spalte ändert ihre Bedeutung. Die
Tabelle gehört in die Löschliste der Projektlöschung und in `tests/project_graph.py`. Siehe
[`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0123`](../decisions/0123-der-sehenswuerdigkeitsname-wird-lokal-verortet-und-am-event-geprueft.md)
festgehalten. Sie löst in ADR
[`0106`](../decisions/0106-grobe-ortsangabe-geht-in-die-sehenswuerdigkeits-erkennung.md) Punkt 5 die
Begründung ab, ein lokaler Abgleich sei im Bestand nicht möglich; die Prompt-Auflage dort bleibt in
Kraft, die lokale Prüfung tritt **neben** sie. ADR
[`0105`](../decisions/0105-ortsnamen-aus-dem-lokalen-datensatz-als-auszug-auf-einem-volume.md)
Punkt 3 wird **ergänzt**: der Ortsauszug bleibt unverändert, ein zweiter tritt daneben. ADR
[`0107`](../decisions/0107-sehenswuerdigkeitsname-eine-grenze-und-ein-projektgebundenes-namensregister.md)
(welcher Name) und ADR
[`0120`](../decisions/0120-der-sehenswuerdigkeitsname-braucht-rueckhalt-und-der-ortsname-tritt-daneben.md)
(ob er Rückhalt hat) gelten vollständig weiter; diese Spec entscheidet, **ob er am richtigen Ort
liegt**.

### 1. Die Datenquelle: ein zweiter Auszug aus demselben Bezug

Kein zweiter Datensatz, kein Ortsdienst, **keine Modell-Rückfrage**. `geonames.py` trägt die
Konstanten des zweiten Auszugs (Klassen `S`/`T`/`L`/`H`/`V`, Spalten `name`, `alternatenames`, lat,
lon, class, code an unveränderter Position; `asciiname` wird nicht gelesen), `place_dataset.py`
schreibt ihn. Beides aus **einem** Bezug in **einem** Kommando: Archiv einmal laden, einmal
entpacken, **in einem Durchgang** beide Zieldateien schreiben, jede mit eigener `*.sha256`. Die
zweite Datei liegt als Geschwisterdatei neben `PLACE_DATASET_PATH` — **keine neue
Betriebseinstellung**, sondern eine abgeleitete Funktion (`geonames.py::landmark_dataset_path`),
Muster `dataset_hash_path`. Keine kuratierte `featureCode`-Liste innerhalb der Klassen.

Zwei Dateien statt einer erweiterten, weil der Ortsdurchgang sonst über 13,27 statt 5,77 Mio. Zeilen
liefe, die beiden Durchgänge nach verschiedenen Kriterien sammeln (Kachelnachbarschaft gegen
Namensgleichheit), und **nur getrennt ein fehlender Sehenswürdigkeits-Auszug für sich feststellbar
ist** — daran hängt Punkt 3.

### 2. Der Leser: ein Namensverzeichnis, kein Ortsauflöser

`geonames.py` bekommt neben `GeoNamesResolver` einen **`LandmarkGazetteer`**: namensgeschlüsselt, mit
den offenen Namen im Konstruktor (Muster `GeoNamesResolver` mit den Zellen), **ein** Durchgang durch
den zweiten Auszug, behalten wird, wessen `name` oder eines der `alternatenames` einem gesuchten
Namen entspricht. Ergebnis je gesuchtem Namen ein Eintrag, notfalls ein leerer. Ein billiger
Vorfilter vor der vollen Faltung (Regex-Alternation über die längsten Wörter) ist zulässig.

`fold_landmark_name` ist die **eine** Faltung und liegt hier, nicht in `landmark_names.py`:
Kleinschreibung, getrennte Diakritika, Trennzeichen zu Leerzeichen. Sie wird auf **beiden** Seiten
benutzt — zwei Fassungen liefen auseinander und die Suche schlüge still fehl. **Kein
Ähnlichkeitsrückfall** und kein Einbettungsmodell im Pfad: ein Name, den das Verzeichnis nicht kennt,
fällt unter Zustand (2) und wird verworfen.

Fehlt der Auszug oder weicht er von seinem Hash ab, entsteht **kein** Verzeichnis und **kein**
Ersatzweg (`build_landmark_gazetteer` → `None`) — dieselbe Prüfung wie beim Ortsauszug über das
parametrisierte `dataset_problem`, mit **eigenen** Grund-Token
(`sehenswuerdigkeitsauszug-fehlt` / `-hash-fehlt` / `-hash-abweichung`).

### 3. Die Auskunft: dreiwertig, projektgebunden, lauf-unabhängig

| Zustand | Ablage | Folge |
|---|---|---|
| nie nachgeschlagen | **keine Zeile** | keine Plausibilität feststellbar — Name wie bisher |
| nachgeschlagen, kein Fund | Zeile mit **leerer** Punktmenge | Name gilt als unbestätigt und wird **verworfen** |
| nachgeschlagen, mit Fund | Zeile mit Punkten | bestätigt, wenn ein Fundort im Umkreis liegt |

Fiele (1) mit (2) zusammen, verwürfe ein Lauf ohne Datensatz jeden Namen; fiele (2) mit (3)
zusammen, gäbe es die Regel nicht. Deshalb ist die Punktliste nicht nullbar, sondern darf leer sein.

### 4. Die Prüfung: `events.py::_built`

`explain_events`/`build_events` bekommen einen **schlüsselwort-artigen Parameter**
`landmark_points_by_name: Mapping[str, tuple[Cell, ...]] | None = None`. Die Vorgabe `None` hält alle
34 bestehenden Aufrufe in `test_events.py`/`test_event_probe.py` gültig und heißt „keine Auskunft
vorhanden". `_built` prüft **nach `_name_of` und vor `_place_of`**:

```python
landmark_name = _name_of(members)
if landmark_name is not None and not _landmark_name_is_plausible(
    landmark_name, cells, landmark_points_by_name
):
    landmark_name = None
```

`_landmark_name_is_plausible` ist rein (`haversine_meters` liegt in `events.py` vor) und liest in
dieser Reihenfolge: **keine Auskunft** → wahr; **keine einzige gemessene Zelle** → wahr; **Schlüssel
nicht vorhanden** → wahr; **leere Punktmenge** → falsch; sonst wahr, wenn **mindestens ein** Fundort
**mindestens einer** gemessenen Zelle näher liegt als `LANDMARK_PLAUSIBILITY_RADIUS_METERS`.

- **Konstante:** `LANDMARK_PLAUSIBILITY_RADIUS_METERS = 50_000.0` in `geonames.py`, **nicht**
  `GEONAMES_MAX_DISTANCE_METERS` — beide müssen sich unabhängig bewegen können.
  Dokumentiert-unkalibriert wie `LANDMARK_CONFIDENCE_THRESHOLD`.
- **Kein Nachrücken.** Ein verworfener Name wird `None`; der nächstbeste Kandidat rückt nicht nach.
- **Eine Aufrufstelle.** Name, Zellen und `place_kind` entstehen weiterhin ausschließlich in `_built`;
  `place_kind` kippt mit dem Namen automatisch auf `coordinate`/`multiple`/`None`, die
  Koordinatenstufe greift also wieder.

### 5. Die Verdrahtung im Worker

`_build_grouping_and_rankings` bekommt eine zweite Fabrik `build_landmark_gazetteer` — **ohne**
Vorgabewert, mit derselben Begründung wie `build_place_resolver`. Nach `read_event_inputs` und
**vor** `build_events`:

1. `_landmark_points_by_name(session, project_id, names, build_landmark_gazetteer)` — Muster
   `_place_infos`: die gefalteten Namen der Kandidaten gegen die Tabelle dieses Projekts; für die
   fehlenden wird das Verzeichnis **einmal** gebaut und gefragt, danach je Name eine Zeile
   geschrieben (leere Punktmenge eingeschlossen). Kein `commit`.
2. `build_events(candidates, landmark_points_by_name=…)`.

Der Lauf ruft es am Ende der Landmark-Phase (`run_criterion_scoring`); `rebuild_run_grouping` gibt
`None`. Nachgeschlagen wird die **Kandidatenmenge**, nicht nur die Gewinnermenge: Der Gewinner
entsteht erst *innerhalb* von `_built`, und nur-Gewinner hieße, die Eventbildung zweimal zu rechnen
oder die Namenswahl aus `_built` herauszuziehen.

### 6. Was ausdrücklich nicht passiert

- `places.py`, `landmark.py`, `landmark_names.py`, `event_inputs.py` und das Frontend werden **nicht
  angefasst**. Kein zweiter Ähnlichkeitsweg, keine Ortsprüfung im Vision-Pfad.
- `GEONAMES_MAX_DISTANCE_METERS`, `LANDMARK_MIN_SHARE`, `LANDMARK_CONFIDENCE_THRESHOLD`,
  `PLACE_CELL_DIGITS` und `LANDMARK_PLACE_CELL_DIGITS` bleiben unverändert.
- Kein neues Feld in `events`, keine neue API-Antwort. Kein Log trägt einen Namen, eine Koordinate
  oder eine Entfernung.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `backend/src/photosort/geonames.py` | Klassen/Felder des zweiten Auszugs, `GEONAMES_ALTERNATE_NAMES_FIELD`, `LANDMARK_PLAUSIBILITY_RADIUS_METERS`, `fold_landmark_name`, `LandmarkEntry`/`parse_landmark_line`, `LandmarkGazetteer`/`build_landmark_gazetteer`, `landmark_dataset_path`, drei Grund-Token, `dataset_problem(path, reasons)`, Bandprüfung der Koordinaten im Parser |
| `backend/src/photosort/place_dataset.py` | `extract_landmark_line`; `write_extract` → `write_extracts` (Zielliste, ein Durchgang), `build_dataset(ziel, sehenswuerdigkeitsziel)`, `--sehenswuerdigkeits-pfad` |
| `backend/src/photosort/models.py` | `LandmarkPlaceLookup` (`landmark_place_lookups`) |
| `backend/alembic/versions/<neu>_sehenswuerdigkeitsauskunft.py` | additiv, `down_revision = "c5bc9a02c3c2"` |
| `backend/src/photosort/events.py` | `_landmark_name_is_plausible`, Parameter an `explain_events`/`build_events`, Aufruf in `_built` |
| `backend/src/photosort/worker.py` | `LandmarkGazetteerFactory`, `_landmark_points_by_name`, Verdrahtung in `_build_grouping_and_rankings` + beide Aufrufer |
| `backend/src/photosort/project_deletion.py` | neue Tabelle in der Löschreihenfolge |
| `backend/src/photosort/event_probe.py` | Auskunft **lesend** durchreichen; `LandmarkCounts` um die Gegenanzeige „Namen ohne Lage" |
| `backend/src/photosort/config.py` | **nur Kommentar** an `place_dataset_path` (Geschwisterdatei) |
| `docs/setup.md`, `docs/architecture.md` | zweites Artefakt (~273 MB statt 69 MB), neue Tabelle, Löschliste |
| `specs/architecture/0003-securitykonzept.md` | Fortschreibung — siehe `## Security` |
| `specs/architecture/0002-testkonzept.md` | drei Muster und zwei Lücken — siehe `## Teststrategie` |

`backend/src/photosort/demo_state.py` ist geprüft und **unberührt**: die Demo schreibt ihre Events
direkt und läuft nicht durch `_built`.

### Umsetzungsreihenfolge

1. `geonames.py` — Faltung, Konstanten, Parser, Verzeichnis, Token.
2. `place_dataset.py` — der zweite Extrakt.
3. `models.py` + Migration + `project_deletion.py` — die Ablage.
4. `events.py` — die Regel.
5. `worker.py` — die Verdrahtung, beide Aufrufer.
6. `event_probe.py` — die Gegenanzeige.
7. `docs/setup.md`, `docs/architecture.md` im selben Pull Request.

## UI/UX

**Nicht relevant** — die Story hat keinen eigenen Gestaltungsbedarf. Die Änderung greift
ausschließlich in `events.py::_built` und ändert nicht, *wie* ein Eventname dargestellt wird, sondern
nur, *welcher* Wert in den bereits existierenden, unveränderten Feldern steht. Weder Antwortform noch
Feldbestand der `events`-Ressource ändern sich.

**Bereits abgedeckte Zustände, geprüft.** Die Darstellung läuft an allen drei Stellen über dieselbe
Funktion `frontend/src/utils/timeOfDay.ts::eventPlaceName` (`AlbumDraftPage.tsx` über
`eventGrouping.ts`, `DraftAlternativesDialog.tsx`, `PhotoDetailPage.tsx`). Alle vier Ausgänge
(`"<Name>, <Ort>"`, `"<Name>"`, `"<Ort>"`, `null`) existieren heute samt Tests. Der Fall „Name weg,
Ortsname da" ist exakt der vorhandene Ausgang `"<Ort>"`, der Fall „gar nichts" der vorhandene
`null`-Ausgang; die Rückfälle sind `"Position <n> (<Zeitspanne>)"` in der Überschrift und
`"nicht bestimmbar"` in der Ortszeile. Keine neuen leeren, ladenden oder Fehlerzustände.
`specs/architecture/0004-design-system.md` braucht keine Ergänzung.

Nach der Umstellung kann ein Cluster bei erneutem Lauf anders heißen als zuvor. Eine
Änderungsanzeige ist bewusst nicht vorgesehen.

## Security

**Sicherheitsrelevant, kein Blocker.** Kein neuer Endpunkt, kein Auth-Pfad, kein neues Feld in einer
API-Antwort, kein neuer Cloud-Aufruf, keine neue Eingabe von außen, keine neue Betriebseinstellung,
kein neues Secret, kein neuer Kostenpfad. Die Einwilligung (`cloud_vision_consent_at`) bleibt
unberührt: Die Prüfung arbeitet rein lokal gegen eine bezogene Datei, es geht kein Foto, keine
Koordinate und kein Name hinaus.

- **S1 — `landmark_place_lookups` ist die fünfte Tabelle mit einem Ortswert und die erste mit einer
  ungerundeten Koordinate; sie trägt trotzdem keine neue Informationsklasse.** Die abgelegten Punkte
  sind ausschließlich Koordinaten öffentlich enumerierbarer GeoNames-Einträge, eine reine Funktion
  des gefalteten Namens. **Muss:** In die Punktliste gelangt **nie** eine Foto-, Event- oder
  Zellkoordinate. Die Tabelle bekommt **keine** Spalte für eine Entfernung, für ein Prüfergebnis und
  **keine** `event_id`. **Bei Verletzung** wäre aus einer Namensauskunft eine persistierte
  Aufenthaltsaussage geworden, mit feinerer Körnung als `PLACE_CELL_DIGITS = 2` sie zusichert.
- **S2 — Die Tabelle ist projektgebunden, und die naheliegende Optimierung ist untersagt.** Echter
  Fremdschlüssel `project_id` auf `projects.id`, `NOT NULL`. Der Lesepfad bindet `project_id`
  **ausgeschrieben** und fällt nie auf die Zeile eines anderen Projekts zurück. `project_deletion.py`
  führt die Tabelle, `tests/project_graph.py::build_project_graph` legt eine Zeile an — ohne sie
  prüfen beide Vollständigkeitstests die neue Kante stillschweigend nicht. **Muss:** Die Tabelle wird
  **nicht** projektübergreifend geführt, auch nicht mit dem Argument „die Fundorte eines Namens sind
  projektunabhängig". Der Inhalt ist projektunabhängig, der **Name** ist es nicht.
- **S3 — Der zweite Auszug wird vor jedem Gebrauch gegen seinen eigenen Hash geprüft.**
  `build_landmark_gazetteer` ist der **eine** Bauweg samt seiner Prüfung; ein Auszug ohne seine
  Hash-Datei gilt als unbenutzbar. Die drei Grund-Token sind **eigene**, nie die des Ortsauszugs —
  sonst wäre „der Sehenswürdigkeitsauszug fehlt" von „der Ortsauszug fehlt" nicht zu unterscheiden.
  Der Pfad kommt aus der Betriebseinstellung, **nie** aus Datenbank oder Request.
- **S4 — Die Ausfallrichtung ist fail-open, und das ist hier die richtige.** Fehlt der Auszug, wird
  **kein** Name verworfen, der Lauf bleibt `SUCCESS`. Die Alternative wäre ein Betriebszustand, in
  dem ein einzelner fehlender Auszug **alle** Sehenswürdigkeitsnamen eines Laufs auf einmal entfernt.
  Der Zustand „nie nachgeschlagen" ist deshalb strikt von „nachgeschlagen, ohne Fund" getrennt.
- **S5 — Der Fremdtext wird erstmals zum Aufsuchschlüssel.** **Muss:** (a) Jeder Name — `name` wie
  jedes Element von `alternatenames` — läuft **einzeln** durch `sanitize_landmark_name` (dieselbe
  Funktion wie die Cloud-Pfade), wird bei Überlänge **ganz verworfen, nie gekürzt**; ein Element, das
  die Sanitisierung nicht übersteht, fällt für sich weg, nie die ganze Zeile. (b) Die Faltung läuft
  **danach** — davor zöge sie Bidi- und Zero-Width-Zeichen in den Schlüssel. (c) `alternatenames`
  wird **vor** der Faltung am Komma zerlegt, und „Trennzeichen zu Leerzeichen" umfasst dieses Zeichen
  **nicht** — sonst verschmölzen alle Alternativnamen einer Zeile zu einem Riesenschlüssel. (d)
  `fold_landmark_name` ist **eine** Funktion, diesseits und jenseits dieselbe. Die Faltung darf nur
  Groß-/Kleinschreibung, getrennte Diakritika und Trennzeichen angleichen, nie Zeichen ersatzlos
  entfernen und nie kürzen — eine zu aggressive Faltung zieht verschiedene Sehenswürdigkeiten
  zusammen und **bestätigt** dann einen falschen Namen.
- **S6 — Die Koordinaten brauchen eine Bandprüfung am Parser-Rand.** `parse_geonames_line` prüft
  heute nur auf `ValueError`; `float("nan")`/`float("inf")` passieren die Stelle. Hier würde der Wert
  erstmals **persistiert**. **Muss:** `-90.0 <= lat <= 90.0` und `-180.0 <= lon <= 180.0` als
  **Bereichsvergleich, nie als Klemmen**; beide Komponenten werden verworfen, sobald eine scheitert;
  die Prüfung steht an **einer** Stelle im Parser und wirkt für **beide** Auszüge. **Bei Verletzung**
  stünde ein `NaN` in der JSON-Spalte, verwürfe den Namen lautlos bei jedem künftigen Lauf, und ein
  Lesepfad, der die Spalte ausliefert, legte die Antwort auf `500`.
- **S7 — Der Durchgang braucht eine Speicherobergrenze, die an der gefragten Namensmenge hängt.**
  **Muss:** Die gesuchte Namensmenge kommt **in den Konstruktor**, behalten wird ausschließlich, was
  zu einem gefragten Namen gehört. Ein Gazetteer, der den vollen Auszug hält, erschöpft den
  Worker-Prozess; die Ausfallrichtung ist ein OOM **mitten in einem Lauf, nach den bezahlten
  Cloud-Aufrufen**. Ebenso Muss: Der Durchgang läuft **nur, wenn es offene Namen gibt**. Die
  gemessenen 43 s liegen weit unter `STALL_THRESHOLD` (15 min); ein eigener Fortschrittsstempel ist
  nicht nötig — neu zu stellen, sobald der Durchgang je Lauf mehrfach liefe.
- **S8 — Der Request-Pfad schlägt nichts nach.** `rebuild_run_grouping` gibt **literal `None`** durch,
  `_build_grouping_and_rankings` bekommt **keinen Vorgabewert**. Ohne diese Grenze löste eine
  authentifizierte Anfrage — auch eine mit gestohlenem JWT — einen 43-Sekunden-Durchgang über eine
  204-MB-Datei aus, beliebig oft wiederholbar.
- **S9 — Die Ortskante wächst, in einer Bewegung.** Verwirft die Prüfung einen Namen, fällt das Event
  auf die Koordinatenstufe zurück und schreibt `events.place_lat`/`place_lon` — dieselbe Bewegung wie
  S3(c) aus Spec 0514, erstmals ausgelöst von einer bezogenen Fremddatei statt von einer
  Modellantwort. Keine neue Empfängerklasse, keine neue Körnung (rund 1,1 km), kein neuer ausgehender
  Pfad. Die Prüfung kann Namen nur wegnehmen, nie hinzufügen.
- **S10 — Kein neuer Kanal, nichts Neues in Log, Fehlerzeile oder Messausgabe.** Weder Name noch
  Koordinate noch **Entfernung** gehört in eine Logzeile — in keinem der beteiligten Module; geloggt
  wird ein festes Grund-Token. Für `event_probe.py`: „Namen ohne Lage" ist eine **Anzahl über den
  Lauf**, nie eine Zeile je Name und nie je Event; die Ausgabe geht ins öffentliche Repository.

**Geprüft und ohne Befund:** kein Secret, keine neue Abhängigkeit, kein Modell-Asset, kein
Ähnlichkeitsrückfall, keine Änderung an Auth oder an der Sichtbarkeit zwischen den beiden Nutzern,
kein SSRF-Pfad (Quell-Adresse bleibt Konstante, entpackt wird genau **ein benannter** Archiveintrag,
der zweite Zielname entsteht abgeleitet). Der Wächter
`test_place_dataset.py::TestTheFetchCommandStaysAwayFromEveryAutomaticPath` muss die Umbenennung
`write_extract` → `write_extracts` unverändert überstehen.

### Nachzuziehen im Sicherheitskonzept

`specs/architecture/0003-securitykonzept.md` ist fortzuschreiben:

1. **Abschnitt „Standortdaten", neue Fortschreibung `Spec 0529/ADR 0123`** nach dem
   Spec-0514/ADR-0120-Block: Einstufung, S1–S10 als Auflagen, die wachsende Bewegung aus S9 samt
   Begrenzung.
2. **Bedrohungsmodell (Z. 21):** `landmark_place_lookups` als **fünfte** Tabelle mit einem Ortswert,
   mit dem Zusatz, dass sie als einzige ungerundete Koordinaten führt, diese aber öffentlich
   enumerierbare Gazetteer-Punkte sind (S1).
3. **Vertrauensgrenzen (Z. 45):** ab hier **zwei Dateien aus einem Bezug**, je eigene Hash-Datei und
   eigene Grund-Token; die Trennung ist selbst die Schutzeigenschaft.
4. **Ankerliste (nach Z. 138):** vier neue Zeilen — Hash-Prüfung des zweiten Auszugs mit eigenen
   Token und fail-open; Projektbindung ohne Rückfall plus `build_project_graph`; Request-Pfad ohne
   Gazetteer; die Tabelle trägt keine Entfernung, kein Prüfergebnis, keine `event_id` und keine
   Foto-/Eventkoordinate. Die Bandprüfung aus S6 gehört in die bestehende Sanitisierungszeile
   (Z. 137).
5. **Restrisiko Z. 1297** (ungeschützter Erstbezug) fortschreiben, nicht neu entscheiden: derselbe
   Abruf erzeugt ab hier zwei Dateien, und der zweite bestimmt mit, **ob** eine Überschrift entsteht.
   Der dortige „Neu zu stellen"-Auslöser ist nach Prüfung **nicht** ausgelöst.
6. **Restrisiko Z. 1298** (ortsblind erkannter Name) fortschreiben, nicht streichen: Diese Spec
   **mildert** den Eintrag, hebt ihn nicht auf — sie nimmt den Fall „hunderte Kilometer daneben" weg,
   nicht „am richtigen Ort und trotzdem falsch". Die Aussage in Z. 477 („die Plausibilisierung bleibt
   Out of Scope") gilt ab hier nicht mehr.
7. **Fortschreibung Spec 0469 (Z. 415–418):** Zusatz — der zweite Auszug behält mit `alternatenames`
   **mehr** Fremdtext als der erste, und dieser Text wird erstmals zum **Schlüssel**.

## Teststrategie

**Unit (ohne DB, ohne Netz, ohne echte Datensatzdatei)**

- `fold_landmark_name` in `test_geonames.py` (neue Datei): Kleinschreibung, getrennte Diakritika,
  Trennzeichen, Idempotenz, und ein Paar, das **nicht** zusammenfällt (`Ben Nevis` gegen
  `Ben Nevis Range`).
- `LandmarkGazetteer` gegen eine im Test nach `tmp_path` geschriebene Mini-Auszugsdatei: Treffer über
  `name`, Treffer **nur** über ein Element von `alternatenames`, mehrere Fundorte zu einem Schlüssel,
  Unbekannter → leere Punktmenge (nicht „kein Eintrag"), leerer Kandidatensatz fragt die Datei nicht.
- `_landmark_name_is_plausible` in `test_events.py`: die fünf Zweige in ihrer Reihenfolge. Die Grenze
  wird **am Symbol** geprüft (Muster `_min_share()`) — je ein Fall knapp darunter, exakt darauf (muss
  **verwerfen**) und darüber. Kein Testfall nennt `50_000` als Zahl.
- `write_extracts`/`extract_line` in `test_place_dataset.py`: Klassenfilter `S/T/L/H/V`,
  `alternatenames` in der Ausgabezeile und `asciiname` ausdrücklich nicht, Gleichheitsnachweis
  Auszug/Rohdatei **je Auszug getrennt**, plus die Zusicherung, dass der Ortsauszug aus demselben
  Durchgang unverändert entsteht.

**Integration (mit `db_session`, ohne Netz und ohne echte Datensatzdatei)**

- `_landmark_points_by_name` in `test_worker_place_names.py` (Muster
  `TestPlaceInfosAsksOnlyWhatIsMissing`): nur offene Namen lösen einen Durchgang aus; ein zweiter
  Durchlauf fragt nichts; eine Zeile eines anderen Projekts wird nie gelesen; kein `commit`;
  nachgeschlagen wird die **Kandidatenmenge** (Gegenprobe: ein Name, der die Mehrheitsregel verliert,
  steht danach trotzdem als Zeile da).
- `_build_grouping_and_rankings` als Durchstich über beide Fabriken: bestätigter Name bleibt;
  entfernter Fundort → Ortsname; fehlender/hashabweichender Auszug lässt jeden Namen stehen, schreibt
  keine Zeile, schreibt das Grund-Token, Lauf bleibt `SUCCESS`. Ein Test hält fest, dass die zweite
  Fabrik **keinen** Vorgabewert hat.
- Wächter `TestTheRequestPathAsksNobody` erweitern: der Syntaxbaum-Wächter zählt jetzt **zwei**
  literale `None` an der Aufrufstelle.
- Log-Abwesenheit in `TestNothingLeaksIntoALogOrIntoTheRunRow` um gefalteten Namen und Entfernung
  erweitern, geprüft über `getMessage()` **und** `repr(record.args)`.
- Migration in eigener Datei nach dem `test_migration_ortsauskunft.py`-Muster: Tabelle existiert mit
  FK `NOT NULL`, Eindeutigkeit auf (Projekt, gefalteter Name), bestehende Zeilen unverändert,
  Downgrade entfernt nur die neue Tabelle. Zählung über Zeilenzahlen, nie über „kein
  `IntegrityError`".
- `LandmarkCounts` in `test_event_probe.py`: neue Zählgrößen mit von Hand gerechneten
  Erwartungswerten, plus die bestehende Rein-lesend-Zusage.

**E2E: keine.** Das Aufnahmekriterium (Geometrie, CSS, Breakpoint) ist nicht berührt.

### Wichtigste Edge Cases

1. **Homonym mit mehreren Fundorten**, einer nah → Name bleibt; alle fern → Name fällt. Der erste
   Fundort der Liste ist in beiden Fällen der **falsche**.
2. **Keine gemessene Zelle und zugleich leere Punktmenge** — der Zellen-Fall schlägt den Fund-Fall.
3. **Zwillingstripel der Auskunft**: kein Eintrag / leere Punktmenge / Punkte. Zustand 1 und 3
   liefern dasselbe Event; unterschieden werden sie an der Abwesenheit der Zeile.
4. **Exakt auf der Grenze** → verwirft (`<`, nicht `<=`), am Symbol gerechnet.
5. **Kein Nachrücken**: zweitbester Name mit Fundort im Umkreis bleibt draußen.
6. **Der Vorfilter darf nichts kosten**: ein Name, der nach Faltung träfe, vorher aber anders
   geschrieben ist (`Trevi-Brunnen` gegen `trevi brunnen`), muss gefunden werden.
7. **Ein Name in zwei Events** wird genau einmal nachgeschlagen.
8. **Auszug vorhanden, Ortsauszug fehlt** und umgekehrt — die beiden Ausfälle sind getrennt
   feststellbar.

### Nachzuziehen im Testkonzept

`specs/architecture/0002-testkonzept.md` bekommt drei Punkte und zwei Lücken:

1. **Die Zwillingspaar-Regel wird zur Zwillings-Tripel-Regel:** Wo eine Auskunft mehr Zustände hat
   als Ausgänge, wird jeder Zustand einzeln angefahren und der Unterschied zwischen ergebnisgleichen
   Zuständen an der Datenlage festgemacht, nie am Ergebnis.
2. **Ein zweiter Auszug derselben Quelle braucht seinen eigenen Gleichheitsnachweis und eine
   Zusicherung über den ersten** — ein Durchgang, der beide Dateien erzeugt, kann den alten Auszug
   verändern, ohne dass ein Test über den neuen rot wird.
3. **Ein zugelassener Vorfilter ist ein Testgegenstand, keine Implementierungsfreiheit:** der Fall
   „vom Vorfilter verworfen, von der Normalisierung gefunden" ist Pflichtfall.

Unter „Bekannte Lücken": (a) `LANDMARK_PLAUSIBILITY_RADIUS_METERS` ist dokumentiert-unkalibriert,
Erkennungsweg ist Daniels Abnahme an einer echten Reise; (b) der gemessene Namensverlust (5 von 50)
ist am Repository unbelegt und bleibt es — geprüft ist das Verfahren, nicht die Trefferquote. Das
Coverage-Gate trägt diese Spec nicht; tragend ist die namentliche Fallliste.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR
  [`0123`](../decisions/0123-der-sehenswuerdigkeitsname-wird-lokal-verortet-und-am-event-geprueft.md)
  angelegt.
- `ux-ui-designer` konsultiert (Schritt 2): keine sichtbare Oberfläche, reine Wertänderung hinter
  unveränderter Anzeigelogik.
- `test-engineer` konsultiert (Schritt 3): Teststrategie und geschärfte Akzeptanzkriterien wie oben.
- `security-engineer` konsultiert (Schritt 3): S1–S10 und die Fortschreibung des Sicherheitskonzepts.
- **Entschieden durch Daniel (Refinement):** Ortsplausibilität statt ersatzlosem Entfernen des Namens
  aus dem Eventnamen; keine Handkorrektur von Eventnamen; bei nicht ermittelbarer Lage gilt „im
  Zweifel verwerfen".
- **Selbst entschieden (architect):** zweiter Auszug statt erweitertem ersten; Nachschlagen der
  Kandidaten- statt der Gewinnermenge; `write_extract` wird verallgemeinert statt verdoppelt.
- **Selbst entschieden (ux-ui-designer):** keine Änderungsanzeige für umbenannte Cluster.
- **Selbst entschieden (test-engineer):** keine E2E-Ebene; Grenzrichtung `<`; eigene Testdatei je
  Migration.
- **Selbst entschieden (security-engineer):** der „mehr als Anzeigetext"-Auslöser des
  Erstbezugs-Restrisikos ist nicht ausgelöst; die wachsende Ortskante aus S9 ist keine neue Klasse.

## Offene Fragen

- Keine.

## Out of Scope

- Umbenennen, Bestätigen oder Korrigieren eines Eventnamens von Hand.
- Eine sichtbare Kennzeichnung eines Namens als „unsicher" und ein sichtbarer Hinweis auf einen
  verworfenen Namen.
- Jede Änderung der Erkennung selbst: Modell, Prompt, `LANDMARK_CONFIDENCE_THRESHOLD`, Namensregister.
- Ein Nachziehen bereits berechneter Läufe (kein Backfill) und ein erneuter bezahlter
  Erkennungsaufruf.
- Eine Kalibrierung von `LANDMARK_PLAUSIBILITY_RADIUS_METERS` gegen einen Foto-Korpus.
- Eine kuratierte Auswahl von `featureCode`s innerhalb der fünf Klassen.

---

*Umfang: Diese Spec liegt über dem Richtwert von ~200 Zeilen, weil sie die vier Fachkonsultationen
(Architektur, UI/UX, Security, Teststrategie) samt Umsetzungsplan und Nachzieh-Listen vollständig
trägt — das ist die Arbeitsgrundlage des anschließenden `developer`-Laufs; der Inhalt steht nirgends
sonst.*
