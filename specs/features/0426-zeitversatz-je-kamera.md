# 0426 - Zeitversatz je Kamera korrigieren

**Status:** Implemented ([PR #445](https://github.com/TheRealKoller/photosort/pull/445))
**Erstellt:** 2026-09-12
**Bezug:** [Issue #426](https://github.com/TheRealKoller/photosort/issues/426), Story 2 des Zielbilds
[#424](https://github.com/TheRealKoller/photosort/issues/424); ADR
[`0090`](../decisions/0090-korrigierte-zeit-ist-die-aufnahmezeit-kamera-je-projekt.md)

**Umfang:** rund das Dreifache des Richtwerts von 200 Zeilen. Getragen wird das von drei
Abschnitten, deren Inhalt nirgends sonst steht: die Umsetzung über zehn Schritte von Backend,
Migration und Scan bis API und Frontend, fünf Sicherheitszusagen zur Bedeutungsumkehr von
`taken_at`, und ein Testnachweis je Umsetzungsschritt und je Lesestelle der Aufnahmezeit.

## Ziel

Ein Projekt entsteht aus zwei Geräten: dem Handy, dessen Uhr sich selbst stellt und das seinen Ort
kennt, und einer Kamera ohne Ortsbestimmung, deren Uhr von Hand gestellt wird. Steht diese Uhr auf
Heimatzeit, auf Winterzeit oder schlicht falsch, liegen ihre Fotos um Stunden neben den Handyfotos
desselben Moments.

Das hat zwei Folgen, und beide bleiben unbemerkt. Die zeitliche Gruppierung trennt Aufnahmen, die
zusammengehören. Und ein Kamerafoto, das keinen eigenen Ort mitbringt, übernimmt den Ort des
zeitlich nächsten Fotos seiner Gruppe — bei falsch gehender Uhr also den Ort eines ganz anderen
Moments. Es erscheint dabei keine Fehlermeldung; das Ergebnis sieht plausibel aus und ist falsch.

Diese Story gibt die Möglichkeit, die Abweichung einmal je Kamera zu benennen, statt sie in jedem
einzelnen Foto zu ertragen — und zwar ohne die Originalfotos anzufassen.

## User Story

Als Nutzer, der ein Projekt aus Handy- und Kamerafotos zusammenstellt, möchte ich die
Zeitabweichung einer Kamera einmal für dieses Projekt benennen, damit Aufnahmen desselben Moments
unabhängig vom Gerät zusammen gruppiert werden und Kamerafotos den Ort erben, an dem sie wirklich
entstanden sind.

## Akzeptanzkriterien

- [ ] Zu einem Projekt ist die Liste seiner Kameras abrufbar: je Kamera eine Bezeichnung, die
      Anzahl der Fotos **dieses** Projekts von ihr und der geltende Versatz. Die Liste entsteht
      aus den Fotos selbst, der Nutzer trägt keine Kamera ein. Dieselbe Kamera in einem anderen
      Projekt zählt nicht mit.
- [ ] Zu jeder dieser Kameras lässt sich ein Zeitversatz setzen: vorzeichenbehaftet, in beide
      Richtungen, auf die Minute genau, bis ±100 Jahre. Ein Wert jenseits dieser Grenze wird
      abgelehnt.
- [ ] Eine Kamera ohne je gesetzten Wert hat den Versatz `0`, und für jedes ihrer Fotos sind
      wirksame und aufgezeichnete Zeit gleich. Eine Kamera, die erst bei einem späteren Scan
      hinzukommt, beginnt ebenfalls bei `0`.
- [ ] Der Versatz gilt ausschließlich innerhalb des Projekts, in dem er gesetzt wurde. Dieselbe
      Kamera kann in einem anderen Projekt einen anderen oder gar keinen Versatz haben; eine
      Änderung verschiebt keine Aufnahmezeit eines anderen Projekts.
- [ ] Für jedes Foto einer Kamera mit Versatz gilt: wirksame Zeit = aufgezeichnete Zeit +
      Versatz. Auf dieser wirksamen Zeit arbeitet jede Stelle, die eine Aufnahmezeit liest — die
      zeitliche Gliederung, die Sortierung der Fotoliste, der Aufnahmezeitraum der Statistik und
      die Übernahme des Orts von einem Foto auf ein anderes. Je Stelle prüfbar an einem
      Datensatz, dessen Ergebnis mit gesetztem Versatz anders ausfällt als mit der
      aufgezeichneten Zeit.
- [ ] Die Originaldateien bleiben unverändert: der Ablauf greift ausschließlich lesend auf
      OpenCloud zu, und die aufgezeichnete Aufnahmezeit bleibt auch nach mehrfachem Ändern des
      Versatzes unverändert abrufbar.
- [ ] Die Fotoansicht zeigt die wirksame Zeit. Ist sie korrigiert, trägt sie eine Kennzeichnung
      und die aufgezeichnete Zeit samt Versatz steht daneben; bei Versatz `0` erscheint weder
      Kennzeichnung noch zweite Zeile.
- [ ] Der Nutzer kann den Versatz ausrechnen lassen, statt ihn zu schätzen: Er wählt zwei Fotos
      desselben Moments — eines von der betroffenen Kamera, eines von einer anderen —, und die
      Anwendung ermittelt daraus einen auf die Minute gerundeten Vorschlag und zeigt ihn an,
      ohne ihn zu speichern. Erst eine ausdrückliche Bestätigung setzt ihn; danach bleibt er von
      Hand änderbar. Derselbe Aufruf mit demselben Fotopaar schlägt denselben Wert vor, auch
      wenn inzwischen ein Versatz gilt.
- [ ] Ein gesetzter oder geänderter Versatz ist unmittelbar wirksam — in Gliederung,
      Reihenfolge, Statistik und Ortsübernahme —, ohne dass die Fotos erneut eingelesen werden:
      ohne jeden OpenCloud-Zugriff und ohne jeden Cloud-Aufruf (Aufrufzähler bleiben bei `0`).
      Läuft gerade eine Auswertung des Projekts, wird die Änderung abgelehnt statt teilweise
      angewandt.
- [ ] Fotos, deren Kamera sich nicht bestimmen lässt, bleiben ohne Versatz: ihre wirksame Zeit
      ist gleich ihrer aufgezeichneten, sie erscheinen in keiner Kameraliste, ein Versatz auf
      einer anderen Kamera verändert sie nicht, und jeder Lesepfad antwortet für sie fehlerfrei.

## Datenmodell-Bezug

Neue Entität `ProjectCamera` (`project_cameras`): Projekt × Kamera → Versatz in Minuten. `photos`
bekommt `taken_at_original`, `camera_id` (FK) und `camera_probed`. `Photo.taken_at` wechselt seine
Bedeutung zur korrigierten Zeit. Nachzutragen in
[`docs/architecture.md`](../../docs/architecture.md) im selben Pull Request.

## Architektur / Umsetzung

**Grundlage:** ADR [`0090`](../decisions/0090-korrigierte-zeit-ist-die-aufnahmezeit-kamera-je-projekt.md).
Die dortigen sechs Entscheidungen sind bindend; hier steht ihre Umsetzung.

**Die eine Wahrheitsquelle:** `Photo.taken_at` trägt ab jetzt die **korrigierte** Zeit und bleibt
„die Zeit, mit der die Anwendung arbeitet". Damit ändert sich an keiner der fünf Lesestellen etwas
— `assign_clusters` (Phase A), `build_events`, `infer_locations` (Worker **und** Lesepfad), die
SQL-Sortierung der Fotoliste, `min`/`max` der Statistik rechnen ohne eine Zeile Änderung mit dem
korrigierten Wert. Gruppierung, Reihenfolge und Ortsübernahme bekommen deshalb **keine** eigene
Korrekturlogik. `taken_at_original` tritt daneben und wird nie verschoben.

**1. Datenmodell und Migration** (`models.py`, `alembic/versions/<neu>.py` auf `f5a6b7c8d9e0`,
`project_deletion.py`)

- `ProjectCamera` (`project_cameras`): `id`, `project_id` (echter FK, NOT NULL), `make`, `model`,
  `offset_minutes: int` (NOT NULL, Vorgabe `0`), `UniqueConstraint(project_id, make, model)`.
  `Project.cameras` mit `cascade="all, delete-orphan"`.
- `photos` bekommt drei Spalten: `taken_at_original: datetime` (NOT NULL), `camera_id: int | None`
  (echter FK auf `project_cameras.id`, explizit benannt — `fk_photos_camera_id`), `camera_probed:
  bool` (NOT NULL, `server_default` in Migration **und** Modell, damit beide dieselbe DDL lesen).
- Migrationsablauf: `project_cameras` anlegen → `taken_at_original` nullable ergänzen → `UPDATE
  photos SET taken_at_original = taken_at` → auf NOT NULL setzen (`batch_alter_table`, sonst
  scheitert SQLite) → `camera_id` und `camera_probed` (`false` für Bestandszeilen) ergänzen. **Kein**
  Backfill der Kamera; das erledigt der nächste Scan über `camera_probed` (Punkt 4). `downgrade`
  schreibt `UPDATE photos SET taken_at = taken_at_original` **zurück, bevor** es die Spalten und die
  Tabelle entfernt — ohne diesen Schritt bleiben die korrigierten Zeiten stehen und die
  aufgezeichneten sind unwiederbringlich fort. Der Versatz ist danach fort, die rohen Zeiten stehen.
- `project_deletion.py`: `ProjectCamera` **nach** `photos`, **vor** `projects` (`photos` zeigt auf
  sie). `tests/project_graph.py::build_project_graph` legt eine `ProjectCamera`-Zeile an und
  verknüpft ein Foto damit, sonst prüfen die Vollständigkeitstests die neue Kante nicht.

**2. Neues Modul `backend/src/photosort/cameras.py`** — rein, DB-frei, vollständig unit-testbar,
Muster `events.py`.

```python
MAX_CAMERA_FIELD_LENGTH = 80
MAX_TIME_OFFSET_MINUTES = 52_560_000      # ±100 Jahre; Grenze am Endpunkt

@dataclass(frozen=True)
class CameraIdentity:  make: str; model: str

def camera_identity(make: object, model: object) -> CameraIdentity | None
def camera_label(identity: CameraIdentity) -> str
def shifted(original: datetime, offset_minutes: int) -> datetime | None
def suggested_offset_minutes(camera_original: datetime, reference_effective: datetime) -> int
```

- `camera_identity`: alles, was kein `str` ist, wird verworfen; Entfernen aller Zeichen der
  Unicode-Kategorien `Cc` und `Cf` (Begründung im Abschnitt Security, Punkt 1), Trimmen von
  Whitespace/NUL, innere Leerraumfolgen zu einem Leerzeichen; leer oder länger als
  `MAX_CAMERA_FIELD_LENGTH` gilt als nicht vorhanden. Beide nicht vorhanden → `None`. **Verworfen,
  nie abgeschnitten** — das Entfernen unsichtbarer Zeichen ist eine Normalisierung wie das
  Leerraum-Zusammenziehen und steht vor der Leer-/Längenprüfung.
- `camera_label`: beginnt `model` (ohne Beachtung der Schreibweise) mit `make`, gilt `model` allein,
  sonst `"make model"`; fehlt eines, gilt das andere. Die Beschriftung entsteht im **Backend** —
  eine Stelle entscheidet, wie eine Kamera heißt.
- `shifted`: `None` statt Ausnahme, wenn das Ergebnis außerhalb des darstellbaren Bereichs liegt.
- `suggested_offset_minutes`: auf die nächste Minute, Hälften vom Null weg, über ganzzahlige
  Sekundenarithmetik — **nicht** über `round()` (kaufmännisch vs. banker's).

**3. EXIF** (`opencloud/exif.py`) — `extract_camera(content) -> CameraIdentity | None` liest `Make`
(271) und `Model` (272) als benannte Konstanten aus **demselben** Range-Read-Fenster wie
`extract_taken_at`/`extract_gps` und gibt sie an `camera_identity` weiter; best-effort wie die
beiden Nachbarn (kein Lesefehler bricht einen Scan ab). Eine Logzeile nur im Verwerfungsfall, mit
festem Grund-Token und `photo_id` — **nie** der Rohwert.

**4. Scan** (`worker.py`)

- `ScanExifResult` bekommt `camera: CameraIdentity | None`. `_fetch_and_thumbnail` liest sie mit;
  neuer Parameter `probe_only: bool` überspringt **nur** `_generate_thumbnails` (die Thumbnails
  existieren und wären identisch).
- `_classify_scan_entries` (rein, bestehende Unit-Tests): unveränderter Etag **und**
  `camera_probed` → Skip wie bisher; unveränderter Etag **und nicht** geprüft → Arbeitsposten mit
  `probe_only=True`. Das ist die einmalige Nachhol-Runde für Bestandsfotos; sie zählt in
  `photos_updated` (die Zeile wird tatsächlich aktualisiert).
- `_process_scan_block`, sequentieller Teil nach dem `gather`: Kamera-Zeile über
  `_resolve_project_camera(session, project_id, identity, cache)` auflösen oder anlegen (Cache-Dict
  aus `run_project_scan` durchgereicht, sonst eine Abfrage je Foto), dann **unbedingt**
  `photo.camera_id`, `photo.camera_probed = True`, `photo.taken_at_original` und
  `photo.taken_at = shifted(original, offset) or original` schreiben. Unbedingt wie bei `gps_lat`:
  verliert eine Datei ihre Kamera-Angabe, verliert das Foto sie auch. Eine neu auftauchende Kamera
  bekommt `offset_minutes = 0`. Überlauf → unkorrigierte Zeit plus Warnzeile mit festem Token.

**5. Extraktion ohne Verhaltensänderung** (`worker.py`) — der Block „Event-Bildung + Partitionen +
Rangzeilen" aus `run_criterion_scoring` wird zu

```python
async def _build_grouping_and_rankings(
    session, run: CriterionScoringRun, project_id: int,
    values_by_photo_id: Mapping[int, dict[str, float]],
) -> None
```

Die Kandidatenmenge **ist** `values_by_photo_id.keys()`. Die Funktion liest alles Weitere selbst:
die Fotos des Projekts in **einer** Abfrage (Inferenzbasis **und** `taken_at`/`gps` der Kandidaten),
`_landmark_names`, `_remote_category_evidence`, `photo_scores.category_override`. Für den Lauf sind
das zwei Abfragen mehr **je Lauf** — der Preis dafür, dass es genau einen Weg zur Gliederung und zur
Hauptkategorie gibt. Die Dämpfungsregel (`None`, wenn Hauptzeile **und** Override) wandert als
`_partition_confidence(...)` in einen Helfer und ersetzt auch `reassign_photo_category::
_confidence_for` — dritte Fundstelle derselben Regel.

**6. Neuaufbau der Gliederung** (`worker.py::rebuild_run_grouping(session, project_id)`)

Letzten **erfolgreichen** `CriterionScoringRun` auflösen (keiner → nichts zu tun), seine
Rangzeilen-Fotos und deren `photo_criterion_scores`-Werte laden (`setdefault(photo_id, {})` für
jeden Kandidaten ohne Werte), keine Rangzeile → nichts zu tun. Dann `delete(PhotoRanking)` des
Laufs, `delete(Event)` des Laufs, `flush`, `_build_grouping_and_rankings(...)`. Weder `commit` noch
Transaktionsgrenze — die gehört dem Aufrufer (Muster `project_deletion`/`reassign_photo_category`).

Löschen und Neuschreiben statt Umhängen, weil `UniqueConstraint(criterion_scoring_run_id, position)`
alte und neue Events desselben Laufs nicht gleichzeitig zulässt. Kategorie-Zugehörigkeiten werden
**neu abgeleitet**, nicht aus den alten Zeilen übernommen. Prüfbare Zusage daraus: ein Neuaufbau mit
Versatz `0` erzeugt denselben Zustand wie der Lauf selbst.

**7. API**

- Neues Modul `api/cameras.py`, `APIRouter(prefix="/projects", tags=["cameras"],
  dependencies=[Depends(get_current_user)])` — router-weite Auth wie `api/stats.py`, anders als
  `api/photos.py`; in `main.py` eingehängt.
- `GET /projects/{project_id}/cameras` → `list[ProjectCameraOut {id, label, photo_count,
  offset_minutes}]`, sortiert nach `make`/`model`. Eine Abfrage: `outerjoin` auf `photos` mit
  **beiden** Bedingungen ausgeschrieben (`Photo.camera_id == ProjectCamera.id` **und**
  `Photo.project_id == project_id`), `group_by`, `func.count`. Fotos ohne bestimmbare Kamera
  erscheinen nicht als Eintrag und erzeugen keinen Fehler.
- `PUT /projects/{project_id}/cameras/{camera_id}/time-offset`, Körper `{offset_minutes: int}` mit
  `ge=-MAX_TIME_OFFSET_MINUTES, le=MAX_TIME_OFFSET_MINUTES` → `ProjectCameraOut`. **Eine**
  Transaktion, in dieser Reihenfolge: Kamerazeile mit `id` **und** `project_id` und
  `with_for_update()` laden (fremde Id → `404`, keine Rückspiegelung des Werts) → `409`, solange ein
  Vorgang dieses Projekts `RUNNING` ist, der in dieselben Zeilen schreibt: der
  `CriterionScoringRun` **und der Scan** (der schreibt `taken_at` ebenfalls und hält den Versatz je
  Lauf zwischengespeichert — ohne diesen Wächter schreibt ein weiterlaufender Scan die Zeiten mit
  dem alten Versatz zurück und bricht die Invariante still). Geprüft wird je Typ nur der neueste
  Lauf, Muster `api/projects.py::delete_project`, damit ein hängengebliebener Altlauf nicht
  dauerhaft blockiert → `(id, taken_at_original)` der Fotos dieser
  Kamera in diesem Projekt laden und `shifted` rechnen, ein `None` → `422` **ohne jedes Schreiben**
  → `taken_at` gebündelt schreiben (`session.execute(update(Photo), [...])`, ein Aufruf statt einer
  Anweisung je Zeile) → `offset_minutes` setzen → `rebuild_run_grouping` → ein `commit`. Kein
  früher Ausstieg bei unverändertem Wert; der Ablauf ist idempotent.
- `GET /projects/{project_id}/camera-time-offset-suggestion?photo_id=&reference_photo_id=` →
  `{camera_id, camera_label, offset_minutes, photo_taken_at_original, reference_taken_at}`. Beide
  Parameter `int` mit `ge=1` **und** Obergrenze im Muster von `_MAX_QUERY_POSITION`. Beide Fotos
  mit `Photo.project_id == project_id` ausgeschrieben laden (fehlt eines → `404`); `camera_id is
  None` am Kamerafoto → `422`; gleiche Kamera bei beiden → `422`; Ergebnis jenseits der Grenzen →
  `422`. **Nichts wird geschrieben** — die Übernahme ist der `PUT` oben.
- `api/photos.py`: `PhotoOut` bekommt `taken_at_original: datetime`, `time_offset_minutes: int`
  (aus der Differenz der beiden Zeitstempel, ganze Minuten von Konstruktion wegen; `0` heißt „nicht
  korrigiert") und `camera: CameraOut | None` (`{id, label}`, über `selectinload(Photo.camera)` in
  `_photos_by_id` — eine Abfrage mehr, unabhängig von der Fotoanzahl). `PhotoOut.taken_at` behält
  Namen und Form und liefert die korrigierte Zeit. Zusätzlich `GET /projects/{id}/photos?camera_id=`
  (optional, `ge=1` plus Obergrenze) als ein weiteres Prädikat in `_filtered_photo_ids` — ohne es
  kann die Oberfläche die beiden Fotos für den Vorschlag nicht anbieten.
- **Zwei Registerstellen, die einen neuen Router still übergehen:** `test_auth_guard.py`
  iteriert über eine feste Router-Liste, `test_openapi_beschreibungen.py` über eine eingefrorene
  Routenliste. Ein nicht eingetragener `cameras.router` fällt aus der 401-Vollständigkeitszusage
  bzw. der Beschreibungspflicht, **ohne** dass ein Test rot wird. Beide Eintragungen gehören in
  diesen Schritt.

**8. Demo-Seed** (`demo_state.py`) — `taken_at_original` für jedes Demo-Foto, zwei Kamerazeilen
(eine ohne Versatz, eine mit gesetztem Versatz, deren Fotos entsprechend verschobene `taken_at`
tragen) und einige Fotos mit `camera_id = None`.

**9. Frontend** — `api/types.ts`: `ProjectCameraOut`, `CameraOut`,
`CameraTimeOffsetSuggestionOut`, die drei neuen `PhotoOut`-Felder. Neu `api/cameras.ts` und
`hooks/useCameras.ts` (Liste + Mutation; die Mutation macht Kameraliste, Fotoliste,
Kuratierungskandidaten und Projektstatistik ungültig — ein Versatzwechsel vergibt neue Event-Ids,
der `clusterMetaRef`-Cache in `CurateCategoriesPage.tsx` darf sie nicht über die Änderung hinweg
halten). Neu `utils/timeOffset.ts`: `formatTimeOffset(minutes)` und die Umrechnung
Eingabefeld ↔ Minuten als reine, getestete Funktionen an **einer** Stelle.
`pages/ProjectSettingsPage.tsx` trägt den neuen Abschnitt (Kameraliste, Fotoanzahl, Versatzfeld,
Vorschlagsfluss mit Fotoauswahl über `listPhotos({ camera_id })`). `pages/PhotoDetailPage.tsx` zeigt
die wirksame Zeit, ihre Kennzeichnung als korrigiert und die aufgezeichnete Zeit — eine Aufnahmezeit
je Foto wird heute nirgends angezeigt, diese Stelle ist neu.

**10. Doku** — `docs/architecture.md` im selben Pull Request: Tabelle `project_cameras`, die drei
neuen `photos`-Spalten, die Bedeutungsumkehr von `taken_at` samt Invariante, der Neuaufbau der
Gliederung als zweiter Aufrufer derselben Funktion, die Nachhol-Regel des Scans.
`docs/setup.md` ist nicht betroffen (keine neue Umgebungsvariable, kein neuer Setup-Schritt).

**Reihenfolge der Umsetzung:** 1. `cameras.py` (rein) → 2. `extract_camera` → 3. Modelle/Migration/
Löschordnung → 4. Scan samt Nachhol-Regel → 5. Extraktion `_build_grouping_and_rankings`
(Verhalten unverändert, die grün bleibenden Bestandstests sind der Nachweis) → 6.
`rebuild_run_grouping` → 7. API → 8. Demo-Seed → 9. Frontend → 10. Doku.

## UI/UX

Keine neue Komponentenbibliothek und kein neues Token. Getragen wird alles von Vorhandenem:
`components/ui/dialog.tsx`, `components/ui/button.tsx`, das Dialog-Muster von
`DeleteProjectDialog.tsx`, `PhotoImage` für die Vorschaubilder und die Farbrollen `--text`,
`--text-muted`, `--info`, `--danger` aus `index.css`.

**1. Abschnitt „Kameras und Zeitversatz" in `pages/ProjectSettingsPage.tsx`** — unterhalb der
Cloud-Vision-Einstellung, oberhalb der Gefahrenzone. Je Kamera eine ruhige Zeile: Bezeichnung,
Fotoanzahl, aktueller Versatz (`formatTimeOffset`, bei `0` das Wort „kein Versatz" statt „0:00" —
eine Null liest sich wie ein gesetzter Wert), dazu eine Schaltfläche „Versatz ändern". Die
Bearbeitung selbst liegt **nicht** in der Zeile, sondern im Dialog unter Punkt 2: vier
Eingabefelder je Kamera nebeneinander wären bei mehreren Kameras unlesbar, und der Vorschlagsfluss
braucht ohnehin Platz.

Zustände: ladend (Skelettzeilen), keine Kamera im Projekt (erklärender Text, dass die Zuordnung
beim Scan entsteht — kein Fehlerton), Kamera ohne Versatz (Regelfall, keine Hervorhebung).

**2. Dialog „Zeitversatz für <Kamera>"** — trägt Handeingabe und Vorschlagsrechnung an einer
Stelle, damit ein Vorschlag in dieselben Felder fällt, die auch von Hand bedient werden.

- **Richtung als Klartext, nicht als Vorzeichen:** zwei Optionen, „Kamerauhr ging vor" (Zeiten
  werden zurückgestellt, negativer Versatz) und „Kamerauhr ging nach" (vorgestellt, positiv). Ein
  nacktes `+`/`−` ist die Stelle, an der eine Fehlbedienung den Fehler verdoppelt statt ihn zu
  beheben.
- **Drei Zahlenfelder: Tage, Stunden (0–23), Minuten (0–59).** Tage sind nicht Zierrat — eine
  Kamera mit zurückgesetzter Uhr steht Jahre daneben, nicht Stunden; eine Eingabeform, die nur
  Stunden kennt, kann den häufigsten schweren Fall nicht abbilden.
- **Lebende Vorschau an einem echten Foto dieser Kamera** (das erste der Liste): „aufgezeichnet
  12.08.2026 14:32 → wirksam 12.08.2026 13:32". Das ist die tragende Maßnahme gegen ein falsches
  Vorzeichen: Der Nutzer prüft das Ergebnis, nicht die Rechnung.
- **Vorschlag ausrechnen** als eigener, klar abgesetzter Teil des Dialogs: erst die
  **Referenzkamera** wählen (alle Kameras des Projekts außer dieser — das Handy *ist* eine Kamera
  der Liste, ein Filter auf „keine Kamera" träfe die Fotos mit unbestimmbarem Gerät), dann je
  Seite ein Foto aus einem waagerechten Vorschaustreifen mit Aufnahmezeit unter jedem Bild
  (`listPhotos({ camera_id })`); ohne die Zeit am Bild ist „derselbe Moment" nicht zu finden. Das
  Ergebnis erscheint in einem `--info`-umrandeten Kasten mit der Beschriftung „Vorschlag" und dem
  Satz, dass er noch nicht gilt.
- **Zwei getrennte Handlungen, damit „vorgeschlagen" und „gilt" nicht verwechselbar sind:**
  „Vorschlag übernehmen" füllt nur die Felder oben (und bleibt danach von Hand änderbar),
  „Versatz speichern" ist die einzige Schaltfläche, die schreibt.

Zustände im Dialog: ungültige Eingabe (Feldrand `--danger`, Meldung am Feld, Speichern gesperrt),
Speichern läuft (Schaltfläche gesperrt), `409` — ein Scan oder eine Auswertung des Projekts läuft,
Klartext „Ein Vorgang dieses Projekts läuft gerade; der Versatz kann danach gesetzt werden"
(die Meldung deckt beide Fälle ab), `422` — „Mit diesem Versatz
liegt die Aufnahmezeit eines Fotos außerhalb des darstellbaren Bereichs", mit dem ausdrücklichen
Hinweis, dass nichts gespeichert wurde. Ein Erfolg schließt den Dialog; die Liste zeigt den neuen
Wert. Weil ein Versatzwechsel die Gliederung neu aufbaut, darf die Wartezeit sichtbar sein.

**3. Abschnitt „Aufnahmezeit" in `pages/PhotoDetailPage.tsx`** — neue Anzeigestelle, keine
Kennzeichnung an einer bestehenden: eine Aufnahmezeit je Foto wird heute nirgends gezeigt.
Zeile 1 die wirksame Zeit in `--text`, bei `time_offset_minutes !== 0` gefolgt von einer
zurückhaltenden Marke „korrigiert" (Muster `CategoryOverrideMarker`, Ton `--text-muted`, kein
Alarmton — eine Korrektur ist der gewollte Zustand). Zeile 2 nur im Korrekturfall: „aufgezeichnet
<Originalzeit> · <Versatz>" in `--text-muted`. Dazu die Kamera-Bezeichnung; ist keine bestimmbar,
steht das als ruhiger Satz da und nicht als Fehlen.

**4. `utils/timeOffset.ts`** hält Formatierung, Umrechnung Felder ↔ Minuten und Validierung als
reine, getestete Funktionen an einer Stelle — keine dieser Rechnungen in einer Komponente.

## Security

Sicherheitsrelevant. Neu sind Fremdtext aus der Bilddatei in Datenbank **und** Oberfläche, eine
Datenmodell-Kante, die die Projektgrenze überschreiten könnte, und ein schreibender Endpunkt, der
Bestandsdaten großflächig ersetzt. Kein neues Secret, kein neuer Netzwerkpfad (`Make`/`Model`
kommen aus demselben Range-Read-Fenster wie Zeit und Koordinate), kein Cloud-Aufruf.

**1. `Make`/`Model` sind Fremdtext, auch wenn die Datei aus der eigenen Instanz kommt.** Der Wert
entsteht in einer Kamera-Firmware und erscheint als Kamera-Bezeichnung in Liste, Dialog und
Fotodetail. Der Angriff, gegen den hier etwas gilt, ist **nicht** XSS (React escaped Text, kein
`dangerouslySetInnerHTML`, keine HTML-String-Prop, und die Bezeichnung fließt in kein `href`,
`src`, `style` oder `url()`), sondern die **Verwechslung zweier Listenzeilen**: Die Bezeichnung ist
das einzige Merkmal, an dem der Nutzer die Kamera auswählt, deren Fotos er gleich umschreiben
lässt. Zusage: `camera_identity` entfernt vor der Leer-/Längenprüfung alle Zeichen der
Unicode-Kategorien `Cc` und `Cf` — Bidi-Overrides (U+202A–U+202E, U+2066–U+2069), Zero-Width
(U+200B–U+200D), U+FEFF, U+0085; U+2028/U+2029 fallen unter das Zusammenziehen der Leerraumfolgen.
Bleibt danach nichts Druckbares, gilt das Feld als nicht vorhanden. Damit ist die Alternative
„escapen und anzeigen genügt" für diesen Wert untersagt, obwohl sie beim OpenCloud-Dateinamen
zulässig ist: dort hängt keine Handlung am angezeigten Text, hier hängt die Auswahl daran. Bei
Verletzung: zwei optisch identische Zeilen in der Kameraliste und ein Versatz, der auf der
falschen Kamera landet, ohne dass etwas es anzeigt. Rohwerte bleiben aus jeder Logzeile (fester
Grund-Token plus `photo_id`), aus Spec, PR und Screenshots (dort nur Demo-Werte).

**2. Die Projektgrenze ist eine Zusage, keine Annahme.** Projekte haben keinen Eigentümer — jeder
angemeldete Nutzer sieht und ändert jedes Projekt, und zwischen den beiden Nutzern gilt kein
Innentäter-Modell. Geschützt wird deshalb die **Projekt**grenze (Kriterium 4), nicht eine
Nutzergrenze: Eine `camera_id` oder `photo_id` aus Projekt B, an einem Endpunkt von Projekt A
abgesetzt, darf weder Daten aus B zeigen noch in B schreiben. Zusage auf allen vier Pfaden — die
Projektbedingung steht ausgeschrieben in **derselben** Anweisung, die die Id auflöst:
`ProjectCamera.id` **und** `.project_id` im `GET` der Kameraliste und im `PUT`, `Photo.project_id`
bei **beiden** Foto-Ids des Vorschlags, und `camera_id` in der Fotoliste als weiteres **Prädikat**
neben dem vorhandenen `Photo.project_id == project_id` in `_filtered_photo_ids` — nie als
vorgeschaltete Auflösung der Kamerazeile, aus deren Fotos dann gelistet wird. Unbekannt und fremd
sind dieselbe Antwort (`404` bzw. leere Liste, ohne den Wert zu spiegeln), es entsteht also keine
Existenzauskunft über fremde Zeilen. Zweite Hälfte im Schreibpfad: `Photo.camera_id` zeigt
ausschließlich auf eine Zeile desselben Projekts. Bei Verletzung: Aufnahmezeiten eines fremden
Projekts werden lesbar, oder ein Versatz verschiebt die Zeiten fremder Fotos.

**3. Der schreibende Endpunkt ist der Hebel.** Ein Aufruf ersetzt `taken_at` **aller** Fotos einer
Kamera und verwirft Events und Rangzeilen des letzten erfolgreichen Laufs.

- *Alles oder nichts:* genau ein `commit` am Ende. `409`, `422`, ein Verbindungsabbruch und jeder
  Fehler im Neuaufbau lassen den Vorzustand unverändert — nie eine halb verschobene Fotomenge und
  nie eine Gliederung ohne Rangzeilen, denn diesen Zustand weist keine Ansicht als fehlerhaft aus.
- *Wiederholbar:* beide Schreibpfade rechnen `taken_at` ausschließlich aus `taken_at_original`.
  Untersagt ist damit „Differenz auf den bestehenden Wert addieren" — das kumuliert bei jedem
  weiteren Aufruf und ist nicht zurückrechenbar. Ein wiederholter Aufruf mit demselben Wert ist
  folgenlos, ein Aufruf mit verlorener Antwort darf wiederholt werden.
- *Nebenläufigkeit:* `with_for_update()` serialisiert zwei gleichzeitige `PUT`s unter PostgreSQL
  (unter SQLite wirkungslos, siehe Sicherheitskonzept). Tragend ist deshalb der `409`-Wächter, und
  er muss **jeden** laufenden Vorgang des Projekts erfassen, der in dieselben Zeilen schreibt —
  neben dem `CriterionScoringRun` ausdrücklich auch den **Scan**, der `taken_at` ebenfalls schreibt
  und den Versatz je Lauf zwischenspeichert. Sonst schreibt ein nach dem `PUT` weiterlaufender Scan
  für jedes noch verarbeitete Foto die Zeit mit dem **alten** Versatz zurück und bricht die
  Invariante `taken_at == taken_at_original + offset` still, bis irgendwann erneut gescannt wird.
- *Aufwand:* an die Fotozahl einer Kamera eines Projekts gebunden, ohne Cloud-Aufruf und ohne
  Bildverarbeitung. Keine Obergrenze auf der Fotozahl — der Endpunkt ist authentifiziert, beide
  Nutzer sind die Vertrauensbasis, und eine Grenze würde große Projekte vom Feature ausschließen.
  Bewusst getragen: ein Aufruf auf einem großen Projekt läuft lange und hält dabei Zeilensperren.

**4. Der Integritätsfall ist Datenverlust, nicht Datenabfluss.** `taken_at_original` ist die einzige
Kopie der aufgezeichneten Zeit; ein unverändertes, bereits geprüftes Foto wird nie wieder aus EXIF
gelesen, ein fehlerhafter Schreibpfad ist also dauerhaft und stumm. Zusagen: Der Wert wird
ausschließlich aus der Quelle geschrieben (EXIF `DateTimeOriginal`, sonst `last_modified`), **nie**
aus `taken_at`, und nach dem Setzen nie verschoben. Die Migration kopiert zu einem Zeitpunkt, an dem
es noch keinen Versatz gibt — die Kopie ist damit beweisbar der aufgezeichnete Wert. Das
`downgrade` schreibt `taken_at = taken_at_original` zurück, **bevor** es die Spalte entfernt; ohne
diesen Schritt behält die Datenbank die korrigierten Zeiten und die aufgezeichneten sind fort.

**5. Die Originaldateien bleiben unverändert — faktisch, nicht strukturell.** Die öffentliche
Oberfläche von `opencloud/client.py` enthält ausschließlich lesende Operationen (`PROPFIND`,
Range-`GET`, `GET`), aber `_send(method, …)` nimmt jedes Verb, und kein Test hält das fest. Diese
Story fügt keinen Zugriff und kein Verb hinzu; der Versatz lebt ausschließlich in
`project_cameras.offset_minutes` und ist durch Setzen auf `0` vollständig rücknehmbar. Bei
Verletzung wäre die einzige Kopie der aufgezeichneten Zeit **und** die Quelle zugleich verändert.

## Teststrategie

**Umfang:** über dem Richtwert von rund 60 Zeilen, weil die Zusage je Umsetzungsschritt und je
Lesestelle einen eigenen Nachweis braucht.

**Ebenen.** Schwerpunkt Unit auf `cameras.py` und `utils/timeOffset.ts` (DB- bzw. DOM-frei);
Integration gegen die In-Memory-SQLite für Migration, Scan, Endpunkte und Neuaufbau; keine neue
E2E-Spec — Dialog und Anzeige sind in jsdom vollständig prüfbar.

**Über allen Schritten: die Invariante.** `assert_time_offset_invariant(session, project_id)` läuft
als Nachsatz jedes Falls, der Fotos schreibt (Scan, Versatz-Endpunkt, Demo-Seed) — Muster
`assert_event_invariants`. Dazu ein struktureller Wächter: eine Zuweisung an `Photo.taken_at`
außerhalb von `worker.py::_process_scan_block` und `api/cameras.py` lässt ihn fehlschlagen. Eine
dritte Schreibstelle rötet keinen Verhaltenstest, solange sie den Wert irgendwie setzt.

**1. Datenmodell und Migration** — neu `tests/test_migration_kamera_zeitversatz.py` (Muster
`test_migration_events.py`): `down_revision == "f5a6b7c8d9e0"`; `project_cameras` mit Spaltenform,
`UniqueConstraint(project_id, make, model)` und echtem Fremdschlüssel auf `projects`;
`taken_at_original` nach dem `upgrade` **NOT NULL** und je Bestandszeile gleich ihrem **eigenen**
`taken_at` (Zeilen mit verschiedenen Zeitstempeln, sonst besteht eine Füllung mit einer Konstante);
`camera_id` nullable; `camera_probed` NOT NULL, `false` für Bestandszeilen, und ein `INSERT` ohne
die Spalte gelingt; `downgrade` schreibt die Zeitwerte zurück, entfernt Spalten und Tabelle, die
Versätze sind fort (eigener Fall plus Wächter, der die Unumkehrbarkeit im Migrationsmodul selbst
verlangt). `test_postgres_ddl_compatibility.py` bekommt einen Abschnitt: der `camera_probed`-Default
als Boolean-Literal (nicht `0`), `taken_at_original` als Zeitstempel ohne Zone und NOT NULL,
`fk_photos_camera_id` unter seinem expliziten Namen, `offset_minutes` als INTEGER,
`downgrade`-Render. `test_migration_chain.py` bleibt unverändert (ein Head). `test_models.py`:
Unique-Constraint greift, die `Project`-Kaskade löscht die Kamerazeilen, `camera_probed` trägt im
Modell denselben `server_default` wie in der Migration. `tests/project_graph.py` legt eine
`ProjectCamera`-Zeile an und verknüpft das Foto damit; `test_project_deletion.py` und
`test_api_projects.py` bekommen je eine eigene Zeilenzählung für die neue Tabelle.

Drei Stellen, an denen das bestehende Migrations-Muster nicht reicht: Die Bestandszeilen im
nachgebauten Vor-Schema tragen **je einen eigenen** `taken_at`-Wert — mit gleichen Werten besteht
eine Migration, die eine Konstante einträgt, jeden Test. Der `server_default` von `camera_probed`
ist **zwei** Artefakte und braucht zwei Assertions: Migrationsseite über den Postgres-Renderpfad
(SQLite akzeptiert `DEFAULT 0` auf einer Boolean-Spalte klaglos, Postgres bricht mit
`DatatypeMismatch` ab), Modellseite als `INSERT` ohne die Spalte gegen das aus `Base.metadata`
erzeugte Schema; fehlt die Modellseite, bleibt alles grün und der erste Schreibpfad, der die Spalte
nicht nennt, bricht produktiv. Und `fk_photos_camera_id` ist nur im Postgres-Render sichtbar —
ohne den expliziten Namen ist der `downgrade` nicht ausführbar.

**2. `cameras.py`** — neu `tests/test_cameras.py`, DB-frei, Schwerpunkt. Fälle unter „Edge Cases".

**3. `extract_camera`** — `test_exif.py`: Kamera aus demselben Fenster wie Zeit und Koordinate;
fehlendes `Make`/`Model` → `None`; abgeschnittenes Fenster und undekodierbare Bytes → `None` ohne
Ausnahme; eine Logzeile nur im Verwerfungsfall, mit festem Token und ohne Rohwert (`caplog`).

**4. Scan** — `test_worker_scan_classification.py` (rein): unveränderter Etag **und** geprüft →
Skip; unveränderter Etag **und nicht** geprüft → Arbeitsposten mit `probe_only=True`; geänderter
Etag bleibt voller Posten. `test_worker_scan_project.py`: Kamera, `taken_at_original` und
korrigiertes `taken_at` werden geschrieben; eine neu auftauchende Kamera startet bei `0`; ein Foto
ohne bestimmbare Kamera bekommt `camera_id = None` und gleiche Zeiten; eine Datei, die ihre
Kamera-Angabe verliert, verliert sie auch in der Zeile; dieselbe Kamera in zwei Projekten ergibt
**zwei** Zeilen, und jedes Foto zeigt auf die seines Projekts; Überlauf → unkorrigierte Zeit plus
Warnzeile mit festem Token; eine Abfrage je Kamera statt je Foto (`before_cursor_execute`).
Nachhol-Runde siehe „Edge Cases".

**5. Extraktion `_build_grouping_and_rankings`** — kein neuer Test und **kein Testdiff**: Nachweis
nach dem Verfahren „Nachweis ohne Rot-Grün" (identische Testknotenmenge mit identischem Ausgang,
`Stmts` je Datei unverändert). Eine angepasste Erwartung in `test_worker_criterion_scoring.py` ist
ein Befund, keine Nachpflege.

**6. `rebuild_run_grouping`** — neu `tests/test_worker_rebuild_run_grouping.py`: kein erfolgreicher
Lauf → nichts passiert; Lauf ohne Rangzeile → nichts passiert; **Versatz `0` erzeugt denselben
Zustand wie der Lauf selbst** (Aufbau unter „Edge Cases"); ein Versatz, der ein Foto über eine
Zeitlücke schiebt, ändert Abschnittszahl und Zugehörigkeit erwartungsgemäß; ein gesetzter
Kategorie-Override überlebt den Neuaufbau; die Funktion committet nicht (der Aufrufer sieht eine
offene Transaktion).

**7. API** — neu `tests/test_api_cameras.py`: Liste sortiert, mit Fotoanzahl, Fotos ohne Kamera
erscheinen nicht und erzeugen keinen Fehler, dieselbe Kamera in zwei Projekten zählt getrennt (der
Fall, der ein fehlendes `Photo.project_id`-Prädikat rötet), eine Abfrage unabhängig von der
Kameraanzahl. `PUT`: Erfolg samt verschobener Zeiten der eigenen und unberührter aller anderen
Fotos; `409` bei laufendem Kriterien-Lauf **und bei laufendem Scan** und `422` bei Überlauf je
**ohne jedes Schreiben** (Zeiten, `offset_minutes` **und** Event-Zeilen unverändert); `404` für
eine fremde Kamera-Id ohne Rückspiegelung des Werts; `±MAX` zulässig, `±MAX+1` → `422`; zweimal
derselbe Wert ist idempotent und baut trotzdem neu auf (geprüft am beobachtbaren Zustand nach dem
Aufbau, nicht an der Neuheit der Event-Ids — siehe die Begründung unter „Edge Cases"). Vorschlag: Erfolg mit
beiden Zeitfeldern, `422` bei Kamerafoto ohne Kamera, bei gleicher Kamera auf beiden Seiten und bei
Ergebnis jenseits der Grenzen, `404` bei fremdem Foto, und **nichts geschrieben**.
`test_auth_guard.py` nimmt `cameras.router` in seine 401-Vollständigkeitsprüfung auf,
`test_openapi_beschreibungen.py` die drei Routen in die eingefrorene Liste. `test_api_photos.py`:
die drei neuen `PhotoOut`-Felder, `time_offset_minutes = 0` heißt „nicht korrigiert", `taken_at`
liefert die korrigierte Zeit, `camera_id`-Filter samt Grenzen, Abfragezahl unabhängig von der
Fotoanzahl. `test_api_stats.py`: der Aufnahmezeitraum folgt dem Versatz ohne Codeänderung.
`test_scoring.py`/`test_events.py`: je ein Fall, dessen Gruppierung mit gesetztem Versatz anders
ausfällt als mit dem rohen Wert.

**8. Demo-Seed** — `test_demo_state.py`: alle Zustände, die die Oberfläche zeigen muss, entstehen
tatsächlich (Kamera ohne Versatz, Kamera mit Versatz, Foto ohne Kamera), und die Invariante hält
über alle geseedeten Zeilen.

**9. Frontend** — neu `src/utils/timeOffset.test.ts` (Formatierung, Umrechnung Felder ↔ Minuten,
Validierung; `0` als „kein Versatz" statt „0:00", Tage/Stunden/Minuten an ihren Rändern,
Rückrichtung als Umkehrprobe), `src/api/cameras.test.ts` (Pfade, Parameter, Fehlerdurchleitung),
`src/hooks/useCameras.test.tsx` (die Mutation entwertet Kameraliste, Fotoliste,
Kuratierungskandidaten und Projektstatistik — vier eigene Assertions),
`src/components/CameraTimeOffsetDialog.test.tsx` (je Richtung das **Vorzeichen** des an die
Mutation übergebenen Werts, Vorschau gegen die reine Funktion statt gegen einen abgeschriebenen
String, `409`/`422` als Klartext samt Hinweis „nichts gespeichert", Speichern gesperrt bei
ungültiger Eingabe, „Vorschlag übernehmen" schreibt nicht und lässt die Felder änderbar).
Erweitert: `ProjectSettingsPage.test.tsx` (Liste, Ladezustand, leerer Zustand ohne Fehlerton) und
`PhotoDetailPage.test.tsx` (wirksame Zeit, Marke nur bei Korrektur, aufgezeichnete Zeile nur im
Korrekturfall, ruhiger Satz ohne bestimmbare Kamera).

**10. Doku** — kein Testgegenstand.

**Edge Cases.**

- `shifted`: `datetime.min` mit `-1` und `datetime.max` mit `+1` → `None`; Versatz `0` auf beiden
  Rändern → der Rand selbst, **nicht** `None`; Mikrosekunden bleiben erhalten;
  `±MAX_TIME_OFFSET_MINUTES` auf einem mittleren Datum rechnet durch.
- `suggested_offset_minutes`: `30 s → 1`, `150 s → 3`, `29 s → 0`, `31 s → 1`, `0 s → 0`, und
  jeder Fall gespiegelt im Negativen (`-30 s → -1`, `-150 s → -3`). Die beiden mittleren Fälle
  sind die einzigen, die `round()` von „Hälften vom Null weg" trennen (`round` liefert `0` bzw.
  `2`); ein Satz aus 60/120/180 s bestünde mit jeder Implementierung. Ein Ergebnis jenseits der
  Grenzen wird **nicht** geklemmt — das Zurückweisen liegt am Endpunkt.
- `camera_identity`: `int`/`bytes`/`None`/Liste → verworfen; leer, nur Whitespace, nur NUL → nicht
  vorhanden; Bidi-Overrides, Zero-Width und U+FEFF werden entfernt, und ein Wert, der nur aus
  ihnen besteht, gilt als nicht vorhanden; zwei Werte, die sich nur in unsichtbaren Zeichen
  unterscheiden, ergeben **eine** Kamera; innere Leerraumfolge zu einem Leerzeichen;
  `MAX_CAMERA_FIELD_LENGTH` gültig, ein Zeichen mehr **verworfen statt abgeschnitten** (Assertion
  auf die Abwesenheit des Eintrags, nicht auf einen gekürzten); nur `make`, nur `model`, beides
  fehlend → `None`; die Längenprüfung greift je Feld, nicht an der zusammengesetzten Beschriftung.
- `camera_label`: `model` beginnt mit `make` ohne Beachtung der Schreibweise → `model` allein;
  `model` **enthält** `make`, beginnt aber nicht damit → beides; nur eines vorhanden → dieses.
- Fotos ohne bestimmbare Kamera: kein Listeneintrag und kein Fehler, `camera = null`,
  `time_offset_minutes = 0`, beide Zeiten gleich, als Kamerafoto im Vorschlag → `422`.
- Nachhol-Runde: der Merker wird **auch ohne Fund** gesetzt (sonst liest jeder Scan den Bestand
  erneut); ein unmittelbar folgender zweiter Lauf löst null Netzwerkzugriffe aus; die Runde
  erzeugt nachweislich **keine** Thumbnails (Aufrufzähler `0`); sie zählt in `photos_updated`;
  nach einem Fehlschlag tragen die abgearbeiteten Blöcke ihren Merker und der nächste Lauf liest
  nur den Rest.
- **Neuaufbau mit Versatz `0`** (die stärkste Zusage der Story): Fixture mit mindestens zwei
  Abschnitten (getrennt durch eine Zeitlücke), zwei Kategorien, einer Hauptzeile mit gesetztem
  Override, einem Foto mit Koordinate und einem am Ausschuss-Gate aussortierten Foto. Vollen Lauf
  fahren, Events und Rangzeilen als Tupel **ohne Ids** schnappschussen (Events nach `position`,
  Rangzeilen nach `(Event-position, category_key, rank_position)`), `rebuild_run_grouping`
  aufrufen, erneut schnappschussen: **gleich**. Im selben Fall nachweisen, dass die Zeilen
  **tatsächlich ersetzt** wurden — ohne diesen zweiten Teil bestünde ein `return` am
  Funktionsanfang die Zusage. Der Nachweis ist ein **Marker in einem Feld, das der Neuaufbau neu
  ableitet** (vor dem Aufruf gesetzt, danach fort), **nicht** eine Prüfung auf disjunkte
  Id-Mengen: SQLite vergibt nach einem `DELETE` dieselben `rowid`s erneut (kein `AUTOINCREMENT`),
  die Id-Zusage ist in dieser Suite also unerfüllbar, während sie unter PostgreSQL hielte. Über
  einer Fixture mit einem Abschnitt und einer Kategorie ist die Gleichheit fast trivial und der
  Fall leer.

## Entscheidungen

- **Die korrigierte Zeit lebt in `Photo.taken_at`**, `taken_at_original` tritt daneben (ADR 0090,
  Punkt 1). Die Gegenrichtung hätte jede der fünf Lesestellen umgestellt und wäre bei einer
  übersehenen still mit der falschen Uhr weitergelaufen — genau der Defekt dieser Story.
- **Ein Versatzwechsel gliedert den letzten erfolgreichen Kriterien-Lauf sofort neu**, in derselben
  Transaktion und ausschließlich aus persistierten Werten. Kriterium 9 verlangt Wirkung ohne
  erneutes Einlesen; „wirkt erst beim nächsten Kriterien-Lauf" wäre kleiner, ließe den Kernnutzen
  aber bis zu einem teuren Neulauf unsichtbar.
- **Kamera-Identität ist Hersteller + Modell, ohne Seriennummer.** Die Story spricht von „der
  Kamera", nicht vom Gehäuse. Getragene Kehrseite: zwei baugleiche Gehäuse im selben Projekt sind
  eine Kamera und teilen einen Versatz.
- **Bestandsfotos holt der Scan über den Merker `camera_probed` nach** — einmalig, nur das
  EXIF-Fenster, ohne Voll-Download und ohne Thumbnail-Neuerzeugung. Ohne das bliebe die
  Kameraliste in bestehenden Projekten leer und Kriterium 1 unerfüllt.
- **Die Eingabeform trägt Tage, Stunden und Minuten und benennt die Richtung im Klartext.** Eine
  Kamera mit zurückgesetzter Uhr steht Jahre daneben; eine Form, die nur Stunden kennt, kann den
  häufigsten schweren Fall nicht abbilden. Ein nacktes Vorzeichen ist die Stelle, an der eine
  Fehlbedienung den Fehler verdoppelt — dagegen steht die lebende Vorschau an einem echten Foto.
- **Das Referenzfoto kommt von einer anderen Kamera der Liste, nicht von „keine Kamera".** Das
  Handy ist eine Kamera; ein Filter auf `camera_id = null` träfe genau die Fotos mit
  unbestimmbarem Gerät.
- **`camera_identity` entfernt `Cc`/`Cf`-Zeichen**, bevor es auf leer und Länge prüft. Die
  Kamera-Bezeichnung ist das einzige Merkmal, an dem der Nutzer die Kamera auswählt, deren Fotos
  er umschreiben lässt; zwei optisch identische Zeilen führen den Versatz auf die falsche Kamera.
- **Der `409`-Wächter erfasst auch einen laufenden Scan**, nicht nur den `CriterionScoringRun` —
  der Scan schreibt `taken_at` ebenfalls und würde die Zeiten mit dem alten Versatz zurückschreiben.
- **Keine Obergrenze auf der Fotozahl des Versatz-Endpunkts.** Der Endpunkt ist authentifiziert,
  beide Nutzer sind die Vertrauensbasis, der Ablauf ist idempotent und kostet keinen Cloud-Aufruf.
  Getragen wird, dass ein Aufruf auf einem großen Projekt lange läuft.
- **Die Nachhol-Runde erbt die Ausfallbreite eines Erstscans:** ein dauerhaft unlesbares
  Bestandsfoto setzt den Lauf auf `FAILED`. Keine eigene Toleranz in dieser Story — die
  Risikoklasse ist gegenüber dem bereits getragenen Erstscan nicht neu, und die abgearbeiteten
  Blöcke tragen ihren Merker, der nächste Lauf liest nur den Rest.
- **Ein Wächtertest über `opencloud/client.py` gegen schreibende HTTP-Verben** würde „PhotoSort
  schreibt nie in eine Quelldatei" von faktisch auf strukturell heben. Nicht Teil dieser Story —
  er betrifft den Bestand, nicht diese Änderung, und gehört in eine eigene kleine Story.
- Alle vier Konsultationen (`architect`, `ux-ui-designer`, `test-engineer`, `security-engineer`)
  sind gelaufen; keine wurde übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Die Anwendung sucht **nicht** von sich aus nach Fotopaaren derselben Szene, um einen Versatz
  vorzuschlagen. Der Vorschlag entsteht ausschließlich aus einem Fotopaar, das der Nutzer selbst
  gewählt hat.
- Ein Versatz, der über Projektgrenzen hinweg gilt, vererbt oder vorgeschlagen wird.
- Zeitzonen als eigenes Merkmal. Abgebildet wird eine feste Zeitspanne je Kamera und Projekt, nicht
  eine Zeitzonenzugehörigkeit mit Sommer-/Winterzeitregeln.
