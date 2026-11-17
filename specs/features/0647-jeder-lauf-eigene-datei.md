# 0647 - Jeder Lauf hat seine eigene Datei

**Status:** Implemented ([PR #658](https://github.com/TheRealKoller/photosort/pull/658))
**Erstellt:** 2026-11-17
**Bezug:** Issue [#647](https://github.com/TheRealKoller/photosort/issues/647)

## Ziel

`worker.py` hat 4.952 Zeilen und mischt Scan, Export, Scoring, Kriterien-Bewertung,
Klassifizierung, Remote-Kategorien, das Aufräumen hängender Läufe und die Worker-Einstellungen.
`api/photos.py` hat 3.434 Zeilen, davon sind die ersten 1.610 Umwandlungs- und Lesehilfen; die
zwölf Endpunkte beginnen erst danach. Zusammen importieren 39 Dateien `worker` und 8 `api.photos`.

Wer an einem Lauf etwas ändert, liest 5.000 Zeilen Kontext, in dem sechs andere Läufe mitlesen,
und jede Verbesserung, die einen Teilschritt einzeln prüfen müsste, stößt auf eine Funktion mit
643 Zeilen, die nur als Ganzes startbar ist.

Ziel: Jeder Ablauf hat eine Datei. Für eine Änderung an einem Lauf liest man dessen Datei, nicht
das ganze Modul, und ein einzelner Teilschritt lässt sich prüfen, ohne den vollständigen Lauf zu
starten.

Dieser Abschnitt überschreitet den Umfangs-Richtwert einer Feature-Spec: zwei unabhängig
umsetzbare Stränge, sieben Läufe, zwölf Endpunkte und zwölf Wächter-Auswertungsstellen sind je
einzeln zu benennen, und die Patch-Ziel-Regel steht nirgends sonst.

## User Story

Als Entwickler dieses Projekts — Mensch wie KI — möchte ich, dass die beiden größten
Backend-Module nach ihren fachlichen Abläufen aufgeteilt sind, damit ich für eine Änderung nur
noch die Datei lesen muss, die den betroffenen Ablauf enthält, statt 5.000 Zeilen Kontext zu
laden, und damit Prüfungen einen einzelnen Teilschritt ansteuern können, ohne den ganzen Ablauf
zu starten.

## Akzeptanzkriterien

- [ ] **Verhalten unverändert.** Die gesamte bestehende Testsuite ist grün, ohne dass ein
      Testfall in Szene, Eingabe, Erwartungswert oder Zusicherung geändert, gelöscht,
      übersprungen oder als erwartet fehlschlagend markiert wurde. Wo ein Test die Ablage nennt
      (Importpfad, Patch-Ziel eines Modulnamens, Dateischlüssel eines strukturellen Wächters,
      Pfadangabe in einem Doku-Block), folgt dieser Bezug der neuen Ablage; die geprüfte Aussage
      bleibt wortgleich. Das Abdeckungs-Gate wird unverändert bestanden.
- [ ] **Die öffentliche Schnittstelle wächst nicht.** Andere Module beziehen danach dieselbe
      Namensmenge aus denselben Einstiegspunkten wie heute; kein Aufrufer muss ein neues
      Untermodul kennen, und kein Untermodul wird von außen direkt angesprochen. Der
      Worker-Prozess startet über denselben Aufruf wie heute, mit denselben fünf registrierten
      Jobs (Zeitlimit, kein Hintergrund-Wiederholversuch) und demselben einen Aufräum-Cron.
- [ ] **Die HTTP-Schnittstelle ist unverändert.** Ein Vergleich der Routentabelle der Anwendung
      vor und nach der Aufteilung zeigt dieselben zwölf Routen der Aufnahmen-Ansicht mit
      gleichem Pfad, gleicher Methode, gleichem Erfolgs-Statuscode, gleichem Namen des
      Antwortschemas (unqualifiziert) und gleicher Reihenfolge in der Routentabelle. Die bewusst
      je Endpunkt ausgeschriebene Absicherung bleibt sichtbar: die Aufteilung führt weder eine
      routerweite Absicherung ein noch lässt sie einen Endpunkt ohne Torwächter zurück.
- [ ] **Ein Zuhause je Lauf, keine Ringe.** Jeder der sieben Lauf-Einstiegspunkte
      (`run_project_scan`, `run_export`, `run_project_scoring`, `run_criterion_scoring`,
      `run_classification`, `run_remote_category_classification`, `reap_stalled_runs`) ist im
      Paket genau einmal definiert. Gemeinsam Genutztes (Lauf beenden, Abbruch prüfen,
      Fehlschlag melden, Phasenwechsel, Cloud-Kosten und -fehler verbuchen) liegt in einer
      gemeinsamen Schicht, nicht als Kopie in den Lauf-Dateien. Keine Lauf-Datei importiert eine
      andere im Kreis; die einzige Verkettung ist die des einen verketteten
      Klassifizierungs-Jobs, und sie bleibt an genau einer Stelle sichtbar.
- [ ] **Kriterien-Bewertung entflochten, Phasen einzeln prüfbar.** Die Kriterien-Bewertung ist
      keine 643-Zeilen-Funktion mehr: lokale Kriterien, Cloud und Sehenswürdigkeiten, Eye,
      Personen sowie Rangfolge und Auswahl sind je eine eigene benannte Einheit, und keine
      Funktion der beiden Bereiche liegt über 200 Zeilen (heute 643, 320, 247, 226, 223). Eine
      einzelne Phase lässt sich ausführen, ohne die übrigen Phasen und ohne den vollständigen
      Modellsatz aufzubauen. Jede Phase erhält den Modellsatz als **einen** Parameter; keine
      Phasensignatur nennt einen einzelnen Modell-Builder, und ein zusätzliches Modell ist ein
      Feld im Modellsatz plus seine Verwendung in genau einer Phase. Reihenfolge der Phasen,
      Abbruch- und Fehlschlag-Semantik sowie das geschlossene Verhalten der Cloud-Freigabe
      bleiben unverändert.
- [ ] **Endpunktgruppen nach Thema, Umwandlung getrennt.** Die Endpunkte der Aufnahmen-Ansicht
      liegen in thematisch geschnittenen Gruppen (Album-Entwurf, Album-Auswahl,
      Duplikat-Gruppen, Ausschuss, Entwurfs-Austausch, Bild), die Umwandlung in Ausgabeobjekte in
      einer eigenen Datei. Keine Endpunktgruppe importiert eine andere; gemeinsam genutzte
      Lesehilfen liegen an einer Stelle.
- [ ] **Die strukturellen Wächter bleiben scharf.** Die bestehenden Zusicherungen halten
      unverändert und nennen die neuen Ablagen: genau eine Funktion setzt den Phasenwechsel
      (beide Spalten gemeinsam), genau eine Stelle vergibt den Auswahlplatz, die Schreibstellen
      auf den Aufnahmezeitpunkt bleiben bei den zwei bekannten, die Aufrufstellen der
      Ausschuss-Prädikate bleiben je Prädikat und in Summe gleich (14 / 12 / 2), und die Liste
      der erlaubten Leser der Endauswahl-Entscheidung bleibt gleich (Gleichheit, nicht
      Obermenge). Kein Wächter wird weiter gefasst — insbesondere nicht von „genau eine Stelle"
      auf „mindestens eine".
- [ ] **Lebende Doku folgt, abgeschlossene Historie nicht.** Architektur-Doku, die lebenden
      Konzeptdokumente (`docs/architecture.md`, `specs/architecture/*.md`), Doku-Blöcke und
      Kommentare in `backend/src` sowie Docstrings in `backend/tests` nennen die neuen Ablagen;
      kein Pfadverweis dort zeigt auf eine nicht mehr existierende Datei. Abgeschlossene
      Feature-Specs, angenommene Entscheidungen und das Änderungsprotokoll werden nicht gelesen
      und nicht umgeschrieben.

## Datenmodell-Bezug

Keiner. `models.py` und die Alembic-Revisionen bleiben unberührt; es ändert sich ausschließlich
die Ablage von Code.

## Architektur / Umsetzung

Ansatz: [ADR 0149](../decisions/0149-ein-lauf-eine-datei-ein-einstiegspunkt.md). Zwei
voneinander unabhängige Stränge; jeder Schritt bleibt für sich grün, weil Patch-Ziele und
Wächter-Schlüssel im selben Schritt mitziehen.

### Gemeinsame Regel: Paket mit einem Einstiegspunkt

`worker.py` wird zu `photosort/worker/`, `api/photos.py` zu `api/photos/`. `__init__.py`
re-exportiert die heutige Namensmenge in einem ausdrücklichen `__all__`. Kein Aufrufer und kein
Test-Import ändert sich; ein Untermodul wird von außerhalb des Pakets nicht angesprochen —
einzige Ausnahme sind Monkeypatch-Ziele (siehe unten). Der Startbefehl
`python -m arq photosort.worker.WorkerSettings` bleibt; `WorkerSettings`, die fünf
`arq_func`-Jobs und der eine `cron(reap_stalled_runs, minute=set(range(0, 60, 5)),
run_at_startup=True)` bleiben Inhalt von `worker/__init__.py`. Alle Importe sind absolut.
`worker/__init__.py` bindet **jedes** Untermodul ein — daran hängen acht
`import_closure("photosort.worker")`-Zusicherungen (u. a. `test_persons_import_graph.py`,
`test_place_dataset.py`) und `test_album_stage.py`, das `photosort.eye_client` im
Einstiegspunkt selbst stehen sieht.

### Patch-Ziel ist die Nachschlagestelle

Ein `monkeypatch.setattr(worker, "<name>", …)` wirkt nur, wenn der Name dort nachgeschlagen wird,
wo er benutzt wird. Jeder Patch nennt deshalb das Untermodul, in dem der Name zur Laufzeit
nachgeschlagen wird. Namen, die nur **gelesen** werden (51 Namen für `worker`, 8 für
`api.photos`), bleiben über `__init__` erreichbar. Geteilte Namen der gemeinsamen Schicht werden
qualifiziert angesprochen (`import photosort.worker._runs as runs`; `runs._set_phase(...)`); ein
`from … import` erzeugte je Modul eine eigene Bindung und machte einen Patch still wirkungslos.

### Worker: ein Zuhause je Lauf

```
photosort/worker/
    __init__.py          WorkerSettings, 5 Jobs, 1 Cron, on_startup, Logging-Setup, __all__
    _runs.py             gemeinsame Schicht: logger, _now_utc, _set_phase, _fail_run,
                         _fail_export_run, _finish_cancelled, _take_over_queued_run,
                         _raise_if_cancel_requested, _finish_if_cancel_requested, _try_build,
                         _counted, _commit_phase_costs, Cloud-Fehler/-Kosten-Verbuchung,
                         _MAX_*-Konstanten
    scan.py              run_project_scan, scan_project, Block-/Thumbnail-/EXIF-Helfer,
                         Aspect-Ratio-Nachlauf, OpenCloudScanClient
    export.py            run_export, export_project, ExportClient, Namensaufbau, _parent_folders
    scoring.py           run_project_scoring, score_project, PhotoMetrics
    criterion_scoring.py run_criterion_scoring (Orchestrierung, Run-Kontext, ModelSet),
                         _start_criterion_scoring_run, rebuild_run_selection/-grouping,
                         _latest_successful_criterion_run, CriterionScoring*-Fehler
    _criterion/local.py  lokale Kriterienphase + Header-Schreiber, ContentCriteria
    _criterion/landmark.py  Sehenswürdigkeiten-Phase
    _criterion/eye.py       Eye-Phase
    _criterion/persons.py   Personen-Phase
    _criterion/ranking.py   Rangfolge + Auswahl, Places/Gazetteer-Fabriken
    remote_categories.py run_remote_category_classification, Kandidaten, Album-Eignung
    classification.py    run_classification, classify   ← einzige Verkettungsstelle
    stall_reaper.py      reap_stalled_runs, Schwellen, Stall-Prädikate, JOB_TIMEOUT_SECONDS
```

Importrichtung ohne Ring: alle Lauf-Dateien → `_runs`; `_criterion/*` → `_runs`;
`criterion_scoring.py` → `_criterion/*`; `classification.py` → `criterion_scoring`,
`remote_categories`, `_criterion/eye`; `__init__.py` → alle. Keine Lauf-Datei importiert eine
andere; die einzige Verkettung steht in `classification.py`. Fester Loggername
`photosort.worker` für alle Untermodule (der Logger entsteht in `_runs.py`) — 12 `caplog`-Stellen
prüfen `record.name`.

### Kriterien-Bewertung: Phasen statt 643 Zeilen

`run_criterion_scoring` behält Reihenfolge, Phasenwechsel und die
`try/except (RunCancelled, asyncio.CancelledError, Exception)`-Semantik. Es baut einmal einen
Run-Kontext (Session, Lauf, Projekt, Cache-Verzeichnis, Zeitpunkt, Kandidatenzeilen,
`candidate_values`, `area_fractions_by_photo_id`, `existing_criterion_scores`) und ruft die
Phasen in heutiger Reihenfolge: lokale Kriterien → Landmark (nur bei
`use_cloud and project.cloud_vision_detection_enabled and rows` — der geschlossene Wächter bleibt
im Orchestrator sichtbar) → Rangfolge/Auswahl (die Aufrufe `_build_grouping_and_rankings`,
`_recognize_persons`, `_apply_run_selection` bleiben als **blosse Namen** wörtlich im
Orchestrator, weil Wächter sie im Syntaxbaum so suchen) → Erfolgspfad (`status = SUCCESS`,
`_set_phase(None)`, `finished_at`).

Der **Modellsatz** (`ModelSet`, eingefrorene Dataclass mit den heutigen Builder-Feldern) wird im
Orchestrator einmal gebaut und jeder Phase als ein Parameter übergeben; jede Phase baut nur ihre
eigenen Modelle über `_try_build`. Die öffentlichen Signaturen von `run_criterion_scoring` und
`run_classification` bleiben unverändert — Tests lesen ihre Defaults.

Mit zerlegt werden die übrigen Funktionen über 200 Zeilen:
`run_remote_category_classification` (320), `run_project_scoring` (247), `run_classification`
(226) und `draft_alternatives` (223) — sonst bliebe die 200-Zeilen-Zusage wörtlich unerfüllt.

### Endpunkte: sechs Gruppen, eine Umwandlung, geteilte Lesehilfen

```
photosort/api/photos/
    __init__.py       router = APIRouter(tags=["photos"]), include_router in fester Reihenfolge,
                      Re-Exports (router, MAX_QUERY_POSITION, DuplicateGroupOut,
                      build_duplicate_group_out, MotifCorrectionIn, _suggestion_reason,
                      _selection_state_of), Abweichungs-Kommentar (keine routerweite Absicherung)
    _conversion.py    alle Out-Schemas und reine Umwandlung (PhotoOut, DuplicateGroup*,
                      AlbumDraftOut, Platz/Ereignis/Standort, Eye-, Motiv-, Ausschuss-Objekte,
                      RatingFilter)
    _reads.py         geteilte Lesehilfen: _get_project_or_404, _photos_by_id,
                      _event_and_location_by_photo_id, _final_selection_decisions,
                      _latest_successful_criterion_scoring_run_id, _ranking_by_photo_id,
                      _auto_decided_ids, _filtered_photo_ids, PlacedPhotos, RunEvents,
                      MAX_QUERY_POSITION
    album_draft.py    album_draft, list_photos, _draft_photo_ids, Entwurfsmengen
    album_selection.py album_selection, _participants
    duplicate_groups.py beide Duplikat-Endpunkte, build_duplicate_group_out, Index
    ausschuss.py      beide Ausschuss-Endpunkte, Ausschuss-Objekte, _ausschuss_reason
    draft_exchange.py draft_alternatives, _exchange_sides, DraftExchange(In|Out), Undo(In|Out)
    image.py          get_photo_image, Motiv-Korrektur (set/delete), MotifCorrection*, _get_photo_or_404
```

Keine Gruppe importiert eine andere; jede ist ein `APIRouter()` **ohne** `dependencies`. Jeder
der zwölf Endpunkte behält `current_user: User = Depends(get_current_user)` und seinen
ausgeschriebenen Sicherheitskommentar. `tags=["photos"]` trägt der Aggregat-Router. Die
Einbindereihenfolge entspricht der heutigen Registrierungsreihenfolge (album-draft, photos,
album-selection, duplicate-groups, ausschuss, draft-alternatives, draft-exchange,
draft-exchange/undo, image, motif-corrections), damit `create_app().openapi()` auch in der
Reihenfolge gleich bleibt. `api/duplicate_decisions.py` importiert unverändert aus
`photosort.api.photos`. `list_photos` bleibt bei `album_draft.py` — die Mengen- und Lesehilfen
liegen dort, und die Reihenfolge der Routentabelle bleibt unberührt.

`test_auth_guard.py::_protected_router_operations()` bekommt `photos.router` **nicht**: Seit
FastAPI 0.162.1 liefert `include_router` `_IncludedRouter`-Objekte ohne `routes`; die
Parametrisierung wäre leer und der Test still grün. Der Vollständigkeitsnachweis kommt aus dem
Routentabellen-Test (Teststrategie 4(a)).

### Wächter, die die Ablage nennen

Alle Zeilen gegen den Code geprüft. Verbote lesen paketweit, Erlaubnisse nennen Datei und
Funktion.

| Wächter | Auswertungsstelle nachher |
|---|---|
| `test_models.py:1458` `_ALLOWED_TAKEN_AT_WRITERS` | `{"worker/scan.py", "api/cameras.py"}` |
| `test_models.py:1562` `_ALLOWED_SELECTION_POSITION_WRITERS` | `{"worker/_criterion/ranking.py"}` |
| `test_models.py:2340` `_ALLOWED_PHASE_WRITER_MODULES` | `{"worker/_runs.py", "demo_state.py"}` |
| `test_models.py:2088` `_ALLOWED_DECISION_MODEL_READERS` | `api/photos/_reads.py::_final_selection_decisions`, `api/photos/album_selection.py::album_selection` |
| `test_models.py:2486` `_worker_source()` | Vereinigung über `worker/**/*.py`, **je Datei** ausgewertet (nicht Quelltexte aneinandergehängt) |
| `test_ausschuss_ueberlebende.py` `_ERWARTETE_VERWENDUNGEN` | `worker/_criterion/eye.py` 1, `worker/criterion_scoring.py` 1, `worker/remote_categories.py` 1; `api/photos/_conversion.py` 2, `api/photos/album_draft.py` 1, `api/photos/ausschuss.py` 2 — Summe 14, SQL 12, Objekte 2 |
| `test_selection.py:1318` `_SELECTING_MODULES` | alle Dateien beider Pakete, **aufgezählt** (kein Glob) |
| `test_api_motif_corrections.py:597` | `api/photos/image.py`, Slice ab `async def set_motif_correction` |
| `test_worker_rebuild_run_grouping.py:611/808/822` | Paketquellen, Funktionssuche je definierender Datei |
| `test_worker_criterion_scoring.py:6218` Landmark-Wächter | liest `worker/criterion_scoring.py`, `_place_infos` bleibt dort blosser Name |
| `test_worker_persons.py:662/677` | `PhotoPersonCorrection`/`person` paketweit verboten; positive Hälfte `_criterion/persons.py` |
| `test_worker_place_names.py:1485` | `rebuild_run_grouping`/`run_criterion_scoring` paketweit, Aufruf als blosser Name |
| `test_album_stage.py:223` | bleibt grün, weil `worker/__init__.py` `photosort.eye_client` selbst importiert |

Für die Modulquellen-Wächter kommt **eine** Hilfsfunktion `package_files(module)` in
`tests/import_closure.py` dazu: alle `.py` unter dem Paket, bei einem Modul die eine Datei.

### Reihenfolge

Worker: **W1** `worker.py` → `worker/__init__.py` (Wächter-Schlüssel mit), **W2** `_runs.py` +
qualifizierte Zugriffe + fester Loggername, **W3** `stall_reaper`, `export`, `scan`, `scoring`,
**W4** `remote_categories`, `_criterion/*` + `criterion_scoring`, `classification`, **W5**
Modellsatz + Zerlegung auf ≤ 200 Zeilen.
Endpunkte: **P1** `api/photos.py` → `api/photos/__init__.py`, **P2** `_conversion`/`_reads`,
**P3** sechs Gruppen + Aggregation + Zerlegung von `draft_alternatives`. Danach die Doku-Pfade
(AK8).

### Abnahme

`pytest -n auto --cov=photosort --cov-fail-under=80` bleibt unverändert bestanden; `ruff check`,
`ruff format --check` und `mypy src` laufen über die neuen Dateien. `mypy` verlangt `__all__` für
die re-exportierten privaten Namen (`_set_phase`, `_fail_run`, `_try_build`, …).

## UI/UX

nicht relevant — reine Umverteilung von Backend-Code; die HTTP-Schnittstelle bleibt nach
Akzeptanzkriterium 3 unverändert, keine Frontend-Datei wird berührt.

## Security

Sicherheitsrelevant, obwohl sich die Schnittstelle nicht ändert: Für `/photos/*` hängt die
Absicherung **nur** am `current_user: User = Depends(get_current_user)` der jeweiligen
Endpunktsignatur. `photos.router` trägt bewusst keine routerweite `dependencies`-Liste, und
`test_auth_guard._protected_router_operations()` führt ihn nicht. Ein Endpunkt, der beim
Verschieben seinen Parameter verliert, ist still öffentlich — ohne Fehler, ohne 401. Zwölf solcher
Parameter wechseln die Datei.

Kein neuer Endpunkt, keine neue Methode, kein neuer Pfad, kein neues Secret, kein neuer externer
Empfänger; JWT, Rate-Limit, CORS und Rollenmodell unverändert.

| # | Zusicherung | Prüfung |
|---|---|---|
| S1 | Jeder der zwölf Endpunkte behält seine ausgeschriebene Dependency, in derselben Form. | Neu: je Handler der Paketquellen ein Parameter mit `Depends(get_current_user)` (strukturell, weil `_IncludedRouter` die Route-Objekte verbirgt). 10 der 12 Endpunkte haben heute einen pfadbenannten 401-Fall, `GET /projects/{id}/photos` und `GET /photos/{id}/image` keinen. |
| S2 | Kein Router dichtet routerweit ab: alle sechs Gruppen-Router **und** das Aggregat tragen `dependencies == []`. | Derselbe Wächter: kein `APIRouter(...)`/`include_router(...)` im Paket übergibt `dependencies=`. Ohne diesen Teil wäre S1 durch eine Router-Dependency scheinbar erfüllbar. |
| S3 | Die Routenmenge bleibt exakt: zwölf Operationen, gleiche Methode, gleicher Pfad, gleicher Erfolgs-Statuscode, gleiches Antwortschema, gleiche Reihenfolge. | Routentabellen-Schnappschuss aus `create_app().openapi()` mit Selbstschutz `len == 12`; ergänzend unverändert `test_openapi_beschreibungen.py`. |
| S4 | Gemeinsame Grenz-Helfer werden verschoben, nicht kopiert: `_get_project_or_404`, `_filtered_photo_ids`, `_draft_photo_ids`, `_exchange_sides`, `_ausschuss_reason`, `_album_level_source`, `_participants`, `_to_photo_out`, `build_duplicate_group_out` je genau einmal; kein Router baut eine zweite Projekt- oder Sichtbarkeitsbedingung. Eine Kopie wäre eine zweite, driftende Grenze — Ausfallrichtung: kohärent aussehende Menge fremder Fotos. | `test_ausschuss_ueberlebende.py`, `test_models.py` (Endauswahl-Leser), unveränderte Prädikate und Summen, neue Dateischlüssel. |
| S5 | Die Sichtbarkeitsgrenze zwischen den beiden Nutzern bleibt gleich: `_to_photo_out` bekommt weiter `current_user.id`, `build_duplicate_group_out` behält `current_user_id`, `_participants` bleibt die Zwei-Spalten-Projektion, Antwortformen byte-gleich. | Unverändert: `test_api_photos.py` (Antwort hängt vom Anfragenden ab, Teilnehmer-Form), `test_api_duplicate_groups.py`. |
| S6 | Eingabegrenzen reisen mit: `MAX_QUERY_POSITION` weiter über den Paket-Einstieg geteilt, `PathParam(ge=1, le=MAX_QUERY_POSITION)` unverändert, `variant` bleibt `Literal["thumbnail", "display"]` (Allowlist gegen Path-Traversal). | Unverändert die Grenzfall-Tests; der Schnappschuss friert Pfade und Methoden. |
| S7 | Wächter, die eine Datei lesen, verlieren mit dem Umzug nicht ihren Griff (ADR 0149 Punkt 9). | Tabelle „Wächter, die die Ablage nennen"; `test_selection.py` zählt Dateien auf, statt zu globben — ein Glob wäre grün mit null Abdeckung. |
| S8 | Der Worker-Teil bringt keine neue Angriffsfläche: kein neuer Empfänger, kein neues Secret, Logger bleibt auf `photosort.worker`, die vier cloud-bestimmenden Prädikatsstellen bleiben vier. | Unverändert: `test_ausschuss_ueberlebende.py`, `test_models.py`, `test_worker_*`. |

Der Abweichungs-Kommentar („kein Vollständigkeitstest") wandert nach `photos/__init__.py` und
wird dort präzisiert: Das Vollständigkeitsnetz prüft jetzt die **Anwesenheit** der
ausgeschriebenen Dependency an allen zwölf Operationen, nicht die Nutzerabhängigkeit der Antwort.

Nachzupflegen in `specs/architecture/0003-securitykonzept.md` (aussagegleich, nur Pfad): Zeilen 4,
116, 117, 124, 125, 126, 130, 142–144, 151, 175, 181, 189, 200, 201, 240, 460, 505, 510, 543, 575,
745, 1072, 1364, 1539. Nicht nachzupflegen: 1060, 1064, 1278, 1643 (die genannten Funktionen
existieren seit der entfallenen Kategorie-Übersteuerung nicht mehr — vorbestehende Drift) und
1415, 1423, 1441 (`photos.router` bleibt der Aggregat-Router).

## Teststrategie

Die Story ändert Ablage, nicht Verhalten. Drei Zusagen brauchen je einen eigenen Nachweis:
*nichts am Verhalten* (AK1), *nichts an der öffentlichen Fläche* (AK2–AK7), *kein Verweis ins
Leere* (AK8).

### Verhalten unverändert (AK1)

Abnahme unverändert: `pytest -n auto --cov=photosort --cov-fail-under=80`, `ruff check`,
`ruff format --check`, `mypy src`. Das Gate bleibt ein Summenwert über `photosort`.

Nachweis über den Vorher-Nachher-Vergleich aus
[`0002-testkonzept.md`](../architecture/0002-testkonzept.md) gegen `origin/main`:

1. **Identische Testknoten-Menge** (`pytest --collect-only -q`, sortiert verglichen). Einzige
   Ausnahme: die zwei Parametrisierungs-Schlüssel `worker.py`/`api/photos.py` in
   `test_selection.py` werden durch die 24 Dateischlüssel der beiden Pakete ersetzt — derselbe
   Knoten, derselbe Prüfkörper, nur der Dateischlüssel ist die Ablage.
2. **Identischer Ausgang je Knoten** (`pytest -q --tb=no`, Ausgang je Knoten-ID gegenübergestellt,
   nicht „grün" — ein umgebungsbedingter Fehlschlag darf vorher wie nachher fehlschlagen).
3. **`Cover` je Paket nicht niedriger.** Über `coverage json`: `worker.py` 95,17 % → `worker/**`
   95,84 %, `api/photos.py` 70,9 % → `api/photos/**` 75,0 %. Die Summe `Stmts` kann nicht gleich
   bleiben — jedes Untermodul trägt eigene Importe, die Dateien `__init__.py` ihre Re-Exporte
   (+272 bzw. +124); der Nachweis gegen Code-Verlust ist deshalb (2) plus die Wächter über
   Einstiegspunkte und Funktionslängen, nicht die Statement-Zahl.

**Kein Testfall inhaltlich geändert** wird mechanisch geprüft, nicht per Blick: Jede geänderte
Zeile unter `backend/tests/` darf sich ausschließlich in Zeichenfolgen ändern, die einen
Ablage-Bezug nennen — Paket → Untermodul, Dateipfad-Schlüssel, `module_file(...)` →
`package_files(...)`, Modulobjekt als Patch-Ziel, Name in Doku-Block oder Prüfmeldung. Alles
andere (Zahl, Vergleich, Fixture-Aufbau, neuer `assert`) ist ein Finding. Hinzugefügte Zeilen
entstehen nur in den neuen Testdateien, in `package_files` und in Wächter-Konstanten. Die Regel
fängt auch eine Aufweichung an `_ALLOWED_*` — eine Mengenänderung ist kein Ablage-Bezug.

Gemessener Umfang: 54 Patch-Ziele in 14 Testdateien (26 verschiedene Namen, keines als
Zeichenkette adressiert), 12 Dateischlüssel, 43 Importanweisungen, 51 öffentliche Worker-Namen.

### Neue Tests — nur diese

| Datei | Zusicherung | Gefangene Fehlklasse |
|---|---|---|
| `backend/tests/test_route_table_photos.py` | eingefrorene Folge von zwölf `(Methode, Pfad, Erfolgs-Statuscode, Schemaname unqualifiziert, Tags)` aus `create_app().openapi()`; dazu: jeder dekorierte Handler hat `Depends(get_current_user)`, kein `APIRouter`/`include_router` übergibt `dependencies=` | Route verschwindet, ändert Pfad/Methode/Status/Schema oder Reihenfolge (statische Route hinter `…/{project_id}/…` fängt den falschen Handler); Endpunkt ohne Torwächter; routerweite Absicherung (andere 401/422-Reihenfolge) |
| `backend/tests/test_worker_package_boundary.py` | kein Modul außerhalb der Pakete importiert ein Untermodul; in `backend/tests` erscheint ein importiertes Untermodul nur als Patch-Ziel; `__all__` deckt die beobachtete Namensmenge und ist auflösbar; kein Test hängt einen Namen auf dem Paket um; die sechs Themengruppen importieren einander nicht | zweiter Einstiegspunkt; verschwundener Name (`ImportError` beim Start); `__all__`-Eintrag ohne Objekt; Patch am Paket, der keinen Aufrufer erreicht; Querimport zwischen Gruppen |
| `backend/tests/test_criterion_phases_standalone.py` | jede Phase mit `ModelSet`, dessen übrige Builder `pytest.fail` werfen, ohne andere Phase und ohne `run_criterion_scoring` | Phase greift auf Modell/Zustand einer anderen Phase zu |
| `backend/tests/test_function_length_limit.py` | Syntaxbaum über beide Pakete, ≤ 200 Zeilen je Funktion | Rückfall in den Monolithen, den kein Verhaltenstest bemerkt |
| `backend/tests/test_worker_import_graph.py` | kein Zyklus; genau eine Lauf-Datei mit paketinternen Importen (`classification.py`); erlaubte Kantenklassen; `__init__` erreicht jedes Untermodul; jeder der sieben Einstiegspunkte genau einmal definiert | zweiter Verkettungsort; Zyklus reisst den arq-Start ab; zweite Definition eines Laufs |
| `scripts/tests/test_doku_pfade_existieren.py` | gelesen: `docs/architecture.md`, `specs/architecture/*.md`, Docstrings/Kommentare in `backend/src`, Docstrings in `backend/tests`; jeder Quellpfad-Token zeigt auf eine existierende Datei, `::name` auf eine Top-Level-Definition; ein Pfad, den die Git-Historie als geloescht kennt, zaehlt als Historie; `worker.py`/`api/photos.py` kommen dort nicht mehr vor | Verweis ins Leere (heute 61 in `docs/architecture.md`, 84 in `0003-securitykonzept.md`, 47 in `0002-testkonzept.md`) |

Verworfen: exakte Dateiliste je Paket (nagelt Ablageform fest), Zeilen pro Datei (Zusage gilt je
Funktion), `__all__` als eingefrorene Liste (blockierte Wachstum statt es zu prüfen), Prüfung,
dass `_conversion.py` keine Endpunkte enthält (beschreibt Ablage, nicht Verhalten), zweiter
401-Durchlauf über alle zwölf Pfade (pfadbenannte Fälle existieren), OpenAPI-Text-Schnappschuss.

### Fallen für die Umsetzung

- Ein Name in zwei Lauf-Dateien ist nach der Aufteilung nicht mehr mit einem Patch zu treffen
  (`throttle_for_provider`, `build_eye_client`, `build_label_embedder`). Ein am Einstiegspunkt
  belassener Patch ist still wirkungslos; der Test bleibt grün, weil er nur das Fehlen einer
  Wirkung behauptet.
- Default-Argumente binden beim `def`: `build_*`-Vorgabewerte werden in der Datei nachgeschlagen,
  die das `def` trägt.
- `caplog` prüft `record.name`; Kind-Logger brechen 12 Zusicherungen ohne Verhaltenstest.
- `_place_infos`, `_build_grouping_and_rankings`, `_recognize_persons`, `_run_eye_phase` müssen in
  ihrem Modul als blosse Namen stehen — vier Wächter suchen `ast.Name`.
- Ein falscher Dateischlüssel in `_ERWARTETE_VERWENDUNGEN` ist ein `FileNotFoundError`, kein roter
  `assert`; er wird als Ablage-Fehler behoben, nicht durch Streichen des Eintrags.
- `create_app()` in einer Fixture benutzen (wie `test_openapi_beschreibungen.py`), nicht das beim
  Import erzeugte `app`-Objekt.

### Testkonzept

`specs/architecture/0002-testkonzept.md` bekommt zwei Ergänzungen: (1) im Abschnitt „Nachweis ohne
Rot-Grün" die vierte Regel für reine Ablage-Änderungen — Ablage-Bezug darf sich ändern, der
Nachweis ist die Wortdiff-Klassifikation, und `Stmts`/`Cover` werden paketweise verglichen; (2) im
Backend-Abschnitt die Routentabelle als Schnappschuss aus `create_app().openapi()` samt Grund,
warum nicht über `router.routes`.

## Entscheidungen

- architect konsultiert (Schritt 1): Ansatz und Aufteilung in
  [ADR 0149](../decisions/0149-ein-lauf-eine-datei-ein-einstiegspunkt.md) — Paket mit einem
  Einstiegspunkt, gemeinsame Schicht `_runs.py` qualifiziert angesprochen, Patch-Ziel ist die
  Nachschlagestelle, fester Loggername, Modellsatz als einziger Einhängepunkt, Verbote paketweit,
  Erlaubnisse dateigenau.
- ux-ui-designer nicht konsultiert (Schritt 2): Die Story berührt keine sichtbare Oberfläche —
  kein Frontend-Code, keine neue Darstellung, HTTP-Antworten byte-gleich.
- test-engineer konsultiert (Schritt 3): Teststrategie oben; geschärft wurden AK3 (Erfolgs-
  Statuscode, Reihenfolge), AK4 (genau einmal definiert), AK5 (Modellsatz als ein Parameter;
  Zahlen 643/320/247/226/223), AK7 (Gleichheit statt Obermenge) und AK8 (welche Dokumente
  „lebend" sind). Befunde gegen die Architektur: `survives_ausschuss` im Kriterien-Lauf steht in
  `criterion_scoring.py`, nicht `local.py`; der Wächter heißt `_ALLOWED_DECISION_MODEL_READERS`;
  drei weitere Wächter (`test_worker_persons.py`, `test_worker_place_names.py:1485`) brauchen
  Nachzug, sonst wären sie nach W1 grün und blind; `test_auth_guard` darf `photos.router` nicht
  bekommen.
- security-engineer konsultiert (Schritt 3): Security-Abschnitt oben. Pflicht-Wächter für die
  Anwesenheit der Dependency je Endpunkt und die Leere der Router-`dependencies`.
- `classification.py` bindet `criterion_scoring`, `remote_categories` und `_criterion/eye` ein —
  die einzige Stelle, an der die Verkettung sichtbar ist.
- `list_photos` bleibt bei `album_draft.py` (Mengen und Lesehilfen liegen dort, Routenreihenfolge
  bleibt); fachlich wäre „Bild" vertretbar, das verschöbe aber `create_app().openapi()`.
- `run_classification` (226) und `draft_alternatives` (223) werden mitzerlegt, obwohl die Story
  sie nicht namentlich nennt: sonst bliebe die 200-Zeilen-Zusage wörtlich unerfüllt.
- Der Modellsatz ist eine eingefrorene Dataclass im Orchestrierungsmodul, keine neue Abstraktion
  über die Phasen; die öffentlichen Signaturen von `run_criterion_scoring`/`run_classification`
  bleiben unberührt.

## Offene Fragen

Keine.

## Out of Scope

- `models.py` und die kleineren Module (`demo_state`, `event_probe`, `events`, `api/projects`,
  `api/classification_reviews`)
- Das Freistellen privater Funktionen und das Umstellen der Testimporte (eigenes Thema, direkt
  anschließend)
- Das Kürzen von Kommentaren und Docstrings (eigenes Thema, danach)
- Aufteilen der großen Testdateien (eigenes Thema, danach)
