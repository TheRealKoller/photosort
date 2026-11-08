# 0621 - Eyes Albumtauglichkeit im Album-Entwurf

**Status:** Accepted
**Erstellt:** 2026-11-08
**Bezug:** Issue [#621](https://github.com/TheRealKoller/photosort/issues/621), ADR
[`0144`](../decisions/0144-albumstufe-folgt-dem-verfahren-des-laufs.md)

Umfang über dem Richtwert, weil drei Schichten (Lauf, API, Oberfläche) und je Abschnitt prüfbare
Zusagen in einer Spec stehen.

## Ziel

Ein Projekt, das seine Fotos mit Eye auf dem Heimserver einstuft, bekommt heute keinen
Album-Entwurf: Der Entwurf setzt eine Cloud-Bewertung voraus. Diese Story hebt die Kopplung auf:
Eyes Stufe fließt in den Entwurf ein, sodass auch ein Projekt ohne Cloud-Einwilligung einen
vollständigen Entwurf erhält — ohne einen einzigen Cloud-Aufruf.

Welche Stufe zählt, folgt der Kategorisierung, die im Projekt eingestellt ist (Spec 0383). Die
Regel ist eine einzelne, austauschbare: Eine spätere gemeinsame Auswertung von Eye und Cloud (#622)
ersetzt sie.

Bekanntes Restrisiko: Ob Eye geschlossene Augen und verdeckte Gesichter erkennt, ist nicht
ausgewertet. Sichtbar wird die Herkunft jeder Stufe trotzdem.

## User Story

Als Nutzer eines Projekts, das seine Fotos mit Eye auf dem Heimserver einstuft, möchte ich, dass
Eyes Albumtauglichkeit in den Album-Entwurf einfließt, damit ich auch ohne Cloud-Einwilligung
einen vollständigen Entwurf bekomme und an jedem Bild sehe, woher seine Einstufung stammt.

## Akzeptanzkriterien

**Entwurf ohne Cloud**

- [x] Ein Projekt ohne Cloud-Einwilligung, das für die Kategorisierung Eye eingestellt hat, erhält nach einem erfolgreichen Lauf einen Album-Entwurf; während des ganzen Laufs gibt es keinen Cloud-Aufruf und keine Cloud-Kosten.
- [x] In einem solchen Projekt erscheint kein Hinweis mehr, dass für den Entwurf eine Cloud-Freigabe nötig sei — weder auf der Entwurfsseite noch in der Ablaufübersicht.
- [x] Ist Eye in dieser Installation nicht eingeschaltet oder noch nie gelaufen, bleibt die Ansicht nicht leer, sondern nennt den fehlenden Schritt.

**Welche Stufe zählt**

- [x] Für ein Foto zählt ausschließlich die Stufe des Verfahrens, das im Projekt für die Kategorisierung eingestellt ist — auch dann, wenn das Foto zusätzlich eine Stufe des anderen Verfahrens trägt.
- [x] Fehlt einem Foto die Stufe des eingestellten Verfahrens, gibt es keinen Rückfall auf die Stufe des anderen Verfahrens und keinen rein lokal gebildeten Wert; das gilt auch für ein Foto, dessen Eye-Aufruf fehlgeschlagen ist. Es behält seine Event-Zugehörigkeit, bleibt im einsehbaren Vorrat und wird nicht vorgeschlagen; von Hand aufgenommen erscheint es als „noch nicht eingestuft".
- [x] Ein späterer Lauf des eingestellten Verfahrens holt fehlende Stufen nach, auch für Fotos, die aus früheren Läufen schon eine Eye-Stufe tragen; Fotos mit vorhandener Stufe dieses Verfahrens werden nicht erneut bewertet.

**Wechsel der Projekteinstellung**

- [x] Ein Wechsel zwischen Cloud und Eye ändert den bestehenden Vorschlag nicht sofort, sondern wirkt mit dem nächsten erfolgreichen Lauf; bis dahin bleiben Entwurf, Stufen und Herkunft unverändert.
- [x] Nach dem ersten Lauf mit der neuen Einstellung enthält der Vorschlag nur noch Fotos mit einer Stufe des neuen Verfahrens; Stufen des vorherigen Verfahrens bleiben gespeichert und zählen wieder, sobald zurückgewechselt und erneut gelaufen wurde. Von Hand aufgenommene und gestrichene Fotos bleiben über jeden Wechsel erhalten.

**Anzeige**

- [x] Bei einem Foto, dessen zählende Stufe von Eye stammt, steht an der Stelle der Begründung die Herkunft „Eye" — an der Entwurfskachel, im Alternativen-Band und in der Endauswahl. Keine leere Zeile, kein Platzhalter, kein erfundener Text.
- [x] Die Qualitätsstufe (wenig / bedingt / gut albumtauglich) wird für Eye-Stufen nach derselben Einteilung angezeigt wie für Cloud-Stufen; es gibt keine zweite Skala und keine Umrechnung.

**Was unverändert bleibt**

- [x] Eye-Stufen ändern weder die Kandidatenmenge noch die Kostenschätzung des nächsten Cloud-Laufs.
- [x] In einem Projekt mit eingestellter Cloud-Kategorisierung bleiben Entwurf, Stufen und Begründungen nach einem Eye-Lauf unverändert.
- [x] Scan, Ausschuss-Gate, die lokale Bewertung und die Klassifizierungsprüfung bleiben unverändert.

## Datenmodell-Bezug

- `criterion_scoring_runs.album_level_source` (neu, `CategoryMethod` `cloud`/`eye`, NOT NULL,
  bleibender `server_default 'cloud'`); Migration `6299223059c8_album_level_source.py`,
  `down_revision = "43a3afeb7312"` (Kennung aus `scripts/nummern.py migration
  album-level-source`, Exit 0).
- Gelesen, nicht geändert: `photo_album_suitability.level`, `photo_eye_results.album_level`
  (beide 1–5), `photo_rankings.rank_score`.
- Siehe [`docs/architecture.md`](../../docs/architecture.md) (Modellwahl, `CriterionScoringRun`,
  `PhotoRanking`, Eye-Tabellen).

## Architektur / Umsetzung

Entscheidung: [ADR 0144](../decisions/0144-albumstufe-folgt-dem-verfahren-des-laufs.md). Die
zählende Stufe folgt dem am **Lauf** eingefrorenen Verfahren, nicht der aktuellen
Projekteinstellung — deshalb wirkt ein Wechsel erst mit dem nächsten erfolgreichen Lauf, auch über
`rebuild_run_grouping` (Versatz) hinweg.

### Datenfluss

1. **Verfahren am Lauf.** `models.py::CriterionScoringRun.album_level_source:
   Mapped[CategoryMethod]` mit demselben `SQLEnum` wie `Project.category_method`
   (`native_enum=False`, `length=20`, `values_callable`), `default=CategoryMethod.CLOUD`,
   `server_default="cloud"`. Migration additiv per `batch_alter_table`, ohne Datenmigration,
   `downgrade()` entfernt die Spalte (Muster `43a3afeb7312_modellwahl_je_projekt.py`).
   `worker.py::_start_criterion_scoring_run` setzt `album_level_source=project.category_method` für
   **jeden** Modus, auch `local`.
2. **Ein Lesepunkt.** Neues Modul `backend/src/photosort/album_stage.py`:
   `async def load_album_levels(session, source: CategoryMethod, photo_ids: Collection[int]) ->
   dict[int, int]`. `CLOUD` liest `PhotoAlbumSuitability.level`, `EYE` `PhotoEyeResult.album_level`,
   je mit `in_(photo_ids)`; leere Eingabe → `{}` ohne Abfrage; nie ein Rückfall, nie ein lokaler
   Wert.
3. **Rangbildung.** `worker.py::_build_grouping_and_rankings` ersetzt die Inline-Abfrage durch
   `load_album_levels(session, run.album_level_source, values_by_photo_id.keys())`. Beide Aufrufer
   (`run_criterion_scoring`, `rebuild_run_grouping`) folgen damit. Ein Foto ohne zählende Stufe
   bleibt auf dem bestehenden Pfad (`rank_score`/`rank_position` NULL, `event_id` bleibt).
   `quality.py`, `selection.py`, `compute_quality_score` unverändert.
4. **Eye holt nur nach.** `worker.py::_run_eye_phase`: Kandidaten zusätzlich
   `~exists().where(PhotoEyeResult.photo_id == Photo.id)`; `api/projects.py::_count_eye_candidates`
   zählt dieselbe Menge (bewusste, dokumentierte Doppelung). Schattenzeilen und `upsert_assessment`
   nur für neu analysierte Fotos; `eye_photos_total` zählt die Nachhol-Menge; ein gescheitertes
   Foto hat keine Zeile und ist im nächsten Eye-Lauf wieder Kandidat. Eye schreibt weiterhin nie in
   `photo_album_suitability`, `photo_fine_labels`, `fine_labels`.
5. **Herkunft in der API (`api/photos.py`).** `AlbumSuitabilityOut.source: Literal["cloud",
   "eye"]`. `_album_suitability_out(photo, source)`: `EYE` → `level=eye_result.album_level`,
   `reason=None`, `source="eye"`; `CLOUD` → wie heute plus `source="cloud"`; fehlende Zeile →
   `None` — unabhängig von der Herkunft der Motiv-Kopfzeile. `_to_photo_out` bekommt den
   **Pflicht**-Keyword-Parameter `album_level_source`, an allen sechs Aufrufstellen (Entwurf,
   Fotoliste, Endauswahl, Duplikatgruppe, `_ausschuss_photo_outs`, Alternativen). Neuer Helfer
   `_album_level_source(session, project)`: Quelle des jüngsten erfolgreichen Laufs, ohne Lauf
   `project.category_method`; einmal je Anfrage. `_eye_result_out`/`PhotoOut.eye_result`
   unverändert.
6. **Feedback friert die zählende Stufe ein.** `api/photos.py::_exchange_sides(session, run_id,
   source, photo_ids)` liest `level` über `load_album_levels` statt per OUTER JOIN;
   `feedback_log.load_frozen_context` nutzt die Quelle des geladenen Laufs, ohne Lauf
   `project.category_method` (eine `select(Project.category_method)`-Abfrage, kein Lazy-Load).
   Sonst stammte die Feedback-Stufe aus einem anderen Verfahren als der eingefrorene `rank_score`.
   Bestehende Feedback-Ereignisse bleiben unverändert.
7. **Frontend.** `api/types.ts`: `AlbumSuitabilityOut.source: 'cloud' | 'eye'` (alle Fixtures
   ergänzen). Darstellung siehe `## UI/UX`. `PhotoDetailPage.tsx` nimmt
   `currentPhoto.album_suitability` (die Stufe reist mit ihrer Herkunft); `utils/eyeVerdict.ts`
   liefert nur noch `fineLabels`.

### Randfälle

- Foto mit beiden Stufen: nur die des Lauf-Verfahrens zählt; die andere bleibt gespeichert,
  unsichtbar.
- Wechsel ohne neuen Lauf: Entwurf, Stufen, `source` bleiben, auch nach Versatz-Neuaufbau.
- Altläufe tragen `album_level_source='cloud'` — wahrheitsgemäß, Verhalten unverändert.
- Eye-Projekt **mit** Einwilligung: die Sehenswürdigkeits-Phase darf weiter die Cloud rufen
  (ADR 0138); das AK „kein Cloud-Aufruf" gilt für ein Projekt **ohne** Einwilligung.

### Ausdrücklich unverändert

Scan, Ausschuss-Gate (`survives_ausschuss`), lokale Bewertung, `compute_quality_score`/
`normalize_level`, `classification_review.py`, `classification_comparison.py`,
`select_remote_category_candidates`, `_count_remote_category_candidates`, Cloud-Anteil von
`_build_classification_estimate`, Rangfolge `local < eye < cloud` in `upsert_assessment`,
`demo_state.py`.

## UI/UX

Nur bestehende Bausteine, keine neuen Farben.

### Herkunft statt Begründungszeile

- `CurationDetails.tsx` (Entwurfskachel, Alternativen-Band, Endauswahl) und `PhotoVerdict.tsx`:
  bei `album_suitability?.source === 'eye'` erscheint im Platz der Begründungszeile eine
  Herkunftszeile — immer vorrangig vor `reason`, auch wenn `reason` unerwartet gesetzt ist.
- Neue Konstanten in `utils/albumSuitability.ts`: `ALBUM_SUITABILITY_ORIGIN_LABEL = 'Eingestuft
  von'`, `ALBUM_SUITABILITY_EYE_ORIGIN_TEXT = 'Eye'`; die Zeile liest „Eingestuft von Eye". Ein
  nacktes „Eye" ließe offen, was Eye behauptet — gerade für einen Screenreader.
- Form wie die Begründungszeile, `REASON_ATTRIBUTION` ersetzt durch das Herkunftslabel:
  `<p data-album-suitability-origin=""><span className="mr-1 text-text-muted">{LABEL}</span>
  <span>{EYE}</span></p>`; nie `data-album-suitability-reason`. In `PhotoVerdict` Label
  `mr-2 text-xs tracking-wide text-text-muted uppercase`, Wert `text-sm text-text`, unter
  „Stufe n von 5".
- Wörter, nie Badge, Farbe, Symbol, Chip oder `role`; kein `aria-label`. Wie die Begründung im
  Ruhezustand `sr-only`, sichtbar bei Hover/Fokus/Langdruck (`useRevealOnDemand` unverändert).
- Qualitätsstufe unverändert: `QualityMeter`/`qualityLevel(rank_score)`/`QUALITY_LEVEL_LABELS`.

### „Noch nicht eingestuft"

`ALBUM_SUITABILITY_NOT_RATED_TEXT` wird einmal, global, von `'Noch nicht bewertet'` zu
`'Noch nicht eingestuft'` — keine zweite Konstante. Derselbe Zustand (keine zählende Stufe) für
„nie eingestuft" und „Aufruf gescheitert"; „bewertet" ist in PhotoSort das Wort für die
menschliche Bewertung. Betrifft auch den Cloud-Fall.

### Leerzustände auf `AlbumDraftPage`, in Vorrang-Reihenfolge

Höchstens einer zugleich; Satz in `text-sm text-text` mit `secondary`/`sm`-Schaltfläche, kein
`Alert`, keine Fehlerfarbe.

1. **Laden:** `CurationSkeletonList` — Entwurf, Projekt und `useModelChoiceQuery(id)`, letzteres
   nur bei `category_method === 'eye'` ohne Events (sonst kippte der Leertext nach dem Laden).
2. **Ladefehler:** bestehende `Alert`s. Scheitert nur die Modellwahl-Abfrage, gilt Zustand 5.
3. **Cloud-Freigabe fehlt:** `model_choice.category_method === 'cloud' &&
   cloud_vision_detection_enabled !== true` → `DRAFT_CLOUD_CONSENT_TEXT` + `SETTINGS_LINK_LABEL`.
   Im Eye-Projekt nie.
4. **Eye abgeschaltet:** `category_method === 'eye'`, `eye.unavailable_reasons` enthält
   `eye_disabled`, keine Events → neu `DRAFT_EYE_DISABLED_TEXT = 'Eye ist in dieser Installation
   abgeschaltet — ohne Eye-Lauf entsteht kein Album-Entwurf. Die Kategorisierung stellst du in den
   Projekteinstellungen um.'` + `SETTINGS_LINK_LABEL` → `/projects/{id}/settings`.
5. **Keine Events** (Eye nie gelaufen o. ä.): `DRAFT_EMPTY_TEXT` + „Zur Klassifizierung",
   unverändert.
6. **Entwurf vorhanden:** bleibt ohne Hinweis sichtbar, auch nach Abschalten oder Wechsel.

`AlbumSelectionPage` behält ihren Leerzustand unverändert.

### Ablaufübersicht (`WorkflowOverviewDialog.tsx`)

Am Album-Schritt erscheinen `DRAFT_CLOUD_CONSENT_TEXT` **und** die Schaltfläche „Zu den
Projekteinstellungen" nur bei `project.model_choice.category_method === 'cloud'`. Im Eye-Projekt
keines von beiden; die Schaltflächenzeile wird dann gar nicht gerendert (kein leeres `div`). Kein
Eye-aus-Hinweis in der Übersicht.

### Modellwahl (`ModelChoiceSection.tsx`)

Der Absatz „Eye liefert keine Grundlage für den Album-Entwurf, solange #621 nicht umgesetzt ist."
entfällt ersatzlos. „Wirkt mit dem nächsten Lauf" deckt die bestehende Speicherbestätigung
(`MODEL_CHOICE_TEXTS.saved`) ab.

### Namensnennung einmal je Ansicht

`EyeAttribution` einmal in `AlbumDraftPage` (im `<header>` unter `draftOverviewText`) und einmal in
`AlbumSelectionPage` (im `<header>` direkt unter der `h1`), sobald
`items.some(p => p.album_suitability?.source === 'eye')`. Nicht an Kachel, Band, Lightbox oder
Leiste; Form unverändert.

### Detailansicht

`PhotoVerdict` bekommt `currentPhoto.album_suitability ?? null`. Der Text des Eye-Bands nennt
„Albumtauglichkeit und Feinlabels stammen aus der Eye-Auswertung — …" nur bei `source === 'eye'`,
sonst „Feinlabels stammen aus der Eye-Auswertung — …".

### Design-System (`specs/architecture/0004-design-system.md` und Skill `design-system`)

- „Leiste bei Bedarf": Begründung (mit Zuordnung) **oder** Herkunft „Eingestuft von Eye".
- „Zuordnung mit Herkunft": Herkunft einer Modellstufe als Wörter anstelle der Begründung.
- „Namensnennung eines Drittanbieters": einmal je Ansicht (Kopf) in Entwurf und Endauswahl.
- Nicht-eingestuft-Wortlaut „Noch nicht eingestuft".
- Eintrag „Namensnennung" an `EyeAttribution.tsx` angleichen (`text-text-muted`).

## Teststrategie

Die Teststrategie folgt `specs/architecture/0002-testkonzept.md`. Gemockt wird nur an der Außenschnittstelle (`FakeEyeClient`, aufzeichnende Cloud-Clients, autouse-Netzsperre). DB-Fälle laufen gegen In-Memory-SQLite. Einen E2E-Fall gibt es nicht: Keine Zusage braucht echte Geometrie oder echtes CSS (Aufnahmekriterium). Für das Coverage-Gate zählt die namentliche Abdeckung der Fälle unten, nicht die Prozentzahl.

**Leitregel: Jede Lage mit zwei Quellen ist so gebaut, dass sie unterscheiden *kann*.** Trägt ein Foto beide Stufen, liegen Cloud- und Eye-Stufe auseinander, und zwar so, dass sie die Fotos *umgekehrt* ordnen. Die Lage prüft das als eigene Vorbedingung. Bei gleichen Stufen bestünde jeder Fall „zählt nur das Lauf-Verfahren“ auch gegen einen Rückfall oder gegen „liest immer Cloud“ (Testkonzept, Umkehrung der Unterschiedsregel).

| AK | Ebene | Datei, Fall |
|---|---|---|
| Entwurf ohne Cloud, kein Aufruf, keine Kosten | Integration Worker + API | `test_worker_eye_phase.py`: ein voller Eye-Lauf ohne Einwilligung ergibt Rangzeilen mit `rank_score` und Vorschlagsplätzen. Die Bauer der Cloud-Clients werfen beim Bau (Muster `_exploding_eye_builder`), dazu `cloud_requested is False` und keine Cloud-Kostenbilanz. In `test_api_photos.py` ist `GET …/album-draft` danach nicht leer. |
| Kein Freigabe-Hinweis im Eye-Projekt | Komponente | `AlbumDraftPage.test.tsx`: Eye mit `cloud_vision_detection_enabled: false` zeigt weder `DRAFT_CLOUD_CONSENT_TEXT` noch den Einstellungslink. `WorkflowOverviewDialog.test.tsx`: Im Eye-Projekt gibt es am Album-Schritt weder den Text noch einen Link (`queryAllByRole('link')` ist leer) und keine leere Schaltflächenzeile. |
| Eye aus oder nie gelaufen | Komponente | `AlbumDraftPage.test.tsx`: Die Vorrang-Zustände 1–6 werden als Tabelle durchgegangen. Pflichtfälle: (a) Eye aus und Events vorhanden ergibt den Entwurf ohne Hinweis. (b) Scheitert nur die Modellwahl-Abfrage, gilt Zustand 5. (c) Im Cloud-Projekt wird `getModelChoice` nie aufgerufen (`not.toHaveBeenCalled`). (d) Bei zurückgehaltener Modellwahl-Antwort bleibt das Skeleton stehen, und `DRAFT_EMPTY_TEXT` ist noch nicht zu sehen (kein Umkippen nach dem Laden). |
| Nur das Lauf-Verfahren zählt, kein Rückfall | Unit (DB) | Neu `test_album_stage.py` für `load_album_levels`, je Quelle: Ein Foto mit beiden Stufen liefert nur die Stufe der Quelle. Ein Foto nur mit der anderen Stufe fehlt im Ergebnis. Eine leere Eingabe ergibt `{}` ohne Abfrage (gemessen mit `_recorded_select_statements`). Ein Strukturwächter auf Ebene des Funktionsrumpfs prüft, dass `PhotoAlbumSuitability.level` und `PhotoEyeResult.album_level` nur an einer festen Menge von Stellen gelesen werden; die Menge wird bei der Umsetzung aus dem Bestand gebildet. Dazu eine Positiv-Gegenprobe, die zeigt, dass die Suche nicht blind ist. |
| Gescheiterter Eye-Aufruf, kein Wert | Integration | `test_worker_eye_phase.py`: Ein Foto, das der Dienst nicht dekodieren kann, hat keine `PhotoEyeResult`-Zeile, behält aber seine `event_id`, hat `rank_score IS NULL` und bekommt keinen Vorschlagsplatz. Das Foto trägt eine Cloud-Stufe, damit ein Rückfall auffiele. `test_api_photos.py`: Von Hand aufgenommen steht es im Entwurf mit `album_suitability: null`. |
| Nachholen ohne Neubewertung | Integration | `test_worker_eye_phase.py`, zwei Läufe hintereinander: Lauf 2 schickt nur das Foto an Eye, das in Lauf 1 scheiterte, und dazu ein neues Foto (`client.calls`). Das bereits bewertete Foto behält `computed_at`/`mapping_version`, seine Kopfzeile wird nicht befördert. `eye_photos_total` entspricht der Nachhol-Menge. Bei null Kandidaten läuft die Gesundheitsprüfung trotzdem (`health_calls == 1`). `test_api_classification_estimate.py`: `_count_eye_candidates` ist mengengleich zur Kandidatenmenge der Eye-Phase über demselben Bestand (Muster Z. 785ff.). |
| Wechsel wirkt erst mit dem nächsten Lauf | Integration | Neu je Lesepfad: Lauf mit `cloud`, dann `category_method=eye` ohne Lauf. Danach sind gleich: Rangwerte nach `rebuild_run_grouping`/Versatz (`test_worker_rebuild_run_grouping.py`, Schnappschuss-Muster), `source` auf allen sechs `_to_photo_out`-Pfaden (`test_api_photos.py`, parametrisiert über Entwurf, Liste, Endauswahl, Duplikatgruppe, Ausschuss, Alternativen) und die eingefrorene Stufe im Feedback (`test_feedback_log.py`, `test_api_draft_exchange.py`). |
| Neues Verfahren nach dem Lauf, Rückwechsel, Handentscheide | Integration | `test_worker_selection.py`, als Folge: Cloud-Lauf, Eye-Lauf, Cloud-Lauf. Nach dem Eye-Lauf stehen nur Fotos mit Eye-Stufe im Vorschlag. Beide Stufentabellen sind nach jedem Schritt zeilengleich. Nach dem Rückwechsel ist der Vorschlag gleich dem nach Lauf 1. Ein aufgenommenes Foto ohne Stufe des neuen Verfahrens und ein gestrichenes Foto behalten ihre `Rating`-Zeile und ihren Anzeigezustand über alle drei Läufe (`test_api_photos.py`, `…/album-draft`). |
| Herkunft „Eye“ an Kachel, Band, Endauswahl | Komponente | `CurationPhotoTile.test.tsx` (voll): Bei `source: 'eye'` gibt es eine `[data-album-suitability-origin]`-Zeile mit `ALBUM_SUITABILITY_ORIGIN_LABEL` + `…_EYE_ORIGIN_TEXT` und kein `[data-album-suitability-reason]`. Ist `reason` bei Eye trotzdem gesetzt, gewinnt die Herkunft. Bei Cloud ist alles wie bisher, ohne Herkunftszeile. Kein `role`, kein `aria-label`, kein Badge oder Icon; das Aufklappen (Reveal) verhält sich wie bei der Begründung. Je ein Verdrahtungsfall in `DraftAlternativesBand.test.tsx` und `SelectionPhotoTile.test.tsx`. `PhotoVerdict.test.tsx`: Herkunftszeile unter „Stufe n von 5“. `AlbumDraftPage.test.tsx`/`AlbumSelectionPage.test.tsx`: `eye-attribution` erscheint genau einmal bei zwei E…
| Keine zweite Skala | Integration + Komponente | `test_worker_rebuild_run_grouping.py`, Zwillingsprojekte: Eye-Stufen gleich den Cloud-Stufen des Zwillings ergeben identische `rank_score`. `CurationPhotoTile.test.tsx`: gleicher `rank_score`, Quelle Cloud bzw. Eye, ergibt dieselbe `QUALITY_LEVEL_LABELS`-Stufe. |
| Cloud-Kandidaten und Kosten unverändert | Integration | `test_api_classification_estimate.py`: Ein echter Eye-Lauf wird vorher und nachher über `select_remote_category_candidates` und `GET …/classify/estimate` verglichen; Menge und Cloud-Anteil sind gleich. |
| Cloud-Projekt nach Eye-Lauf unverändert | Integration | `test_worker_eye_phase.py`: Projekt mit `category_method=cloud`, Lauf mit `mode=eye` ergibt `album_level_source == cloud`, die Rangwerte entstehen aus den Cloud-Stufen, und die API liefert `source: "cloud"` samt Begründung. Dieser Fall trennt „Quelle = Projekteinstellung“ von „Quelle = Laufweg“. |
| Scan, Gate, lokal, Prüfung unverändert | Regression | Die bestehenden Suiten bleiben grün, ohne Anpassung, insbesondere `test_ausschuss_ueberlebende.py` (Zählung unverändert), `test_classification_review_isolation.py` und `test_worker_score_project.py`. |

**Quelle am Lauf.** In `test_worker_criterion_scoring.py` läuft `_start_criterion_scoring_run` parametrisiert über `mode` × `category_method` (auch `local`); jeweils gilt `album_level_source == category_method`. Neu `test_migration_album_level_source.py`: Eine Altzeile liest nach dem Upgrade `cloud`, die Spalte ist NOT NULL, `downgrade()` entfernt sie. Die Zusage „Altläufe tragen `cloud`“ steht in der Spec, deshalb ist dieser Fall kein Bestandswert-Fall im Sinne von ADR 0095. Dazu die DDL-Prüfung in `test_postgres_ddl_compatibility.py`.

**Bewusst geänderte oder gelöschte Tests**
- `test_worker_eye_phase.py::test_a_new_run_replaces_a_v1_row_with_the_run_mapping` wird umgeschrieben auf: „eine v1-Zeile bleibt v1 und wird nicht erneut an Eye geschickt“ (ADR 0144, Konsequenz zur `MAPPING_VERSION`).
- `test_worker_eye_phase.py::test_the_eye_phase_leaves_album_suitability_and_cloud_labels_untouched` **bleibt** und wird um `fine_labels` erweitert. Nach ADR 0144 Punkt 3 gilt die Schreibgrenze weiter; nur über sie bleiben Cloud-Kandidaten und Kosten unverändert. Das alte Verhalten kodiert dieser Test nicht.
- `test_api_photos.py` (Z. 5348, 5371): Die exakten Vergleiche der Antwort-Dicts bekommen `"source": "cloud"`.
- `ModelChoiceSection.test.tsx` Z. 187: Statt `/solange #621 …/` zu erwarten, prüft der Test jetzt, dass der Satz fehlt (`not.toHaveTextContent`).
- `PhotoVerdict.test.tsx` Z. 150 und `PhotoDetailPage.test.tsx` Z. 1466: „Noch nicht bewertet“ wird zu `ALBUM_SUITABILITY_NOT_RATED_TEXT`.
- `PhotoDetailPage.test.tsx`, Fall „zeigt im Urteil Eyes Stufe …“ (Z. 1447): Die Stufe kommt jetzt aus `album_suitability` mit `source: 'eye'`. Neu dazu: `album_suitability: null` mit `eye_result` ergibt „Noch nicht eingestuft“. Der Bandtext „Albumtauglichkeit und …“ steht nur bei `source === 'eye'`.
- `eyeVerdict.test.ts`, Fall „takes the level from Eye …“: entfällt.
- `AlbumDraftPage.test.tsx` Z. 355ff. und `WorkflowOverviewDialog.test.tsx` Z. 111–128: Die Fixtures setzen ausdrücklich `category_method: 'cloud'`.
- `CurationPhotoTile.test.tsx` Z. 123: Testtitel umbenennen.
- Alle `AlbumSuitabilityOut`-Fixtures bekommen `source`; `tsc` erzwingt das.
- `albumSelection.structure.test.ts`: Der Fall „Textbaustein genau einmal als Literal“ wird für „Noch nicht eingestuft“ und „Eingestuft von“ erweitert. Neu: Das alte Literal „Noch nicht bewertet“ kommt im Produktcode null Mal vor, mit Gegenprobe.

## Security

**Sicherheitsrelevant: ja, in geringem Umfang.** Es kommt kein neuer Endpunkt dazu, kein Secret, kein neuer Empfänger und keine neue Eingabe von außen. Die Story ändert aber zwei Dinge, die mit Sicherheit zu tun haben. Erstens wird ein Projekt ohne Einwilligung zum ersten Mal vollständig nutzbar. Damit hängt das Einwilligungsversprechen „kein Cloud-Aufruf" an einem Pfad, den Nutzer künftig tatsächlich gehen. Zweitens bestimmt eine Fremdstufe (Eye-Beta) erstmals den Album-Entwurf. Betroffen ist dabei die Integrität, nicht die Vertraulichkeit. Begrenzt wird sie durch `CHECK album_level BETWEEN 1 AND 5`, die festen Bänder in `eye_mapping.album_level` und den Grundsatz „kein Rückfall".

- **S1 — Ohne Einwilligung verlässt kein Bild das System, auch nicht im jetzt vollständigen Eye-Pfad.** Das Gate bleibt unverändert: `mode is EYE and project.cloud_vision_detection_enabled` für `cloud_requested`/Sehenswürdigkeits-Phase (Spec 0609 S6, ADR 0138). Die Remote-Kategorie-Phase läuft nur bei `mode=cloud`. `album_stage.py` ist ein reiner Datenbank-Lesepfad und importiert keinen Netzwerk-Client, keinen Vision-Client und keinen Eye-Client. **Prüfbar:** Ein Worker-Test fährt einen ganzen Eye-Lauf ohne Einwilligung, einschließlich Rangbildung und Entwurf. `build_landmark_client` und der Remote-Kategorie-Builder sind dabei durch werfende Fakes ersetzt. Der Lauf endet mit `SUCCESS`, und es gibt Rangzeilen. Der heutige `test_eye_without_consent_requests_no…
- **S2 — Die Herkunft legt der Server fest, und die Werte sind geschlossen.** `AlbumSuitabilityOut.source: Literal["cloud","eye"]` stammt nur aus `run.album_level_source` bzw. aus `_album_level_source(session, project)`. Er kommt nie aus einem Query- oder Body-Parameter, nie aus der Motiv-Kopfzeile und nie aus `eye_result`. Kein Endpunkt nimmt eine Quelle entgegen. `album_level_source` wird nur in `_start_criterion_scoring_run` geschrieben, kein Request-Pfad schreibt es (auch nicht `rebuild_run_grouping`). **Prüfbar:** Der Schema-Test zeigt, dass ein anderer Wert die Antwortvalidierung bricht. `grep` findet genau eine Schreibstelle von `album_level_source`. Ein API-Test belegt, dass ein mitgeschicktes `?source=`/`album_level_source` wirkungslos bleibt.
- **S3 — Die Projektbindung bleibt beim Lauf, `load_album_levels` ist keine Auflösung.** `_album_level_source` liest den jüngsten erfolgreichen Lauf **dieses** Projekts (`CriterionScoringRun.project_id == project.id`) und nie den global jüngsten (gleiche Fehlerklasse wie Anker „Endauswahl-Projektbindung"). In `_exchange_sides` bleibt das `PhotoRanking`-Laufprädikat die **einzige** auflösende Menge (Exchange-S2). `load_album_levels` bekommt nur die Foto-IDs aus diesen Rangzeilen, nie die rohen Payload-IDs. Eine Seite entsteht nur aus einer Rangzeile, nie aus dem Stufen-Dict. **Prüfbar:** Der bestehende Fremdprojekt-Tauschtest bleibt grün und läuft zusätzlich mit `album_level_source='eye'` (fremdes Foto mit Eye-Zeile → `404`/Ablehnung). Ein Test mit zwei Proje…
- **S4 — Bei Eye gibt es keinen Modelltext, die Herkunft ist eine Konstante.** `reason=None` für `source="eye"` wird serverseitig gesetzt, nicht im Frontend ausgeblendet. Die Herkunftszeile rendert nur `ALBUM_SUITABILITY_ORIGIN_LABEL`/`ALBUM_SUITABILITY_EYE_ORIGIN_TEXT` als React-Textknoten. Sie steht nie in einem Attribut und interpoliert keinen Wert aus der Antwort (weder `model_revision` noch `mapping_version` noch `reason`). Für die Cloud-Begründung gilt der bestehende Anker (Sanitisierung, vollständig, nur Textknoten) unverändert. **Prüfbar:** Ein Backend-Test zeigt: Ein Eye-Foto, das zusätzlich eine `photo_album_suitability`-Zeile mit `reason` trägt, liefert `reason is None`. Ein Frontend-Test mit `source:'eye'` und gesetztem `reason` (Marker-String) z…
- **S5 — Der Request-Pfad ruft Eye nicht auf.** `rebuild_run_grouping` (Versatz) und alle Lesepfade lesen die Eye-Stufe nur aus `photo_eye_results`. Ein Sidecar-Aufruf entsteht nur in `_run_eye_phase` eines bewusst gestarteten Laufs. Die Auflage gilt analog zum Anker „Request-Pfad schlägt nichts nach": Ein gestohlenes JWT darf keine Modellarbeit auslösen. **Prüfbar:** Ein `rebuild_run_grouping`-Test mit `album_level_source='eye'` und einem werfenden Eye-Client-Builder läuft grün.
- **S6 — Die Nachholmenge verkleinert die Exposition, und das Gesundheits-Gate bleibt.** Kandidaten sind nur Ausschuss-Überlebende **dieses** Projekts ohne `photo_eye_results`-Zeile. `_count_eye_candidates` zählt dieselbe Menge, damit die Anzeige nicht weniger nennt als tatsächlich gesendet wird. Der Health-Check vor dem Einreihen läuft auch bei null Kandidaten. Innerhalb eines Laufs gibt es weiter keinen Retry (0609 S3). Ein gescheitertes Foto kommt erst im nächsten bewusst gestarteten Lauf erneut dran. **Prüfbar:** Ein Worker-Test zeigt, dass ein Foto mit vorhandener Eye-Zeile dem Fake-Client nicht übergeben wird. Ein Paritätstest belegt, dass Zählung und Kandidatenmenge gleich sind.
- **Keine neue Auflage, mit Begründung:**
  - *Migration:* Sie ist additiv, ohne Datenmigration und ohne neue Datenklasse. `server_default 'cloud'` ist für Altläufe die richtige Ausfallrichtung, weil es dem bisherigen Verhalten entspricht. `downgrade()` entfernt nur die Spalte. Projektlöschung: Die Spalte hängt an `criterion_scoring_runs`, die schon im Löschgraphen stehen, `project_graph.py` muss sich nicht ändern.
  - *Sichtbarkeit zwischen den Nutzern:* `source` und die zählende Stufe sind laufglobal und hängen nicht vom anfragenden Nutzer ab (vgl. 0609 S11). Die Cache-Schlüssel-Auflage in `_to_photo_out` wächst nicht. `suggestion` und Entwurfsmenge bleiben wie bisher nutzerabhängig.
  - *Eye schreibt nie in `photo_album_suitability`/`photo_fine_labels`/`fine_labels`* (0609 S8, ADR 0144 Punkt 3): Diese Auflage gibt es schon, sie gilt unverändert weiter.

**Im selben PR nachzuziehen in `specs/architecture/0003-securitykonzept.md`:** (1) unter
„Angriffsflächen → `eye`-Dienst": die Eye-Stufe zählt im Entwurf (ADR 0138 Punkt 4 abgelöst);
akzeptiertes Integritätsrisiko — ein präpariertes Bild setzt höchstens die Stufe 1..5 eines Fotos
im eigenen Projekt, begrenzt durch CHECK, Bänder und keinen Rückfall. (2) Ankerliste: „Herkunft der
zählenden Stufe am Lauf eingefroren, nie aus Request, Projekt-Livewert (bei vorhandenem Lauf) oder
Kopfzeile" → `_start_criterion_scoring_run`, `_album_level_source`/`_to_photo_out` (Tests S2/S3);
„`load_album_levels` löst nicht auf, die Projektbindung trägt das Laufprädikat" →
`_exchange_sides`, `load_frozen_context` (Tests S3). (3) Kopfzeile „Letzte Aktualisierung".

## Entscheidungen

- Architektur-Konsultation durchgeführt (kein Skip): konkrete Datenfluss-Stellen in Worker, API
  und Feedback-Log; Ergebnis ADR 0144 und Abschnitt oben.
- UI/UX-Konsultation durchgeführt (kein Skip): Entwurfskachel, Alternativen-Band, Endauswahl,
  `AlbumDraftPage`, Ablaufübersicht, Modellwahl und Detailansicht sind betroffen.
- Teststrategie-Konsultation durchgeführt (kein Skip): nicht-triviales Verhalten (Quellenwahl,
  Nachholen, Wechsel über Läufe).
- Security-Konsultation durchgeführt (kein Skip): Einwilligungsversprechen „kein Cloud-Aufruf",
  neues API-Feld, Datenmodell-Änderung.
- „noch nicht eingestuft" ersetzt global `'Noch nicht bewertet'` (eine Konstante, auch im
  Cloud-Fall); „bewertet" bleibt der menschlichen Bewertung vorbehalten.
- Lesart AK „Nachholen": Ein späterer Lauf bewertet genau die Fotos ohne Stufe des eingestellten
  Verfahrens, auch wenn andere Fotos des Projekts schon eine tragen; vorhandene Stufen werden
  weder erneut angefragt noch ersetzt.
- Lesart AK „Anzeige": die Herkunft „Eye" erscheint als Zeile „Eingestuft von Eye".
- Ein Lauf, bei dem die Einstellung zwischen Auslösen und Worker-Start wechselt, kann
  `mode=eye` mit `album_level_source=cloud` tragen; maßgeblich ist `album_level_source`
  (Projekteinstellung beim Laufstart).

## Offene Fragen

Keine.

## Out of Scope

- Gemeinsame Auswertung von Eye und Cloud für ein Foto (#622).
- Prüfung, ob Eye geschlossene Augen und verdeckte Gesichter erkennt.
- Neubewertung bestehender Eye-Ergebnisse bei einer neuen `MAPPING_VERSION`.
- Änderung bestehender Feedback-Ereignisse.
