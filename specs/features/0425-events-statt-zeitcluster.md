# 0425 - Events statt Zeitcluster: Zeit, Ort und Sehenswürdigkeit gliedern das Album

**Status:** Accepted
**Erstellt:** 2026-09-12
**Bezug:** [Issue #425](https://github.com/TheRealKoller/photosort/issues/425), Teil des Zielbilds
[#424](https://github.com/TheRealKoller/photosort/issues/424); ADR
[`0087`](../decisions/0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Umsetzung acht Schritte über Backend,
Migration, API und Frontend trägt und zehn Sicherheitsauflagen als prüfbare Zusagen mitführt.

## Ziel

Das Album soll der Reise folgen: erst der eine Ort, dann der nächste, in der Reihenfolge, in der wir
dort waren. Heute entsteht diese Gliederung als Nebenprodukt einer Zeitrechnung — eine Zeitlücke
beginnt einen neuen Abschnitt, ein Ortssprung ebenso. Das trennt an den falschen Stellen: Ein
Spaziergang in kleinen Schritten wird nie getrennt und überspannt am Ende Kilometer, während eine
längere Pause an ein und demselben Ort ihn zerreißt.

Diese Story macht aus dem Abschnitt ein **Event** — eine Einheit mit Anfang, Ende, Ort und Namen, auf
die sich die späteren Stories des Zielbilds beziehen können. Nutzen haben beide Nutzer, zunächst
mittelbar: Besser wird die Gliederung dort, wo die Ortsausdehnung heute versagt.

## User Story

Als Nutzer, der nach einer Reise seine Fotos durchgeht, möchte ich, dass sie nach Events gegliedert
sind — danach, wo ich war und wie lange —, damit das spätere Album der Reise folgt statt einem
Zeitraster.

## Akzeptanzkriterien

**Was ein Event ist**

- [ ] Ein Event ist eine zusammenhängende Folge von Fotos mit Anfangszeit, Endzeit und Ortsbezug.
- [ ] Die Events eines **Kriterien-Laufs** sind chronologisch geordnet und überschneidungsfrei: für je
      zwei aufeinanderfolgende gilt `events[i].ended_at <= events[i+1].started_at`, und `position`
      läuft lückenlos von 1 bis n. Träger ist der Lauf, nicht das Projekt — ein Projekt hat mehrere.
- [ ] Jedes **Kandidatenfoto des Laufs** (die Ausschuss-Überlebenden, also genau die Fotos mit
      `PhotoRanking`-Zeile) gehört zu genau einem Event. Aussortierte Fotos gehören zu keinem.
- [ ] Ein Event trägt **höchstens einen** Namen. Liegt einer vor, ist er die Bezeichnung; sonst lautet
      sie `Position <position> (<hh:mm>–<hh:mm> Uhr)`.
- [ ] Ein Event reicht nicht über eine Kalendertagsgrenze hinaus. Maßgeblich sind die ersten zehn
      Zeichen von `taken_at` (zonenlos, keine Zeitzonen-Umrechnung).

**Wann ein neues Event beginnt**

- [ ] Zeitlücke und Ortssprung zwischen zwei aufeinanderfolgenden Fotos: unverändertes Verhalten,
      geprüft **am Symbol** (`TIME_CLUSTER_GAP`, `GPS_CLUSTER_SPLIT_DISTANCE_METERS`,
      `EVENT_EXTENT_MAX_METERS` ± ε), nie am Zahlwert.
- [ ] **Neu:** Grenze, sobald die räumliche Ausdehnung des laufenden Events die festgelegte Größe
      überschreitet — auch dann, wenn jeder einzelne Schritt für sich klein war. Gemessen
      **einschließlich des gerade betrachteten Fotos**; dieses Foto beginnt dann das neue Event, es
      beendet nicht das alte. Die Größe liegt in der Größenordnung eines Stadtviertels, ist nicht
      kalibriert und bleibt änderbar.
- [ ] Sehenswürdigkeit: Grenze **nur**, wenn Kandidat und laufendes Event je einen nicht-leeren,
      verschiedenen Namen tragen. Namenlose Fotos lösen nie aus.
- [ ] Ein Name, der nach `sanitize_landmark_name` leer oder länger als `MAX_LANDMARK_NAME_LENGTH` (80)
      ist, gilt als **nicht vorhanden** — er löst keine Grenze aus und wird nicht in
      `events.landmark_name` geschrieben. Verworfen, nie abgeschnitten.

**Ort für Fotos ohne eigene Ortsangabe**

- [ ] Ein Foto ohne eigene Ortsangabe übernimmt den Ort des zeitlich nächsten Fotos mit Ortsangabe.
      Bezugsmenge sind **alle Fotos des Projekts mit gemessener Koordinate** — auch aussortierte, auch
      solche, die am Ende in einem anderen Event landen.
- [ ] Tie-Break: bei gleichem zeitlichen Abstand gewinnt der frühere Zeitpunkt, bei identischem
      `taken_at` die kleinere `photo_id`. Kein Anker im Projekt → kein Foto erbt einen Ort.
- [ ] Der übernommene Ort steht fest, **bevor** die Events gebildet werden, und **wirkt** auf sie
      (Schrittabstand und Ausdehnung rechnen mit der wirksamen Koordinate).
- [ ] Der übernommene Ort **speist nie** `events.place_kind`/`place_lat`/`place_lon`. Ein Event, dessen
      Fotos alle nur geerbte Orte tragen, hat keinen Ortsbezug; seine Fotos zeigen ihren Ort trotzdem.
- [ ] „Bleibt als übernommen erkennbar" konkret: `PhotoOut.location.source == "derived"`, nie
      `"exif"`.

**Verhalten am Rand**

- [ ] Trägt kein einziges Foto des Projekts eine Ortsangabe, ist die Gliederung identisch mit einer
      reinen Zeitlücken-Gliederung, zusätzlich getrennt an jeder Kalendertagsgrenze. (Nicht „wie
      heute": die Tagesgrenze ist neu, eine Nacht ohne Zeitlücke trennt künftig.)
- [ ] Phase A bleibt unverändert: `run_project_scoring`/`assign_clusters`/`PhotoScore.cluster_key`
      gliedern weiterhin grob vor dem Ausschuss-Gate. Die Divergenz zwischen `PhotoScore.cluster_key`
      und `PhotoRanking.event_id` ist gewollt.
- [ ] `GET /projects/{id}/curation-candidates?event_id=…` liefert für ein `event_id`, das zu einem
      anderen Projekt oder zu einem älteren Lauf gehört, keine Fotos — `items: []` **und** `total: 0`.
- [ ] Ein Kriterien-Lauf von vor dieser Änderung hat keine Rangzeilen mehr; die Kuratierung zeigt für
      ihn nichts, bis er neu berechnet wird. Der Leerzustand der Ansicht trägt diesen Fall: ein
      erfolgreicher Lauf **ohne** Rangzeilen ist neu.

## Datenmodell-Bezug

Neue Entität `Event` (`events`), je Zeile ein Event eines `CriterionScoringRun`. `PhotoRanking`
verliert `cluster_key` und bekommt `event_id`. `PhotoScore.cluster_key` bleibt unangetastet.
[`docs/architecture.md`](../../docs/architecture.md) zieht im selben Pull Request nach.

## Architektur / Umsetzung

**Grundlage:** ADR 0087. Die dortigen sechs Entscheidungen sind bindend; hier steht ihre Umsetzung.

Die Event-Bildung wird **ein** sortierter Durchlauf über die Kandidaten eines Kriterien-Laufs, an der
Stelle, an der heute `refine_clusters_by_landmark` steht — nach der Landmark-Phase, vor dem Aufbau
der Partitionen. Der übernommene Ort entsteht projektweit **vor** dem Durchlauf und bleibt
unpersistiert.

**1. Datenmodell und Migration** (`models.py`, `alembic/versions/<neu>.py`, `project_deletion.py`)

- `Event` (`__tablename__ = "events"`): `id`, `criterion_scoring_run_id` (echter FK, NOT NULL),
  `position` (1-basiert, chronologisch je Lauf), `started_at`, `ended_at`, `landmark_name: str | None`,
  `place_kind: str | None` (`"landmark"` | `"coordinate"` | `"multiple"`), `place_lat`/`place_lon:
  float | None` (bereits gerundet). `UniqueConstraint(criterion_scoring_run_id, position)`.
- `PhotoRanking.cluster_key: str` → `event_id: int` (echter FK, NOT NULL).
- Migrationsablauf: `events` anlegen → **`DELETE FROM photo_rankings`** (alle Zeilen; es gibt keine
  Altläufe mit Events) → `event_id` NOT NULL ergänzen → `cluster_key` entfernen. **Kein** Nachziehen
  bestehender Gruppen, **keine** Namen aus `photo_landmark_detections` in die neue Spalte.
  `criterion_scoring_runs` bleibt unberührt. Das `downgrade` holt die Zeilen nicht zurück — im
  Migrationsmodul zu vermerken.
- `project_deletion.py`: `Event` **nach** `PhotoRanking`, **vor** `CriterionScoringRun`.
  `tests/project_graph.py::build_project_graph` legt zusätzlich eine `Event`-Zeile an und verknüpft
  die `PhotoRanking`-Zeile damit, sonst prüfen die Vollständigkeitstests die neue Kante nicht.

**2. Neues Modul `backend/src/photosort/events.py`** — rein, DB-frei, vollständig unit-testbar.
Bewusst nicht in `scoring.py`: das ist Phase A. `_haversine_meters` wird dort öffentlich gemacht
(`haversine_meters`) und importiert, nicht kopiert.

```python
EVENT_EXTENT_MAX_METERS = 1000.0          # unkalibriert, Muster TIME_CLUSTER_GAP

@dataclass(frozen=True)
class LocationEntry:      photo_id, taken_at, gps_lat, gps_lon
@dataclass(frozen=True)
class EffectiveLocation:  lat, lon, inferred: bool
@dataclass(frozen=True)
class EventCandidate:     photo_id, taken_at, location: EffectiveLocation | None,
                          gps_lat, gps_lon,          # GEMESSEN, nur für den Ortsbezug
                          landmark_name: str | None
@dataclass(frozen=True)
class BuiltEvent:         position, photo_ids, started_at, ended_at,
                          landmark_name, place_kind, place_lat, place_lon

def infer_locations(entries) -> dict[int, EffectiveLocation]
def build_events(candidates, signals=None) -> list[BuiltEvent]
def default_signals() -> list[BoundarySignal]
```

- `BoundarySignal` als `Protocol`: `is_boundary(candidate) -> bool` (**rein**), `begin(candidate)`,
  `advance(candidate)`. Der Durchlauf wertet alle Signale aus (`any([...])` über eine Liste,
  ausdrücklich **nicht** kurzgeschlossen) und ruft danach genau eine der schreibenden Methoden auf
  **allen** auf.
- Fünf Signalklassen: `TimeGapSignal` (unverändert), `DayBoundarySignal` (Kalendertag als
  `iso[:10]`-Vergleich), `StepDistanceSignal` (Bezug ist die letzte **wirksame** Koordinate des
  laufenden Events, Rücksetzung an jeder Grenze), `ExtentSignal` (neu, Diagonale der umschließenden
  Box, einschließlich des betrachteten Fotos), `LandmarkChangeSignal` (neu, ersetzt
  `refine_clusters_by_landmark`).
- Ortsbezug je Event ausschließlich aus **gemessenen** Koordinaten und Namen, Rangfolge `landmark` →
  eine gerundete Koordinatenzelle → `multiple` → kein Ortsbezug. `_rounded` und
  `_CLUSTER_PLACE_COORDINATE_DIGITS` wandern aus `api/photos.py` hierher.

**3. Verdrahtung im Worker** (`worker.py::run_criterion_scoring`)

- `refine_clusters_by_landmark`-Aufruf und `cluster_by_photo` entfallen, auch der Passthrough in der
  Kandidatenschleife.
- Eine zusätzliche Abfrage für die Inferenzbasis über **alle** Fotos des Projekts, mit
  `Photo.project_id == project.id` ausgeschrieben (abgeleitet aus `CriterionScoringRun.project_id`).
- `_landmark_names(...)` bleibt unverändert und ist die **einzige** Quelle für `events.landmark_name`.
- `build_events(...)` → `Event`-Zeilen, `session.flush()` für die Ids, `event_id_by_photo` aufbauen.
- Partitionsschlüssel `(cluster_key, category_key)` → `(event_id, category_key)`.
- `reassign_photo_category` und ihre Aufrufer: Parameter `cluster_key: str` → `event_id: int`. Die
  Event-Id kommt weiter serverseitig aus `ranking.event_id`, **nie** aus Body oder Query; das
  Lauf-Prädikat bleibt neben `event_id` stehen.

**4. `scoring.py` aufräumen** — `refine_clusters_by_landmark` samt Tests entfernen, `assign_clusters`
unverändert lassen, `_haversine_meters` öffentlich machen.

**5. API** (`api/photos.py`)

- `ClusterPlaceOut` → `EventPlaceOut` (Form unverändert); neu `EventOut { id, position, started_at,
  ended_at, place }`. `PhotoOut.cluster_place` entfällt zugunsten `PhotoOut.event: EventOut | None`.
  `PhotoOut.location` bleibt in Form und Bedeutung unverändert. `RankingOut.cluster_key` →
  `event_id: int`. `SuggestionOut.cluster_key` (aus `PhotoScore`) bleibt.
- `_event_and_location_by_photo_id` mit zwei Abfragen: (a) alle Fotos des Projekts → `infer_locations`
  → `location`; (b) die Events der Rangzeilen der Antwort. Beide Bindungen ausgeschrieben —
  `Photo.project_id` bzw. `Event.criterion_scoring_run_id == run_id`.
- `GET /projects/{id}/curation-candidates`: `cluster_key: str` → `event_id: int = Query(..., ge=1,
  le=…)` mit Obergrenze im Muster von `_MAX_QUERY_POSITION`. `_partition_sizes` gruppiert nach
  `(event_id, category_key)`. `_MAX_PARTITION_KEY_LENGTH` bleibt für `category_key` bestehen.
- Alle drei Lesepfade liefern `event` und `location`.

**6. Demo-Seed** (`demo_state.py`) — echte `Event`-Zeilen statt eines `cluster_key`-Strings, in allen
Anzeigezuständen: `place_kind` dreifach, kein Ortsbezug, je ein Event mit und ohne Namen.

**7. Frontend** — `api/types.ts`: `EventPlace`, `EventOut`, `PhotoOut.event`, `RankingOut.event_id`.
`api/photos.ts` und `CurationCandidates.tsx`: Query-Parameter `event_id`.
`utils/timeOfDay.ts`: `formatClusterHeading(photos)` → `formatEventHeading(event)`, rein über **einem**
Event; `timeOfDayBucketLabel` und `TIME_OF_DAY_BUCKETS` entfallen samt Testfällen, `dayKeyOf`,
`hourOf` und `formatTimeRange` bleiben. `CurateCategoriesPage.tsx`: Gruppierung nach
`ranking.event_id`, Sortierung nach `event.position`, Tagesgruppe aus `event.started_at`; der
`clusterMetaRef`-Cache bleibt und hält künftig das `EventOut`.

**8. Doku** — `docs/architecture.md` im selben Pull Request: neue Tabelle `events`, Wegfall der
nachträglichen Landmark-Verfeinerung, vorgezogene projektweite Ortsherleitung, geänderter
Partitionsschlüssel, und dass ein Lauf von vor dieser Änderung neu berechnet werden muss.
`docs/setup.md` ist nicht betroffen.

**Erweiterbarkeit (ausdrückliche Anforderung der Story):** Das Motivwechsel-Signal aus #427 ist danach
eine Klasse in `events.py` und ein Eintrag in `default_signals()` — kein Eingriff in den Durchlauf,
das Datenmodell oder die API. Tragend dafür ist die Trennung von `is_boundary` (rein) und
`begin`/`advance` (schreibend).

## UI/UX

Sichtbar ändert sich allein die Überschriftenbildung der Kuratierungsansicht auf Cluster-Ebene. Keine
neue Ansicht, keine neue Navigation, keine neue Komponente, keine Design-System-Erweiterung.

**Überschriften-Form**, gebildet direkt aus dem Event statt aus aggregierten Foto-Metadaten:

- mit erkannter Sehenswürdigkeit: `Eiffelturm (10:30–11:45 Uhr)`
- sonst (Koordinate, mehrere Orte, oder kein Ortsbezug): `Position 3 (10:30–11:45 Uhr)`

Tageszeit-Kategorien („Vormittags", „Nachmittags") entfallen ersatzlos: Eine sprechende
Sehenswürdigkeit oder Nummer plus Zeitspanne ist informativer, und die Form wird über alle Events
einheitlich statt gemischt. Eine Koordinate erscheint nicht mehr als Name. Die Uhrzeit-Spanne bleibt
präzise und trägt den Kontext.

**Betroffene Zustände:** Der Leertext der erschöpften Partition ist heute an die Tageszeit gebunden
(„Keine Fotos in dieser Tageszeit") und trifft danach nicht mehr zu — Ersatz: „Keine Fotos in dieser
Gruppe". Zusätzlich trägt der Leerzustand der Ansicht künftig den Fall „erfolgreicher Lauf ohne
Rangzeilen" (Altlauf vor der Migration).

**Design-System-Bezug** ([`0004`](../architecture/0004-design-system.md)): Überschriftenebene, Abstände
und Formsprache bleiben unverändert.

## Security

**Sicherheitsrelevant, kein Blocker.** Keine neue Angriffsflächen-Klasse (kein Secret, kein externer
Empfänger, keine Auth-Änderung, kein Cloud-Aufruf). Vier Verschiebungen: eine von außen gelieferte
Objekt-Id ersetzt einen Freitextschlüssel, Standortdaten werden erstmals aggregiert persistiert,
extern erzeugter Freitext bekommt eine eigene Spalte, Löschordnung und Bezugsmenge wachsen. Im Saldo
eine Verengung.

- **M1 Projektbindung bleibt ausgeschrieben.** `event_id` ist ein **globaler** Surrogatschlüssel: eine
  Id aus Projekt B identifiziert unter `/projects/A/...` eindeutig fremde Rangzeilen. Ohne das
  Lauf-Prädikat liefert der Endpunkt **kohärente** Fotos eines fremden Projekts statt einer erkennbar
  falschen Kollisionsmenge — die Ausfallrichtung wird unauffälliger, nicht harmloser. Das Prädikat
  steht in **jeder** Abfrage des Endpunkts, `_partition_sizes` hinter `total` eingeschlossen; die
  Lauf-Id kommt ausschließlich aus dem Pfadparameter. Fremdes `event_id` → `200` mit leerer Antwort,
  keine Rückspiegelung des Werts.
- **M2 Auth am Endpunkt unverändert Muss.** `api/photos.py` hat kein router-weites
  `dependencies=[Depends(get_current_user)]`; ein Endpunkt ohne den Parameter ist still öffentlich.
  Die geänderte Signatur behält `current_user: User = Depends(get_current_user)`, und `current_user.id`
  geht weiter an `_to_photo_out`.
- **M3 Eingabewechsel `str` → `int`.** Es entfällt der Wert, der bisher ungeprüft bis zum
  Datenbankvergleich lief; `ge=1` plus Typprüfung ist enger als `max_length=200`.
  `_MAX_PARTITION_KEY_LENGTH` bleibt für `category_key`. Zusätzlich eine **Obergrenze** (`le=…`), damit
  ein Wert jenseits von 2^63 unter SQLite keinen `OverflowError` → 500 erzeugt. FastAPI spiegelt bei
  `422` den Rohwert im `input`-Feld zurück — nur als React-Textknoten rendern, nicht ins Log.
- **M4 Umhängen bezieht die Event-Id serverseitig.** `set_category_override`/
  `delete_category_override` reichen `ranking.event_id` aus der Zeile des aufgelösten Laufs weiter —
  nie aus Body oder Query. Die Partitionsabfrage behält neben `event_id` das Lauf-Prädikat.
- **M5 Die neue Bezugsmenge braucht ihre eigene Bindung.** Die Bindung wandert von der Lauf-Id auf
  `Photo.project_id` und steht in **beiden** Aufrufern ausgeschrieben (Lesepfad und Worker). Ohne sie
  erbt ein Foto Koordinaten aus einem fremden Projekt bzw. hängen Event-Grenzen in Projekt A an Fotos
  aus Projekt B.
- **M6 Die Ausweitung auf aussortierte Fotos ist tragbar.** Die Information ist nicht neu: aussortierte
  Fotos stehen im Standard-Listing desselben Projekts mit `source="exif"` in voller Präzision, für
  beide Nutzer. Neue Herkunft, keine neue Datenklasse, keine neue Reichweite; der projektweit nächste
  Anker ist nie *weiter* entfernt als der clusterweite. Unverändert Muss: `source` wird **nicht**
  persistiert, steht an jedem ausgelieferten Ort, und kein Verbraucher behandelt `derived` wie `exif`.
- **M7 Feldkombination als geprüfte Invariante.** `place_kind='landmark'` ⇒ `landmark_name` gesetzt;
  `'coordinate'` ⇒ beide Koordinaten gesetzt; `'multiple'` ⇒ **beide Koordinaten NULL**. Koordinaten
  werden **gerundet geschrieben**, nie in voller Präzision. Ein Event ohne gemessene Koordinate trägt
  `place_kind IS NULL`.
- **M8 Unbekannter `place_kind` bringt keine Antwort um.** `place` ist `None`, wenn `place_kind` NULL
  oder nicht aus dem Vorrat ist — Mitgliedschaftsprüfung statt blindem Cast; sonst legt ein einzelner
  Wert die gesamte Listenantwort auf 500.
- **M9 `events.landmark_name` ausschließlich über `sanitize_landmark_name`.** Gelesen über
  `worker.py::_landmark_names`; kein direkter Zugriff auf `PhotoLandmarkDetection.name` an der
  Schreibstelle, **kein Abschneiden**, und die Migration kopiert **keine** Namen. Die XSS-Auflage
  wandert mit dem Feld mit: ausschließlich als regulärer React-Textknoten (nie
  `dangerouslySetInnerHTML`, nie `href`/`src`/`style`). Neues Logziel `events.py`: Koordinaten nie ins
  Log, ein Name nur als `%r` mit Längenbegrenzung.
- **M10 Löschordnung und Verwaisungsschutz.** `events` zwischen `photo_rankings` und
  `criterion_scoring_runs`, beide Kanten als **echte** Fremdschlüssel — eine bloß logische Spalte
  fiele still aus der Erreichbarkeitsprüfung, und unter Postgres entstünden verwaiste Zeilen.

**Bewusst akzeptiertes Restrisiko (Daniel, 2026-09-12):** Das unbedingte Zurückschreiben von
`gps_lat`/`gps_lon` ist der einzige Weg, auf dem das *Entfernen* von GPS aus einer Quelldatei in
PhotoSort ankommt. Mit `events.place_lat`/`place_lon` überlebt eine **gerundete** Kopie (~1,1 km) im
Lauf-Artefakt, bis ein neuer Kriterien-Lauf die Events neu bildet; ältere Läufe behalten sie. Getragen
wird das von der Granularität (eine Größenordnung über Wohnadress-Auflösung), davon, dass kein neuer
Empfänger entsteht, und davon, dass ein Nachziehen über alle Alt-Läufe neue Mechanik für wenig
Schutzgewinn wäre.

`specs/architecture/0003-securitykonzept.md` zieht in diesem Pull Request nach: Abschnitt
„Standortdaten" (erstmals zwei Tabellen mit Ortswerten, geänderte Bezugsmenge, M7 als Ersatz der
strukturellen „multiple trägt keine Koordinate"-Zusicherung, Aufteilung der Laufbindung in zwei
getrennte Bindungen, das Restrisiko oben), Abschnitt „Projektweite Löschung" (vierzehnte Tabelle, M10),
Abschnitt „Voller Bildvorrat in der Kuratierung" (der Partitionsschlüssel verliert seinen
Freitextanteil; die Auflage bleibt für `category_key`).

## Teststrategie

**Unit (`backend/tests/test_events.py`, neu, DB-frei) — der Schwerpunkt.**

- Ein Helfer `assert_event_invariants(candidates, events)` prüft chronologische Ordnung,
  Überschneidungsfreiheit, `position` lückenlos ab 1, `started_at <= ended_at` und „jeder Kandidat in
  genau einem Event"; er läuft am Ende **jedes** `build_events`-Testfalls. Kein Property-Testing —
  `hypothesis` wäre eine ADR-pflichtige neue Abhängigkeit.
- Jedes Signal einzeln, mit ± ε am Symbol; `>` vs. `>=` explizit festgelegt.
- **Ausdehnung schließt das laufende Foto ein** (eigener Regressionsfall): Kette kleiner Schritte,
  deren Box-Diagonale bei Foto k überschreitet → k ist das **erste** Foto des neuen Events.
- **Ausdehnung trennt, wo der Schritt es nicht tut** (der fachliche Kern): Spaziergang in 400-m-
  Schritten über 3 km → mehr als ein Event. Komplementär: eine lange Pause am selben Ort zerreißt
  nichts, solange die Zeitlücke unterschritten bleibt.
- **Nicht-Kurzschluss, zwei Nachweise:** verhaltensnah (eine durch die Zeitlücke ausgelöste Grenze
  setzt auch Schritt- und Ausdehnungssignal zurück) und als Vertrag (ein Spion-Signal belegt, dass bei
  jedem Kandidaten alle Signale gefragt werden). Der zweite ist ein Struktur-, kein Verhaltenstest —
  er steht, weil #427 auf genau dieser Zusage aufsetzt.
- `infer_locations`: beide Tie-Breaks; Anker ist ein **aussortiertes** Foto; Anker jenseits einer
  späteren Event-Grenze; kein Anker → leeres Ergebnis; `inferred=True` durchgehend.
- **Backward Compatibility ohne jede Koordinate** gegen eine **im Test nachgebildete**
  Referenzimplementierung aus Zeitlücke + Kalendertag, nicht gegen `assign_clusters` (das die
  Tagesgrenze nicht kennt).
- **`place_*` nur aus gemessenen Werten:** Event mit ausschließlich geerbten Koordinaten → kein
  Ortsbezug, obwohl die geerbten Werte die Grenzen mitbestimmt haben.

**Integration.** `test_worker_criterion_scoring.py`: Event-Zeilen mit `position`/Zeiten/Ortsfeldern,
der bestehende Rot-Anker „Lauf ohne Cloud-Phase mit Detections aus einem früheren Lauf" wandert auf das
neue Signal, `PhotoScore.cluster_key` wird nachweislich nicht mutiert, Partitionen über
`(event_id, category_key)`. `test_api_photos.py`: `PhotoOut.event` über alle Fotos eines Events
feldgleich, über beide Lesepfade und über `top_n_per_category=1` vs. `=10`; Rot-Anker für `location`
verschärft (einziger Anker ist ein aussortiertes Foto ohne Rangzeile); `event_id`-Validierung
(`0`/`-1` → 422, Obergrenze); fremdes `event_id` → `items: []` **und** `total: 0`; Abfrageanzahl fest
und unabhängig von der Fotoanzahl über den `before_cursor_execute`-Mitschnitt. `test_migration_events.py`:
die Rangzeilen der Altläufe sind fort, die Lauf-Zeilen stehen, keine Waise, `downgrade()` als
festgeschriebenes Verhalten, `test_migration_chain.py` bleibt bei einem Head. Dazu
`test_postgres_ddl_compatibility.py` (Tabelle, FK, `UniqueConstraint`) und `test_project_deletion.py`
(Event im Vollgraphen, eigene Zeilenzählung, Reihenfolge). `test_demo_state.py`: echte Event-Zeilen in
allen Anzeigezuständen. Zu löschen: die `refine_clusters_by_landmark`-Tests in `test_scoring.py`; die
`assign_clusters`-Tests bleiben **unangetastet** — sie sind der Nachweis, dass Phase A nicht mitgewandert
ist.

**Frontend (`vitest`).** `formatEventHeading(event)` als reiner Formatierer, beide Formen, Zeitspanne
über String-Slicing statt `Date`-Gettern. Gruppierung nach `ranking.event_id` mit Sortierung nach
`event.position` — Rot-Anker: eine Fixture, deren `id`-Reihenfolge der `position`-Reihenfolge
widerspricht. Der XSS-als-Text-Nachweis für `landmark_name` wandert mit. `timeOfDayBucketLabel` geht
samt Testfällen. Der Leerzustand bei erfolgreichem Lauf ohne Rangzeilen wird geprüft.

**E2E** unberührt — die Überschrift ist reine Textzusammensetzung, das kann jsdom.

**Bewusst nicht geprüft:** der Zahlwert `EVENT_EXTENT_MAX_METERS` (unkalibriert; ein Test darauf wäre
eine Spiegelung des Codes), Haversine selbst (in `test_scoring.py` abgedeckt). Das 80-%-Coverage-Gate
trägt hier nichts — die Backend-Coverage liegt bei ~97 %, `events.py` könnte vollständig ungetestet
bleiben, ohne es zu röten. Die oben benannten Fälle sind namentlich verbindlich.

`specs/architecture/0002-testkonzept.md` zieht in diesem Pull Request nach: eine neue Backend-Sektion
für das Muster „protokoll-gebundene Signalliste" (reine Frage / schreibende Fortschreibung samt
Nicht-Kurzschluss-Vertrag, Invarianten-Helfer über allen Fällen desselben Durchlaufs, geteilte
Ableitung mit projektweiter Bezugsmenge); ein Vermerk an der `refine_clusters_by_landmark`-Sektion,
dass sie mit ADR 0087 entfällt, **weil** die Umgruppierung Überschneidungsfreiheit unmöglich macht
(kommentarlos gelöscht, übernähme der nächste Leser die Drei-Schlüssel-Regel aus einem Altstand); und
ein Eintrag unter „Bekannte Lücken", dass `EVENT_EXTENT_MAX_METERS` unkalibriert und durch keinen Test
gepinnt ist.

## Entscheidungen

- **Event wird persistiert** (Daniel, 2026-09-12). Die Alternative „abgeleitet lassen" erfüllt alle
  Akzeptanzkriterien mit kleinerem Eingriff, verschiebt die Tabelle aber nur nach #430.
- **Altläufe werden entwertet** (Daniel, 2026-09-12): keine Events, die Migration löscht ihre
  Rangzeilen, die Kuratierung zeigt für sie nichts bis zur Neuberechnung. Gewählt gegen „Altbestand
  ausnehmen" (Empfehlung `test-engineer`) und „Migration verschmilzt". Folge: `PhotoRanking.event_id`
  ist NOT NULL, es gibt keinen Ausnahmezweig im Lesepfad.
- **Das GPS-Restrisiko wird akzeptiert** (Daniel, 2026-09-12), siehe Abschnitt Security.
- `architect` konsultiert (Schritt 1) — ADR 0087 angelegt, ADR 0029 und 0072 mit Teil-Vermerk versehen.
- `ux-ui-designer` konsultiert (Schritt 2) — Tageszeit-Kategorien entfallen.
- `test-engineer` konsultiert (Schritt 3) — elf geschärfte Akzeptanzkriterien, darunter das
  Sicherheits-Kriterium zum fremden `event_id` und die Klarstellung, dass „wie heute" für den
  koordinatenlosen Fall falsch wäre.
- `security-engineer` konsultiert (Schritt 3) — sicherheitsrelevant, zehn Auflagen, kein Blocker.

## Offene Fragen

Keine.

## Out of Scope

- **Motivwechsel als drittes Trennsignal** — setzt die Motive mit Stärke aus #427 voraus; die heutige
  Hauptkategorie taugt nicht als Ersatz, weil #427 genau sie abschafft. Die Event-Bildung ist so
  angelegt, dass das Signal ergänzt werden kann, ohne sie neu zu bauen.
- **Ortsnamen aus Koordinaten** (Reverse-Geocoding) — eigene Story nach Abschluss des Zielbilds #424.
- **Eine neue Ansicht** — wie die Oberfläche Events zeigt, entscheidet #430. Dass die bestehende
  Kuratierungsansicht ihre Überschriften aus der Gliederung bildet, ist gewollt, aber kein
  zusätzlicher Umfang.
- **Kalibrierung von `EVENT_EXTENT_MAX_METERS`** — der Wert ist bewusst unkalibriert und änderbar.
