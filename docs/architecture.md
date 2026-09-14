# Architektur-Übersicht

**Status:** Living Document (kein Lifecycle, wird laufend aktualisiert)
**Letzte Aktualisierung:** 2026-09-10
**Umfang:** über dem Richtwert von rund 300 Zeilen, weil je Komponente und je Entität die
Zusicherungen mitstehen, die aus dem Modell allein nicht ablesbar sind.

## Systemkontext

PhotoSort verwaltet keine eigenen Bilddateien dauerhaft — die Fotos bleiben auf einer externen
**OpenCloud**-Instanz. PhotoSort speichert Metadaten, Bewertungen und einen lokalen
Verarbeitungs-Cache (Thumbnails).

![Systemkontext: OpenCloud, Backend, Postgres, Redis, Worker, Frontend](../specs/diagrams/component-overview.svg)

<sub>Diagramm-Quelle: [`specs/diagrams/component-overview.d2`](../specs/diagrams/component-overview.d2), gerendert per `scripts/render-diagrams.sh` (siehe ADR [`decisions/0013-diagram-tooling-d2.md`](../specs/decisions/0013-diagram-tooling-d2.md)).</sub>

## Komponenten

- **Frontend** (`frontend/`): React + TypeScript + Vite, als PWA installierbar. Kommuniziert
  ausschließlich über die Backend-API (kein direkter OpenCloud-Zugriff vom Client aus, um App-Tokens
  nicht im Browser zu exponieren). Routing (`react-router`) und Server-State/Datenzugriff
  (`@tanstack/react-query` über einen schlanken Fetch-Wrapper, `api/client.ts`) gemäß
  [`decisions/0004-frontend-app-shell.md`](../specs/decisions/0004-frontend-app-shell.md) — mit Spec
  0006 (Auth) eingeführt (Login-Route/geschützte Routen benötigten bereits Routing), Spec 0005 baut
  die restlichen Projekt-Routen direkt darauf auf. `api/client.ts` hängt bei vorhandenem Token
  automatisch `Authorization: Bearer <token>` an (Token aus `localStorage`, siehe
  [`decisions/0005-auth-implementation.md`](../specs/decisions/0005-auth-implementation.md)) und
  löst bei 401-Antworten zentral die Abmeldung/Weiterleitung zu `/login` aus.
  - neue Komponente `components/CloudVisionStatusList.tsx` + permanente Sektion in
    `PhotoDetailPage.tsx`.
  - die deutschen Kategorie-Bezeichnungen kommen aus `GET /categories` (react-query, langlebiger
    Cache — das Set ändert sich nur per Deployment);
    `categoryLabels.ts::CATEGORY_DISPLAY_NAME_OVERRIDES` entfällt, der generische Fallback bleibt
    nur noch für Altwerte historischer `PhotoRanking`-Zeilen.
    `CurateCategoriesPage.tsx::sortCategoryKeys` sortiert nach Registry-Reihenfolge statt
    alphabetisch (`nicht_erkannt` immer zuletzt), die Override-Auswahl bietet das vollständige Set
    statt der erkannten Kandidaten, Feinlabels erscheinen als Chips am Foto.
  - **Motive statt Kategorien im Frontend (Spec
    [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
    [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md)):**
    `CategoryBadge`/`CategorySelect`/`SecondaryCategoryMarker`/`CategoryOverrideMarker`,
    `utils/categoryLabels.ts`, `hooks/useCategories.ts` und `hooks/useCategoryOverrideControls.ts`
    entfallen — ebenso `api/categories.ts`, `utils/confidenceLabels.ts`,
    `components/CurationPhotoTile`s Kategorie-Anteil und `pages/CurateCategoriesPage.tsx` — und
    werden durch `MotifStrengthList` (alle acht Motive mit Stärke und Korrekturschaltern, bedienbar
    in der Detailansicht, schreibgeschützt im Kachel-Popover), `pages/CuratePage.tsx` sowie
    `hooks/useMotifs.ts`/`hooks/useMotifCorrection.ts` und `utils/motifLabels.ts` ersetzt. **Auf der
    Kachel steht kein Motiv**: acht Werte haben dort keinen Platz, und der stärkste allein
    behauptete wieder die Zuordnung, die diese Spec ablöst — der einzige neue Kachelmarker ist
    `components/MotifAssessmentMarker.tsx` („Motive noch nicht bestimmt"). **Am Einzelwert erscheint
    kein Bandwort** (Bänder gibt es nur in der aggregierten Statistiktabelle). Die Kuratierung
    gruppiert nur noch nach Tag und Foto-Moment — die Kategorie-Ebene der Gruppierung fällt weg.
    Anzeigenamen, Reihenfolge und Bandgrenzen kommen aus `GET /motifs`; das Frontend spiegelt sie
    nicht.
  - die Projektnavigation liegt in der Kopfzeile der `AppShell` statt am Seitenende — neues
    `utils/projectRoutes.ts` als einzige Quelle der Wahrheit für "welcher Pfad hat Projektkontext"
    (speist die `<Route>`-Erzeugung in `App.tsx`, die `projectId`-Ermittlung der Kopfzeile und die
    Ableitung des aktiven Navigationsziels) und neues `components/ProjectNav.tsx` als die Leiste
    selbst. Reines Frontend, kein API-Delta.
  - die Zieltabelle ist in Haupt- und Nebenziele geteilt — die Leiste führt ab `lg:` nur noch
    Projekt, Fotos und Endauswahl, ein einziger Auslöser (bei jeder Breite genau einer im DOM) öffnet
    den Nebenbereich mit Einstellungen und Statistik; unterhalb `lg:` führt sein Panel alle fünf
    Ziele in zwei abgesetzten Blöcken. `utils/projectRoutes.ts` führt sie dafür in zwei Gruppen
    (`PROJECT_NAV_PRIMARY_TARGETS`, `PROJECT_NAV_SECONDARY_TARGETS`, `ALL_PROJECT_NAV_TARGETS` als
    abgeleitete Verkettung); der Name `PROJECT_NAV_TARGETS` entfällt bewusst, damit sich die
    Bedeutung eines Bezeichners nicht still unter allen Aufrufstellen ändert. Ebenfalls reines
    Frontend, kein API-Delta, keine neue Route.
  - die Klassifizierungs-Sektion zerfällt in einen Container (`ClassificationSection.tsx` —
    Checkbox, Consent-Gate, Mutation, Auslöser) und drei neue Blöcke: `ClassificationEstimate.tsx`
    (aufgeschlüsselte Kostenvorschau inkl. Anbieter/Modell und der „nicht schätzbar"-Aussage),
    `ClassificationProgress.tsx` (Teilschrittliste mit je eigenem Fortschritt, abgesetzten Aufrufen
    und Fehlschlägen) und `ClassificationBalance.tsx` (Bilanz des zuletzt abgeschlossenen
    Durchlaufs). Unterhalb des Auslösers steht zu jedem Zeitpunkt **genau einer** der beiden
    Zustandsblöcke — Fortschrittsliste oder Bilanz, nie beide; das ist die prüfbare Form des
    Akzeptanzkriteriums „überfrachtet die Seite nicht". Die Ableitung „welche Teilschritte hat
    dieser Lauf, in welchem Zustand, mit welchem Fortschritt" liegt in einem reinen, unit-getesteten
    Modul `utils/classificationSteps.ts` (Muster `pipelineSteps.ts`), nicht im JSX. **Eine
    Währungsformatierung im Produkt:** das lokale `$1.23`-Format entfällt, Schätzung und Bilanz
    nutzen `utils/formatStats.ts::formatUsd` — zwei Formate direkt nebeneinander unterliefen das
    Akzeptanzkriterium „tatsächliche Kosten gegen die Schätzung einordenbar". `api/types.ts`
    typisiert alle neuen Felder pflichtig als `| null` (kein `?`), damit `tsc` die Behandlung der
    Unbekannt-Fälle erzwingt; ein `?? 0` im Pfad ist damit ein Typfehler statt eines stillen „0,00
    USD". Die vierte Polling-Bedingung in `hooks/useProjects.ts` entfällt mit
    `last_remote_category_classification_run` ersatzlos und wird nicht ersetzt — der
    Klassifizierungslauf ist während des GESAMTEN verketteten Durchlaufs `running`, die verbleibende
    Bedingung deckt seine Remote-Phase mit ab.
- **Backend** (`backend/`): FastAPI. REST-API für Projekte, Fotos, Bewertungen; Auth (JWT,
  `Authorization: Bearer`-Header, kein Cookie); Anbindung an OpenCloud via WebDAV; stößt
  Hintergrund-Jobs im Worker an.
  - `/opencloud/browse`, `/projects` (CRUD + Scan-Trigger), OpenCloud-Client (`opencloud/client.py`,
    `opencloud/webdav_xml.py`, `opencloud/exif.py`). `ProjectOut` trägt die Bestandszahlen
    `photo_count`/`taken_at_earliest`/`taken_at_latest`; `GET /projects` lädt sie für **alle**
    Projekte in **einer** gruppierten Abfrage (`photo_aggregates.py`), nicht je Projekt.
  - `POST /auth/login`, `get_current_user`-Dependency (Argon2/PyJWT gemäß
    [`decisions/0005-auth-implementation.md`](../specs/decisions/0005-auth-implementation.md)),
    `/projects`- und `/opencloud`-Router sind auth-pflichtig (Router-Level-Dependency).
  - `GET /projects/{id}/photos` (Listing/Filter/Pagination), `GET /photos/{id}/image`
    (Thumbnail-/Display-Streaming aus dem lokalen Cache), `PUT`/`DELETE /photos/{id}/rating`
    (`api/photos.py`, `api/ratings.py`) — auth-pflichtig per Endpoint-Dependency statt
    Router-Level-Dependency, da beide Router mehrere URL-Präfixe bedienen und den `User` ohnehin für
    die Bewertungszuordnung brauchen.
  - `POST /projects/{id}/score` (`api/projects.py`, analog `POST /projects/{id}/scan`, gleicher
    Router-Level-Auth-Guard), `PhotoOut.suggestion` (`api/photos.py`, nur befüllt ohne eigenes
    `Rating`), `ProjectOut.last_scoring_run` (analog `last_scan`). `POST
    /projects/{id}/confirm-ausschuss-gate` (synchron, idempotent, projektweit), `GET
    /projects/{id}/photos?top_n_per_category=N` (Top-N je Partition),
    `ProjectOut.last_criterion_scoring_run`, `ScoringRunSummary.id`/`.gate_confirmed_at`,
    `PhotoOut.ranking`/`RankingOut`.
  - `GET /opencloud/folder-counts?path=<Pfad>` (gleicher Router-Level-Auth-Guard wie
    `/opencloud/browse`) zählt parallel
    (`asyncio.Semaphore(settings.opencloud_folder_count_concurrency)`, Default 4) die rekursive
    Bilddatei-Anzahl je direktem Unterordner über einen Early-Exit-Konsum von
    `OpenCloudClient.walk()` (`api/opencloud.py::_count_images_up_to_limit`, Obergrenze
    `FOLDER_COUNT_LIMIT = 500`) — `GET /opencloud/browse` selbst unverändert. `IMAGE_EXTENSIONS`
    liegt öffentlich in `opencloud/client.py`: Der Request-Pfad (`api/opencloud.py`) darf
    strukturell nicht von `worker.py` abhängen, das `mediapipe`/`tensorflow` nachzieht. `PUT
    /projects/{id}/cloud-vision-consent` (`api/projects.py`, Body `{"enabled": bool}`, am
    Router-Level-Auth-Guard) setzt
    `Project.cloud_vision_detection_enabled`/`.cloud_vision_consent_at` synchron (Zeitstempel bei
    Aktivierung, `NULL` bei Deaktivierung); beide Felder stehen zusätzlich auf `ProjectOut`.
    Derselbe Schalter gated Sehenswürdigkeits- **und** Kategorie-Erkennung — kein zweiter Consent.
    `PUT`/`DELETE /photos/{id}/category-override` (`api/photos.py`); `PUT` nimmt `{"category_key":
    "<canonical_key>"}` entgegen.
  - additiv `PhotoOut.cloud_vision_status: list[CloudVisionStatusOut]` (`api/photos.py`, kein neuer
    Endpunkt); die volle Prioritäts-Kaskade steht in ADR 0035.
  - zwei neue, rein lesende Endpunkte — `GET /categories` (eigener Router `api/categories.py`,
    Router-Level-Auth: liefert das feste Kategorien-Set in Registry-Reihenfolge mit
    `key`/`display_name`/`definition`/`locally_available`; das Frontend spiegelt das Set bewusst
    NICHT) und `GET /projects/{id}/fine-labels` (`api/projects.py`: nach Häufigkeit sortierte
    Feinlabel-Liste des Projekts als Änderungspfad für das Set). `PUT
    /photos/{id}/category-override` validiert seither gegen `categories.py::is_known_category` statt
    gegen die foto-skopierte Erkennungsmenge (`422` bei unbekanntem Key, `409` weiterhin ohne
    `PhotoRanking`-Zeile im aktuellen Lauf); `_photo_category_candidate_keys` entfällt. `PhotoOut`
    trägt `fine_labels: list[FineLabelOut]`, `remote_category: str | None` und `category_candidates`
    (nur Set-Keys mit `origin`, ohne `score`).
  - **Motive statt Kategorien (Spec [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
    [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md)):**
    `GET /categories` wird `GET /motifs` (neuer Router `api/motifs.py`, gleicher Router-Level-Auth)
    und liefert die acht Motive in Registry-Anzeigereihenfolge samt der beiden Bandgrenzen der
    Statistik und je Motiv `locally_assessable` (aus `LOCAL_MOTIF_SIGNALS` abgeleitet: kann die
    lokale Erkennung dieses Motiv überhaupt beurteilen) — das Frontend spiegelt nichts davon. `PUT`/`DELETE
    /photos/{id}/motif-corrections/{motif_key}` (Body `{"applies": bool}`) ersetzt
    `PUT`/`DELETE /photos/{id}/category-override`; der Schlüssel wird gegen
    `motifs.py::is_motif_key` validiert (`422` sonst), und das `409` der fehlenden
    `PhotoRanking`-Zeile entfällt — eine Korrektur hängt am Foto, nicht am Lauf. `409` bleibt
    ausschließlich die Abbildung eines `IntegrityError` aus dem Unique-Constraint, damit ein
    gleichzeitiger `PUT` beider Nutzer auf dasselbe Paar nicht als `500` herauskommt; eine Sperre
    gibt es dafür nicht. `PhotoOut` trägt statt
    `remote_category`/`category_confidence`/`category_candidates`/`category_override` die Felder
    `motif_assessment: MotifAssessmentOut | None` (`source`, `excluded_document`, `provider`,
    `computed_at`; `None` heißt „noch nicht klassifiziert") und `motifs: list[MotifStrengthOut]`
    (acht Einträge in Registry-Reihenfolge mit `key`, `strength` als **wirksamer** Stärke,
    `correction: bool | None` und — seit Spec
    [`0430`](../specs/features/0430-album-entwurf-je-nutzer.md) — `present: bool`; leer, solange
    keine Kopfzeile existiert). Die überstimmte
    Modellzahl geht bewusst **nicht** mit: die Oberfläche darf sie neben dem Korrekturwort nicht
    zeigen, und ein Feld ohne Leser verschiebt nur die Frage, was es bedeutet. Der
    Kuratierungsparameter hieß bis Spec 0429 `top_n_per_event` (siehe die Ablösung weiter unten),
    und `GET /projects/{id}/curation-candidates` verliert `category_key` — die Partition ist allein
    das Event. `GET /projects/{id}/stats` liefert `motifs` (je Motiv `strong_count`/`medium_count`/
    `weak_count`/`average_strength`), `strength_bands`, `motif_correction_count`,
    `unassessed_photo_count` und `excluded_photo_count` statt `categories`/`category_confidence`/
    `manual_category_override_count`.
  - `POST /projects/{id}/classify` (Body `{scoring_run_id: int, use_cloud: bool}`, kein Default für
    `use_cloud`) ist der EINE Auslöser der Klassifizierung — Vorbedingungen unverändert von
    `score-criteria` übernommen (`403` Feature-Flag, `404` unbekanntes Projekt, `409` ohne
    erfolgreichen `ScoringRun`/ohne bestätigtes Gate/bei veralteter `scoring_run_id`), neu `403` bei
    `use_cloud=true` ohne projektweite Einwilligung. `GET /projects/{id}/classify/estimate` liefert
    zusätzlich `remote_category_candidate_count`/`landmark_candidate_count`, deren Summe
    `candidate_count` ist (neuer Helfer `_count_landmark_candidates`, wertet
    `criteria.py::is_landmark_candidate` gegen die bereits gespeicherten Kriterien-Werte aus —
    strukturell eine Schätzung, vor dem ersten Lauf eines Projekts 0). Kein hinterlegter Preis
    heißt `null`, nie `0` — `ClassificationEstimateOut.price_per_image_usd`/`.estimated_cost_usd`
    sind entsprechend nullable, dazu das Feld `model`. `CriterionScoringRunSummary` trägt additiv
    `phase`/`cloud_requested`/`cloud_error_message`.
  - neues Router-Modul `api/stats.py` mit dem einzigen Endpunkt `GET /projects/{project_id}/stats` —
    reine Leseleistung über Bestandsdaten, löst keinen Lauf aus und schreibt nichts. Auth doppelt:
    `current_user` als expliziter Parameter (der Bewertungsstand ist die erste rein personenbezogene
    Aggregatzahl der Anwendung und wird ausschließlich über `Rating.user_id == current_user.id`
    ermittelt) UND `dependencies=[Depends(get_current_user)]` am Router, damit ein künftiger zweiter
    Endpunkt dieses neuen Moduls nicht ungeschützt bleiben kann. Der geschätzte Datenbank-Anteil
    läuft über eine Dialekt-Weiche (`session.get_bind().dialect.name == "postgresql"`, kein
    try/except um fehlschlagendes SQL); außerhalb Postgres ist der Wert `null`, nicht `0`. Die
    Cache-Messung (`thumbnails.py::measure_cache_usage`) läuft über `asyncio.to_thread`.
  - neues Router-Modul `api/cameras.py` *(Spec
    [`0426`](../specs/features/0426-zeitversatz-je-kamera.md))* mit drei Endpunkten und
    router-weiter Auth wie `api/stats.py`: `GET /projects/{id}/cameras` (Kameraliste mit
    Fotoanzahl und geltendem Versatz, **eine** Abfrage — der `outerjoin` trägt
    `Photo.camera_id == ProjectCamera.id` **und** `Photo.project_id == project_id`
    ausgeschrieben, sonst zählte dieselbe Kamera die Fotos eines fremden Projekts mit),
    `PUT /projects/{id}/cameras/{camera_id}/time-offset` und
    `GET /projects/{id}/camera-time-offset-suggestion` (rein lesend, speichert nichts). Dazu trägt
    `GET /projects/{id}/photos` den optionalen Filter `camera_id` — als weiteres **Prädikat**
    neben `Photo.project_id`, nie als vorgeschaltete Auflösung der Kamerazeile.
    - Der Versatz-Endpunkt ist **alles oder nichts** mit genau **einem** `commit`, in dieser
      Reihenfolge: Kamerazeile mit `id` **und** `project_id` und `with_for_update()` laden (fremde
      Id → `404`, ohne Rückspiegelung des Werts) → `409`, solange ein `CriterionScoringRun`
      **oder ein Scan** dieses Projekts `RUNNING` ist → alle Zeiten rechnen, ein einziger Überlauf
      → `422` **ohne jedes Schreiben** → `taken_at` gebündelt schreiben (ein
      `session.execute(update(Photo), [...])`) → `offset_minutes` setzen → `rebuild_run_grouping`
      → committen. Ein `409`, ein `422`, ein Verbindungsabbruch und jeder Fehler im Neuaufbau
      lassen den Vorzustand unverändert; es entsteht nie eine halb verschobene Fotomenge und nie
      eine Gliederung ohne Rangzeilen — diesen Zustand weist keine Ansicht als fehlerhaft aus.
    - **Der `409`-Wächter erfasst ausdrücklich auch den Scan**, nicht nur den Kriterien-Lauf: der
      Scan schreibt `taken_at` ebenfalls und hält den Versatz je Lauf zwischengespeichert. Ohne
      ihn schreibt ein nach dem `PUT` weiterlaufender Scan für jedes noch verarbeitete Foto die
      Zeit mit dem **alten** Versatz zurück und bricht die Invariante still, bis irgendwann erneut
      gescannt wird. Geprüft wird je Typ nur der neueste Lauf (Muster `delete_project`), damit ein
      hängengebliebener Altlauf nicht dauerhaft blockiert.
    - Der Ablauf ist **wiederholbar**: beide Schreibpfade rechnen `taken_at` ausschließlich aus
      `taken_at_original`. Kein früher Ausstieg bei unverändertem Wert — ein Aufruf mit verlorener
      Antwort darf wiederholt werden. Keine Obergrenze auf der Fotozahl (authentifiziert, beide
      Nutzer sind die Vertrauensbasis); bewusst getragen: ein Aufruf auf einem großen Projekt
      läuft lange und hält dabei Zeilensperren.
    - `PhotoOut` bekommt `taken_at_original`, `time_offset_minutes` (aus der Differenz der beiden
      Zeitstempel; `0` heißt "nicht korrigiert") und `camera: CameraOut | null`
      (`selectinload(Photo.camera)` — eine Abfrage mehr, unabhängig von der Fotoanzahl).
      `PhotoOut.taken_at` behält Namen und Form und liefert die korrigierte Zeit; der brechende
      Bedeutungswechsel ist beabsichtigt.
  - `DELETE /projects/{project_id}` (`api/projects.py`, Body `{"confirm_name": "<string>"}` mit
    `max_length=500`, hängt am bestehenden Router-Level-Auth-Guard, **kein Owner-Check**) löscht ein
    Projekt und alle PhotoSort-eigenen Daten daran — die Original-Fotos auf OpenCloud bleiben
    unangetastet. Reihenfolge der Prüfungen: `404` → `409` (einer der **vier** letzten Läufe ist
    `RUNNING`; ein nicht mehr aktueller `RUNNING`-Altlauf blockiert nicht) → `400`
    (`confirm_name.strip() != project.name`, case-sensitiv — serverseitig getrimmt, im Frontend
    bewusst nicht) → `(photo_id, etag)`-Paare lesen → Mengenlöschung + genau ein `commit()` →
    best-effort Cache-Cleanup über `asyncio.to_thread(thumbnails.delete_cached_variants, ...)` →
    eine `INFO`-Logzeile mit `user.id`/`project.id`/Zeilenzahlen **ohne** Projektnamen → `204`. Ein
    nebenläufiger `IntegrityError` wird als `409` beantwortet, nicht als `500`. Die Löschung selbst
    liegt im neuen Modul `project_deletion.py` — eine feste Folge von `delete(Model).where(...)` in
    `reversed(Base.metadata.sorted_tables)`-Reihenfolge statt einer ORM-Kaskade (bei mehreren
    tausend Fotos hingen rund 10^5 Zeilen daran); `demo_state.py::purge_demo_state` nutzt dasselbe
    Modul, es gibt danach genau **eine** Aufzählung dessen, was an einem Projekt hängt. Die
    Import-Richtung ist verbindlich (`demo_state` → `project_deletion`, nie umgekehrt), sonst wäre
    der von der Demo-Seeder-Sperre bewachte Teil über einen HTTP-Endpunkt erreichbar.
  - kein neuer Endpunkt, drei additive Antwortfelder. `CategoryCandidateOut.confidence: float |
    None` (`api/photos.py`) — die Zahl folgt dem SCHLÜSSEL, nicht der `origin`-Kennzeichnung: ein
    lokal UND remote erkannter Schlüssel bleibt `origin="local"`, behält aber die Modellzahl; ein
    rein lokaler Kandidat bekommt `null`, nie `0.0`. Ausdrücklich keine Wiederkehr des mit Spec 0289
    entfallenen `score`-Felds — jenes war die Rechengröße der abgeschafften
    Zahlenvergleichs-Auswahl, diese Zahl beeinflusst weder Auswahl noch Sortierung noch irgendeine
    Schwelle im Backend. `PhotoOut.category_confidence: float | None` ist die Konfidenz zu
    `remote_category` — ein eigenes Feld statt einer clientseitigen Ableitung aus der
    Kandidatenliste, weil `remote_category` `nicht_erkannt` lauten kann und dann gar nicht in
    `detected_categories` steht; es trägt den clientseitigen Kuratierungsfilter.
    `ProjectStatsOut.category_confidence: CategoryConfidenceOut` (`api/stats.py`) ist ein neuer
    Block NEBEN `categories` mit anderer Grundmenge: eine GROUP-BY-Abfrage über
    `photo_category_classifications`, projektskopiert über `_photos_of_project`, gruppiert über die
    MODELL-Kategorie und ausdrücklich nicht über `photo_rankings.category_key` — der vorhandene
    Block beantwortet "wie ist mein Bestand verteilt", dieser "wie gut arbeitet die Erkennung"; ein
    übersteuertes Foto zählt hier weiterhin zu seiner Modell-Kategorie. Je Registry-Key ein Eintrag
    in Anzeigereihenfolge (`category_key`/`display_name`/`photo_count`/`average_confidence`), dazu
    die ausgewiesene Bezugsbasis `photos_with_confidence`/`photos_without_confidence`.
    `average_confidence` ist `null` bei `photo_count == 0`, nie `0.0`. **Keine Schwelle im
    Backend:** weder API noch Datenbank kennen einen Begriff von "unsicher" — der 60-%-Filter der
    Kuratierung ist eine Konstante der Oberfläche.
  - ein neuer Lese-Endpunkt `GET
    /projects/{id}/curation-candidates?event_id=N&category_key=…&after_rank=N&limit=…&offset=…`
    (`api/photos.py`) liefert die Zugehörigkeiten **einer** Partition mit `rank_position >
    after_rank`, aufsteigend, als `PhotoListOut`; `total` ist die Restmenge der Partition
    (`max(partition_size - after_rank, 0)`) und damit unabhängig von `limit`/`offset`. Kein
    erfolgreicher Lauf, unbekannte Schlüssel oder ein `after_rank` jenseits der Partitionsgröße
    liefern `200` mit leerer Liste, kein Fehler und keine Rückspiegelung der übergebenen Schlüssel.
    `curation_position` wird ausschließlich für die **angefragte** Zugehörigkeit gesetzt. **Zwei
    Muss-Kriterien:** die Auth-Dependency ist ausgeschrieben (`api/photos.py` verzichtet bewusst auf
    eine Router-weite `dependencies`-Liste — ein vergessener Parameter ergäbe dort einen still
    öffentlichen Endpunkt), und `criterion_scoring_run_id` aus dem **Pfadparameter** steht in jeder
    Abfrage inklusive der Zählabfrage hinter `total`, weil `photo_rankings` keine `project_id` trägt
    und `event_id` ein **globaler** Surrogatschlüssel ist (bis Spec 0425: `cluster_key`, in jedem
    Projekt derselbe String — die Ausfallrichtung ohne Prädikat ist seither unauffälliger, nicht
    harmloser: kohärente Fotos eines fremden Projekts statt einer erkennbaren Kollisionsmenge).
    Gleichzeitig entfällt
    der Ablehnungsfilter aus dem bestehenden Kuratierungszweig (siehe **PhotoRanking** oben) — kein
    neues Antwortfeld, keine Migration.
  - `PhotoOut` trägt **zwei** Ortsfelder, beide auf **allen drei Lesepfaden** ausgeliefert
    (`list_photos` in beiden Modi, `curation_candidates`), nie nur im Kuratierungsmodus:
    - `location` (`lat`/`lon` in **voller** EXIF-Präzision, `source: "exif" | "derived"`) — die
      eigene Koordinate oder die des zeitlich nächstgelegenen Fotos **des Projekts** mit
      Koordinate, Tie-Break: früherer Zeitpunkt, dann kleinere `photo_id`. Nirgends persistiert.
      Seit Spec 0425 ist die Bezugsmenge das **ganze Projekt** statt des Clusters (auch
      aussortierte Fotos ankern), und dieselbe reine Funktion `events.py::infer_locations` speist
      **beide** Aufrufer — Lesepfad und Worker. Die Bindung an `Photo.project_id` steht in beiden
      ausgeschrieben; ohne sie erbt ein Foto Koordinaten aus einem fremden Projekt.
    - `event` (`EventOut`: `id`, `position`, `started_at`, `ended_at`, `place`) — seit Spec 0425
      an der Stelle des früheren, zur Anfragezeit berechneten `cluster_place`. Nummer, Zeitspanne
      und Ort stehen jetzt in der `events`-**Zeile** und hängen damit strukturell nicht mehr davon
      ab, welche Fotos eine Antwort gerade enthält — genau die Teilmengen-Abhängigkeit, die den
      alten Wert eine Aussage über die Top-N sein ließ. `place` ist `null`, wenn `place_kind` NULL
      **oder nicht aus dem Vorrat** ist (Mitgliedschaftsprüfung statt Cast — ein einzelner
      driftender Wert legte sonst die gesamte Listenantwort auf 500).
    Die Lauf-Id wird **einmal pro Request** aufgelöst und durchgereicht; fehlt sie, bleibt `event`
    `null` (Ausfallrichtung „nichts anzeigen", nie „aus irgendeinem Lauf herleiten"). Die
    Event-Abfrage trägt `Event.criterion_scoring_run_id` ausgeschrieben. Die Ortsrundung auf zwei
    Nachkommastellen liegt unverändert im Backend, seit Spec 0425 aber an der **Schreib**stelle
    (`events.py`): dieselbe Zahl entscheidet dort über `"coordinate"` vs. `"multiple"`. Ein
    Sehenswürdigkeit-Name über `MAX_LANDMARK_NAME_LENGTH` (80) wird **verworfen, nie
    abgeschnitten**; das Event fällt dann auf die Koordinatenstufe zurück. Im Frontend bildet
    `utils/timeOfDay.ts::formatEventHeading()` daraus seit Spec
    [`0434`](../specs/features/0434-ortsnamen-fuer-events.md) **drei** Formen, sequenziell:
    `"<Sehenswürdigkeit> (<Zeitspanne>)"` → `"<Ortsname> (<Zeitspanne>)"` →
    `"Position <n> (<Zeitspanne>)"`. Der Ortsname kommt aus `EventOut.place_name` und steht dort
    **neben** `place`, nicht darin: `place` ist bei unbekanntem `place_kind` `null`, und der Name
    fiele sonst still mit. Die zusammengesetzte Form `"Ort, Viertel"` kommt fertig vom Server; das
    Frontend setzt nichts zusammen. Tageszeit-Kategorien und die Koordinate als Name entfallen mit
    Spec 0425.
  - **Der Kuratierungsparameter wird ein Schalter, und ein neuer Schreib-Endpunkt setzt den
    Richtwert** *(Spec [`0429`](../specs/features/0429-auswahl-richtwert-und-mischung.md), ADR
    [`decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md`](../specs/decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md))*:
    `GET /projects/{id}/photos` verliert `top_n_per_event` **ersatzlos** und bekommt
    `selection: bool = false`. Im Auswahlmodus liefert der Endpunkt genau die Fotos mit
    `selection_position IS NOT NULL` des letzten erfolgreichen Laufs, sortiert nach
    `(events.position, selection_position)`; `curation_position` trägt dort die
    `selection_position`, **nicht** die `rank_position`. Das Antwortschema bleibt unverändert. Ein
    Aufruf mit dem alten Parameter endet in `422` statt still ignoriert zu werden — ein
    Übergangsweg, der beide Parameter kennt, wäre eine zweite Auswahlregel.
    `GET /projects/{id}/curation-candidates` bleibt unberührt: der volle Vorrat bleibt einsehbar.
    - **`limit`/`offset` wirken im Auswahlmodus weiterhin gar nicht** — nie halb. Damit entfällt
      die bisherige Obergrenze der Kuratierungsantwort (`top_n <= 10` je Event) ersatzlos; die
      neue Obergrenze ist der auswahlfähige Bestand des Laufs. Bewusst getragen (die Ansicht zeigt
      den Vorschlag als Ganzes, beide Nutzer sind die Vertrauensbasis); ein abgeschnittener
      Vorschlag, den die Ansicht als vollständigen ausweist, wäre dagegen ein Zustand, den keine
      Anzeige als fehlerhaft erkennt.
    - `PUT /projects/{id}/selection-target` (`api/projects.py`, am Router-weiten Auth-Guard, Body
      `{"target": int | null}` mit `ge=1` und statischem Deckel `MAX_SELECTION_TARGET`) setzt den
      Richtwert und rechnet den Vorschlag des letzten erfolgreichen Laufs **synchron in derselben
      Transaktion** neu (`worker.py::rebuild_run_selection`, ohne Cloud-Aufruf und ohne
      Bildverarbeitung; Events und Rangzeilen bleiben unangetastet), Antwort ist `ProjectOut`.
      Reihenfolge der Prüfungen: `404` → `409`, solange der neueste `CriterionScoringRun` des
      Projekts `RUNNING` ist (enger als der Versatz-Wächter: nur dieser Lauftyp schreibt
      `selection_position`) → schreiben. `null` ist ein eigener zulässiger Wert (der Rückweg zur
      Vorbelegung) und von „Feld fehlt" zu unterscheiden; `0` ist kein Weg dorthin.
    - **Nicht geschlossen, bewusst:** zwei synchron rechnende Endpunkte schreiben auf dieselben
      Rangzeilen (`PUT …/time-offset` über `rebuild_run_grouping`, `PUT …/selection-target` über
      `rebuild_run_selection`). Der `409`-Wächter deckt Endpunkt-gegen-Lauf ab, nicht
      Endpunkt-gegen-Endpunkt; beide Wege erzeugen einen vollständigen, gültigen Vorschlag, und
      der schlechteste Ausgang ist einer nach altem Richtwert.
  - **Der Auswahlmodus wird der Album-Entwurf, und seine Antwortmenge hängt am anfragenden
    Nutzer** *(Spec [`0430`](../specs/features/0430-album-entwurf-je-nutzer.md), ADR
    [`decisions/0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md`](../specs/decisions/0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md))*:
    `GET /projects/{id}/photos` verliert `selection` und bekommt `draft: bool = false`. Der Zweig
    liefert `Vorschlag(letzter erfolgreicher Lauf) ∪ eigene Bewertung album_worthy`, **ohne
    Ablehnungsfilter** — ein gestrichenes Foto bleibt in der Antwort und trägt seinen Zustand in
    `ratings[]`; Streichen ist ein Anzeigezustand, kein Filter. Der Entwurf ist **abgeleitet**, es
    entsteht keine Entwurfstabelle: „nie angefasst" ist die Abwesenheit einer eigenen
    Albumentscheidung.
    - Reihenfolge `(events.position, photos.taken_at, photos.id)` — innerhalb eines Events also
      **chronologisch** nach der korrigierten Aufnahmezeit, nicht nach `selection_position`. Nach
      `selection_position NULLS LAST` zu sortieren ist ausgeschlossen: Ein aufgenommenes Foto hat
      keinen Platz im Vorschlag und stünde dann stets am Gruppenende, ein Austausch verschöbe das
      Bild also statt es an seiner Stelle zu ersetzen. `curation_position` numeriert die
      **gelieferte** Reihenfolge je Event lückenlos ab 1.
    - `RankingOut` bekommt `proposed: bool` (`selection_position IS NOT NULL`) — **lauf-global,
      ohne Nutzerbezug und auf allen Lesepfaden befüllt**, nicht nur im Entwurfsmodus. Erst dieses
      Feld unterscheidet im Entwurf „vom Lauf vorgeschlagen" von „vom Nutzer aufgenommen".
    - `MotifStrengthOut` bekommt ebenso additiv `present: bool` — ob das Foto dieses Motiv
      **trägt**, ebenfalls auf allen Lesepfaden befüllt. Es speist die Motivmischung am Event;
      **die Grenze bleibt im Backend** und verlässt es nie als Zahl: `strength` und `present`
      entstehen in `_motifs_out` aus einer lokalen Größe, und die Entscheidung fällt
      ausschließlich in `selection.py::motif_is_present`. Kosten: keine — der Zweig lädt die
      wirksamen Stärken für genau diese Fotomenge ohnehin.
    - Ein aufgenommenes Foto **ohne Rangzeile** (im Ausschuss-Schritt aussortiert) wird über
      `events.py::event_for_time` eingeordnet — Containment schlägt Nähe, beide Grenzen inklusiv,
      bei Gleichstand gewinnt das frühere Event. Die Rangzeile hat Vorrang vor dieser Zuordnung.
      Die Eventliste wird **einmal** geladen, die Zuordnung läuft in einem Durchgang: nie eine
      Abfrage je Foto (Auflage S14). Ohne erfolgreichen Lauf ist der Entwurf leer, auch wenn der
      Nutzer bereits Fotos aufgenommen hat.
    - `limit`/`offset` bleiben in diesem Zweig **vollständig** wirkungslos — nie halb.
    - `selection` bleibt als schemaloser Parameter stehen und endet in **beiden** Belegungen in
      `422`. `selection=false` ist der gefährlichere Fall: heute ein gültiger Aufruf, der sonst
      still in den Listing-Zweig fiele, obwohl die Antwortmenge des Nachfolgers eine andere
      Bedeutung hat.
    - `RatingWriteOut` nennt zusätzlich `user_id` (aus `current_user`, nie aus der Anfrage): Die
      Entwurfsansicht schreibt den geschriebenen Zustand in ihre bereits geladene Liste fort,
      statt sie neu zu laden, und ein Eintrag von `PhotoOut.ratings[]` trägt `user_id`.
  - **Die Kuratierungsansicht wird der Album-Entwurf** *(dieselbe Spec)*: neue Seite
    `pages/AlbumDraftPage.tsx` unter `PROJECT_ROUTE_PATHS.album = '/projects/:projectId/album'`,
    mit Tages- und Eventgliederung in der **Antwortreihenfolge des Servers** (die Seite sortiert
    nicht nach und bildet keine Auswahlregel nach), Richtwert und Ist-Anzahl nebeneinander ohne
    Fehleroptik, und der Entwurfskachel `CurationPhotoTile` mit dem Zweizustand „Im Album" ⇄
    „Gestrichen" (`aria-pressed`). Die Entscheidung läuft über eine **eigene** Mutation
    (`useDraftDecisionMutation`), die den betroffenen Eintrag im Cache fortschreibt und nur die
    übrigen Fotoabfragen invalidiert — die breite Invalidierung träfe sonst die Entwurfsliste mit,
    und das gerade gestrichene Bild verschwände unter dem Finger. `pages/CuratePage.tsx`,
    `utils/rankings.ts::curatedRanking` und die Route `/projects/:id/curate` entfallen
    **ersatzlos, ohne Weiterleitung**: Ein stillschweigend umgeleiteter Altlink verdeckte, dass
    sich die Ansicht geändert hat.
  - **Der Vorrats-Endpunkt wird der Alternativen-Endpunkt** *(dieselbe Spec, ADR 0098 Punkt 5)*:
    `GET /projects/{id}/curation-candidates` entfällt **ersatzlos** (`404`), an seine Stelle tritt
    `GET /projects/{id}/draft-alternatives?event_id=N&photo_id=N&limit=…&offset=…`. Er liefert die
    Fotos **eines** Events des letzten erfolgreichen Laufs abzüglich des Entwurfs des anfragenden
    Nutzers; ein von ihm **gestrichenes** Foto ist enthalten — genau daraus folgt, dass ein
    Austausch umkehrbar ist, ohne dass es einen Rückgängig-Knopf oder einen Verlauf gäbe. Ein
    Foto ohne Rangzeile (im Ausschuss-Schritt aussortiert) erscheint nicht. `total` ist die
    Restmenge und damit unabhängig von `limit`/`offset`; `curation_position` ist hier `null` — die
    Alternativen sind keine Auswahl, zu der ein Bild einen Platz hätte.
    - Die Reihenfolge entsteht in der **reinen** Funktion `selection.py::order_alternatives` mit
      dem Schlüssel `(0 wenn geteiltes Motiv sonst 1, -quality, photo_id)`: erst die Träger eines
      Motivs des Bezugsbildes nach Qualität absteigend, dann die übrigen; `quality is None`
      sortiert **innerhalb seiner Gruppe** ans Ende, und `0.0` ist kein fehlender Wert. Die
      Motivgruppe ist **binär** (drei geteilte Motive schlagen ein geteiltes nicht) und die
      Grenze dieselbe wie in der Auswahl (`carried_motifs`/`motif_is_present`). **Zeitliche Nähe
      ist kein Kriterium** — `AlternativeCandidate` trägt dafür bewusst keine Aufnahmezeit.
      Sortiert wird deshalb in Python und nicht im `ORDER BY`; `limit`/`offset` schneiden danach
      die Seite heraus, und nur sie wird hydratisiert.
    - **Vier Muss-Kriterien:** die Auth-Dependency ist ausgeschrieben (dieser Router hat kein
      Vollständigkeitsnetz in `test_auth_guard.py` — ein vergessener Parameter ergäbe einen still
      öffentlichen Endpunkt); `criterion_scoring_run_id` aus dem **Pfadparameter** steht in jeder
      Abfrage, weil `photo_rankings` keine `project_id` trägt und `event_id` ein **globaler**
      Surrogatschlüssel ist; `photo_id` wird **ausschließlich** über eine Rangzeile desselben
      Laufs und desselben Events aufgelöst, nie über `session.get(Photo, …)`, und scheitert das,
      ist die Antwort `200` mit leerer Liste und `total: 0` — ein `404` wäre ein Existenz-Orakel
      über fremde Ids, und die Sortierung hängt allein an diesem Bild, also liefe sonst ein
      fremdes Motivprofil über die beobachtete Reihenfolge ab; alle vier Query-Parameter tragen
      deklarative Grenzen.
    - Oberfläche: Der Austausch läuft in `components/DraftAlternativesDialog.tsx` (`ui/dialog`,
      **kein** Popover — ein Bildraster mit eigenem Blätterweg braucht auf 360px die volle Fläche,
      und der Vorgang verlangt Fokusfang). Geladen wird **erst beim Öffnen**: eine Abfrage je
      geöffnetem Bild, nie eine je Kachel. Ein Tippen löst **einen** Schreibvorgang aus (siehe den
      Austausch-Endpunkt unten; bis Spec 0432 waren es zwei), schließt den Dialog und setzt den
      Fokus auf die nun an dieser Stelle stehende Kachel; die Entwurfsliste wird dabei **nicht**
      neu geladen (`useDraftExchangeMutation` schreibt sie über
      `utils/albumDraft.ts::insertDraftPhoto` mit dem Sortierschlüssel des Servers fort).
      `components/CurationCandidates.tsx`, `useCurationCandidatesQuery` und
      `listCurationCandidates` entfallen.
  - **Der Austausch ist ein Aufruf, eine Transaktion und ein Ereignis** *(Spec
    [`0432`](../specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md), ADR
    [`decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md`](../specs/decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md)
    Punkt 3)*: `POST /projects/{project_id}/draft/exchange` (`api/photos.py`, Body
    `{"photo_id": …, "replaced_photo_id": …}`, Antwort `DraftExchangeOut` mit **beiden**
    geschriebenen Bewertungszeilen). „B statt A" ist die Aussage; die beiden Bilder für sich tragen
    sie nicht. Zwei getrennte `PUT /photos/{id}/rating` ließen sich nachträglich nur über eine
    Heuristik zu einem Paar zusammenfügen, und der zweite konnte fehlschlagen — dann blieb ein
    halb ausgeführter Austausch stehen.
    - Beide Bewertungszeilen und das eine `exchanged`-Ereignis gehen in **einer** Transaktion oder
      gar nicht. Dafür ist die Transaktionsgrenze aus `api/ratings.py::write_own_rating` zum
      Aufrufer gewandert: Die Schreibstelle flusht weiterhin (daran hängt der `409`-Fall),
      committet aber nicht mehr. Ihr neuer Parameter `record=False` unterdrückt die Aufzeichnung
      für beide Teilschreibvorgänge — ohne ihn zählte jeder Austausch **dreifach**.
    - **Projektbindung über die Rangzeile:** Beide Ids werden ausschließlich über eine Zeile von
      `photo_rankings` mit dem Prädikat „jüngster erfolgreicher Kriterienlauf dieses Projekts"
      aufgelöst, nie über `session.get(Photo, …)` mit nachgelagerter Projektprüfung.
      `photo_rankings` trägt keine `project_id`, und ohne das Laufprädikat identifiziert eine Id
      aus Projekt B unter `/projects/A/…` eindeutig fremde Zeilen — der Endpunkt liefe dann nicht
      in eine erkennbar falsche Menge, sondern **tauschte kohärent zwei Bilder eines fremden
      Projekts**. Beide Fotos müssen zudem im **selben Event** liegen; `event_id` des Ereignisses
      stammt aus der Rangzeile und nie aus dem Body.
    - `404` ohne Projekt, `422` für dasselbe Foto auf beiden Seiten, eine unbekannte oder
      projektfremde Id und zwei verschiedene Events — **alle drei mit identischem Text**, sonst
      wäre der Endpunkt ein Existenz-Orakel über fremde Foto-Ids. Der Body trägt genau zwei
      Felder mit deklarativen Grenzen und weist jedes weitere ab; `weight` wäre der Wert, mit dem
      ein Aufrufer die eigene Korrektur in der global wirkenden Gewichtsableitung
      überproportional zählen ließe.
    - Die Umkehr eines Austauschs ist ein **weiterer** Austausch mit eigenem Ereignis; sie löscht
      nichts. Das Favoriten-Kennzeichen bleibt auf beiden Seiten unberührt, weil der Austausch
      durch dieselbe Schreibstelle läuft wie `PUT /photos/{id}/rating`.
  - **Die Endauswahl des Projekts, eine Ebene über beiden Entwürfen** *(Spec
    [`0431`](../specs/features/0431-endauswahl-gemeinsam.md), ADR
    [`decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md`](../specs/decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md))*:
    zwei neue Endpunkte und drei additive `PhotoOut`-Felder. Gespeichert wird ausschließlich die
    **ausdrückliche** gemeinsame Entscheidung (`FinalSelectionDecision`); die Endauswahl selbst ist
    **abgeleitet** und entsteht in der reinen, DB-freien Funktion
    `album_selection.py::selection_state` — sie lebt dort und **nur** dort, die Oberfläche bildet
    sie nirgends nach. Daraus folgen **ohne durchsetzenden Code** beide Zusagen zugleich: Einigkeit
    ist eine **Vorbelegung** (sie wirkt nur im Zweig ohne Entscheidung), und eine getroffene
    Entscheidung überlebt jede spätere Entwurfsänderung und jeden neuen Vorschlagslauf. Ein
    strittiges, **unentschiedenes** Bild gehört **nicht** zur Endauswahl. Die Zahl **zwei** steht an
    keiner Stelle im Code — der Nenner ist die Nutzerzahl.
    - `PUT /photos/{photo_id}/album-decision` (`api/album_decisions.py`, Body `{"included": bool}`,
      Antwort `AlbumDecisionOut`) — **eigener Router mit router-weiter Auth-Dependency**, weil der
      Endpunkt als einziger Schreibendpunkt des Projekts **kein** `current_user` entgegennimmt: Die
      Entscheidung gehört dem Projekt, nicht einem Nutzer. Genau deshalb ist seine
      Authentifizierung an der Signatur unsichtbar, und er trägt drei Sicherungen statt einer
      (Router-Dependency, Eintrag in `test_auth_guard.py::_protected_router_operations()`, eigener
      pfadbenannter 401-Fall). `included` ist pflichtig und ohne Vorgabewert — genau wie die
      Spalte. **Kein `DELETE`:** „wieder strittig werden" ist kein Zustand des Produkts, ändern
      heißt den anderen Wert schreiben.
    - `GET /projects/{project_id}/album-selection` (`api/photos.py`, Antwort `AlbumSelectionOut`
      mit `participants`, `has_proposal`, `items`) — **ohne `total` und ohne Seitenweise**, wie der
      Entwurfszweig. Die Antwortmenge ist **additiv**: `strittig ∪ Endauswahl ∪ entschieden`. Der
      dritte Teil ist keine Redundanz — ein ausdrücklich **herausgenommenes** Bild gehört nicht zur
      Endauswahl und verschwände sonst aus beiden Sichten, die Entscheidung ließe sich dann nicht
      mehr ändern. Ein Bild, das **beide** gestrichen haben, erscheint nicht; der Weg zurück führt
      über den Einzelentwurf. `curation_position` ist hier `null`. `participants` führt **alle**
      Konten nach `user_id` sortiert (auch das ohne jede Bewertung) und trägt genau `user_id` und
      `username`; seine **Länge ist der Nenner** der Regel und stammt damit aus derselben
      Leseoperation wie die Anzeige. `has_proposal` trennt die beiden Leerzustände („kein
      Auswahlvorschlag" gegen „keine Unterschiede offen"), die verschiedene Handlungen verlangen.
    - **Projektbindung (Muss-Kriterium):** Die Kandidatenmenge entsteht aus einem ODER **dreier**
      Quellen, von denen zwei projektblind sind (`final_selection_decisions` hat nur `photo_id`,
      `Rating` nur `(photo_id, user_id)`). `Photo.project_id == project_id` ist deshalb eine
      **UND-Bedingung über die gesamte Menge** und steht außerhalb der ODER-Verknüpfung; der
      Rangzweig hängt zusätzlich am Lauf dieses Projekts. Ein hineingerutschtes Projektprädikat ist
      syntaktisch unauffällig und lieferte kohärent aussehende Fotos eines **fremden** Projekts.
    - `PhotoOut` bekommt `final_selection_decision: bool | null`, `in_final_selection: bool` und
      `contested: bool` — **auf allen vier Lesepfaden befüllt** (Muster `RankingOut.proposed`), alle
      drei **ohne Vorgabewert**. `_to_photo_out` bekommt `decisions` und `user_count` als
      **pflichtige** Schlüsselwortparameter: Ein vergessener Aufrufer wirft keine Ausnahme, er
      antwortet still `in_final_selection: false` für jedes Foto, und der Fehler zeigte sich erst
      an einem leeren Album. `mypy --strict` ist die einzige Prüfung, die ihn vor der Laufzeit
      fängt. **Nicht** `album_decision` benannt — so heißt bereits `ratings[].status`.
    - **Der Einzelentwurf bleibt unberührt**, und das ist strukturell geprüft: `ratings` bekommt
      keine Spalte und `RatingStatus` keinen Wert, die neue Tabelle hat keinen Nutzerbezug, und ein
      AST-Wächter hält fest, dass weder `_draft_photo_ids` noch `draft_alternatives` die
      Entscheidungstabelle nennt. Die Einheit dieses Wächters ist der **Funktionsrumpf**, nicht die
      Datei: `album_selection` liegt im selben Modul, ein Wächter auf Dateiebene wäre dauerhaft rot.
    - Die Einordnung in Events teilen beide Zweige: `_place_in_events` (vormals die Schritte 3 und
      4 von `_draft_photo_ids`, das Ergebnis heißt `PlacedPhotos` statt `DraftContent`). Zweimal
      geschrieben ordneten Entwurf und Endauswahl dieselben Fotos verschieden — sichtbar, ohne dass
      eine Prüfung rot würde.
    - **Die Ansicht** ist `pages/AlbumSelectionPage.tsx` unter
      `PROJECT_ROUTE_PATHS.selection = '/projects/:projectId/selection'`, Titel „Endauswahl". **Ein
      Ort, zwei Sichten, eine Abfrage** (`hooks/useAlbumSelection.ts`, Query-Key
      `['photos', projectId, 'selection']` unter demselben breiten Präfix wie Raster, Einzelbild
      und Entwurf): Die Arbeitssicht filtert lokal auf `contested`, die Ergebnissicht auf
      `in_final_selection` plus die ausdrücklich Herausgenommenen. **Der Umschalter lädt nichts
      nach**, und die Entscheidungsmutation nimmt den eigenen Schlüssel von der Invalidierung aus
      (Muster `useDraftDecisionMutation`) — daraus folgt beides zugleich: Das entschiedene Bild
      verlässt die Arbeitssicht sofort, und die Ergebnissicht ordnet sich dabei nicht neu.
    - **Die Zugehörigkeit kommt vom Server.** `utils/albumDraft.ts::isInAlbum` wird auf dieser
      Seite ausdrücklich **nicht** benutzt: Seine Aussage (`status !== 'rejected'`) gilt nur
      innerhalb der Antwortmenge des Entwurfszweigs, und die Endauswahl enthält auch Fotos, die in
      keinem der beiden Entwürfe stehen. Lokal ausgewertet wird allein
      `utils/albumSelection.ts::applyAlbumDecision`, und das ist exakt, weil eine Entscheidung
      immer überschreibt. Ein struktureller Wächter (`albumSelection.structure.test.ts`) hält beide
      Richtungen fest: Entwurfsseite und Entwurfskachel nennen keines der drei neuen Felder,
      Endauswahlseite und -kachel importieren `isInAlbum` nicht.
    - **Die Kachel** `components/SelectionPhotoTile.tsx` trägt je Teilnehmer **eine benannte
      Haltungszeile** — die Zuordnung entsteht aus `user_id` und dem vorangestellten Namen, nie aus
      der Position in `ratings[]`, und die Zahl der Zeilen ist die Kardinalität von `participants`.
      Kennzeichen ist der bestehende `RatingBadge`; das Symbol `check` ist ausgeschlossen (es ist
      im Produkt die Erfolgsmeldung), und `variant="destructive"` ist hier unzulässig — gefülltes
      `--danger` bei Radius 6px ist formgleich mit dem Kennzeichen „Aussortiert", und diese Seite
      zeigt Bewertungs-Kennzeichen. `PhotoCard` bekommt dafür `setAside`: dieselbe optische
      Zurücknahme wie eine Streichung, aber **ohne** Bewertungs-Kennzeichen — ein unbenanntes
      „Verworfen" am Kartenkörper wäre neben den benannten Haltungszeilen als Haltung einer Person
      lesbar.
    - **Die Vergleichsseite entfällt ersatzlos.** `pages/PhotoComparePage.tsx` und die Route
      `/projects/:id/compare` sind weg, **ohne Weiterleitung** — aus demselben Grund wie bei der
      Kuratierung: Ein zweiter Weg auf den einen verbleibenden Ort wäre ein zweiter Ort. Das dritte
      Hauptziel der Projektnavigation heißt „Endauswahl" statt „Vergleich"; `PhotoDetailPage`
      verlinkt dorthin. Backendseitig entfällt nichts — die Seite las das Standard-Listing.
      `groupDraftByDay` zieht dabei nach `utils/eventGrouping.ts::groupPhotosByDay`, weil beide
      Ansichten dieselbe Antwortform gliedern.
  - **Duplikate vergleichen und einzeln entscheiden** *(Spec
    [`0374`](../specs/features/0374-duplikate-vergleichen.md), ADR
    [`decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md`](../specs/decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md))*:
    drei Endpunkte über einer **abgeleiteten** Gruppe. `PhotoOut` bekommt **kein** Feld — die
    Entscheidung reist in einem eigenen Antwortmodell **neben** dem Foto, weil sie außerhalb dieser
    Ansicht keine Anzeigerolle hat und sonst auf jedem Lesepfad stünde.
    - **Der Ausschuss-Überlebender-Bestand ist seither ein Prädikat an genau einer Stelle**
      (`duplicates.py::survives_ausschuss` als SQL-Fassung, `survives_ausschuss_for` als
      Objektfassung), nicht mehr ein an sechs Stellen ausgeschriebenes
      `PhotoScore.suggested_status IS NULL`:

      > `discard` überlebt nie · `keep` überlebt, solange `duplicate_of IS NOT NULL` · sonst
      > entscheidet `suggested_status`

      Aus den sechs ersetzten Vorkommen werden **sieben** Aufrufstellen — die eine Bedingung
      zerfällt in zwei Funktionen („überlebt" und „offener Vorschlag", seit ADR 0104 nicht mehr
      komplementär), und „der Vorschlags-Zweig" war schon vorher eine SQL- und eine Objektfassung.
      **Vier** der sieben Aufrufstellen bestimmen unmittelbar, welche Fotos den Homeserver
      Richtung Cloud-Anbieter verlassen: `worker.py::run_criterion_scoring` (speist zugleich den
      Sehenswürdigkeits-Teilschritt), `worker.py::select_remote_category_candidates` und die beiden
      **vorgelagerten Kostenschätzungen** in `api/projects.py`. Die Schätzungen folgen der Auswahl
      nicht von selbst — sie sind eigene Anweisungen und müssen dieselbe Menge zählen, die der Lauf
      sendet, sonst beruht die Freigabe eines kostenpflichtigen Laufs auf einer Zahl, die nicht
      gilt. Die übrigen drei (`api/photos.py`) sind Anzeige. Das Prädikat prüft **positiv auf
      `keep`** und behandelt „keine Zeile" als ausdrückliches `IS NULL` auf die Unterabfrage: Die
      Spalte ist eine Zeichenkette ohne DB-seitigen Wertevorrat, ein unerwarteter Wert muss zur
      zurückhaltenden Seite fallen, und `<Unterabfrage> != 'discard'` ergäbe bei fehlender Zeile
      `NULL` und damit den leeren Bestand. **„Überlebender" und „offener Vorschlag" sind nicht
      komplementär:** Eine mit `discard` entschiedene Aufnahme ist weder das eine noch das andere.
      Die Asymmetrie zwischen den beiden Werten ist die Entscheidung, nicht ein Detail —
      `suggested_status = REJECTED` trägt zwei Gründe, und ein unbedingtes `keep` höbe eine
      Ablehnung auf, zu der der Nutzer nie befragt wurde.
    - `GET /projects/{project_id}/duplicate-groups/{photo_id}` (`api/photos.py`, Antwort
      `DuplicateGroupOut` mit `items[]` aus `photo: PhotoOut` und `decision`, dazu `position` und
      `total`). Die Gruppe hat **keine eigene Id**: Sie ist der zur Lesezeit gebildete Stern über
      `PhotoScore.duplicate_of` und damit über **jedes** ihrer Mitglieder unter derselben Antwort
      erreichbar, den Gewinner eingeschlossen. `404` deckt vier ununterscheidbare Fälle —
      unbekanntes Foto, fremdes Projekt, Foto ohne Duplikat und Vorschlag wegen geringer
      Bildqualität; unterschiede die Antwort sie, wäre der Endpunkt ein Existenz-Orakel über fremde
      Foto-Ids. `total` zählt die noch **offenen** Gruppen, vereinigt mit der gerade angesehenen:
      Nur so gilt `1 ≤ position ≤ total` auch für die Gruppe, die man soeben fertig entschieden
      hat.
    - `PUT /projects/{project_id}/photos/{photo_id}/duplicate-decision` und
      `PUT /projects/{project_id}/duplicate-groups/{photo_id}/decision`
      (`api/duplicate_decisions.py`, Body **ausschließlich** `{"decision": "keep"|"discard"}`,
      Antwort dieselbe `DuplicateGroupOut` wie der Lesepfad) — **eigener Router mit router-weiter
      Auth-Dependency** plus Eintrag in `test_auth_guard.py::_protected_router_operations()` und je
      einem pfadbenannten 401-Fall. In `photos.router` wäre ein vergessener Torwächter still
      öffentlich, und das ist hier ein unauthentifizierter Schreibzugriff darauf, welche Bilder den
      Homeserver verlassen. **Keine Id-Liste im Body:** Welche Fotos die Gruppe umfasst, bestimmt
      der Server aus dem Stern; eine vom Aufrufer gelieferte Menge wäre ein Massen-Schreibweg auf
      beliebige Fotos des Projekts. Der Gruppenweg löst den Repräsentanten **zuerst** auf und
      antwortet bei fehlender Gruppe `404`, **bevor** geschrieben wird — ein `None` als
      Vergleichswert würde in SQLAlchemy zu `duplicate_of IS NULL` und träfe jede nicht aussortierte
      Aufnahme des Projekts. Geschrieben wird in **einer** Transaktion; ein wiederholtes `PUT`
      überschreibt, statt am Primärschlüssel in eine 500 zu laufen. Es gibt **kein `DELETE`**: „noch
      nicht entschieden" ist kein Zustand, in den man zurückkehrt.
    - **Die Ansicht** ist `pages/DuplicateComparePage.tsx` unter
      `PROJECT_ROUTE_PATHS.photoDuplicates`, erreichbar aus der Ausschuss-Sichtung und nur bei
      `suggestion.reason === 'duplicate'`. Die Kachel `components/DuplicatePhotoTile.tsx` steht
      bewusst **neben** `PhotoCard`/`CurationPhotoTile`/`RatingBadge` statt auf ihnen: Deren
      Vokabular ist die Albumentscheidung eines Nutzers. Die Vergrößerung ist **kein Dialog** — die
      gewählte Kachel spannt die Rasterbreite, die übrige Gruppe bleibt sichtbar, und genau das ist
      der Zweck.
  - **Die laufende Diagnose der Modellfehler** *(Spec
    [`0432`](../specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md), ADR
    [`decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md`](../specs/decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md))*:
    `GET /feedback/diagnosis` (`api/feedback.py`, Antwort `FeedbackDiagnosisOut` mit
    `correction_count`, `motif_errors[]`, `exchanges[]`, `criteria[]`).
    - **Ohne Projektparameter**, und das ist die Aussage des Endpunkts: Er zählt über das
      **gesamte** Log, alle Projekte und beide Nutzer, weil der Gewichtssatz global gilt — zählte
      er nur ein Projekt, stünden die Fallzahlen neben einem Vorschlag, den sie nicht belegen.
      Deshalb auch ein eigener Endpunkt statt eines Blocks in `ProjectStatsOut`: Er rechnet über
      das ganze Log, ist spürbar teurer als die Projektzahlen und wird für sich neu geladen.
    - **Ausschließlich Aggregate**: kein Einzelereignis, kein `user_id`, keine Foto-Id-Liste, keine
      Aufschlüsselung je Nutzer. Das Log ist die einzige Stelle, die auch **zurückgenommene**
      Korrekturen hält — alles andere, was die Diagnose zählt, ist über `PhotoOut.ratings[]`
      ohnehin je Foto und namentlich lesbar. Der Router trägt
      `dependencies=[Depends(get_current_user)]` plus Eintrag in
      `test_auth_guard.py::_protected_router_operations()` und einen eigenen pfadbenannten
      401-Fall; ohne ihn wäre dies ein unauthentifizierter Lesepfad auf Aussagen über alle
      Projekte.
    - Die **Rechnung** liegt im reinen, DB-freien `feedback.py` (Muster
      `quality.py`/`selection.py`), die Abfragen in `feedback_log.py::load_diagnosis`. Drei
      Motiv-Fehlerfälle (`too_weak`/`missing`/`overcalled`, Präsenzgrenze über
      `selection.py::motif_is_present` und nie als Zahl), drei **disjunkte und erschöpfende**
      Tauschklassen, die **nirgends summiert** werden — `undetermined` ist eine eigene ausgewiesene
      Klasse und kein Restposten —, und je Kriterium die auswertbare Fallzahl samt
      Zustimmungsrate. Die eingefrorenen Zahlen kommen aus dem Ereignis, die lokalen
      Kriterienwerte **live** aus `photo_criterion_scores`; ein Paar mit unvollständigen Werten
      fällt heraus, und die kleinere Fallzahl macht das sichtbar.
    - **Gewichtet wird nur gerechnet, ausgewiesen wird ungewichtet:** `correction_count` und jede
      Fallzahl sind die schlichte Anzahl der Korrekturen. Eine gewichtete Zahl als Fallzahl
      behauptete Korrekturen, die niemand vorgenommen hat.
    - **Die Ansicht** ist `components/FeedbackDiagnosisSection.tsx` als letzter Abschnitt von
      `ProjectStatsPage` — mit **eigener** Abfrage (`hooks/useFeedbackDiagnosis.ts`, Query-Key
      `['feedback-diagnosis']` ohne Projekt- und ohne Nutzersegment, weil die Antwort in Menge und
      in jedem Feld von beidem unabhängig ist). Eine Unterzeile spricht die projektübergreifende
      Zählung aus und behält ihren Platz im Lade-, Leer- und Fehlerzustand; ohne sie liest jeder
      die Zahlen als Aussage über das offene Projekt. Im **Leerzustand** wird keine einzige
      Kennzahlen- oder Tauschzeile dargestellt — sonst wäre „noch nie korrigiert" nicht von
      „N Korrekturen, 0 Fehler" zu unterscheiden. `Section`, `Metric`, `MetricRow` und `DetailRow`
      liegen dafür in `components/StatsLayout.tsx` statt weiter in `ProjectStatsPage.tsx`.
  - **Die Gewichte aus der Nacharbeit** *(dieselbe Spec und ADR)*: derselbe `feedback`-Router trägt
    zusätzlich `POST /feedback/weights` (Body `{based_on_event_id}`) und
    `POST /feedback/weights/revert` (Body `{reverts_set_id}`); beide antworten mit
    `WeightPreviewOut`, das auch in `FeedbackDiagnosisOut.weights` steht (`current[]`,
    `proposed[]` je mit `delta`, `based_on_event_id`, `current_set_id`, `can_revert`).
    - **Der Body trägt nie ein Gewicht.** Beide Felder sind Wächter, `extra="forbid"` weist ein
      zusätzliches Feld ab, und der Server rechnet den Vorschlag neu. `weight` wäre der einzige
      Wert, mit dem ein Aufrufer die eigene Korrektur in der global wirkenden Ableitung
      überproportional zählen ließe.
    - `based_on_event_id` ist ein **Zustimmungs-Token, kein Objektverweis**: nie zu einer Zeile
      aufgelöst, geprüft auf **strikte Gleichheit** gegen die höchste `id` des **gesamten** Logs
      (`feedback_log.py::latest_event_id`, ohne jeden Filter), bei leerem Log `0`. Ein seither
      hinzugekommenes Ereignis — gleich in welchem Projekt — ergibt `409`, und es wird **nichts**
      geschrieben. Gegen ein nach Projekt oder Art gefiltertes Maximum geprüft, entstünde die
      Fassung gegen eine Lage, die niemand gesehen hat.
    - Auch die **Rücknahme** trägt einen Wächter: Sie nennt die Fassung, die zurückgenommen werden
      soll, und antwortet `409`, wenn sie nicht mehr die geltende ist. Ohne ihn legen zwei Aufrufe
      kurz hintereinander erst die Rücknahme und dann deren Rücknahme an — das Ergebnis ist der
      Ausgangszustand, die Kette sieht lückenlos aus, und keine Anzeige weist das als falsch aus.
      Zurückgesetzt wird als **neue Fassung** mit den Werten der Vorgängerin; es wird nie eine
      gelöscht, und der zweite Druck führt auf die Werte zurück, von denen der erste zurückgesetzt
      hat.
    - **Der Vorschlag wird aus den Startwerten abgeleitet**, nie aus den geltenden Gewichten:
      Sonst verschöbe jede Übernahme die Grundlage der nächsten, und die Bandbreite
      (`feedback.py::FEEDBACK_WEIGHT_SPAN`) wäre nach wenigen Runden verlassen, ohne dass eine
      einzelne Übernahme sie je verletzte. `delta` ist dagegen der Unterschied zum **geltenden**
      Gewicht — genau der zwischen den beiden nebeneinander dargestellten Spalten.
    - **Die Übernahme schreibt die neue Fassung und sonst nichts**: keine Rangzeile bewegt sich,
      es entsteht kein Lauf, es wird nichts eingereiht, es ergeht kein Modell- oder Cloud-Aufruf.
      Erst der nächste Durchlauf rechnet damit — der bewusste Gegensatz zu
      `PUT /projects/{id}/selection-target`, das synchron neu rechnet; eine Gewichtsanpassung wirkt
      global und risse sonst jeden offenen Entwurf jedes Projekts um.
    - **Die Herkunft der wirksamen Gewichte** liegt in `quality_weights.py`: `effective_weights`
      überlagert die geltende Fassung über die Startwerte aus `quality.py`, **in beide Richtungen
      geprüft** — ein den Startwerten unbekannter Schlüssel der Fassung wird verworfen, ein der
      Fassung unbekannter Startwertschlüssel behält seinen Startwert. Der wirksame Schlüsselsatz
      ist damit immer exakt der Startwertsatz; insbesondere gelangt kein Kriterium mit
      Inhaltsaussage in den Qualitätswert. Kein nicht-endlicher und kein nicht-positiver Wert
      erreicht die Persistenz, und der Lesepfad nimmt keinen an: Ein gespeichertes `NaN` käme durch
      jede Schranke von `quality.py` und machte die Rangfolge **aller** Projekte beliebig, ohne
      einen Fehler zu erzeugen.
    - **Die Ansicht** ist die Gewichts-Vorschau im selben Abschnitt: je Kriterium geltendes
      Gewicht, Vorschlag, Abweichung mit Vorzeichen und Fallzahl, darunter der Hinweis auf den
      nächsten Durchlauf, „Gewichte anpassen" (mit Bestätigungsdialog und verkürzter
      Gegenüberstellung) und „Auf vorige Gewichte zurücksetzen" nur bei `can_revert`. Die
      Belastbarkeit trägt allein die sichtbare Fallzahl; die Zustimmungsrate bleibt über den
      Endpunkt verfügbar und wird nicht dargestellt. Aufbereitung in `utils/feedbackWeights.ts`
      (rein), Mutationen in `hooks/useFeedbackDiagnosis.ts`.
- **Worker** (`backend/`, eigener Container-Prozess): `arq`-basierte Jobs für Foto-Ingest (Listing,
  Download, Thumbnail-Erzeugung), lokale Heuristik-Berechnung und optionale Cloud-KI-Bewertung.
  Siehe [`decisions/0002-hybrid-ai-scoring.md`](../specs/decisions/0002-hybrid-ai-scoring.md).
  - `score_criteria`-Job (`worker.py::run_criterion_scoring`) bekommt eine neue, consent-gegate
    Cloud-Phase nach der bestehenden lokalen Foto-Schleife — erste tatsächlich produktive
    `CriterionSource.CLOUD`-Anbindung im Projekt (`landmark.py::AnthropicLandmarkClient`, direkter
    `httpx`-REST-Aufruf gegen die Anthropic Messages API, kein SDK). Vorfilterung auf
    `landschaft`/`gebaeude` (Wiederverwendung der Registry-Schwellwerte; bis Spec 0217
    `content_landscape`/`gebaeude`), Skip bereits gescorter Fotos (einzige Ausnahme vom "jeder Lauf
    scort neu"-Prinzip), Block+`gather`-Nebenläufigkeit über `settings.landmark_api_concurrency`
    (Default 2, `LANDMARK_API_CONCURRENCY`), best-effort Fehlerbehandlung ohne Laufabbruch. Details
    siehe "Datenmodell" unten.
  - `landmark.py::build_landmark_client()` ist jetzt eine kleine Dispatch-Factory zwischen
    `AnthropicLandmarkClient` (weiterhin Default) und dem neuen `MistralLandmarkClient` je nach
    `settings.landmark_provider` (env `LANDMARK_PROVIDER`) — `run_criterion_scoring` selbst bleibt
    unverändert, die Factory ist dort bereits als injizierbarer Default-Parameter verankert.
  - `score_criteria`-Job berechnet drei weitere `criterion_key`-Werte (`symmetrie`, `horizont`,
    `freiraum`) — `symmetrie` (`classification.py::compute_symmetry_score`, keine neue Abhängigkeit)
    und `horizont` (neues Modul `horizon.py::compute_horizon_tilt_score`, klassische
    `cv2`-Kantendetektion/Hough-Transformation, `source=local_heuristic`) laufen unconditional wie
    `content_landscape`; `freiraum` (`classification.py::detect_face_orientation` über ein viertes
    mediapipe-Task-API-Paar, `FaceLandmarker`, `source=local_ml`) läuft mit eigenem
    Best-effort-`try`/`except` und eigenem `_try_build`-Aufruf, analog den bestehenden Detektoren.
    Neue Backend-Abhängigkeit `opencv-contrib-python` in `backend/pyproject.toml` — dieselbe
    Distribution, die `mediapipe` bereits seit Spec 0024 transitiv installiert, dadurch **kein neuer
    Netto-Footprint** im Docker-Image.
  - `score_criteria`-Job berechnet vier weitere `criterion_key`-Werte
    (`tier`/`gebaeude`/`goldener_schnitt`/`aesthetics`) über `classification.py` (erweitert um
    `detect_animals`/`classify_scene`, zwei weitere mediapipe-Task-APIs neben `FaceDetector`) und
    das neue, eigenständige Modul `aesthetics.py` (NIMA/MobileNet über `tensorflow`).
    `worker.py::_compute_content_criteria` ruft `detect_person`/`detect_animals` je Foto höchstens
    einmal auf und teilt sich das Ergebnis zwischen mehreren abhängigen Kriterien, statt pro
    Kriterium neu zu detektieren.
  - `scan_project`/`run_project_scan` läuft jetzt zweiphasig — eine reine Enumerationsphase
    (`_enumerate_scan_entries`, kein Photo-DB-Zugriff) gefolgt von einer begrenzt parallelen
    Verarbeitungsphase in festen Blöcken (`_process_scan_block`, Blockgröße = neue Einstellung
    `settings.scan_download_concurrency`, Default 4, env-überschreibbar `SCAN_DOWNLOAD_CONCURRENCY`)
    — erste Intra-Job-Nebenläufigkeit im Projekt (`asyncio.gather`, bewusst statt
    `asyncio.TaskGroup`, siehe ADR
    [`decisions/0020-scan-enumeration-und-parallele-verarbeitung.md`](../specs/decisions/0020-scan-enumeration-und-parallele-verarbeitung.md)).
  - `scan_project`/`score_project`/`select_top_photos` sind über `arq.worker.func(fn, timeout=86400,
    max_tries=1)` registriert (24h-Not-Anker statt arq-Default 300s, kein automatischer
    Hintergrund-Retry); neuer periodischer `arq`-Cron-Job `reap_stalled_runs`
    (`worker.py::WorkerSettings.cron_jobs`, alle 5 Minuten, `run_at_startup=True`) markiert
    dauerhaft hängende `RUNNING`-Läufe als `FAILED` — erste Nutzung von `arq`s Cron-Mechanismus im
    Projekt, siehe ADR
    [`decisions/0019-job-lauf-heartbeat-watchdog.md`](../specs/decisions/0019-job-lauf-heartbeat-watchdog.md)
    und "Datenmodell" unten (`last_progress_at`).
  - `scan_project`-Job (`worker.py`) für Foto-Ingest.
  - Thumbnail-/Display-Erzeugung (`thumbnails.py`, Pillow) beim Scan, Ablage im lokalen Cache
    (Docker-Volume `photo_cache`), Dateiname deterministisch aus `photo_id`+`etag` (kein neues
    DB-Feld).
  - `score_project`-Job (`worker.py::run_project_scoring`, analog zu `scan_project`), reine
    Heuristik-Funktionen in `scoring.py` (analog zu `thumbnails.py`:
    Schärfe/Belichtung/dHash+Hamming-Distanz, Duplikat-/Zeitfenster-Clustering), operiert auf der
    bereits vom Scan gecachten `display`-Variante — kein erneuter OpenCloud-Download für Phase A.
    Details siehe
    [`decisions/0006-local-scoring-datamodel.md`](../specs/decisions/0006-local-scoring-datamodel.md).
  - `score_criteria`-Job (`worker.py::run_criterion_scoring`, ersetzt
    `select_top_photos`/`run_top_selection`) mit der Kriterien-Registry `criteria.py` (bewusst
    getrennt von `scoring.py` — die `mediapipe`-Abhängigkeit soll nicht in den Phase-A-Importpfad
    einsickern, wie schon zu Spec-0024-Zeiten) und der reinen Rangfolgen-Funktion
    `ranking.py::rank_photos`. Seit Spec
    [`0428`](../specs/features/0428-albumtauglichkeit-vom-modell.md) ist `rank_photos` eine **reine
    Sortierung**: der Qualitätswert selbst entsteht in `quality.py` — dort stehen die Gewichte
    (`QUALITY_CRITERION_WEIGHTS`) und `LOCAL_CORRECTION_SPAN` an genau einer Stelle, und
    `album_suitability.py` hält Stufenband, Ankertexte und den Parser der Modellaussage. Seit Spec
    [`0429`](../specs/features/0429-auswahl-richtwert-und-mischung.md) hängt am Ende desselben
    Schritts — innerhalb der bestehenden Phase `RANKING`, unmittelbar hinter den Rangzeilen — der
    Auswahlvorschlag aus dem vierten reinen Modul dieser Familie, `selection.py`: es trägt die
    Kontingent- und Vergabelogik samt ihren fünf Stellschrauben (`EVENT_SHARE_CAP`,
    `MOTIF_PRESENCE_THRESHOLD`, `SIMILARITY_DECAY`, `SIMILARITY_TIME_WINDOW`,
    `DEFAULT_TARGET_DIVISOR`) an genau einer Stelle und nennt `motifs.py` nicht — die Grenze, ab
    der ein Motiv als getragen gilt, ist **keines** der Anzeigebänder (ADR 0091 Punkt 8). Der
    Klassifizierungs-Prompt lebt in `classification_prompt.py` (Motivblock plus
    Klassifizierungs-Prompt lebt in `classification_prompt.py` (Motivblock plus
    Albumtauglichkeits-Block); `motifs.py` bleibt reines Registermodul und weiß nichts über die
    Antwortform des Anbieters. `classification.py`s mediapipe Face Detector Task-API (gepinntes
    `.tflite`-Binärasset) und Pillow-Laplace-Kachel-Heuristik werden weiterhin genutzt, jetzt über
    `criteria.py::compute_content_people`/`compute_content_landscape`. Läuft auf ALLEN
    Ausschuss-Überlebenden (nicht mehr nur einem vorgefilterten Kandidatenpool pro Cluster — der
    bisherige Vorfilter entfällt bewusst, da `N` beim Scoren nicht mehr bekannt ist,
    bekannter/akzeptierter Performance-Trade-off). Details siehe
    [`decisions/0015-lokale-kategorie-klassifikation.md`](../specs/decisions/0015-lokale-kategorie-klassifikation.md),
    [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../specs/decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md).
  - `criteria.py::CriterionDefinition` bekommt zwei neue, optionale Felder — `category_eligible:
    bool = False`, `category_presence_threshold: float | None = None` (Invariante `category_eligible
    == (category_presence_threshold is not None)`, durch einen eigenen Registry-Test erzwungen) —
    Kategorie-Fähigkeit ist damit ein reines Registry-Attribut, kein externes Mapping mehr; genau
    `content_people`/`content_landscape`/`tier`/`gebaeude` sind `category_eligible=True`, reine
    Qualitätskriterien (`sharpness`/`exposure`/`goldener_schnitt`/`aesthetics`) bleiben beim
    Default. Neue, reine Funktion `criteria.py::derive_active_categories(candidate_values,
    threshold_fraction=CATEGORY_ACTIVE_THRESHOLD_FRACTION=0.15)` ermittelt EINMAL pro
    `score_criteria`-Lauf, projektweit über alle Kandidaten-Fotos (nicht pro `cluster_key`), welche
    `category_eligible`-Kriterien im jeweiligen Lauf überhaupt eine eigene Kategorie bilden dürfen
    (Anteil der Fotos, die die jeweilige `category_presence_threshold` erreichen, `>=
    threshold_fraction`) — läuft in `worker.py::run_criterion_scoring` nach der bestehenden
    Foto-Schleife (auf dem dort ohnehin vollständig im Speicher gehaltenen `candidate_values`), das
    Ergebnis wird an die geänderte `criteria.py::derive_category_key(criterion_values,
    active_criteria)` durchgereicht (ersetzt die bisherige fest codierte Prioritätskette
    Mensch→Landschaft→Fallback). Bei mehreren gleichzeitig erfüllten aktiven Kriterien gewinnt der
    höchste normierte Score, Tie-Break alphabetisch nach `criterion_key`; `category_key` wird
    generisch aus dem gewinnenden `criterion_key` gebildet (`removeprefix("content_")`), kein
    manuelles Mapping mehr pro Kriterium nötig. Verhaltensänderung (beabsichtigt, kein Bug):
    `"people"`/`"landscape"`/`"detail"` sind keine bevorzugten Standardkategorien mehr, unterliegen
    derselben Häufigkeitsregel wie jedes andere Inhalts-Kriterium. Keine Migration
    (`PhotoRanking.category_key` war bereits ein freier String).
    `worker.py::_CONTENT_CRITERION_KEYS`/`_CONTENT_CRITERION_SOURCES` (bildbasiert berechnete
    Kriterien für Upsert-Buchhaltung, fachlich unabhängig von `category_eligible`) rein kosmetisch
    umbenannt zu `_IMAGE_ANALYSIS_CRITERION_KEYS`/`_IMAGE_ANALYSIS_CRITERION_SOURCES`, um
    Verwechslung zu vermeiden. Kein neuer Endpunkt, kein Frontend-Effekt außer einem
    Anzeigenamen-Mapping für Sonderzeichen (`frontend/src/utils/categoryLabels.ts`: `"gebaeude"` →
    `"Gebäude"`). Siehe Feature-Branch `feature/0045-kategorien-aus-statistiken-ableiten`.
  - neuer, eigenständiger Job
    `classify_categories_remote`/`worker.py::run_remote_category_classification` (KEIN Teil von
    `score_criteria`, eigene Run-Tabelle `remote_category_classification_runs`, eigenes
    Concurrency-Setting `settings.remote_category_classification_concurrency`, Default 2) —
    Kandidatenmenge ist der komplette Ausschuss-Überlebender-Bestand OHNE Vorfilter (anders als
    `landmark`, ADR 0021), Skip bereits klassifizierter Fotos (mind. eine
    `photo_category_detections`-Zeile), best-effort ohne Retry. Neues, providerneutrales Modul
    `cloud_vision.py` (aus `landmark.py` extrahiert:
    URLs/Modell-IDs/Timeout/Response-Parsing-Helfer, von `landmark.py` UND dem neuen
    `remote_classification.py` genutzt) sowie `remote_classification.py` selbst
    (`CategoryLabelDetection`, `AnthropicCategoryClient`/`MistralCategoryClient`,
    `build_category_classification_client()`, `resolve_canonical_label` — löst ein Roh-Label über
    einen exakten NFKC+casefold-Fast-Path oder eine Kosinus-Ähnlichkeits-Prüfung gegen die
    `category_labels`-Registry auf einen kanonischen Eintrag auf). Neues, isoliertes Modul
    `label_embedding.py` (analog `aesthetics.py`): lokales, gepinntes Text-Embedding-Modell über
    `onnxruntime`+`tokenizers` (neue Backend-Abhängigkeiten, CPU-only), SHA256-gepinnte Assets (kein
    Laufzeit-Download). `worker.py::run_criterion_scoring` merged vor dem bestehenden
    `derive_active_categories`/`derive_category_key`-Aufruf bereits vorhandene
    Remote-Label-Ergebnisse als zusätzliche `f"remote:{canonical_key}"`-Pseudo-Kriterien in dieselbe
    `candidate_values`-Struktur (`worker.py::_merge_remote_category_labels`, kein neuer Cloud-Aufruf
    an dieser Stelle) — `criteria.py::derive_active_categories`/`derive_category_key` bekommen dafür
    einen neuen, optionalen `dynamic_keys: frozenset[str]`-Parameter (Default `frozenset()`,
    bestehende Aufrufer bleiben unverändert). Neue Funktion `worker.py::reassign_photo_category`
    verschiebt ein Foto bei einem manuellen Override sofort im selben API-Request zwischen zwei
    `(event_id, category_key)`-Partitionen (`ranking.py::rank_photos` nur für diese zwei
    Partitionen erneut aufgerufen, kein neuer Ranking-Algorithmus, kein voller Re-Scoring-Lauf).
    `reap_stalled_runs` bekommt einen vierten, eigenständigen Tabellen-Block für
    `remote_category_classification_runs`.
  - neue Helfer `worker.py::_record_cloud_vision_error`/`_clear_cloud_vision_error` an vier
    Call-Sites in `run_criterion_scoring`/`run_remote_category_classification`, neue reine Funktion
    `criteria.py::is_landmark_candidate` (extrahiert aus `_select_landmark_candidates`).
  - `run_criterion_scoring` vergibt die Kategorie über die reine Pro-Foto-Funktion
    `categories.py::resolve_category` (feste Vorrangreihenfolge über eine gemeinsame Kandidatenmenge
    aus lokalen Signalen und der remote ermittelten Kategorie) statt über die entfallene
    `derive_active_categories`/`derive_category_key`-Mechanik; `_merge_remote_category_labels` ist
    gelöscht. `run_remote_category_classification` schreibt je Foto eine
    `photo_category_classifications`-Zeile plus 0-2 `photo_fine_labels`-Zeilen.
    `reassign_photo_category` unverändert. `classification.py::detect_animals` → `detect_objects`
    (derselbe COCO-Detektor, genau ein Aufruf pro Foto, jetzt für `tier`/`fahrzeug`/`essen_trinken`
    ausgewertet).
  - neuer Orchestrator `worker.py::run_classification` und der einzige verbleibende
    Klassifizierungs-Job `classify` — die Jobs `score_criteria` und `classify_categories_remote`
    sind ersatzlos entfallen (`WorkerSettings.functions` registriert seither genau
    `scan_project`/`score_project`/`classify`). Ablauf: Lauf-Datensatz anlegen → bei aktiver
    Cloud-Nutzung `run_remote_category_classification` (Phase `remote_categories`) →
    `run_criterion_scoring(run=…, use_cloud=…)` (Phase `criteria`, inkl. Landmark-Teilphase). Beide
    Phasen behalten ihre eigene Run-Tabelle, ihr eigenes Concurrency-Setting und ihre
    Best-effort-Fehlerbehandlung — genau diese Trennung trägt die Teilschritt-Anzeige in der
    Oberfläche. Ein Fehlschlag der Remote-Phase bricht den Lauf NICHT ab; ihre Meldung wandert über
    den neuen Helfer `_append_cloud_error` in `CriterionScoringRun.cloud_error_message`, ebenso ein
    nicht konstruierbarer Landmark-Client und eine Zähl-Zusammenfassung fehlgeschlagener
    Landmark-Aufrufe. Neu ist dabei ein `session.refresh(run)`/`session.refresh(project)` nach einer
    fehlgeschlagenen Remote-Phase: `_fail_run` rollt die Session zurück und expired damit alle
    Objekte darin — bis Spec 0296 fiel das nicht auf, weil der fehlgeschlagene Remote-Lauf das Ende
    des Jobs war.
  - beide Cloud-Phasen (`run_criterion_scoring`s Landmark-Block,
    `run_remote_category_classification`) summieren Aufrufe und Token-Verbrauch über ihre
    ERFOLGREICHEN Ergebnisse und schreiben sie mit dem daraus berechneten Betrag an die Lauf-Zeile —
    im `finally`-Block der jeweiligen Phase samt eigenem Commit, da der Fehlerpfad über `_fail_run`
    mit einem `rollback()` beginnt. `api_calls` zählt jeden stattgefundenen Aufruf, auch wenn dessen
    `usage`-Block fehlte; genau `api_calls > 0` bei Betrag `0`/`NULL` ist der Auslöser des
    Unvollständigkeits-Hinweises. Neues Modul `pricing.py` (`MODEL_PRICING` je Modell-ID,
    `compute_cost_usd` als reine Funktion, unbekanntes Modell → `None` statt eines stillen `0.0`) —
    Code-Konstante statt Settings-Feld, weil eine Preisänderung eine belegpflichtige
    Tatsachenbehauptung ist und nicht in eine `.env` gehört.
  - `run_classification` legt den `RemoteCategoryClassificationRun` selbst an und reicht ihn per
    neuem `run`-Parameter in `run_remote_category_classification` hinein — derselbe Kniff, den ADR
    0050 Punkt 3 für `CriterionScoringRun` eingeführt hat, eine Ebene tiefer und aus demselben
    Grund: der Fremdschlüssel steht damit VOR dem ersten Cloud-Aufruf, und die pollende Oberfläche
    hat schon während der Remote-Phase einen Anker. `run_criterion_scoring` setzt `phase = landmark`
    beim Betreten des Landmark-Blocks und `phase = ranking` unmittelbar danach — ohne den vierten
    Wert bliebe die Anzeige während Kategorieableitung/`rank_photos` auf `landmark` bei 100 %
    Fortschritt stehen. Beide Cloud-Phasen setzen ihre Live-Zähler beim BETRETEN auf `0` und
    schreiben sie danach **je `asyncio.gather`-Block** samt `last_progress_at` fort; für die
    Landmark-Phase sind das die ersten Commit-Punkte überhaupt vor ihrem `finally`, und genau
    darüber schließt sich die Watchdog-Lücke. Fortgeschrieben wird am BLOCKENDE, nie beim Betreten:
    sonst stünde nach einem Abbruch mitten im Block ein `processed` da, dem weder ein Aufruf noch
    ein Fehlschlag gegenübersteht (Invariante `photos_processed == api_calls + failed_calls`, per
    Test festgeschrieben, mit der ausdrücklich festgehaltenen Ausnahme des Abbruchs innerhalb eines
    Blocks). Die Modellspalte wandert vom `finally` an den Phasenanfang — derselbe lokale Wert (ADR
    0059 Punkt 7 unverändert), nur früher committet, damit Modell und abgeleiteter Anbieter schon
    WÄHREND des Teilschritts dastehen; der **Betrag** bleibt am Phasenende eingefroren (ADR 0051
    Punkt 4). Das Zählen der Fehlschläge führt ausdrücklich KEINE neue Logzeile ein: der Fehlergrund
    bleibt in der bestehenden Zeile (feste Meldung + `type(exc).__name__`, ADR 0034 Punkt 5), in
    `photo_cloud_vision_errors` und in `cloud_error_message` — der neue Zähler ist eine Anzahl, kein
    Fremdtext. Der `classify`-Job bekommt ein viertes Argument `estimated_cost_usd` mit Default
    `None`, damit ein zum Zeitpunkt eines Deployments bereits eingereihter Job nicht an der
    Signaturänderung scheitert.
  - **Der Anbieter wird aus dem gespeicherten Modell abgeleitet**
    (`cloud_vision.py::provider_for_vision_model`), nie aus `settings.landmark_provider`: Die
    aktuelle Betriebseinstellung sagt nichts darüber, womit ein vergangener Lauf gerechnet hat.
  - Alle Cloud-Aufrufe beider Teilschritte laufen über einen prozessweiten **Schrittmacher je
    Anbieter** (`cloud_vision_throttle.py`) und werden bei HTTP `429` — und nur dort — nach einer
    gedeckelten Wartezeit wiederholt. Die Zeitgrenzen des Laufs werden dabei **nicht abgefragt**,
    sondern durch ein hart gedeckeltes Wartebudget je Anfrage eingehalten (höchstens 5 Versuche,
    120 s summierte Wartezeit, 60 s je Wartevorgang → schlimmster Fall 420 s gegen die
    15-Minuten-Schwelle des Fortschritts-Watchdogs, als Invariantentest festgeschrieben).
  - `run_project_scan` räumt nach einem **erfolgreichen** Lauf verwaiste lokale Bildkopien auf
    (neues Modul `cache_cleanup.py`, reine Mechanik in `thumbnails.py`) — der Aufruf sitzt hinter
    dem Fehler-Handler und erreicht Abbruch- und Fehlerpfad strukturell nicht, mit eigenem `except`
    samt `rollback()`/`refresh(scan_run)`, damit ein Fehler beim Aufräumen einen erfolgreichen Lauf
    weder auf `FAILED` setzt noch den anschließenden Attributzugriff in ein `MissingGreenlet` laufen
    lässt. Gelöscht wird nur, was **alles zugleich** erfüllt: direkter, **regulärer** Eintrag im
    Cache-Verzeichnis (nicht rekursiv, `os.scandir` ohne Symlink-Folgen), Name trifft
    `CACHE_FILE_PATTERN` per `re.fullmatch` exakt, Schlüssel nicht in der **ungefilterten,
    projektübergreifenden** Gültigkeitsmenge (`select(Photo.id, Photo.etag)` ohne `where`) und
    Änderungszeit älter als die Schonfrist von einer Stunde. Die Schonfrist trägt den
    Nebenläufigkeitsfall: Ein paralleler Scan schreibt die Cache-Datei **vor** dem Commit der
    Foto-Zeile, in diesem Fenster ist die Datei da und die Zeile unsichtbar — Jugend schützt, und
    unmittelbar vor dem `unlink` werden `lstat()` (nie `stat()`, das einem untergeschobenen Symlink
    folgte), `S_ISREG` und die Änderungszeit **erneut** geprüft.
  - **Die Kategorieableitung entfällt aus dem Lauf** *(Spec
    [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
    [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md))*:
    **Gelöschte Module:** `categories.py` (samt `CATEGORY_REGISTRY`, `resolve_category`,
    `secondary_categories`, `usable_confidence`, `is_known_category`,
    `build_classification_prompt`, `MAX_REMOTE_CATEGORIES_PER_PHOTO`), `category_diff.py` und der
    Router `api/categories.py`. `MAX_FINE_LABELS_PER_PHOTO` zieht dabei nach
    `remote_classification.py` um — die Zahl begrenzt, was aus **einer Anbieterantwort** übernommen
    wird, und gehört damit zum Parser, nicht zur Motiv-Registry. `run_criterion_scoring` leitet
    keine Kategorie mehr ab und bildet die Partitionen allein über `event_id`;
    `reassign_photo_category` ist ersatzlos entfallen, weil eine Motivkorrektur keine Rangzeile
    verschiebt (sie hängt am Foto, nicht am Lauf) — damit fällt die **einzige** Stelle des Projekts,
    an der ein API-Request `rank_photos` erneut aufrief. Die acht Motive und die beiden
    Anzeige-Bandgrenzen stehen in `motifs.py`; die Bandgrenzen haben **keinen Leser im Auswahl- oder
    Rangfolgepfad** und keinen im Frontend (`scripts/tests/test_kategorien_restlos_entfernt.py`
    hält beides fest). Die **Präsenzgrenze** ist davon getrennt und wohnt in `selection.py`
    (`MOTIF_PRESENCE_THRESHOLD`): Sie wird ausschließlich über das Prädikat `motif_is_present`
    gelesen — geteilt wird nie die Zahl, sonst stünde der inklusive Vergleich an zwei Stellen — und
    sie verlässt das Backend einzig als `MotifStrengthOut.present`. Beides hält der strukturelle
    Wächter in `backend/tests/test_selection.py` fest, der seit Spec 0430 auch `api/photos.py`
    führt.
- **Postgres**: Metadaten (Projekte, Fotos, Bewertungen, Nutzer), keine Bilddaten.
- **Redis**: Job-Queue für den Worker.
- **Lokaler Cache**: Docker-Volume für Thumbnails/Zwischenergebnisse, kein Ersatz für OpenCloud als
  Quelle der Wahrheit. **Implementiert (Spec
  [`0349`](../specs/features/0349-verwaiste-bildkopien-aufraeumen.md), ADR
  [`decisions/0076-verwaiste-bildkopien-verzeichnisdurchgang-mit-schonfrist.md`](../specs/decisions/0076-verwaiste-bildkopien-verzeichnisdurchgang-mit-schonfrist.md)):**
  Das Volume `photo_cache` ist ab jetzt fest an **genau eine** Datenbank gekoppelt — nach jedem
  erfolgreichen Scan entfernt `cache_cleanup.py::cleanup_orphaned_cache` daraus die gemusterten
  Dateien, zu denen es kein Foto in seiner aktuellen Fassung mehr gibt (Dateiname
  `<sha256(photo_id:etag)>_thumbnail.jpg`/`_display.jpg`, siehe `thumbnails.py::cache_key`). Zwei
  Stacks, die sich das Volume teilen, aber nicht die Datenbank, löschen sich seither gegenseitig den
  Cache; der eigene Compose-Projektname `photosort-e2e` in `docker-compose.e2e.yml` (Spec
  [`0174`](../specs/features/0174-browser-zugang-fuer-claude.md)) ist dadurch keine reine Hygiene
  mehr, sondern Betriebsauflage. Unbekannte Dateien, Unterverzeichnisse, Symlinks und alles jünger
  als eine Stunde bleiben unangetastet.
- **Prüfstack und Oberflächenprüfung** (`e2e/`, `docker-compose.e2e.yml`): eigenständiges npm-Paket
  neben `backend/`, `frontend/` und `scripts/` — `@playwright/test` (nur Chromium) prüft die real
  laufende Anwendung in einem echten Browser und dient zugleich als Ad-hoc-Blick auf die Oberfläche
  (`npm run shot` / `npm run drive`). Bewusst nicht in `frontend/` eingehängt: `vitest` und
  `@playwright/test` kollidieren über `test`/`expect`, und der `frontend`-CI-Job soll ohne
  Browser-Download bleiben. Der zugehörige Prüfstack (Compose-Projektname `photosort-e2e`, eigene
  Volumes, alle Ports auf `127.0.0.1`) fährt `postgres`/`redis`/`backend`/`frontend`; seine Zustände
  stammen aus dem deterministischen Seeder `backend/src/photosort/demo_state.py`, der über die
  echten Modelle und die echte `thumbnails.py`-Logik schreibt (kein zweites Abbild des Datenmodells)
  und durch eine dreiteilige, fail-closed Sperre gegen jede fremde Datenbank gesichert ist. Reine
  Entwicklungs-/Prüf-Infrastruktur: kein Produktivpfad importiert dieses Modul, `docker-compose.yml`
  bleibt unverändert. Siehe
  [`specs/features/0174-browser-zugang-fuer-claude.md`](../specs/features/0174-browser-zugang-fuer-claude.md)
  und ADR
  [`decisions/0058-browsergestuetzte-oberflaechenpruefung.md`](../specs/decisions/0058-browsergestuetzte-oberflaechenpruefung.md).

## Logging

Seit Spec [`0056`](../specs/features/0056-structured-logging-cloud-vision-errors.md) (ADR
[`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`](../specs/decisions/0034-strukturiertes-logging-cloud-vision-fehler.md),
erste Logging-Einführung im Projekt — zuvor kein einziges `logging`/`print` im Backend) gilt
projektweit: Pythons Standardbibliothek `logging`, kein `structlog`/JSON (keine Log-Aggregation im
Projekt, einziger Konsument ist `docker compose logs` für den Einzelbetreiber). Jedes Modul, das
loggen will, holt sich `logger = logging.getLogger(__name__)` als Modul-Konstante direkt nach den
Imports, kein Logger-Objekt wird injiziert/durchgereicht. Zentrale, einmalige Konfiguration über
`logging_config.py::configure_logging()` (`logging.basicConfig`, Level `WARNING`, Format
`%(asctime)s %(levelname)s %(name)s: %(message)s`), aufgerufen an beiden Prozess-Einstiegspunkten —
`main.py::create_app()` (API-Prozess) und `worker.py::WorkerSettings.on_startup` (Worker-Prozess,
erste Nutzung von arqs `on_startup`-Mechanismus im Projekt). `WARNING` bleibt reserviert für
erwartetes, best-effort behandeltes Verhalten (z.B. ein einzelner fehlgeschlagener
Cloud-Vision-Aufruf, der den Lauf nicht abbricht); `ERROR` bleibt an die tatsächliche
`FAILED`-Semantik eines Laufs gebunden (`_fail_run`/Watchdog, ADR 0019). Kein
`exc_info=True`/Traceback, kein Rohtext von API-Antworten/Secrets im Log — nur `type(exc).__name__`,
die bereits sanitierte `str(exc)` sowie Foto-Kontext (`photo.id`/`relative_path`). Erste Anwendung:
`worker.py::_log_cloud_vision_failure`, aufgerufen in der Landmark- und der Remote-Kategorie-Phase
direkt vor dem jeweils bestehenden best-effort-`continue`.

## Datenmodell (Skizze, wird pro Feature-Spec verfeinert)

- **User** *(implementiert, Spec 0006, `models.py`)*: Account (Daniel, Ehefrau), getrennt
  authentifiziert — `username` (frei, kein festes Enum) + `password_hash` (Argon2). Initial über
  eine idempotente Alembic-Seed-Migration angelegt, Passwörter aus Umgebungsvariablen. Künftiges
  `Rating` (Spec 0002) referenziert `User` über `user_id`.
- **Project** *(implementiert, `models.py`)*: z.B. "Costa Rica"; referenziert genau einen
  OpenCloud-Ordner (rekursiv inkl. Unterordner) über `opencloud_drive_id` + `opencloud_path`.
  - additiv `cloud_landmark_detection_enabled: bool` (Default `False`) — projektweiter
    Einwilligungs-Schalter für die Cloud-Sehenswürdigkeit-Erkennung, kein `user_id`-Bezug
    (konsistent mit dem "kein Innentäter-Modell"-Grundsatz) — und `cloud_landmark_consent_at:
    datetime | None` (Zeitstempel bei Aktivierung, `NULL` bei Deaktivierung, kein volles Audit-Log,
    analog `ScoringRun.gate_confirmed_at`). **Umbenannt (Spec
    [`0055`](../specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md), ADR
    [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md)):**
    beide Felder heißen jetzt `cloud_vision_detection_enabled`/`cloud_vision_consent_at`
    (wertsicheres `RENAME COLUMN`, Migration `b3c4d5e6f7a8`) — gaten seitdem sowohl `landmark` als
    auch die neue Remote-Kategorie-Klassifizierung. **Löschumfang (Spec
    [`0044`](../specs/features/0044-projekte-loeschen.md), ADR
    [`decisions/0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md`](../specs/decisions/0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md)):**
    `DELETE /projects/{id}` entfernt in **einer** Transaktion die Zeilen aller zwanzig am Projekt
    hängenden Tabellen (`photos`, `project_cameras`, `scan_runs`, `scoring_runs`,
    `criterion_scoring_runs`, `remote_category_classification_runs`, `ratings`, `photo_scores`,
    `photo_criterion_scores`, `photo_rankings`, `events`, `photo_landmark_detections`,
    `photo_fine_labels`, `photo_motif_assessments`, `photo_motif_strengths`,
    `photo_motif_corrections`, `photo_album_suitability`, `photo_cloud_vision_errors`,
    `final_selection_decisions`, `feedback_events`) sowie das Projekt selbst, dazu
    best-effort die Cache-Varianten des aktuellen `(photo.id, photo.etag)`-Paars. `users` und
    `fine_labels` bleiben unangetastet — beide sind Fremdschlüssel-**Eltern** und fallen aus der
    Erreichbarkeitsprüfung automatisch heraus, ohne eigene Ausnahmeliste; ein `fine_labels`-Eintrag,
    den ein anderes Projekt weiterhin referenziert, überlebt. Kein Soft-Delete, kein Undo, keine
    Audit-Tabelle. Die Liste steht nicht doppelt im Code: sie wird von zwei Tests aus
    `Base.metadata` abgeleitet (Reihenfolge gegen `reversed(sorted_tables)`, Vollständigkeit über
    die Erreichbarkeit von `projects` entlang der Fremdschlüsselkanten) — nötig, weil die Testsuite
    gegen SQLite **ohne** `PRAGMA foreign_keys=ON` läuft und eine falsche Reihenfolge dort
    strukturell nicht auffiele. `feedback_events` ist seit Spec 0432 dabei und ist zugleich die
    **einzige Ausnahme** der Append-only-Zusage dieser Tabelle: Ohne die Anweisung überlebten
    Aussagen über gelöschte Familienfotos ihr Projekt. `quality_weight_sets` und
    `quality_weight_entries` bleiben dagegen **bewusst stehen** — sie hängen an keinem Projekt,
    tragen sieben Zahlen und einen Nutzerverweis und sind auf kein Foto zurückzurechnen; ein
    eigener Testfall hält diese Gegenrichtung fest, weil die beiden Metadaten-Tests nur prüfen,
    dass nichts vergessen wird.
  - **Richtwert des Auswahlvorschlags** *(Spec
    [`0429`](../specs/features/0429-auswahl-richtwert-und-mischung.md), ADR
    [`decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md`](../specs/decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md),
    Migration `e7f8a9b0c1d2`)*: additiv `selection_target: int | None`. **`NULL` heißt nicht „kein
    Richtwert", sondern „nicht selbst eingestellt"** — wirksam ist dann ein Zehntel der Bilderzahl
    des Projekts, aufgerundet und mindestens 1, im Moment der Auswahl berechnet und damit mit dem
    Bestand mitwachsend. Die Vorbelegung wird **nie** in die Spalte geschrieben; ein
    eingeschriebener Vorgabewert wäre von einer Nutzereingabe nicht mehr zu unterscheiden. Die
    Ableitung lebt an genau einer Stelle (`selection.py::effective_target`), und `ProjectOut` trägt
    beide Werte (`selection_target`, `effective_selection_target`), damit das Frontend die zweite
    nicht selbst bildet. Projektweit, ohne `user_id`-Bezug.
  - **Bestandszahlen an `ProjectOut`** *(Spec
    [`0375`](../specs/features/0375-projektuebersicht-umfang-und-naechster-schritt.md), ADR
    [`decisions/0103-bestandszahlen-an-projectout-stand-bleibt-frontend-ableitung.md`](../specs/decisions/0103-bestandszahlen-an-projectout-stand-bleibt-frontend-ableitung.md))*:
    ohne Migration, additiv `photo_count: int`, `taken_at_earliest`/`taken_at_latest:
    datetime | None`. **`photo_count == 0` ist eine Aussage, die beiden `null` sind ihre
    Abwesenheit** — das Frontend unterscheidet sichtbar zwischen „0 Fotos" und dem Strich „keine
    Angabe". Die drei Werte entstehen an genau einer Stelle
    (`photo_aggregates.py`: `COUNT`/`MIN`/`MAX` über `photos` mit `GROUP BY project_id`) und
    speisen **sowohl** `ProjectOut` **als auch** `GET /projects/{id}/stats`; ein Projekt ohne Fotos
    fehlt in der Gruppierung und bekommt die benannte Vorgabe `(0, None, None)`. `photo_count`
    speist zugleich `effective_selection_target` — es ist dieselbe Zahl, die die Antwort ausweist,
    keine zweite Zählung daneben. Der **Bearbeitungsstand** wird bewusst **kein** Feld: er bleibt
    Frontend-Ableitung (`utils/pipelineSteps.ts`), weil dieselbe Ableitung das Ziel der
    Weiterleitung von `/projects/:id` bestimmt und ein zweiter Ort dafür auseinanderliefe.
- **OpenCloud-Verbindung**: kein eigenes DB-Modell — eine einzige, instanzweite Verbindung,
  konfiguriert über
  `OPENCLOUD_BASE_URL`/`OPENCLOUD_USERNAME`/`OPENCLOUD_APP_TOKEN`/`OPENCLOUD_DRIVE_NAME` in `.env`.
  Details siehe
  [`features/0001-opencloud-project-connection.md`](../specs/features/0001-opencloud-project-connection.md).
- **ProjectCamera** *(implementiert, Spec
  [`0426`](../specs/features/0426-zeitversatz-je-kamera.md), ADR
  [`decisions/0090-korrigierte-zeit-ist-die-aufnahmezeit-kamera-je-projekt.md`](../specs/decisions/0090-korrigierte-zeit-ist-die-aufnahmezeit-kamera-je-projekt.md),
  `models.py`)*: eine Kamera, wie sie in **genau diesem** Projekt vorkommt, samt ihrem Zeitversatz
  — `project_id` (echter Fremdschlüssel), `make`, `model`, `offset_minutes` (NOT NULL, Vorgabe
  `0`), `UniqueConstraint(project_id, make, model)`. Projekteigen statt projektübergreifend: "der
  Versatz gilt nur in diesem Projekt" ist damit **strukturell** wahr — es gibt keine Zeile, die
  zwei Projekte sehen könnten, und kein Prädikat, das in jeder Abfrage ausgeschrieben stehen
  müsste. Dieselbe Kamera in zwei Projekten sind zwei Zeilen mit getrennten Versätzen. Die Zeilen
  entstehen ausschließlich beim Scan aus den Fotos selbst; der Nutzer trägt keine Kamera ein.
  Identität ist Hersteller **und** Modell, zeichengenau und **ohne** Seriennummer — zwei baugleiche
  Gehäuse im selben Projekt sind eine Kamera und teilen einen Versatz. `offset_minutes` ist eine
  vorzeichenbehaftete Ganzzahl Minuten, keine Zeitzonenzugehörigkeit: abgebildet wird eine feste
  Zeitspanne, keine Regel mit Sommer-/Winterzeit.
- **Photo** *(implementiert, `models.py`)*: gehört zu einem Project, referenziert
  `relative_path`/`etag` auf OpenCloud, `taken_at`/`last_modified`, `content_length`. Nur
  JPEG/PNG/HEIC (MVP).
  - **`taken_at` trägt seit Spec [`0426`](../specs/features/0426-zeitversatz-je-kamera.md) die
    KORRIGIERTE Zeit** (Migration `a6b7c8d9e0f1`). Name und Rolle ("die Zeit, mit der die Anwendung
    arbeitet") sind unverändert, der Inhalt hat sich gedreht: hier steht seither die um den
    Kamera-Versatz verschobene Zeit. Daneben treten `taken_at_original: datetime` (NOT NULL, die
    aufgezeichnete Zeit — EXIF `DateTimeOriginal`, sonst der Rückfall auf `last_modified`),
    `camera_id: int | None` (echter, nullabler Fremdschlüssel auf `project_cameras`, explizit
    benannt `fk_photos_camera_id`; `NULL` heißt "Kamera nicht bestimmbar" und ist ein regulärer
    Zustand ohne Versatz) und `camera_probed: bool` (NOT NULL, `server_default` in Migration **und**
    Modell).
    - **Invariante, im Schreibpfad gehalten:** `taken_at == taken_at_original + offset_minutes` der
      Kamera dieses Fotos in genau diesem Projekt; ohne Kamera oder bei `offset_minutes = 0` sind
      beide Werte gleich. Es gibt **genau zwei** Schreibstellen —
      `worker.py::_process_scan_block` und `api/cameras.py` —, beide über die eine reine Funktion
      `cameras.py::shifted` und beide ausschließlich aus `taken_at_original` gerechnet, nie durch
      Addition auf den bestehenden Wert. Eine dritte Schreibstelle gibt es nicht; ein struktureller
      Wächtertest hält das fest, weil sie keinen Verhaltenstest röten würde. Bei Verletzung zeigt,
      gruppiert und erbt die Anwendung nach einer Zeit, die zu keinem Versatz passt — ohne
      Fehlermeldung.
    - Deshalb ändert sich an **keiner** Lesestelle etwas: `assign_clusters`, `build_events`,
      `infer_locations` (Worker und Lesepfad), die SQL-Sortierung der Fotoliste und `min`/`max` des
      Aufnahmezeitraums der Statistik rechnen ohne eine Zeile Änderung mit dem korrigierten Wert.
      Gruppierung, Reihenfolge und Ortsübernahme haben **keine** eigene Korrekturlogik.
    - `taken_at_original` trägt **weder Python- noch server-seitig einen Default**: es ist die
      einzige Kopie der aufgezeichneten Zeit, und ein unverändertes, bereits geprüftes Foto wird
      nie wieder aus EXIF gelesen — ein Schreibpfad, der die Spalte vergisst, soll laut an der
      NOT-NULL-Bedingung scheitern statt still einen falschen Wert zu erben. Das `downgrade` der
      Migration schreibt `taken_at = taken_at_original` **zurück, bevor** es die Spalte entfernt;
      ohne diesen Schritt behielte die Datenbank die korrigierten Zeiten und die aufgezeichneten
      wären fort. Die gesetzten Versätze sind nach dem Rückweg unwiederbringlich weg.
    - **Nachhol-Regel des Scans:** `camera_probed` ist der Merker "EXIF dieses Fotos wurde auf die
      Kamera-Angabe geprüft". Ein Foto ohne ihn wird beim nächsten Scan **trotz unveränderten
      Etags** erneut gelesen — nur das EXIF-Fenster, ohne Voll-Download und ohne
      Thumbnail-Neuerzeugung (`_classify_scan_entries` erzeugt dafür einen Arbeitsposten mit
      `probe_only=True`). Einmalig; danach steht der Merker, **auch wenn die Datei keine Kamera
      nennt** — sonst läse jeder weitere Scan den gesamten Bestand erneut. Ohne diese Runde bliebe
      die Kameraliste in bestehenden Projekten leer.
  - additiv `gps_lat: float | None` / `gps_lon: float | None` (Migration `d1e2f3a4b5c6`, beide
    nullable, **kein** `server_default` — `0.0` wäre eine gültige Koordinate, keine
    Abwesenheitsmarkierung —, kein Backfill). Dezimalgrad aus dem EXIF-`GPSInfo`-IFD, beim Scan über
    `opencloud/exif.py::extract_gps` aus **demselben** Range-Read-Fenster wie `taken_at` gelesen
    (kein zusätzlicher Netzwerkzugriff). `extract_gps` prüft Wertebereiche als **Vergleich, nie als
    Klemmen** — ein `IFDRational` mit Nenner 0 ergibt `nan` ohne Exception, und ein einziges
    betroffenes Foto legte sonst die gesamte Listenantwort des Projekts auf 500. Es gibt nie eine
    halbe Koordinate: scheitert eine Komponente, sind beide `None`. `_process_scan_block` schreibt beide Felder für jeden
    verarbeiteten Arbeitsposten **unbedingt**, auch zurück auf `None` — das ist der einzige Pfad,
    über den das *Entfernen* von GPS aus einer Quelldatei in PhotoSort ankommt
    (Datenschutzbedingung, siehe Sicherheitskonzept). Bereits gescannte Fotos bekommen ihre
    Koordinaten erst, wenn sich die Datei auf OpenCloud ändert (kein Bestandsnachzug, Daniels
    Entscheidung).
  - neue `cloud_vision_errors: list[PhotoCloudVisionError]`-Relationship (`cascade="all,
    delete-orphan"`, siehe `PhotoCloudVisionError`-Eintrag unten).
- **ScanRun** *(implementiert, `models.py`)*: ein (Re-)Scan-Lauf eines Projekts — Status
  (`running`/`success`/`failed`), Zähler (`files_found`, `photos_added`, `photos_updated`,
  `photos_removed`, `files_skipped`), `error_message` bei Fehlern. `files_found` wird seit
  [`features/0022-scan-live-fortschrittszaehler.md`](../specs/features/0022-scan-live-fortschrittszaehler.md)
  periodisch zwischen-committet (`worker.py::run_project_scan`, `SCAN_COMMIT_BATCH_SIZE`) statt nur
  einmal am Ende, damit die Projekt-Detailseite einen live wachsenden Zähler zeigen kann. Liefert
  die Zusammenfassung, die über `GET /projects/{id}` als `last_scan` ausgegeben wird.
  - additiv `last_progress_at: datetime` (`server_default=func.now()`, analog `started_at`), an
    denselben Stellen wie `files_found` zwischen-committet — rein interne Watchdog-Buchhaltung
    (`worker.py::reap_stalled_runs`), kein API-Response-Delta.
  - additiv `total_files: int | None` (`None` = Enumerationsphase noch nicht abgeschlossen,
    unterscheidet sich explizit von `0` = leeres Projekt — überall `is not None` statt truthy
    geprüft) — wird nach Abschluss der neuen Enumerationsphase
    (`worker.py::_enumerate_scan_entries`) einmalig gesetzt; `files_found` wechselt danach die
    Bedeutung von "in Phase 1 gelistet" auf "in Phase 2 verarbeitet" (kein zweites Zählerfeld, siehe
    ADR
    [`decisions/0020-scan-enumeration-und-parallele-verarbeitung.md`](../specs/decisions/0020-scan-enumeration-und-parallele-verarbeitung.md)).
    Im API-Response als `ScanSummary.total_files` durchgereicht, macht den bisherigen reinen
    Rohzähler zu einem echten Prozent-Fortschritt auf der Projekt-Detailseite.
- **PhotoScore** *(implementiert, Spec 0003, `models.py`, Datenmodell festgelegt in
  [`decisions/0006-local-scoring-datamodel.md`](../specs/decisions/0006-local-scoring-datamodel.md))*:
  1:1 zu `Photo` (`photo_id` als Primary Key). Ergebnis der lokalen Heuristiken aus Phase A:
  `sharpness`, `exposure`, `phash` (dHash, ohne neue Abhängigkeit direkt mit Pillow berechnet),
  `duplicate_of` (selbstreferenzierender FK auf `photos.id`), `cluster_key`, `suggested_status`
  (wiederverwendet `RatingStatus`, praktisch nur noch `REJECTED`), `computed_at`. Der geteilte
  Wertevorrat ist eine **Kopplung ohne Fremdschlüsselbeziehung**: Verliert `RatingStatus` einen
  Wert, muss diese Spalte in derselben Migration mitgeführt werden, sonst wirft eine Bestandszeile
  beim Lesen einen `LookupError` — eine 500 auf jeder Fotoliste, die das Foto enthält. Bewusst
  getrennt
  von `Rating` — ein automatischer Vorschlag ist nie eine `Rating`-Zeile, sondern wird der API/dem
  Frontend als eigenes Feld `PhotoOut.suggestion` neben `ratings` angeboten; erst eine explizite
  Nutzerbestätigung erzeugt eine echte `Rating`-Zeile über den bestehenden `PUT
  /photos/{id}/rating`-Endpunkt. **Entfernt (Spec
  [`0037`](../specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md), erste
  nicht-additive Migration im Projekt):** `category`/`local_quality_score` (Spec 0024) sind
  ersatzlos gedroppt — reiner, nie manuell editierter Ableitungszustand, dessen Nachfolge jetzt
  strukturell durch `PhotoCriterionScore`/`PhotoRanking` übernommen wird.
  - additiv `category_override: str | None` (ein beliebiger `canonical_key` statt eines von drei
    festen Werten) — dauerhafte manuelle Übersteuerung des sonst automatisch abgeleiteten
    `category_key`, `worker.py::run_criterion_scoring` verwendet `category_key =
    score.category_override or <abgeleitete Kategorie>` bei jeder künftigen Partitionsbildung.
  - der Wertebereich ist seither das feste Kategorien-Set (`categories.py::CATEGORY_REGISTRY`,
    dreizehn Werte) statt eines offenen Vokabulars; die Ableitung ist
    `categories.py::resolve_category(...)`. Die Migration setzt alle Bestandswerte auf `NULL`, da
    sie außerhalb des neuen Sets liegen.
  - **`category_override` entfällt ersatzlos (Spec
    [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
    [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md)):**
    „ein Foto umhängen" ist keine Handlung mehr, die das Datenmodell kennt. Seine Aufgabe übernimmt
    die Motivkorrektur (`photo_motif_corrections`), die keinen Schreibzugriff auf die Rangfolge und
    damit keine Sperre braucht.
  - kein Schema-Eingriff — `cluster_key` entsteht seither aus Zeit **und** Ort
    (`scoring.py::assign_clusters`, vormals `assign_time_clusters`): ein neues Cluster beginnt bei
    einer Zeitlücke über `TIME_CLUSTER_GAP` **oder** einer Haversine-Distanz über
    `GPS_CLUSTER_SPLIT_DISTANCE_METERS` (500,0) zum letzten koordinatentragenden Foto des laufenden
    Clusters; die Bezugskoordinate wird an jeder Cluster-Grenze zurückgesetzt. Ohne jede Koordinate
    im Lauf ist das Ergebnis `dict`-identisch mit dem bisherigen Zeitfensterverhalten.
    `PhotoScore.cluster_key` bleibt der **Phase-A-Basiswert** und wird von der Phase 2 **nie**
    mutiert (Ownership-Grenze ADR 0021) — seit Spec 0425 ist die Phase 2 die Event-Bildung, und die
    Divergenz zu `PhotoRanking.event_id` ist unverändert gewollt (siehe dortigen Eintrag).
- **PhotoCriterionScore** *(implementiert, Spec
  [`0037`](../specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md), `models.py`, ADR
  [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../specs/decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md))*:
  eine Zeile pro (Foto, Kriterium) — generische Tabelle statt weiterer fixer `PhotoScore`-Spalten,
  damit ein neues Kriterium nie eine neue Migration erzwingt. `criterion_key: str` (freier String,
  kein Enum — siehe `criteria.py::CRITERIA_REGISTRY`), `value: float` (immer normiert `[0, 1]`,
  "höher = besser"), `source: CriterionSource` (`local_heuristic`/`local_ml`/`cloud` — `cloud` war
  bis Spec [`0047`](../specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md) ein
  reiner, ungenutzter Registry-Wert ohne Compute-Pfad — seither hat `landmark` einen echten
  `cloud`-Compute-Pfad, siehe unten), `computed_at`. `UniqueConstraint(photo_id, criterion_key)`,
  Upsert bei jedem Lauf, keine Historie.
  - vier weitere `criterion_key`-Werte (`tier`, `gebaeude`, `aesthetics` — `source=local_ml`;
    `goldener_schnitt` — `source=local_heuristic`) — keine neue Migration, reine Erweiterung des
    bereits generischen Wertebereichs.
  - drei weitere `criterion_key`-Werte (`symmetrie`, `horizont` — `source=local_heuristic`;
    `freiraum` — `source=local_ml`), alle `category_eligible=False` — ebenfalls keine neue
    Migration, reine Erweiterung desselben generischen Wertebereichs.
  - keine Tabellen-/Spaltenänderung — die neuen
    `CriterionDefinition.category_eligible`/`.category_presence_threshold`-Felder in
    `criteria.py::CRITERIA_REGISTRY` sind reine In-Code-Registry-Metadaten (steuern, welche
    `criterion_key`-Werte als Kategorie-Quelle in Frage kommen), keine DB-Spalten dieser Tabelle.
  - ein weiterer `criterion_key`-Wert (`landmark`, `category_eligible=True`) — **erste tatsächlich
    produktiv geschriebene `source=CriterionSource.CLOUD`-Zeile** im Projekt (der Enum-Wert
    existierte bereits seit ADR 0021, war aber bis hierhin ungenutzt). Keine neue Migration, reine
    Erweiterung des bereits generischen Wertebereichs.
  - ein weiterer `criterion_key`-Wert `landschaft` (`source=local_ml`, aus derselben
    Szenen-Klassifikation wie `gebaeude`) — wieder ohne Migration, reine Erweiterung des generischen
    Wertebereichs. `content_landscape` bleibt unverändert als Zeile bestehen, ist aber nicht mehr
    kategorie-fähig (reines Ranking-Signal).
  - **Die Registry-Metadaten schrumpfen auf ein Feld** *(Spec
    [`0427`](../specs/features/0427-motive-mit-staerke.md))*: `CriterionDefinition` ist
    `key`/`display_name`/`source`/`presence_threshold`. `category_eligible` **entfällt** — es war
    genau `presence_threshold is not None` und damit eine zweite, driftende Quelle derselben
    Aussage; `category_presence_threshold` heißt nur noch `presence_threshold`. Weiterhin gibt es
    **kein Prioritäts-, Rang- oder Gewichtsfeld**: welches Motiv ein Foto trägt, entscheidet eine
    Stärke je Motiv und keine Rangliste. Nach außen tritt die Aussage als
    `CriterionScoreOut.has_presence_threshold` (ein `bool` aus der Registry, nicht die Schwelle
    selbst — die Zahl ist eine Kalibrierung und keine API-Zusage). Wieder keine
    Tabellen-/Spaltenänderung.
- **PhotoLandmarkDetection** *(implementiert, Spec
  [`0047`](../specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md), `models.py`, ADR
  [`decisions/0025-cloud-landmark-erkennung.md`](../specs/decisions/0025-cloud-landmark-erkennung.md))*:
  1:1 zu `Photo` (`photo_id` als Primary Key, analog `PhotoScore`, nicht `id`+`UniqueConstraint` wie
  `PhotoCriterionScore` — eine optionale Detail-Zeile pro Foto, kein Mehrfach-Kriterien-Fact).
  `name: str`, `confidence: float` (bewusste kleine Duplikation zu
  `PhotoCriterionScore(criterion_key="landmark").value` — hält die Tabelle für eine spätere
  UI-Abfrage ohne Join selbsttragend, beide Werte stammen atomar aus derselben API-Antwort),
  `computed_at`. Nur angelegt, wenn tatsächlich ein Name identifiziert wurde (kein Platzhalter).
  Kein UI-Verweis in v1 — reine Persistenz-Vorbereitung, vermeidet einen späteren, erneut
  kostenpflichtigen Cloud-Durchlauf aller bereits gescorten Fotos, falls der Name doch einmal
  angezeigt werden soll.
  - additiv `provider: str` (Python-seitiger Default `"anthropic"`, Migration `a2b3c4d5e6f7`) — hält
    fest, welcher Cloud-Provider (`"anthropic"`/`"mistral"`) die jeweilige Zeile erzeugt hat, atomar
    mit `name`/`confidence` im selben Upsert gesetzt.
- **ScoringRun** *(implementiert, Spec 0003, `models.py`)*: ein Lauf des Phase-A-Scoring-Jobs,
  analog zu `ScanRun` (nutzt bewusst denselben `ScanStatus`-Enum statt eines eigenen, identische
  running/success/failed-Semantik), mit `photos_total`/`photos_processed` für granularen, periodisch
  zwischen-committeten Live-Fortschritt inkl. bekanntem Nenner ("X von Y") — anders als bei
  `ScanRun.files_found`, das zwar seit Spec 0022 ebenfalls periodisch committet, aber wegen des lazy
  durchlaufenen OpenCloud-Ordnerbaums nie einen Nenner kennt — siehe
  [`decisions/0006-local-scoring-datamodel.md`](../specs/decisions/0006-local-scoring-datamodel.md).
  Liefert die Zusammenfassung, die über `GET /projects/{id}` als `last_scoring_run` ausgegeben wird.
  - additiv `last_progress_at: datetime`, analog `ScanRun` oben.
  - additiv `gate_confirmed_at: datetime | None` (Ausschuss-Gate, projektweit, kein `user_id`-Bezug)
    — vom Worker automatisch gesetzt, wenn `suggestions_found == 0`, sonst über `POST
    /projects/{id}/confirm-ausschuss-gate`.
- **CriterionScoringRun** *(implementiert, Spec
  [`0037`](../specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md), `models.py`, ADR
  0021, ersetzt `TopSelectionRun`)*: ein Lauf des Kriterien-/Rangfolgen-Jobs, analog `ScoringRun`
  (nutzt denselben `ScanStatus`-Enum); `scoring_run_id` (FK, bindet den Lauf an den
  `ScoringRun`-Stand, dessen `cluster_key` er voraussetzt — Grundlage für den `409`-Staleness-Guard
  bei einem zwischenzeitlichen Re-Scan/Re-Scoring), `photos_total`/`photos_processed` für granularen
  Live-Fortschritt (kleinere Batch-Größe als `ScoringRun`, mediapipe-Inferenz pro Foto). Kein
  `top_n_per_cluster`/`candidates_total`/`suggestions_found` mehr (anders als `TopSelectionRun`) —
  `N` ist beim Scoren nicht mehr bekannt, der Job berechnet immer den vollen Rangfolge-Pool aller
  Ausschuss-Überlebenden. Liefert die Zusammenfassung, die über `GET /projects/{id}` als
  `last_criterion_scoring_run` ausgegeben wird.
  - die Tabelle ist seither der Run-Datensatz des GESAMTEN Klassifizierungslaufs, nicht mehr nur
    seiner Kriterien-Phase — sie wird deshalb von `run_classification` angelegt, bevor die erste
    Phase startet. Drei additive Spalten (Migration `e2f3a4b5c6d7`): `phase` (neuer Enum
    `ClassificationPhase`, `remote_categories`/`criteria`; `NULL` = läuft nicht mehr, gilt auch für
    alle Altzeilen), `cloud_requested` (`NOT NULL`, Server-Default `false` — war die Cloud-Nutzung
    für diesen Lauf angefordert; Altzeilen bekommen `false`, weil die Frage nachträglich nicht
    beantwortbar ist), `cloud_error_message` (laufweite, menschenlesbare Zusammenfassung der
    Cloud-Probleme; gesetzt zu sein heißt NICHT, dass der Lauf fehlgeschlagen ist — der lokale
    Bewertungsanteil läuft trotzdem vollständig durch). Bewusst KEIN FK auf
    `remote_category_classification_runs` und keine vierte Run-Tabelle für den Gesamtlauf
    (Begründung in ADR 0050 Punkt 3).
  - vier additive, nullable Kostenspalten
    `landmark_api_calls`/`landmark_input_tokens`/`landmark_output_tokens`/`landmark_cost_usd`
    (Migration `f4a5b6c7d8e9`) — der Landmark-Anteil dieses Laufs; Präfix, weil die Tabelle seit ADR
    0050 den Gesamtlauf trägt und die Kriterien-Phase selbst nichts kostet. Python-seitiger
    Modell-Default `0`, ausdrücklich KEIN Server-Default: `NULL` heißt "nicht erfasst"
    (Bestandszeile aus der Zeit vor der Migration), `0` heißt "erfasst, keine Kosten angefallen" —
    dasselbe `ScanRun.total_files`-Idiom, und die Grundlage des Unvollständigkeits-Hinweises der
    Statistikseite. Der Betrag wird beim Phasenende eingefroren; eine spätere Preisänderung
    verändert keinen historischen Betrag.
  - fünfte additive, nullable Spalte `landmark_model` (Migration `5ab22032843c`) — die Modell-ID der
    Landmark-Phase und damit die Preisgrundlage des daneben eingefrorenen Betrags. Seit die
    Modellwahl eine Betriebseinstellung ist, sagt der je Foto persistierte `provider` nicht mehr,
    womit gerechnet wurde. `NULL` = "nicht erfasst" (Bestandszeile), ausdrücklich kein
    Server-Default mit dem damaligen Voreinstellungs-Modell — das wäre eine unbelegbare Behauptung
    über die Vergangenheit. Geschrieben im selben `finally` und Commit wie der Betrag, aus demselben
    lokalen Wert. An der Lauf- statt an den Foto-Zeilen, weil eine Foto-Zeile nur bei einem Treffer
    entsteht: ein Lauf, der Aufrufe bezahlt und nichts erkennt, hinterließe dort keine Spur des
    Modells. Bewusst ohne Lesepfad in der Oberfläche (dieselbe eng begrenzte Ausnahme wie
    Tokens/Aufrufzahl).
  - `ClassificationPhase` hat seither VIER Werte in Ausführungsreihenfolge (`remote_categories` →
    `criteria` → `landmark` → `ranking`) — der Wertebereich ist ein `VARCHAR(20)` ohne
    DB-Prüfeinschränkung, für die zwei neuen Werte war deshalb keine Migration nötig. Dazu fünf
    weitere additive, nullable Spalten (Migration `b8c9d0e1f2a3`), alle mit Python-Default `None`
    und ausdrücklich OHNE `server_default`. Drei **Live-Zähler** der Landmark-Phase —
    `landmark_photos_total` (Kandidatenzahl; zugleich der MARKER, ob es diesen Teilschritt in diesem
    Lauf überhaupt gab), `landmark_photos_processed` (abgesetzte Aufrufe, Erfolge UND Fehlschläge)
    und `landmark_failed_calls` —, gesetzt auf `0` beim Betreten der Phase (nicht bei der
    Zeilenanlage) und danach je `asyncio.gather`-Block committet. Sie sind **strikt getrennt** von
    den vier Kostenspalten darüber: die werden einmal am Phasenende geschrieben, und `api_calls > 0`
    bei Betrag `0`/`NULL` ist der Auslöser des Unvollständigkeits-Hinweises — ein laufend
    hochgezähltes `api_calls` löste ihn bei jedem laufenden Cloud-Lauf als Fehlalarm aus. Dazu
    `estimated_cost_usd` (die Schätzung, mit der genau dieser Lauf gestartet wurde; ein BELEG, nie
    eine Eingabe — sie geht in keine spätere Rechnung, kein Budget-Gate und keine Ableitung der
    Ist-Kosten ein, und bei `use_cloud=false` steht dort `NULL`, nicht `0.0`) und
    `remote_category_classification_run_id` (FK auf `remote_category_classification_runs.id`,
    gesetzt von `run_classification` vor dem Start von Phase 1; `NULL` = dieser Lauf hatte keine
    Remote-Phase oder ist eine Altzeile). Damit ist der oben genannte Vermerk „bewusst KEIN FK auf
    `remote_category_classification_runs`" aus ADR 0050 Punkt 3 **abgelöst**; der Rest jenes Punktes
    (keine vierte Run-Tabelle, `criterion_scoring_runs` als DER Lauf-Datensatz des Gesamtlaufs)
    bleibt unverändert in Kraft. Der Constraint ist **explizit benannt** — `Base.metadata` trägt
    keine `naming_convention`, und ein unbenannter Fremdschlüssel ist im `downgrade()` unter SQLite
    nicht droppbar. Für Läufe ab dieser Migration gilt die per Test festgeschriebene Invariante
    `landmark_photos_processed == landmark_api_calls + landmark_failed_calls`. Die Löschreihenfolge
    in `project_deletion.py` passte bereits (`criterion_scoring_runs` vor
    `remote_category_classification_runs`); ein benannter Testfall hält das ab jetzt fest, statt es
    dem Zufall zu überlassen. `landmark_model` bekommt mit dieser Spec seinen Lesepfad in der
    Oberfläche (die frühere Aussage „bewusst ohne Lesepfad" ist damit überholt) und wird bereits am
    Phasenanfang geschrieben statt erst im `finally`.
- **PhotoRanking** *(implementiert, Spec
  [`0037`](../specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md), `models.py`, ADR
  0021)*: der volle, sortierte Kandidatenpool einer Partition für einen `CriterionScoringRun` —
  NICHT nur die Top-N. Die Partition ist seit Spec 0425 `event_id`×`category_key`, davor
  `cluster_key`×`category_key`. `category_key: str` (freier String wie
  `criterion_key`, kein `PhotoCategory`-Enum mehr), `rank_score: float`, `rank_position: int`
  (1-basiert je Partition). `UniqueConstraint(criterion_scoring_run_id, photo_id)`. Macht "zeig die
  besten N pro Kategorie" (`GET /projects/{id}/photos?top_n_per_category=N`) zu einer reinen
  Lese-Query statt eines Job-Parameters, die Auswahl ist schlicht `rank_position <= N` je Partition.
  - kein Schema-Eingriff — im bestehenden Feld `category_key` erscheinen seit dieser Spec die neuen
    Werte `"landschaft"` und `"unerkannt"` (statt `"landscape"`/`"detail"`); Zeilen älterer Läufe
    bleiben unverändert stehen und dienen `photosort.category_diff` als "Vorher"-Stand.
  - ein Foto hat pro Lauf **eine Zeile je Kategorie**, zu der es gehört. Neue Spalte `is_primary:
    bool` (NOT NULL, **ohne** Default — ein Schreibpfad, der sie vergisst, soll auffallen statt
    still eine zweite Hauptkategorie zu erzeugen), und der Unique-Constraint wandert von
    `(criterion_scoring_run_id, photo_id)` auf
    `uq_photo_ranking_run_photo_category(criterion_scoring_run_id, photo_id, category_key)`
    (Migration `c9d0e1f2a3b4`, kein Backfill: Bestandszeilen werden einmalig zu `is_primary=true`,
    Nebenzeilen entstehen erst in einem neuen Lauf, `downgrade()` löscht sie vor dem
    Zurücktauschen). Genau eine Zeile je (Lauf, Foto) trägt `is_primary=true`; diese zweite
    Invariante ist **keine** Datenbankbedingung und wird im Schreibpfad gehalten
    (`worker.py::reassign_photo_category` stellt die gesamte Zugehörigkeitsmenge her, die
    Override-Endpunkte sperren dafür vorher die `photo_scores`-Zeile mit `with_for_update()`; ein
    `IntegrityError` aus dem neuen Constraint wird zu `409`, nie zu einer 500). **Die Ableitung
    liegt in zwei reinen Funktionen:** `categories.py::secondary_categories(confidences,
    primary_key)` liefert die Nebenkategorien in Registry-Anzeigereihenfolge — alle Schlüssel mit
    einer Modellkonfidenz `>= SECONDARY_CATEGORY_MIN_CONFIDENCE` (0,7; Konstante der Taxonomie, in
    keiner API-Antwort und keiner Umgebungsvariable), ohne die Hauptkategorie und ohne
    `nicht_erkannt`; `ranking.py::confidence_ordering_score(rank_score, confidence)` zieht für die
    SORTIERUNG innerhalb einer Partition höchstens `CONFIDENCE_RANK_PENALTY` (0,15) ab. Beide
    behandeln einen entarteten persistierten Wert als „keine Angabe" (`None`), nie als `0.0`
    (`categories.py::usable_confidence`). **`rank_score` bleibt ungedämpft** und ist damit über alle
    Zugehörigkeitszeilen eines Fotos identisch (er trägt im Frontend die Qualitäts-Einordnung);
    `rank_position` ist innerhalb einer Partition dadurch **nicht mehr monoton in `rank_score`** —
    gewollt, kein Defekt. **Die Hauptkategorie bleibt unberührt:**
    `resolve_category`/`derive_photo_category` behalten Signatur und Regeln, keine Zahl entscheidet,
    WELCHE Kategorie gilt. **API:** `PhotoOut.ranking` entfällt ersatzlos zugunsten von
    `PhotoOut.rankings: list[RankingOut]` (immer eine Liste, Hauptzeile zuerst, danach
    Registry-Anzeigereihenfolge); `RankingOut` trägt zusätzlich `is_primary` und `curation_position`
    (der Platz dieser Zugehörigkeit in der um die eigenen Ablehnungen bereinigten Auswahl —
    nutzerabhängig, **nie** persistiert oder zwischengespeichert, ausdrücklich nicht dieselbe Zahl
    wie `rank_position`). Gezählt wird in Auswertungen weiterhin die Hauptkategorie
    (`api/stats.py::_ranking_counts_by_category` und `category_diff.py::collect_assignments` filtern
    auf `is_primary`), die Partitionsgröße im Info-Popover dagegen **alle** Zeilen der Partition.
  - **kein Schema-Eingriff, keine Migration, kein neues Antwortfeld** — die Story nutzt aus, was
    diese Tabelle ohnehin führt: den **vollen** Pool. Der Ablehnungsfilter fällt aus
    `api/photos.py::_top_n_per_category_photo_ids` (Outer-Join auf `Rating` und `row_number()`
    entfallen), womit beim Verwerfen nichts mehr nachrückt und die Auswahl ausschließlich vom Lauf
    abhängt statt vom Bewertungsstand des Betrachters. `curation_position` ist dadurch **entweder
    `null` oder gleich `rank_position`**; ihre verbliebene Aufgabe ist allein die Auskunft, unter
    welchen Kategorien ein Foto zu zeigen ist. Die Auflage „nutzerabhängiger
    Cache-/`ETag`-Schlüssel“ entfällt **nicht**, sondern wandert vom Feld an den Antwortaufbau
    (`_to_photo_out`/`list_photos`) und hängt dort an `PhotoOut.suggestion`. Der bisher
    unerreichbare Rest einer Partition wird über den neuen Lese-Endpunkt `GET
    /projects/{id}/curation-candidates` einsehbar.
  - **Spaltentausch** *(Spec [`0425`](../specs/features/0425-events-statt-zeitcluster.md), ADR
    0087, Migration `f5a6b7c8d9e0`)*: `cluster_key: str` wird durch `event_id: int` **ersetzt**
    (echter Fremdschlüssel, NOT NULL), nicht ergänzt — zwei Träger derselben Zugehörigkeit
    nebeneinander wären eine zweite, driftende Abbildung. Die nachträgliche Landmark-Verfeinerung
    (`scoring.py::refine_clusters_by_landmark`, Schlüsselform `cluster-<n>-<i>`) entfällt
    **ersatzlos**: sie erzeugte zeitlich zerrissene Gruppen, in denen „überschneidungsfrei" gar
    nicht herstellbar war. Die Sehenswürdigkeit wirkt seither als **Trennsignal** im einen
    Durchlauf der Event-Bildung. **Die Migration löscht alle Zeilen dieser Tabelle** und legt für
    Altläufe keine Events an (die Lauf-Zeilen selbst bleiben unangetastet — sie tragen die nicht
    wiederherstellbaren Ist-Kosten der Cloud-Aufrufe). Ein Lauf von vor dieser Änderung **muss
    einmal neu berechnet werden**; bis dahin zeigt die Kuratierung für ihn nichts, und der
    Leerzustand der Ansicht trägt diesen Fall. **Die Divergenz zu `PhotoScore.cluster_key` bleibt
    beabsichtigt** (analog `category_key`, ADR 0021): dort steht weiterhin der Phase-A-Basiswert,
    hier die pro Lauf tatsächlich für Kuratierung und Anzeige verwendete Gliederung.
  - **Die Partition verliert die Kategorie-Dimension** *(Spec
    [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
    [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md))*:
    `category_key` und `is_primary` entfallen, der Unique-Constraint geht auf
    `uq_photo_ranking_run_photo(criterion_scoring_run_id, photo_id)` zurück. Die Partition ist allein
    das Event, ein Foto steht pro Lauf in **genau einer** Zeile, und der Sortierschlüssel ist wieder
    der reine `rank_score` — `ranking.py::confidence_ordering_score` samt
    `CONFIDENCE_RANK_PENALTY` entfällt, weil es die Partition nicht mehr gibt, innerhalb derer er
    verglich. `PhotoOut.rankings` wird wieder `PhotoOut.ranking: RankingOut | None`, `RankingOut`
    verliert `is_primary`. **Die Migration (`c3d4e5f6a7b8`) dünnt `photo_rankings` auf eine Zeile je
    `(criterion_scoring_run_id, photo_id)` aus — und zwar VOR dem Constraint-Tausch**, sonst ist sie
    an einer echten Datenbank nicht ausführbar. Sie tut das nicht über `WHERE is_primary = false`:
    Das setzte voraus, dass je Gruppe genau eine Zeile `is_primary = true` trägt, und ein Bestand mit
    zwei solchen Zeilen (oder mit keiner) überlebte die Löschung und brächte den neuen Constraint zum
    Scheitern. Stattdessen behält ein einziges portables `DELETE` über
    `ROW_NUMBER() OVER (PARTITION BY criterion_scoring_run_id, photo_id ORDER BY is_primary DESC,
    id ASC)` je Gruppe genau die erste Zeile — die frühere Hauptzeile, wenn es eine gibt, sonst die
    älteste. Die Reihenfolge der beiden Schritte ist am gerenderten Postgres-DDL geprüft
    (`test_postgres_ddl_compatibility.py`), die Datenwirkung am SQLite-Lauf
    (`test_migration_kategorien_abloesung.py`) — einschließlich des Falls zweier Hauptzeilen.
    `downgrade()` stellt die **Struktur** wieder her, **nie die Daten**: `category_key` kommt als
    Leerstring zurück, `category_override` als `NULL`.
  - **`rank_score` und `rank_position` werden nullable, und `rank_score` ist ab hier der
    Qualitätswert** *(Spec [`0428`](../specs/features/0428-albumtauglichkeit-vom-modell.md), ADR
    [`decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md`](../specs/decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md))*:
    er entsteht nicht mehr aus der Gleichgewichtung aller Kriterien, sondern aus
    `quality.py::compute_quality_score` — der Modellstufe der Albumtauglichkeit, korrigiert um
    höchstens `±LOCAL_CORRECTION_SPAN` durch die lokalen Qualitäts-/Kompositionskriterien;
    Inhaltssignale gehen nicht mehr ein. `NULL` in beiden Spalten heißt **„kein Qualitätswert, weil
    keine Modellbewertung"** (Cloud nicht freigegeben, oder der Aufruf für dieses Foto ist
    fehlgeschlagen); ein solches Foto erscheint nicht im Album-Entwurf, bleibt aber im einsehbaren
    Vorrat. `event_id` bleibt `NOT NULL` — die Gliederung nach Events ist keine Cloud-Leistung und
    entsteht auch ohne Freigabe.
  - **Neue Spalte `selection_position: int | None` und eine neue Auswahlregel** *(Spec
    [`0429`](../specs/features/0429-auswahl-richtwert-und-mischung.md), ADR
    [`decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md`](../specs/decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md),
    Migration `e7f8a9b0c1d2`)*: der 1-basierte Platz eines Fotos im Auswahlvorschlag **innerhalb
    seines Events**; `NULL` heißt „gehört nicht zum Vorschlag". Der Vorschlag ist damit ein
    **persistiertes Lauf-Artefakt** statt eines Leseparameters: „die besten N je Event, N beim
    Ansehen gewählt" entfällt ersatzlos. Berechnet wird er von der reinen, DB-freien Funktion
    `selection.py::select_album_draft` in zwei Stufen — Kontingente je Event (jedes Event
    mindestens ein Platz, der Rest nach `√n_i` im Größte-Reste-Verfahren, Obergrenze
    `min(n_i, max(⌈T/m⌉, ⌈0,25·T⌉))` mit Umverteilung der gekappten Plätze) und darin eine
    motivgeführte Greedy-Vergabe mit Ähnlichkeitsabwertung
    (`rank_score · 0,5^Σ ähnlichkeit`, `ähnlichkeit = geteiltes_motiv · max(0, 1 − |Δt|/15min)`).
    Auswahlfähig ist eine Rangzeile mit `rank_score IS NOT NULL` und ohne `excluded_document` am
    Foto. **Geschrieben an genau einer Stelle** (`worker.py`, ein struktureller Wächter in
    `test_models.py` hält das fest), mit drei Auslösern: dem Kriterien-Lauf und dem Neuaufbau nach
    einer Versatz-Änderung (beide über `_build_grouping_and_rankings`, innerhalb der bestehenden
    Phase `RANKING` — **kein** neuer `ClassificationPhase`-Wert) sowie `rebuild_run_selection`
    hinter dem Richtwert-Endpunkt. **Der Wert ist lauf-global und hat keinen Nutzerbezug.**
    Bestandsläufe tragen überall `NULL` und zeigen einen leeren Vorschlag, bis ein neuer Lauf oder
    eine Richtwert-Änderung ihn erzeugt; eine rückwirkend rechnende Migration gibt es bewusst
    nicht.
- **Event** *(implementiert, Spec
  [`0425`](../specs/features/0425-events-statt-zeitcluster.md), `models.py`, Tabelle `events`, ADR
  [`decisions/0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md`](../specs/decisions/0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md),
  Migration `f5a6b7c8d9e0`)*: ein Abschnitt der Reise — eine zusammenhängende Folge von
  Kandidatenfotos **eines** `CriterionScoringRun`, mit `position` (1-basiert, chronologisch),
  `started_at`/`ended_at`, `landmark_name` und `place_kind`/`place_lat`/`place_lon`.
  `UniqueConstraint(criterion_scoring_run_id, position)`, echter Fremdschlüssel auf den Lauf.
  - **Warum persistiert:** Nummer und Zeitspanne sind Bestandteil des *Namens* und müssen deshalb
    unabhängig davon feststehen, welche Fotos eine Antwort gerade enthält. Ein Event ist ein
    Lauf-Artefakt wie `PhotoRanking`, kein reiner Funktionswert über `photos`; der Ortswert eines
    einzelnen Fotos bleibt unpersistiert.
  - **Gebildet wird in EINEM sortierten Durchlauf** (`events.py::build_events`, aufgerufen in
    `worker.py::_build_grouping_and_rankings` an der Stelle der früheren Landmark-Verfeinerung —
    nach der Cloud-Phase, vor dem Aufbau der Partitionen).
  - **Zwei Aufrufer, EIN Weg zur Gliederung** *(Spec
    [`0426`](../specs/features/0426-zeitversatz-je-kamera.md))*: Event-Bildung, Partitionen,
    Kategorieableitung und Rangzeilen stehen seither gemeinsam in
    `worker.py::_build_grouping_and_rankings`. Aufrufer sind der Kriterien-Lauf
    (`run_criterion_scoring`) **und** `worker.py::rebuild_run_grouping`, das der Versatz-Endpunkt
    nach einer Änderung ausführt: Reihenfolge, Anzeige und Ortsherleitung sind mit der Bedeutung
    von `taken_at` sofort richtig, die **Events** sind dagegen persistierte Lauf-Artefakte und
    wären es nicht. Der Neuaufbau **löscht und schreibt neu** statt umzuhängen —
    `UniqueConstraint(criterion_scoring_run_id, position)` lässt alte und neue Events desselben
    Laufs nicht gleichzeitig zu — und leitet die Kategorie-Zugehörigkeiten **neu ab** statt sie aus
    den alten Zeilen zu übernehmen; sonst gäbe es zwei Wege zur Hauptkategorie, und ein
    zwischenzeitlich gesetzter Override könnte still verloren gehen. Daraus folgt die prüfbare
    Zusage: ein Neuaufbau mit Versatz `0` erzeugt denselben Zustand wie der Lauf selbst. Die
    Funktion liest alles selbst aus persistierten Werten (zwei Abfragen mehr je Lauf) und
    committet nicht — die Transaktionsgrenze gehört dem Aufrufer, der genau einmal committet. Ein
    Versatzwechsel vergibt dabei **neue Event-Ids**; ein Client, der sie zwischenspeichert, hält
    sie nicht über die Änderung hinweg. Die Grenzen entstehen aus einer **Liste
    gleichrangiger Trennsignale**: Zeitlücke (`TIME_CLUSTER_GAP`), Kalendertag (Vergleich der
    ersten zehn Zeichen des zonenlosen Zeitstempels — neu, eine Nacht ohne Zeitlücke trennt
    seither), Schrittabstand (`GPS_CLUSTER_SPLIT_DISTANCE_METERS`), **Ausdehnung**
    (`EVENT_EXTENT_MAX_METERS`, 1000,0 — Diagonale der umschließenden Box **einschließlich** des
    betrachteten Fotos; unkalibriert und durch keinen Test gepinnt) und Sehenswürdigkeit-Wechsel.
    Der Durchlauf fragt **alle** Signale bei jedem Kandidaten (`any` über eine gebaute Liste,
    ausdrücklich nicht kurzgeschlossen) und ruft danach genau eine der schreibenden Methoden auf
    allen auf. Nur diese Trennung von reiner Frage (`is_boundary`) und Fortschreibung
    (`begin`/`advance`) erlaubt ein zustandsbehaftetes Signal neben einem paarweisen, ohne dass die
    Auswertungsreihenfolge zum Bestandteil des Ergebnisses wird — ein weiteres Signal ist danach
    eine Klasse und ein Listeneintrag.
  - **Die Ausdehnung ist der fachliche Kern:** die bisherige Schwelle begrenzte den *Schritt*, nicht
    den Durchmesser — ein Spaziergang in 400-m-Schritten trennte nie und überspannte Kilometer.
  - **Der Ortsbezug entsteht ausschließlich aus GEMESSENEN Koordinaten und Namen** (Rangfolge
    Sehenswürdigkeit → eine gerundete Koordinatenzelle → `multiple` → kein Ortsbezug). Ein
    übernommener Ort speist ihn nie: eine Ortsaussage über eine Einheit darf nicht aus Schätzungen
    entstehen. Geprüfte Feldkombination: `'landmark'` ⇒ `landmark_name` gesetzt; `'coordinate'` ⇒
    beide Koordinaten gesetzt; `'multiple'` ⇒ beide Koordinaten NULL.
  - `events.landmark_name` entsteht **ausschließlich** über `worker.py::_landmark_names` (und damit
    `sanitize_landmark_name`) — kein direkter Zugriff auf `PhotoLandmarkDetection.name` an der
    Schreibstelle, kein Abschneiden, und die Migration kopiert **keine** Namen.
  - `events.place_name` *(Spec [`0434`](../specs/features/0434-ortsnamen-fuer-events.md), ADR
    [`0102`](../specs/decisions/0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md),
    Migration `d7e8f9a0b1c2`)*: der aufgelöste **Ortsname dieses Events in diesem Lauf**, nullable
    und additiv — Altläufe behalten `NULL`, nachgezogen wird nichts. Er entsteht in
    `events.py::assign_place_names` aus den Ortsauskünften der Zellen des Events (`PlaceLookup`,
    siehe unten) und ist ausdrücklich **kein Ortswissen**: Ob ein Event „Berlin" oder „Berlin,
    Kreuzberg" heißt, hängt davon ab, was sonst im selben Lauf liegt. Regeln: genau ein Ortsname
    über alle Zellen ⇒ dieser Name, null oder mehrere ⇒ keiner; ein Event **mit** Sehenswürdigkeit
    bekommt keinen und löst auch bei keinem anderen die Viertel-Ergänzung aus; mehrfach vergebene
    Namen bekommen je Event einzeln ihr Viertel, sofern genau eines vorliegt und `"Ort, Viertel"`
    die Längengrenze hält — **gekürzt wird nie**, zwei gekappte Namen wären ein Name und die
    Viertel-Regel griffe für Events an verschiedenen Orten.
- **Rating** *(implementiert, Spec 0002, `models.py`; Neufassung mit Spec
  [`0430`](../specs/features/0430-album-entwurf-je-nutzer.md) / ADR
  [`0098`](../specs/decisions/0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md))*: Die
  Aussage **eines** Users zu **einem** Photo, pro User getrennt gespeichert; Unique-Constraint
  `(photo_id, user_id)`. Zwei unabhängige Felder:
  - `status: RatingStatus | None` — die **Albumentscheidung**, `album_worthy` („gehört ins Album")
    oder `rejected` („gehört nicht ins Album"). Sie ist **keine Aussage über die Bildgüte**; die
    steht allein in `PhotoAlbumSuitability`. `NULL` heißt „keine Albumentscheidung" und ist
    gleichbedeutend mit dem Fehlen der Zeile.
  - `favorite: bool` (`server_default` in Modell **und** Migration) — die Auszeichnung als Favorit.
    Unabhängig von `status`, beide können zugleich gesetzt sein, und sie wirkt nicht auf den
    Album-Entwurf.

  **Aus dem Vorhandensein einer Zeile folgt damit nichts mehr** über den Bewertungsstand: Eine
  Zeile kann allein wegen `favorite` existieren. Jede Lesestelle, die „bewertet" meint, prüft
  `status IS NOT NULL` — der Rasterfilter `unrated`, die Statistikzahl `unrated` und die Bedingung,
  unter der `PhotoOut.suggestion` erscheint.

  **Invariante, an genau einer Stelle durchgesetzt** (`api/ratings.py::_write_own_rating`, über die
  alle drei Schreibendpunkte laufen): Es gibt keine Zeile mit `status IS NULL AND favorite IS
  FALSE` — sie wird gelöscht. Eine solche Zeile wäre auf keinem Lesepfad als Fehler erkennbar,
  unterdrückte aber dauerhaft den Ausschuss-Vorschlag.

  Die drei Schreibendpunkte schreiben je genau ihr Feld, `user_id` stammt überall ausschließlich
  aus `current_user`: `PUT /photos/{id}/rating` (nur `status`, `null` ist kein zulässiger
  Body-Wert), `DELETE /photos/{id}/rating` (nimmt nur `status` zurück und behält eine Zeile mit
  Kennzeichen), `PUT /photos/{id}/favorite` (nur `favorite`).
- **PhotoCategoryClassification** *(implementiert, Spec
  [`0289`](../specs/features/0289-feste-kategorien.md), `models.py`, Tabelle
  `photo_category_classifications`, ADR
  [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](../specs/decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md))*:
  **1:1 zu `Photo`** (`photo_id` als Primary Key und FK, `cascade="all, delete-orphan"`) — das
  Ergebnis der Remote-Kategorie-Klassifizierung, nachdem die Vorrangreihenfolge aufgelöst wurde.
  `category_key: str` (immer ein Wert aus `categories.py::CATEGORY_REGISTRY`), `detected_categories:
  JSON` (die validierte Kandidatenliste des Modells als Audit-Spur — nach der Vorrangauflösung ist
  "warum landete das Foto hier?" die wahrscheinlichste Frage und sonst unbeantwortbar), `provider:
  str`, `computed_at`. 1:1 statt 1:N, weil pro Foto genau eine Kategorie entsteht — das Schema
  erzwingt die Kernaussage der Spec, statt sie nur zu befolgen. Existenz dieser Zeile ist zugleich
  das Skip-Kriterium (`worker.py::select_remote_category_candidates`) und die Erfolgs-Ableitung des
  `remote_category`-Cloud-Vision-Status (`api/photos.py::_cloud_vision_status_out`).
  - zwei additive, nullable Spalten (Migration `a3b4c5d6e7f8`). `detected_category_confidences:
    JSON` ist die Abbildung `category_key -> Konfidenz in [0, 1]` — eine ABBILDUNG und kein
    positionsparalleles Array: der Wert hängt am Schlüssel und überlebt jede Umsortierung. Ihre
    Schlüssel sind eine Teilmenge von `detected_categories` (`set(mapping) <=
    set(detected_categories)`, am Parser erzwungen) — sie sind ein ZWEITER Persistenzkanal aus der
    Modellantwort und werden deshalb erst NACH Schlüsselvalidierung, Dedup und Kappung gefiltert.
    `category_confidence: Float` ist die Konfidenz zur aufgelösten Kategorie dieser Zeile, also
    `detected_category_confidences.get(category_key)` — bewusst redundant, weil die
    Statistik-Aggregation in SQL laufen muss (`AVG` über einen aus JSON extrahierten Wert ist in
    SQLite und PostgreSQL unterschiedlich zu schreiben) und alle Klassifizierungszeilen eines
    Projekts nach Python zu laden nicht zur Größenannahme passt. Tragbar, weil es genau EINE
    schreibende Stelle gibt (`worker.py::run_remote_category_classification`, ein
    Objekt-Konstruktor); die Invariante wird getestet. Beide Spalten ohne `server_default` und ohne
    Backfill: `NULL` heißt "nicht erhoben", `0.0` hieße "das Modell war sich zu 0 % sicher" —
    dasselbe Muster wie bei den Kostenspalten (ADR 0051). Bestandszeilen bleiben dauerhaft ohne
    Angabe, auch bei einem erneuten Lauf (der Worker überspringt jedes Foto mit vorhandener
    Klassifizierungszeile). **KEIN Codepfad, der eine Kategorie bestimmt, liest diese Spalten** (ADR
    0067 Punkt 1) — sie werden ausschließlich von der API-Ausgabe, der Statistik-Aggregation und dem
    Frontend gelesen.
  - **Die Tabelle entfällt vollständig** *(Spec
    [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
    [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md))*:
    mit der Hauptkategorie fällt ihr Inhalt, und eine Tabelle ohne Leser stehen zu lassen verschiebt
    nur die Frage, was sie bedeutet, auf die nächste Änderung. Ihre beiden anderen Rollen —
    Skip-Kriterium des Cloud-Teilschritts und Erfolgs-Ableitung seines Status — übernimmt
    `photo_motif_assessments`. Kein Backfill: die gespeicherten Konfidenzen werden **nicht** in
    Motivstärken umgerechnet (das wäre eine Modellaussage, die das Modell nie getroffen hat).
    Migration `c4d5e6f7a8b9` (eigene Revision **nach** dem Spaltenabbau `c3d4e5f6a7b8`, damit ein
    Tabellenabbau und ein Spaltenumbau nicht in einer Revision vermischt sind); `downgrade()` legt
    sie leer wieder an.
- **PhotoMotifAssessment** *(Spec [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR
  [`decisions/0091-motive-mit-staerke-statt-hauptkategorie.md`](../specs/decisions/0091-motive-mit-staerke-statt-hauptkategorie.md),
  `models.py`, Tabelle `photo_motif_assessments`)*: die **Grundlage** der Motivbeurteilung eines
  Fotos, **1:1 zu `Photo`** (`photo_id` als Primary Key und Fremdschlüssel,
  `cascade="all, delete-orphan"`). `source` (`cloud` | `local`, `SQLEnum(native_enum=False)`),
  `excluded_document: bool` (NOT NULL, **ohne jeden Default** — ein Schreibpfad, der die Spalte
  vergisst, soll laut scheitern statt still ein Foto aus jeder Motivauswahl zu entfernen),
  `provider: str | None` (`NULL` bei lokaler Grundlage), `computed_at`. **Die Abwesenheit dieser
  Zeile ist der Zustand „noch nicht klassifiziert"** und damit unterscheidbar von „nichts erkannt"
  (Zeile vorhanden, Stärken durchgehend niedrig). Eine Cloud-Grundlage wird von einem lokalen Lauf
  **nie** überschrieben; der Kriterien-Lauf schreibt nur, wenn keine Zeile existiert oder die
  vorhandene `source='local'` trägt.
- **PhotoMotifStrength** *(Spec [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR 0091,
  `models.py`, Tabelle `photo_motif_strengths`)*: **1:N** zur Kopfzeile (Fremdschlüssel auf
  `photo_motif_assessments.photo_id`, `UniqueConstraint(photo_id, motif_key)`) — `motif_key: str`
  (freier String wie `criterion_key`, der Lesepfad prüft die Mitgliedschaft in
  `motifs.py::MOTIF_REGISTRY`), `strength: float` in `[0, 1]`. Zeilen statt einer JSON-Abbildung,
  weil je Motiv sortiert und geschwellt wird und eine JSON-Struktur zu Zeilen zu expandieren in
  SQLite und PostgreSQL unterschiedlich zu schreiben ist. Eine Stärke kann ohne Kopfzeile nicht
  existieren; eine neue Grundlage ersetzt den **gesamten** Vektor eines Fotos. Eine in einer
  Cloud-Antwort nicht genannte Stärke wird als `0.0` geschrieben, nicht als „keine Angabe": der
  Prompt verlangt alle acht Zahlen, Schweigen ist dort die Aussage „nicht zu sehen".
- **PhotoAlbumSuitability** *(Spec [`0428`](../specs/features/0428-albumtauglichkeit-vom-modell.md),
  ADR
  [`decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md`](../specs/decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md),
  `models.py`, Tabelle `photo_album_suitability`)*: das Urteil des Vision-Modells darüber, wie
  brauchbar ein Foto für ein Album ist — **1:1 zu `Photo`** (`photo_id` als Primary Key und
  Fremdschlüssel). `level: int` (die Modellstufe `1..5`, normiert über
  `album_suitability.py::normalize_level` auf `[0, 1]`; der normierte Wert bekommt **keine** zweite
  Spalte), `reason: str | None` (zeichensanierte, längenbegrenzte Modellbegründung; `NULL` heißt
  „keine brauchbare Begründung", nie eine leere Zeichenkette), `provider: str`, `computed_at`.
  Bewusst **nicht** an `photo_motif_assessments` gehängt, obwohl beide aus demselben Modellaufruf
  entstehen: die Kopfzeile ist eine Aussage über den Bildinhalt und existiert auch auf lokaler
  Grundlage, diese Zeile ist eine Aussage über die Bildgüte und existiert nur mit Cloud-Grundlage.
  Die Abwesenheit der Zeile ist der Zustand „nicht beurteilt" und macht das Foto erneut zum
  Kandidaten des Modellaufrufs, ohne dass das Projekt neu eingelesen werden muss.
- **FinalSelectionDecision** *(Spec [`0431`](../specs/features/0431-endauswahl-gemeinsam.md), ADR
  [`decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md`](../specs/decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md),
  `models.py`, Tabelle `final_selection_decisions`)*: die **gemeinsame Entscheidung des Projekts**
  über ein Foto — `photo_id` als Primary Key **und** Fremdschlüssel auf `photos` (Muster
  `PhotoAlbumSuitability`; „höchstens eine Entscheidung je Foto" ist damit strukturell wahr, ohne
  eigenen Unique-Constraint), `included: bool` **NOT NULL ohne jeden Default**, `updated_at`.
  **Kein `user_id`, kein `decided_by`, keine Lauf-Bindung:** Die Entscheidung gehört dem Projekt,
  nicht einem Nutzer — wer angemeldet ist, spielt für ihre Wirkung keine Rolle, und es gibt keine
  Spalte, in der ein Nutzerbezug stehen könnte. Weil die Zeile am **Foto** hängt und an keinem Lauf,
  überlebt sie jeden neuen Vorschlagslauf. Die **Abwesenheit** der Zeile heißt „unentschieden", und
  es gibt keinen Weg zurück in diesen Zustand (kein `DELETE`-Endpunkt); genau deshalb trägt
  `included` keinen Vorgabewert — ein solcher erfände eine Entscheidung, die niemand getroffen hat,
  und der so entstandene Zustand wäre nicht korrigierbar, nur überschreibbar. Die Endauswahl selbst
  wird **nicht** materialisiert. Zuordenbarkeit, wer was wollte, bleibt unangetastet in den
  `Rating`-Zeilen.
- **PhotoDuplicateDecision** *(Spec [`0374`](../specs/features/0374-duplikate-vergleichen.md), ADR
  [`decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md`](../specs/decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md),
  `models.py`, Tabelle `photo_duplicate_decisions`)*: die Entscheidung des **Projekts** darüber, ob
  eine Aufnahme des Ausschusses den Ausschuss-Schritt **überlebt** — `photo_id` als Primary Key
  **und** Fremdschlüssel auf `photos` (Muster `FinalSelectionDecision`), `decision ∈ {keep,
  discard}` **NOT NULL ohne jeden Default**. Kein `user_id`, keine Lauf-Bindung; die Abwesenheit
  der Zeile heißt „noch nicht entschieden", und es gibt keinen Weg zurück in diesen Zustand.
  **`discard` und ausdrücklich nicht `RatingStatus.REJECTED`:** Jenes ist die Albumentscheidung
  eines Nutzers, dies die Antwort auf eine andere Frage auf einer anderen Ebene — ein geteilter
  Wertevorrat machte die beiden an jeder Lesestelle verwechselbar. Die **Duplikat-Gruppe** bekommt
  keine eigene Entität: Sie bleibt ein zur Lesezeit über `PhotoScore.duplicate_of` gebildeter
  Stern (`duplicates.py`), flach nach Bauart, und eine gespeicherte Gruppen-Id wäre ein zweites
  Abbild derselben Aussage, das jeder Lauf neu vergeben müsste.
- **FeedbackEvent** *(Spec
  [`0432`](../specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md), ADR
  [`decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md`](../specs/decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md),
  `models.py`, Tabelle `feedback_events`)*: **ein Handgriff der Nacharbeit am Album-Entwurf**,
  unveränderlich festgehalten — die erste Tabelle des Projekts, die **Verlauf statt Zustand** hält.
  Spalten: `id` (Primary Key), `project_id` (Fremdschlüssel, NOT NULL, indiziert), `user_id`
  (Fremdschlüssel, **nullable**), `photo_id` (Fremdschlüssel, NOT NULL), `kind` (neun Werte:
  `photo_included`, `photo_removed`, `decision_withdrawn`, `exchanged`, `motif_added`,
  `motif_dropped`, `motif_correction_withdrawn`, `final_decision_in`, `final_decision_out`),
  `occurred_at`, `weight` (NOT NULL, Vorbelegung `1.0`), `criterion_scoring_run_id`, `event_id`,
  `replaced_photo_id`, `motif_key`, `motif_strength`, `level`/`replaced_level`,
  `quality`/`replaced_quality`.
  - **Append-only:** Auf die Tabelle läuft ausschließlich `INSERT`; einzige Ausnahme ist die
    Projektlöschung. Daraus folgen ohne durchsetzenden Code beide Zusagen der Story — ein Ereignis
    überlebt jede Neuklassifizierung und die Rücknahme der Korrektur, und mehrere Korrekturen am
    selben Foto bleiben in ihrer Reihenfolge erkennbar. **Die Reihenfolge *ist* die aufsteigende
    `id`**, nie `occurred_at`: Zwei Schreibvorgänge derselben Sekunde sind über eine Zeit nicht zu
    ordnen. Ein struktureller Wächter hält fest, dass außerhalb von `project_deletion.py` kein
    Modul `update`/`delete` auf dieser Tabelle absetzt.
  - **Die eingefrorene Entscheidungslage:** `level`, `quality` und `motif_strength` halten fest, was
    zum Zeitpunkt der Korrektur galt und von einem späteren Lauf überschrieben wird — sonst wäre
    „zu schwach oder gar nicht genannt?" danach nicht mehr beantwortbar. Alle sind **nullbar**; ein
    Foto ohne Modellbewertung erzeugt trotzdem ein Ereignis. Eingefroren wird die **gespeicherte**
    Motivstärke, nie die wirksame: Letztere trägt bereits eine frühere Korrektur desselben Paares.
    Die lokalen Kriterienwerte werden dagegen **nicht** eingefroren — sie sind eine
    deterministische Messung an denselben Pixeln.
  - **`user_id IS NULL` genau für `final_decision_in`/`final_decision_out`:** Die gemeinsame
    Entscheidung gehört dem Projekt, und ihr Schreibendpunkt nimmt aus genau diesem Grund kein
    `current_user` entgegen (ADR 0099). Ein Ereignisschreiber, der sich dafür eines besorgte, führte
    das dort verworfene `decided_by` durch die Hintertür ein.
  - **`event_id` trägt keinen Fremdschlüssel**, obwohl die Spalte wie eine Referenz aussieht:
    `worker.py::rebuild_run_grouping` löscht die `events`-Zeilen eines Laufs und legt sie neu an.
    Ein echter Fremdschlüssel hielte den Neuaufbau an oder risse Log-Zeilen mit — beides bräche die
    Append-only-Zusage. Gültig ist die Spalte allein zusammen mit dem `criterion_scoring_run_id`
    derselben Zeile.
  - Geschrieben wird ausschließlich über `feedback_log.py`; dort hängt die Feldmatrix je `kind`
    (welches Feld pflichtig, welches verboten), in beide Richtungen durchgesetzt. Festgehalten
    werden nur Verweise, Zeitpunkt, Art und Zahlen — **keine Bilddaten, kein Fremdtext**.
- **QualityWeightSet / QualityWeightEntry** *(dieselbe Spec und ADR, `models.py`, Tabellen
  `quality_weight_sets`/`quality_weight_entries`)*: **eine Fassung des global geltenden
  Gewichtssatzes** der Qualitätskriterien und ihre Gewichte je Kriterium.
  `quality_weight_sets`: `id` (Primary Key **und** die Version), `created_at`,
  `created_by_user_id` (Fremdschlüssel, NOT NULL), `origin` (`feedback`|`revert`),
  `based_on_event_id` (nullable, **ohne** Fremdschlüssel), `reverts_set_id` (Fremdschlüssel auf
  sich selbst, nullable). `quality_weight_entries`: `id`, `set_id` (Fremdschlüssel, Kaskade),
  `criterion_key` (**freier String ohne Fremdschlüssel**, derselbe Grund wie bei
  `photo_criterion_scores` — ein neues Kriterium erzwingt nie eine Migration), `weight`,
  `UniqueConstraint(set_id, criterion_key)`.
  - **Es gilt die Fassung mit der höchsten `id`.** Es gibt kein `active`-Kennzeichen, das
    danebentreten und mit ihr auseinanderlaufen könnte; `id` *ist* die Version.
  - **Ohne eine einzige Zeile gelten die Startwerte** aus `quality.py`. Keine Migration schreibt
    sie ein — ein eingeschriebener Vorgabewert wäre von einer übernommenen Anpassung nicht mehr zu
    unterscheiden, und „zurück auf die Startwerte" hieße danach „zurück auf eine Fassung, die
    jemand übernommen hat". Aus demselben Grund ist die Vorgängerin der ersten Fassung der
    Startwertsatz, ohne dass er je gespeichert würde.
  - **Keine Bindung an Projekt oder Nutzer.** `created_by_user_id` ist Urheberschaft, nie
    Geltungsbereich: Die Fassung wirkt auf jeden Lauf jedes Projekts. Beide Tabellen hängen
    folgerichtig an **keinem** Projekt und bleiben von der Projektlöschung **unberührt** — sie
    tragen sieben Zahlen und einen Nutzerverweis, keinen Foto-Bezug; ein eigener Testfall hält
    diese Gegenrichtung fest.
  - `criterion_scoring_runs.quality_weight_set_id` (nullable) hält fest, **mit welcher Fassung ein
    Lauf gerechnet hat**; `NULL` heißt „Startwerte oder Altzeile". Gelesen und geschrieben wird
    **einmal je Lauf** vor der Partitionsschleife (`worker.py::_build_grouping_and_rankings`, dazu
    `demo_state.py`) — zuvor stand die Konstante innerhalb der Schleife, je Foto neu. Ohne die
    Spalte wäre ein vergangener `rank_score` nach der nächsten Anpassung nicht mehr nachrechenbar.
- **PhotoMotifCorrection** *(Spec [`0427`](../specs/features/0427-motive-mit-staerke.md), ADR 0091,
  `models.py`, Tabelle `photo_motif_corrections`)*: die menschliche Korrektur **einer** Motivaussage
  — `photo_id` (Fremdschlüssel auf `photos`, Kaskade), `user_id`, `motif_key`, `applies: bool`,
  `updated_at`, `UniqueConstraint(photo_id, motif_key)`. Bewusst **nicht** am Lauf und nicht an der
  Kopfzeile: deshalb überlebt sie jede erneute Klassifizierung ohne Sonderfallcode. Fehlende Zeile
  heißt „nicht korrigiert" (Muster wie `Rating`), Entfernen ist Löschen. `user_id` hält fest, wer
  zuletzt korrigiert hat, steht aber **nicht** im Unique-Constraint — die Korrektur ist eine Aussage
  über das Foto, nicht über einen Geschmack. Der Schlüsselraum sind **ausschließlich die acht
  Motive**: `dokument_screenshot` ist nicht korrigierbar, ein fälschlich ausgeschlossenes Foto kommt
  allein über einen erneuten Klassifizierungslauf zurück. Die **wirksame** Stärke entsteht im
  Lesepfad (`applies=true` → `1.0`, `applies=false` → `0.0`, keine Zeile → Wert der Grundlage) und
  wird nie in die Stärkezeile materialisiert; der SQL-Ausdruck dafür lebt an genau einer Stelle
  (`motif_strengths.py`), gehalten von einem Wächtertest.
- **PlaceLookup** *(Spec [`0434`](../specs/features/0434-ortsnamen-fuer-events.md), ADR
  [`0102`](../specs/decisions/0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md),
  `models.py`; Tabelle `place_lookups`, Migration `d7e8f9a0b1c2`)*: die Auskunft darüber, **was an
  einer vergröberten Ortszelle liegt** — `project_id` (echter Fremdschlüssel, NOT NULL),
  `cell_lat`/`cell_lon` (das auf `places.PLACE_CELL_DIGITS` gerundete Paar aus
  `places.place_cell`), die vier Stufen `neighbourhood`/`locality`/`region`/`country`,
  `matched_level`, `source`, `resolved_at`; `UniqueConstraint(project_id, cell_lat, cell_lon)`.
  - **LAUF-UNABHÄNGIG und trotzdem am Projekt.** Einmal beschafft, danach wiederverwendet: dieselbe
    Zelle wird in einem zweiten Lauf nicht erneut gefragt, dieselbe Zelle in einem zweiten Projekt
    dagegen schon — die Auskunft des einen Projekts wird für das andere nie gelesen. Jede Zeile ist
    eine Aussage darüber, wo die Familie war, kein allgemeines Vokabular wie `fine_labels`; sie ist
    damit die **dauerhafteste Ortsspur des Systems** und fällt ausschließlich mit dem Projekt
    (`project_deletion.py`). Es gibt bewusst keinen zweiten Weg, sie loszuwerden.
  - **Beschafft wird ausschließlich im Worker** (`worker.py::_place_infos`, gebunden an
    `project_id`). Drei unterschiedene Ausgänge: **keine Antwort** schreibt keine Zeile (sonst
    vergiftete eine vorübergehende Störung die Zelle dauerhaft), eine **Antwort ohne brauchbare
    Ebene** schreibt eine Zeile mit leeren Namensstufen und wird nicht erneut gefragt, und
    **mehrere Ortsnamen im Event** ergeben keinen Namen. In allen drei Fällen behält das Event
    Nummer und Zeitspanne, und der Lauf läuft weiter. `rebuild_run_grouping` bekommt **keinen**
    Auflöser: es läuft in einem Request, liest nur den Bestand und fragt niemanden.
  - **Vier benannte Stufen, kein Beutel.** Straße und Hausnummer fallen am Parser-Rand und
    erreichen die Tabelle nie. `matched_level` ist die Aussage der Quelle, nicht die Ableitung aus
    gefüllten Spalten, und wird an beiden Rändern gegen `places.PLACE_LEVELS` geprüft; ein Treffer
    auf `region`/`country` gilt als „kein Name aufgelöst".
- **Der Ortsdatensatz als Betriebsartefakt** *(ADR
  [`0105`](../specs/decisions/0105-ortsnamen-aus-dem-lokalen-datensatz-als-auszug-auf-einem-volume.md))*:
  Die Ortsauskunft entsteht **vollständig innerhalb des Systems**, aus einem vorbereiteten Auszug
  des GeoNames-Datensatzes — kein externer Ortsdienst, kein Schalter, der einen aufmachen könnte.
  Der Auszug ist eine GeoNames-Datei mit **geleerten ungebrauchten Spalten** an unveränderter
  Spaltenposition (dieselben Zeilen, dieselben Felder, derselbe Parser wie die Rohdatei), gepackt
  rund 69 MB, erzeugt vom getippten Kommando `python -m photosort.place_dataset`. Er liegt auf dem
  Volume `place_dataset`: im Backend-Dienst schreibbar, im Worker **nur lesend** — genau ein
  Schreiber, und der operative Pfad ist keiner. **Geprüft wird vor jedem Gebrauch die Datei, die
  gelesen wird**, gegen den beim Bezug gebildeten Hash; stimmt er nicht oder fehlt sie, wird
  **kein Auflöser gebaut** (`geonames.py::build_place_resolver`), es entsteht **kein Ersatzweg**,
  und jeder Lauf schreibt eine laute Zeile mit festem Grund-Token. Das ist der Zustand von heute —
  Events heißen dann nach Nummer und Zeitspanne —, kein Fehlerzustand. Weder Rohdatei noch Auszug
  liegen im Image oder im Repository.
- **FineLabel** *(implementiert, Spec
  [`0055`](../specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md),
  `models.py`; Tabelle `fine_labels`, bis Spec 0289 `category_labels`/`CategoryLabel`, ADR
  [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](../specs/decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md))*:
  kanonische Label-Registry für die offene Remote-Kategorie-Klassifizierung — bewusst
  **projektübergreifend** (kein `project_id`-Bezug: reine Vokabular-Einträge, keine Fotoinhalte,
  verhindert wiederholte Neuanlage identischer Label über mehrere Projekte hinweg). `canonical_key:
  str` (`UNIQUE`, Slug), `display_name: str` (zuerst gesehener Roh-Label-Text), `embedding: JSON`
  (384-dimensionaler Text-Embedding-Vektor, `label_embedding.py`), `created_at`. Kein Cascade-Ziel
  bei `DELETE /projects/{id}`.
  - die Registry kanonisiert seither ausschließlich **Feinlabels** (frei formulierte
    Zusatzinformation am Foto, inkl. der Anlass-Dimension) — sie bildet keine Kategorien mehr; die
    Ähnlichkeitsauflösung selbst (`resolve_canonical_label`) ist unverändert und macht die
    Häufigkeitsauswertung `GET /projects/{id}/fine-labels` belastbar. Der Vokabular-Bestand bleibt
    bei der Umstellung erhalten (nur die Zuordnungszeilen werden geleert).
- **PhotoFineLabel** *(implementiert, Spec
  [`0055`](../specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md),
  `models.py`; Tabelle `photo_fine_labels`, bis Spec 0289
  `photo_category_detections`/`PhotoCategoryDetection`, ADR
  [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](../specs/decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md))*:
  **1:N zu `Photo`** (bis zu drei Zeilen pro Foto, ein Roh-Label je Zeile — anders als
  `PhotoLandmarkDetection`, das 1:1 bleibt). `raw_label: str` (ungekürzter Roh-Text, Audit-Spur),
  `confidence: float`, `provider: str`, `computed_at`, FK auf `CategoryLabel`.
  `UniqueConstraint(photo_id, fine_label_id)` — verhindert Duplikate, falls zwei Roh-Labels
  desselben Fotos auf denselben `canonical_key` auflösen.
  - 0-2 Zeilen pro Foto (statt 1-3), Spalte `fine_label_id` (vormals `category_label_id`),
    `confidence` entfällt ersatzlos (kein Codepfad wertet sie mehr aus). Die Zeilen sind **reine
    Zusatzinformation** — sie beeinflussen `PhotoRanking.category_key` nicht mehr und werden auch
    dann geschrieben, wenn die Kategorie `nicht_erkannt` lautet.
- **RemoteCategoryClassificationRun** *(implementiert, Spec
  [`0055`](../specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md),
  `models.py`, ADR
  [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md))*:
  ein Lauf des Remote-Kategorie-Klassifizierungs-Jobs, analog `CriterionScoringRun`, aber bewusst
  OHNE `scoring_run_id`-FK (dieser Job schreibt ausschließlich in
  `photo_category_detections`/`category_labels`, berührt weder `cluster_key` noch `PhotoRanking`
  direkt — kein `409`-Staleness-Guard, kein Ausschuss-Gate-Erfordernis).
  `photos_total`/`photos_processed`/`last_progress_at` analog den übrigen Run-Tabellen. Liefert die
  Zusammenfassung, die über `GET /projects/{id}` als `last_remote_category_classification_run`
  ausgegeben wird.
  - die Tabelle ist unverändert, ihre Bedeutung nicht — sie ist seither der Datensatz der ERSTEN
    PHASE des verketteten Klassifizierungslaufs statt eines eigenständig ausgelösten Laufs. Sie
    entsteht nur bei aktiver Cloud-Nutzung; ein rein lokaler Durchlauf erzeugt gar keine Zeile. Ihre
    Fortschrittszahlen speisen die Oberfläche, solange `CriterionScoringRun.phase ==
    'remote_categories'`.
  - vier additive, nullable Kostenspalten `api_calls`/`input_tokens`/`output_tokens`/`cost_usd`
    (Migration `f4a5b6c7d8e9`) — identische `NULL`-vs.-`0`-Semantik wie bei `CriterionScoringRun`,
    hier ohne Präfix, weil dieser Lauf genau einen Zweck hat.
  - fünfte additive, nullable Spalte `model` (Migration `5ab22032843c`) — Gegenstück zu
    `CriterionScoringRun.landmark_model`, Begründung und `NULL`-Semantik wortgleich dort, hier
    erneut ohne Präfix.
  - sechste additive, nullable Spalte `failed_calls` (Migration `b8c9d0e1f2a3`) — der Live-Zähler
    der fehlgeschlagenen Einzelaufrufe, Gegenstück zu `CriterionScoringRun.landmark_failed_calls`;
    `photos_total`/`photos_processed` dieser Tabelle gab es bereits und wurden schon vorher je Block
    committet, deshalb kommt hier nur diese eine Spalte hinzu. Geschrieben am bereits vorhandenen
    Block-Commit-Punkt, nicht im `finally`: die Story verlangt die Zahl WÄHREND des Laufs. Die Zeile
    wird seither von `run_classification` angelegt und hineingereicht (neuer `run`-Parameter), damit
    der Fremdschlüssel des Klassifizierungslaufs sie vor dem ersten Cloud-Aufruf treffen kann; beim
    Direktaufruf legt `run_remote_category_classification` sie weiterhin selbst an. Der obenstehende
    Satz „Liefert die Zusammenfassung, die über `GET /projects/{id}` als
    `last_remote_category_classification_run` ausgegeben wird" gilt **nicht mehr**: dieses Feld ist
    ersatzlos entfallen, die Zahlen kommen jetzt über `last_criterion_scoring_run.cloud_phases` —
    also über den Remote-Lauf DIESES Durchlaufs statt über den jüngsten des Projekts.
- **PhotoCloudVisionError** *(implementiert, Spec
  [`0058`](../specs/features/0058-cloud-vision-status-transparenz.md), `models.py`, ADR
  [`decisions/0035-cloud-vision-attempt-fehler-persistierung.md`](../specs/decisions/0035-cloud-vision-attempt-fehler-persistierung.md))*:
  der letzte bekannte Fehlschlag eines Cloud-Vision-Laufs (`landmark`/`remote_category`, neuer Enum
  `CloudVisionPhase`) für ein Foto — bewusst KEIN Verlauf, nur der jeweils aktuellste Zustand.
  Composite Primary Key `(photo_id, phase)` statt eines separaten `id`+`UniqueConstraint`-Paars
  (analog `PhotoScore`) — es gibt strukturell höchstens eine sinnvolle "letzter Fehlschlag"-Zeile je
  Foto×Lauf-Typ. `error_type: str`/`error_message: str` (identischer Inhalt wie der
  `WARNING`-Log-Eintrag aus Spec
  [`0056`](../specs/features/0056-structured-logging-cloud-vision-errors.md)/ADR 0034 —
  `type(exc).__name__`/`str(exc)`, an der jeweiligen Call-Site einmal berechnet, an Log UND diese
  Tabelle weitergereicht; `error_message` beim Schreiben auf 500 Zeichen gekappt,
  `worker.py::_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH`), `attempted_at: datetime`. Ein
  erneuter Fehlschlag überschreibt (Upsert, `worker.py::_record_cloud_vision_error`) die bestehende
  Zeile, ein erfolgreicher (Retry-)Versuch löscht sie (`worker.py::_clear_cloud_vision_error`) —
  hält die Tabelle konsistent mit ihrer eigenen Bedeutung. Nur diese eine Tabelle ist tatsächlich
  neu: die übrigen fünf möglichen Cloud-Vision-Zustände pro Foto×Lauf-Typ
  (`not_run`/`not_candidate`/`consent_disabled`/`no_result`/`result`) sind bereits vollständig aus
  bestehenden Signalen ableitbar und werden read-time über `api/photos.py::_cloud_vision_status_out`
  bestimmt, nicht separat gespeichert (Zentraler Befund von ADR 0035, vereinfacht den ursprünglich
  vom `requirements-engineer` skizzierten Entwurf einer vollen Status-Tabelle).

## Bewusste Annahmen (können per ADR/Spec revidiert werden)

- Kein eingebauter Reverse Proxy/TLS in `docker-compose.yml` — das Homeserver-Setup von Daniel
  übernimmt das.
- CPU-only-Betrieb: alle lokalen KI-Heuristiken müssen ohne GPU praktikabel laufen.
- Cloud-KI-Aufrufe sind optional/on-demand und nie Voraussetzung für die Kernfunktion — **die
  Kernfunktion ist dabei seit Spec [`0428`](../specs/features/0428-albumtauglichkeit-vom-modell.md)
  ausdrücklich abgegrenzt** (ADR
  [`decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md`](../specs/decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md),
  Abschnitt 1): Scan, Ausschuss-Gate und lokale Bewertung laufen vollständig ohne Cloud, der
  Album-Entwurf dagegen setzt die Freigabe voraus und entsteht ohne sie gar nicht — ohne stillen
  Rückfall auf einen rein lokal gebildeten Qualitätswert. Mit Spec
  [`0047`](../specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md) (ADR
  [`decisions/0025-cloud-landmark-erkennung.md`](../specs/decisions/0025-cloud-landmark-erkennung.md))
  erstmals tatsächlich eingelöst statt nur vorgesehen: das `landmark`-Kriterium ist die **erste
  produktive, aber projektweit standardmäßig deaktivierte** Cloud-Anbindung im
  Kriterien-Scoring-Pfad (Default `Project.cloud_landmark_detection_enabled=False`) — alle sieben
  übrigen Kriterien bleiben rein lokal, kein Projekt verlässt ohne explizite Einwilligung den
  Homeserver. Setzt den in ADR 0015 als vorübergehend markierten "vorerst keine remote
  Modelle"-Grundsatz bewusst und einmalig außer Kraft, genau für den einen Fall, für den lokale
  Erkennung von Anfang an als unwirtschaftlich verworfen wurde (Sehenswürdigkeit-Erkennung braucht
  LLM-Weltwissen, kein trainierbares lokales Modell).
- Zwei lokale ML-Frameworks im Backend-Image (Spec
  [`0038`](../specs/features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md),
  ADR
  [`decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md`](../specs/decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md)):
  `mediapipe` (Gesicht/Tier/Gebäude/Freiraum, seit Spec 0048 vier Task-API-Paare derselben
  Abhängigkeit) und `tensorflow` (nur Ästhetik/NIMA, lokal importiert). Ein drittes schweres
  Framework (z.B. PyTorch für eine treuere Innenraum-Erkennung) wurde bewusst nicht eingeführt —
  Docker-Image-Wachstum ist dadurch trotzdem real gemessen erheblich (Baseline 1,3 GB → 4,17 GB,
  siehe ADR-0022-Nachtrag 2026-08-15), aber weiterhin kein Blocker für den Homeserver.
  `opencv-contrib-python` (Spec
  [`0048`](../specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md), ADR
  [`decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md`](../specs/decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md))
  ist seit dieser Spec eine explizite, direkte `backend/pyproject.toml`-Abhängigkeit
  (`horizon.py::compute_horizon_tilt_score`, klassische `cv2`-Kantendetektion, kein ML-Modell) —
  **kein drittes schweres Framework und kein neuer Netto-Footprint**, da dieselbe Distribution
  bereits seit Spec 0024 transitiv über `mediapipe` im Image vorhanden war; die Zeile macht eine
  bisher implizite Abhängigkeit nur explizit. Die aktive `cv2`-Nutzung ist strukturell auf
  `cv2.Canny`/`cv2.HoughLinesP` auf bereits über Pillow dekodierten Pixeldaten begrenzt, nie auf
  `cv2.imread`/`cv2.imdecode` — Pillow bleibt die alleinige Bild-I/O-Bibliothek im Projekt.

- Der automatisierte Oberflächen-Prüflauf ist **bewusst unvollständig**: der Prüfstack
  (`docker-compose.e2e.yml`) enthält weder eine OpenCloud-Instanz noch den Worker. Begründung: das
  ungepinnte `opencloud-rolling`-Image wäre die wahrscheinlichste Ursache sprunghaft fehlschlagender
  Läufe und stünde damit direkt gegen die Zusage "ein Fehlschlag ist ein verlässliches Signal"; und
  kein Prüfschritt löst einen Hintergrundjob aus. Folge, die man kennen muss: der Ordner-Browser
  wird dort nur in seinem *Fehler*zustand geprüft, sein Normalfall gar nicht, und jeder Zustand, den
  sonst erst ein Hintergrundjob erzeugt, kommt aus dem Seeder statt aus einem echten Lauf.
  Contract-Drift gegen den echten OpenCloud-Server bleibt unverändert nur durch den manuellen
  Smoke-Test abgefangen.