# 0383 - Modellwahl je Projekt und Tätigkeit

**Status:** Accepted
**Erstellt:** 2026-11-08
**Bezug:** [#383](https://github.com/TheRealKoller/photosort/issues/383)

## Ziel

Welches Verfahren ein Foto am besten beurteilt, hängt vom Projekt und von der Tätigkeit ab. Die
Auswertung von Eye gegen die Cloud hat gezeigt, dass Eye bei Motiven teils besser liegt und beim
Dokument-Ausschluss teils schlechter; Sehenswürdigkeiten erkennt ohnehin nur ein Cloud-Modell.
Heute gilt für alle Projekte und beide Tätigkeiten ein einziges Modell, das nur der Betreiber
außerhalb der Anwendung umstellen kann.

Beide Nutzer legen deshalb je Projekt in den Projekteinstellungen fest, womit die Kategorisierung
und womit die Sehenswürdigkeits-Erkennung läuft — mit Anbieter, Preis und Anfragelimit jeder Wahl
sichtbar. Beim einzelnen Lauf bleibt die bewusste Entscheidung erhalten, aber nur noch zwischen
„wie im Projekt eingestellt" und „Nur lokal".

## User Story

Als Nutzer von PhotoSort möchte ich je Projekt festlegen, welches Verfahren die Kategorisierung
und welches Modell die Sehenswürdigkeits-Erkennung übernimmt, und dabei Anbieter, Preis und
Anfragelimit jeder Wahl sehen, damit jedes Projekt mit dem Verfahren beurteilt wird, das für
seine Fotos am besten passt.

## Akzeptanzkriterien

**Auswahl in den Projekteinstellungen**

- [ ] Die Projekteinstellungen enthalten einen Abschnitt zur Modellwahl mit zwei getrennten Wahlen: „Kategorisierung" und „Sehenswürdigkeits-Erkennung" — je Wahl eine eigene Gruppe mit eigener Legende und genau einem wählbaren Wert, nicht ein gemeinsamer Schalter für beide.
- [ ] Für die Kategorisierung stehen genau die Cloud-Modelle der gepflegten, preisgeprüften Auswahl — die Einträge von `VISION_MODELS_BY_PROVIDER`, vollständig und ohne Zusatz — und zusätzlich Eye zur Wahl; für die Sehenswürdigkeits-Erkennung nur diese Cloud-Modelle, ohne Eye-Karte, weil Eye keine Namen von Sehenswürdigkeiten liefert.
- [ ] Beide Wahlen dürfen dasselbe Cloud-Modell tragen, und sie dürfen Modelle verschiedener Anbieter tragen; gespeichert und zurückgelesen werden beide Werte unverändert und unabhängig voneinander.
- [ ] Es gibt keine freie Eingabe eines Modellnamens: der Abschnitt enthält kein Textfeld, jede Wahl entsteht ausschließlich durch Auswahl einer Katalogkarte, und ein **geändertes** Modell außerhalb der Registry wird von der Schreib-API mit `422` abgelehnt.
- [ ] Zu jedem Cloud-Modell sind Anbieter, geschätzter Preis je Bild, Preis je Million Eingabe- und Ausgabe-Token und das Anfragelimit des Anbieters zu sehen — je Karte genau diese fünf Werte, jeder mit dem Wert, den die Katalog-Antwort für dieses Modell liefert; beim Anfragelimit steht, dass es für alle Projekte gemeinsam gilt.
- [ ] Ein Modell ohne hinterlegten Preis erscheint nie mit „0" oder einem erfundenen Betrag: fehlt der Preiseintrag, sind Preis je Bild und beide Token-Preise in der Antwort `null` und die Karte nennt den Preis als „unbekannt" — Text, keine Zahl, kein Währungsbetrag.
- [ ] Eye erscheint als „kostenfrei" — als Wort, nie als „0,00" oder ein Währungsbetrag — mit der vorgeschriebenen Namensnennung von Desert Ant Labs und dem Hinweis auf die nicht abschaltbare Lizenzmeldung ohne Bildinhalte.
- [ ] Die Eye-Wahl sagt, dass sie keine Grundlage für den Album-Entwurf liefert, solange #621 nicht umgesetzt ist; der Hinweis steht an der Eye-Karte der Kategorisierung und entfällt mit #621.
- [ ] Ein Cloud-Modell, dessen Anbieter in dieser Installation kein Zugang hinterlegt ist, ist nicht wählbar — seine Karte bleibt sichtbar, ihre Marke ist deaktiviert — und die Ansicht sagt, warum; dasselbe gilt für Eye, wenn es in dieser Installation nicht eingeschaltet ist. Die Schreib-API lehnt einen **geänderten** so belegten Wert mit `422` ab und lässt die gespeicherte Wahl unverändert; ein unverändert durchgereichter, gespeicherter Wert bleibt zulässig, damit niemand in einer nicht mehr verfügbaren Wahl festsitzt.
- [ ] Die Wahl bleibt gespeichert und gilt für beide Nutzer des Projekts gleich: ein zweiter Nutzer derselben Installation liest nach dem Speichern dieselbe Wahl, und sie überlebt ein Neuladen ohne lokalen Zustand.
- [ ] Laden und Fehler der Ansicht sind als eigene Zustände erkennbar — Ladezustand ohne Kartenwerte, Fehlerzustand mit Wiederholung, gefüllter Zustand; ein fehlgeschlagenes Speichern lässt die bisherige Wahl unverändert, gespeichert **und** angezeigt, und sagt das.

**Auswahl beim einzelnen Lauf**

- [ ] Beim Starten eines Klassifizierungslaufs gibt es genau zwei Wege: „wie im Projekt eingestellt" und „Nur lokal" — genau zwei Marken in dieser Gruppe, der eigene Weg „Eye" entfällt dort; die Start-API nimmt nur diese beiden Werte an und lehnt jeden anderen mit `422` ab.
- [ ] Beim Öffnen ist kein Weg vorausgewählt, keine Wahl wird gemerkt, und ohne Wahl startet kein Lauf: keine Marke gesetzt, keine Schätzung angefragt, der Auslöser gesperrt mit dem Grund als Satz — auch nach einem gestarteten Lauf und nach einem Neuladen.
- [ ] „Wie im Projekt eingestellt" nennt in Kurzform, was laufen wird — Eye oder Anbieter und Modell der Kategorisierung, dazu Anbieter und Modell der Sehenswürdigkeits-Erkennung —, und führt zu den Projekteinstellungen; die Kurzform stammt aus derselben Projektantwort, aus der der Lauf seine Wahl liest.
- [ ] „Nur lokal" verhält sich wie heute: kein Cloud-Aufruf — keine einzige Anfrage an einen Cloud-Anbieter —, kein Eye, kostenfrei; der Lauf wird als lokaler Weg verbucht.

**Wirkung**

- [ ] Ein Lauf nutzt für jede Tätigkeit genau das im Projekt gewählte Verfahren; mit Eye für die Kategorisierung geht für die Kategorisierung kein Foto an einen Cloud-Anbieter — im aufgezeichneten Anfragekörper der Sehenswürdigkeits-Erkennung steht kein Foto aus der Kategorisierung.
- [ ] Bei verschiedenen Anbietern gehen die Fotos jeder Tätigkeit nur an den für sie gewählten Anbieter, und jeder Anbieter wird nur mit seinem eigenen Anfragelimit angefragt — auch wenn mehrere Projekte gleichzeitig laufen: zwei gleichzeitig laufende Projekte teilen den Schrittmacher je Anbieter und mischen keine Anbieter.
- [ ] Die Kostenschätzung vor dem Start weist jede stattfindende Tätigkeit mit ihrer Grundlage aus — ein Cloud-Anteil mit Anbieter, Modell und Preis, ein Eye-Anteil als „kostenfrei"; eine nicht stattfindende Tätigkeit fehlt als `null`-Anteil und wird „findet nicht statt" benannt, nie als Betrag.
- [ ] Angezeigtes, aufgerufenes und abgerechnetes Modell stimmen je Tätigkeit überein — Schätzung, Anfragekörper, Laufspalte und Betrag tragen denselben Wert, geprüft mit einer nicht voreingestellten Wahl —, und die Lauf-Bilanz nennt je Tätigkeit die tatsächliche Grundlage.

**Einwilligung**

- [ ] Die Einwilligung zur Cloud-Verarbeitung bleibt der einzige Schalter, der Cloud-Aufrufe erlaubt; ohne sie wird kein Cloud-Modell aufgerufen, gleich was eingestellt ist — mit Cloud-Kategorisierung antwortet der Auslöser `403`, ohne dass ein Lauf eingereiht oder etwas verändert wird.
- [ ] Ohne Einwilligung und mit Eye für die Kategorisierung startet „wie im Projekt eingestellt" trotzdem: Eye läuft, eine Sehenswürdigkeits-Erkennung findet nicht statt — keine Landmark-Zeile, Anteil `null` —, und die Vorschau sagt das.
- [ ] Ohne Einwilligung und mit einem Cloud-Modell für die Kategorisierung lässt sich „wie im Projekt eingestellt" nicht starten; die Ansicht nennt den Grund und verweist auf die Projekteinstellungen, „Nur lokal" bleibt möglich und startet.
- [ ] Die Erklärung zur Einwilligung nennt alle Anbieter, an die das Projekt nach seiner aktuellen Wahl Fotos sendet — die Menge der Anbieter beider Tätigkeiten, ohne Dopplung, ohne Eye —, und sie ändert sich mit einer geänderten Wahl ohne Neuladen.

**Fehlerfälle**

- [ ] Ist Eye eingestellt, beim Start aber abgeschaltet oder nicht erreichbar, startet der Lauf nicht, nichts wird verändert — kein eingereihter Job, keine Laufzeile, keine veränderte Fotozeile, keine neue Bilanz —, und die Ansicht sagt das; es wird nie still auf die Cloud oder auf „Nur lokal" ausgewichen. Abgeschaltet und nicht erreichbar sind zwei getrennte Fälle mit je eigener Antwort.

**Übergang**

- [ ] Bestehende Projekte und Projekte ohne eigene Wahl verhalten sich nach dem Update wie bisher: dieselben Cloud-Modelle, dieselbe Schätzung, Kategorisierung über die Cloud — die Migration setzt die Methode `cloud` und lässt beide Modelle leer, und die aufgelöste Wahl entspricht der Installationsvorgabe. Kein Projekt wird von selbst auf Eye umgestellt.
- [ ] Eine geänderte Wahl wirkt nur auf künftige Aufrufe; vorhandene Ergebnisse und abgerechnete Beträge bleiben unverändert und werden nicht von selbst neu erzeugt. Wer zur vorherigen Wahl zurückkehrt, bekommt das vorherige Verhalten — die ausdrücklich gespeicherte Vorgabe ist ein gespeicherter Wert und kein Zurückfallen auf „Installationsvorgabe".
- [ ] Ein Eye-Lauf überschreibt nie ein vorhandenes Cloud-Ergebnis desselben Fotos — Kopfzeile, Anbieter und Rückbaudaten bleiben, und die Bilanz nennt weiter die Cloud-Grundlage.

## Datenmodell-Bezug

`Project` erhält drei Spalten: `category_method` (`cloud` | `eye`, NOT NULL, Server-Default
`cloud`), `category_model` und `landmark_model` (beide `NULL` = Installationsvorgabe). Der
Check-Constraint `ck_projects_category_model_requires_cloud` schließt „Eye mit Cloud-Modell" aus.
Einzelheiten in [`docs/architecture.md`](../../docs/architecture.md) und
[ADR 0143](../decisions/0143-modellwahl-je-projekt-und-taetigkeit.md).

## Architektur / Umsetzung

**Grundsatzentscheidung:** [ADR 0143](../decisions/0143-modellwahl-je-projekt-und-taetigkeit.md).
Sie löst Teile von ADR 0059 Punkt 1 und ADR 0138 Punkt 6/7 ab; ADR 0074 Punkt 3 gilt unverändert
weiter, jetzt ausdrücklich je Tätigkeit.

### Ansatz in einem Satz

Das Projekt speichert die Wahl je Tätigkeit. Genau eine Funktion löst sie zu Modell und Anbieter
auf. Der Auslöser löst einmal auf, die Schätzung braucht dieselbe Auflösung. Der Job bekommt die
aufgelösten Werte und nutzt sie überall — Client, Schrittmacher, Preis, Laufspalten, Bilanz. So
gilt „angezeigt = aufgerufen = abgerechnet" per Bau.

### Datenmodell

- `projects.category_method`: `SQLEnum(CategoryMethod, native_enum=False, length=20)`, neues
  `StrEnum CategoryMethod {cloud, eye}` in `models.py`, NOT NULL, `server_default 'cloud'`.
- `projects.category_model: str | None`, `projects.landmark_model: str | None`; `NULL` heißt
  Installationsvorgabe (`settings.resolved_landmark_model()`).
- `CheckConstraint("category_method = 'cloud' OR category_model IS NULL", name="ck_projects_category_model_requires_cloud")`.
- Eine Migration. Bestandsprojekte bekommen `cloud`/`NULL`/`NULL` und verhalten sich damit exakt
  wie heute; kein Projekt wird von selbst auf Eye gestellt.
- Eine ausdrücklich gespeicherte Installationsvorgabe wird als konkreter Modellwert abgelegt,
  nicht als `NULL` — sonst wäre „zur vorherigen Wahl zurückkehren" nicht eindeutig.

### Auflösung (`backend/src/photosort/model_choice.py`, neu)

- `resolve_model_choice(project) -> ResolvedModelChoice` (frozen dataclass):
  `category_method`, `category_model: str | None` (`None` bei Eye), `category_provider:
  str | None`, `landmark_model: str`, `landmark_provider: str`, `category_is_default: bool`,
  `landmark_is_default: bool`.
- Der Anbieter kommt **immer** aus `cloud_vision.provider_for_vision_model(model)`.
- Ein Modell, das nicht mehr in `VISION_MODELS_BY_PROVIDER` steht, wirft
  `UnknownModelChoiceError`. Auslöser und Schätzung antworten dann `409` („Das im Projekt
  eingestellte Modell ist nicht mehr wählbar. Wähle in den Projekteinstellungen ein anderes.");
  es gibt keinen Rückfall. Lesepfade (`GET …/model-choice`, `ProjectOut`) werfen nicht, sie
  zeigen die Modell-ID mit `provider: null`.
- `api_key_for_provider(provider) -> bool` zieht aus `api/classification_reviews.py:367` hierher
  und gibt künftig nur die Anwesenheit zurück.

### API

1. **`GET /projects/{id}/model-choice`** — neuer Router `api/model_choice.py`,
   `APIRouter(prefix="/projects", tags=["model-choice"], dependencies=[Depends(get_current_user)])`,
   eingehängt in `main.py:80-94` **und** in `tests/test_auth_guard.py::_protected_router_operations()`.
   Antwort `ModelChoiceOut`:
   - `current`: `{category_method, category_model, category_provider, category_is_default,
     landmark_model, landmark_provider, landmark_is_default}`
   - `cloud_models`: je Registry-Eintrag, in Registry-Reihenfolge: `provider`, `model`,
     `estimate_usd_per_image: float | None` (`pricing.estimate_usd_per_image`),
     `input_usd_per_mtok`, `output_usd_per_mtok` (aus `MODEL_PRICING`, ohne Eintrag `null`, nie
     `0`), `requests_per_minute` (`settings.resolved_cloud_vision_requests_per_minute(provider)`),
     `available: bool`, `unavailable_reasons: list[Literal["no_api_key"]]`
   - `eye`: `{available: bool, unavailable_reasons: list[Literal["eye_disabled"]]}`
   - Die Einwilligung ist hier **kein** Grund; sie greift erst beim Lauf.
2. **`PUT /projects/{id}/model-choice`** — Body `{category_method: "cloud"|"eye",
   category_model: str|None, landmark_model: str|None}` mit `extra="forbid"`.
   - `422`: Modell nicht in der Registry, kein Schlüssel für den Anbieter (nur bei geändertem
     Wert), `eye` bei `EYE_ENABLED=false` (nur bei geändertem Wert), `category_model` gesetzt
     bei `eye` bzw. fehlend bei `cloud`.
   - `404` bei unbekanntem Projekt, `409` während eines aktiven Klassifizierungslaufs über
     `_reject_while_a_criterion_run_is_active` (`api/projects.py:1230`, Meldung auf die
     Modellwahl angepasst).
   - Alle drei Spalten in einem Commit; bei einem Fehler ändert sich nichts. Antwort: neues
     `ModelChoiceOut`.
3. **`ProjectOut`**: neu `model_choice: ProjectModelChoiceOut` = `{category_method,
   category_provider, category_model, landmark_provider, landmark_model}`, gebaut über
   `resolve_model_choice` in der `ProjectOut`-Fabrik (`projects.py:~791`). `eye_available`
   entfällt; die Verfügbarkeit liefert `GET …/model-choice`.
4. **`POST /projects/{id}/classify`**: `ClassifyRequest.mode: Literal["project", "local"]` ohne
   Vorgabe; `cloud` und `eye` entfallen (Frontend folgt im selben PR). Ablehnungsreihenfolge:
   Feature-Flag `403` → `404` → die drei bestehenden `409` → Auflösung gescheitert `409` →
   wirksam Eye und `EYE_ENABLED=false` `403` → wirksam Cloud ohne Einwilligung `403` (mit
   Hinweis auf die Projekteinstellungen) → wirksam Eye und `/health` ≠ 200 `503`.
   Eye ohne Einwilligung startet mit `202`, die Sehenswürdigkeits-Erkennung entfällt. Eingereiht
   wird `("classify", project_id, scoring_run_id, use_cloud, estimated_cost_usd, mode=<cloud|eye|local>,
   category_model=…, landmark_model=…)`; `use_cloud` ist genau bei wirksamem Cloud-Weg `True`.
5. **`GET /projects/{id}/classify/estimate?mode=project|local`** (ohne Vorgabe):
   `ClassificationEstimateOut` mit `mode`, `candidate_count`, `categorization: …PartOut | None`,
   `landmark: …PartOut | None`, `estimated_cost_usd`. Die Felder `provider`, `model`,
   `price_per_image_usd` auf oberster Ebene und `remote_categories` entfallen. Ein Anteil ist
   `{kind: "cloud"|"eye", provider, model, price_per_image_usd, candidate_count,
   estimated_cost_usd}`; `null` heißt „findet nicht statt", unterscheidbar von „Betrag
   unbekannt". Eye-Kategorisierung: `kind="eye"`, `provider`/`model` `null`, Preis und Betrag
   `0.0`, Anzahl der Ausschuss-Überlebenden (Muster `_run_eye_phase`, `worker.py:2829`).
   Landmark ohne Einwilligung und bei `local` beide Anteile `null`.

### Worker

- `classify` (`worker.py:3685`) bekommt keyword-only `category_model: str | None = None` und
  `landmark_model: str | None = None`; fehlen sie (Job aus der Zeit vor dem Deploy), löst der Job
  über `resolve_model_choice(project)` auf.
- `run_classification` (3498) reicht durch: `run_remote_category_classification(…, model=category_model)`
  (Modell bei 3857) und `run_criterion_scoring(…, landmark_model=landmark_model)` (Auflösung bei 3113).
- An allen Stellen, die heute `settings.landmark_provider` lesen (3136, 3363, 3415, 3896, 3987,
  4001, 4043, 4090), gilt `provider_for_vision_model(<Modell der Tätigkeit>)` — Client-Bau,
  `compute_cost_usd`, `provider`-Spalte je Foto, Zusammenfassungs-Protokoll.
- `landmark.py::build_landmark_client(model)` leitet den Anbieter aus dem Modell ab (Muster
  `remote_classification.py:505-528`) und wirft bei unbekanntem Modell `ValueError`; Schrittmacher
  ist `throttle_for_provider(<abgeleiteter Anbieter>)`. `WorkerSettings` und
  `cloud_vision_throttle.py` bleiben unverändert.

### Frontend

- `api/types.ts`: `ClassificationWay` wird `'project' | 'local'`; neuer Typ `ClassificationPath =
  'cloud' | 'eye' | 'local'` für `CriterionScoringRunSummary.mode`; neue Typen
  `ClassificationEstimateOut`/`ClassificationEstimatePartOut`, `ModelChoiceOut`,
  `ProjectModelChoiceOut`; `ProjectOut.eye_available` entfällt, `model_choice` kommt dazu.
- `api/projects.ts`: `getModelChoice(id)`, `putModelChoice(id, body)`. `hooks/useProjects.ts`:
  `useModelChoiceQuery`, `useUpdateModelChoiceMutation` (invalidiert `['project', id]`, die
  Model-Choice-Query und `classification-estimate`).
- Neu `components/ModelChoiceSection.tsx` in `pages/ProjectSettingsPage.tsx` vor `CameraSection`:
  je Modell eine Karte mit Anbieter, Modell, Preis je Bild, Ein-/Ausgabe je Mio. Token und
  Anfragen pro Minute samt „gilt für alle Projekte gemeinsam"; ein fehlender Preis wird „Preis
  unbekannt", nie „0"; je Karte zwei Auswahlzeilen, je Tätigkeit genau ein Radio mit eigenem
  `name`, die Tätigkeit als sichtbare Beschriftung am Radio und im zugänglichen Namen; Eye-Karte
  nur in der Kategorisierungsgruppe, mit „kostenfrei",
  `EyeAttribution`, dem Lizenzmelde-Hinweis und dem #621-Hinweis; nicht verfügbare Marke
  deaktiviert mit Grund als Satz; Zustände Skeleton, Fehler-Alert mit Wiederholung, bei
  Speicherfehler alte Wahl markiert plus Meldung „nichts geändert".
- `components/ClassificationSection.tsx`: genau zwei Radios („Wie im Projekt eingestellt",
  „Nur lokal"), ohne Vorwahl und ohne Gedächtnis; bei `project` eine Kurzfassung aus
  `project.model_choice` mit Link auf `PROJECT_ROUTE_PATHS.settings`; Cloud ohne Einwilligung
  sperrt den Start mit Grund und Link; Eye ohne Einwilligung sagt, dass die
  Sehenswürdigkeits-Erkennung entfällt; der Datenabfluss-Text nennt die Anbieter der aktuellen
  Wahl.
- `components/ClassificationEstimate.tsx` zeigt je nicht-`null` Anteil Tätigkeit, Grundlage
  (Anbieter/Modell oder „Eye") und Betrag, Eye als „kostenfrei", `null` als „findet nicht statt".
- `pages/ProjectSettingsPage.tsx`: Einwilligungstext nennt die Anbieterliste aus
  `project.model_choice` statt „Anthropic-Cloud-API".
- Die Bilanz (`ClassificationBalance`) bleibt; sie liest die Grundlage je Teilschritt aus den
  Laufspalten.

### Reihenfolge für developer

1. Migration (`scripts/nummern.py migration modellwahl-je-projekt`), `CategoryMethod`, Spalten,
   Check-Constraint in `models.py`.
2. `model_choice.py` mit `resolve_model_choice`, `UnknownModelChoiceError`, umgezogenem
   `api_key_for_provider` (Reviews-Router umstellen).
3. `landmark.py::build_landmark_client` (Anbieter aus dem Modell), Worker-Phasenparameter,
   Job-Keyword-Argumente mit Rückfall, die acht `settings.landmark_provider`-Stellen.
4. Schätzung je Anteil (`ClassificationEstimatePartOut`, `_estimate_part`, Eye-Anzahl).
5. Router `api/model_choice.py` (GET/PUT), `ProjectOut.model_choice`, `eye_available` entfernen.
6. `trigger_classify`: `mode=project|local`, Auflösung, Ablehnungsreihenfolge, Job-Argumente.
7. Frontend-Typen, API-Client, Hooks; alle Fixtures mit `eye_available` auf `model_choice`
   umstellen.
8. `ModelChoiceSection` in den Einstellungen.
9. Laufdialog mit zwei Wegen, Kurzfassung, Link, Einwilligungssperre.
10. `ClassificationEstimate` je Anteil; Einwilligungstext mit Anbieterliste.
11. `.env.example` (57-129) und `docs/setup.md` (402-417, 456-470): `LANDMARK_PROVIDER`/
    `LANDMARK_MODEL` sind die Installationsvorgabe für Projekte ohne eigene Wahl.
12. E2E `e2e/tests/eye-nicht-verfuegbar.spec.ts` umstellen: Eye in den Einstellungen wählen, Lauf
    „Wie im Projekt eingestellt", `503`, kein Rückfall.

## UI/UX

**Sichtbare Oberfläche: ja** — Projekteinstellungen (neuer Abschnitt „Modellwahl") und die
Laufwahl auf der Kriterien-Seite.

### Entwurf

Der Entwurf der Oberfläche liegt in der Penpot-Design-Datei auf der Seite
`Ansicht — Projekteinstellungen` — in beiden Prüfbreiten, mit den Zuständen `gefuellt`, `ladend`
und `fehler` als Variantenachse.

Gestalt: Die Modellwahl sitzt als eigener Abschnitt in den Projekteinstellungen. Jedes verfügbare
Modell steht als Karte mit seinem Anbieter, dem geschätzten Preis je Bild, den Token-Preisen und
dem Anfragelimit des Anbieters. Je Karte gibt es zwei Haken — einen für die Kategorisierung, einen
für die Sehenswürdigkeiten-Erkennung. Beide dürfen auf derselben Karte sitzen, wenn ein Modell
beide Tätigkeiten übernehmen soll.

Die Nachträge im Repository — die Soll-Struktur der Ansicht und die Kardinalitäten des
Rückleseskripts — stehen in PR #419. Eine Produktänderung enthält der Entwurf nicht.

Der Entwurf zeigt den Stand vor dieser Schärfung: Eye als Wahl der Kategorisierung, der Hinweis
zum Album-Entwurf und die auf zwei Wege verkleinerte Laufwahl fehlen darin noch.

### Aufbau

`components/ModelChoiceSection.tsx` sitzt in `pages/ProjectSettingsPage.tsx` **zwischen** dem
Panel „Cloud-Bilderkennung" und `CameraSection` — vor der Gefahrenzone, die letztes Kind des
`gap-6`-Containers bleibt. Eigene `section` in der Panelform der Seite (`flex flex-col gap-4
rounded-lg border border-border bg-surface p-4`), `h2` in `text-lg text-text-h`. Leitsatz: „Für
jede Tätigkeit eine eigene Wahl. Beide gelten für beide Nutzer dieses Projekts. Eine Änderung
wirkt auf künftige Läufe; vorhandene Ergebnisse und abgerechnete Beträge bleiben unverändert."

Karten in `grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4` in **Server-Reihenfolge**
(Registry, nicht alphabetisch), die Eye-Karte als letzte. Karte `flex flex-col gap-3 rounded-lg
border border-border bg-elevated p-3`; die Kartenkante bleibt `--border` in jedem Zustand, weil
sie keiner der beiden Gruppen gehört.

**Je Tätigkeit genau ein Radio, keine Kontrollkästchen.** Zwei ankreuzbare Kästchen erlaubten den
Zustand „keine Kategorisierung", den das Datenmodell ausschließt. Je Karte stehen zwei
Auswahlzeilen untereinander in der Form der bestehenden Wegwahl (`flex min-h-11 cursor-pointer
items-center gap-2 rounded-sm border border-border px-3 py-2 has-[:checked]:border-accent`,
Radio `size-4 accent-accent`). Jede Marke trägt ihre Tätigkeit sichtbar im selben `<label>`, ihr
zugänglicher Name nennt zusätzlich das Modell (`aria-label="Kategorisierung: Mistral,
ministral-3b-25-12"`); die Gruppe entsteht über `name`. Kein `fieldset` je Tätigkeit: die Radios
beider Gruppen stehen Kind für Kind verschachtelt, und ein `fieldset` kann seine Kinder nicht mit
einem zweiten teilen. Beide Marken dürfen gleichzeitig auf derselben Karte stehen; keine Auswahl
löscht die andere.

Die Karte trägt fünf feste Zeilen und **kein Eingabefeld**: Anbieter (`formatProviderLabel`,
`text-sm font-medium text-text-h`), Modell-ID (`font-mono text-xs`, weil zwei Modelle desselben
Anbieters sich erst in Ziffern und Bindestrichen unterscheiden), Preis je Bild, Token-Preise,
Anfragelimit.

- **Preis je Bild** über einen eigenen Formatierer `formatUsdPerImage` in `utils/formatStats.ts`:
  höchstens sechs Nachkommastellen, mindestens vier, abschließende Nullen fallen weg
  („0,0052 USD je Bild"). `formatUsd` ist hier untauglich, weil es jeden Wert unter einem Cent zu
  „< 0,01 USD" macht und die Modelle ununterscheidbar wären. Nie auf „0" gerundet; fehlt der
  Preis, steht **„Preis unbekannt"**.
- **Token-Preise:** „{Eingabe} je Million Eingabe-Token · {Ausgabe} je Million Ausgabe-Token"
  über `formatUsd`; ist eine Seite `null`, steht dort das Wort „unbekannt".
- **Anfragelimit:** „{n} Anfragen pro Minute — gilt für alle Projekte gemeinsam" (bei 1 „1 Anfrage
  pro Minute"); der Nachsatz ist Pflicht und steht in derselben Zeile.
- **Herkunft:** Steht die Wahl auf der Installationsvorgabe (`category_is_default`/
  `landmark_is_default`), trägt die angehakte Zeile zusätzlich das Wort **„Installationsvorgabe"**
  (`text-xs text-text-muted`).

### Eye-Karte

Nur in der Kategorisierungsgruppe; in der Zeile der Sehenswürdigkeits-Erkennung steht statt einer
Marke „Nicht möglich — Eye liefert keine Namen von Sehenswürdigkeiten." Kopf `Eye`; keine Zeile
Token-Preise, keine Zeile Anfragelimit (die Angaben existieren nicht). Preiszeile
**„kostenfrei"**. Darunter `EyeAttribution` unverändert, dann der Lizenzsatz wortgleich aus
`ClassificationSection.tsx` („Eye sendet bei jedem Lauf eine Lizenzmeldung mit einer Zählkennung,
aber ohne Bildinhalte an Desert Ant Labs; diese Meldung lässt sich nicht abschalten."), dann
„Eye liefert keine Grundlage für den Album-Entwurf, solange #621 nicht umgesetzt ist."

### Zustände

- **Laden:** zwei Platzhalter in Kartenhöhe (`Skeleton className="h-40 w-full rounded-lg"`) in
  `div role="status" aria-label="Modellwahl wird geladen"`; keine halb bedienbare Ansicht.
- **Ladefehler:** `Alert` (Ausprägung `error`) mit dem `detail` des Servers wörtlich, sonst „Die
  Modellwahl konnte nicht geladen werden.", `onRetry` → `refetch`; ohne geladene Antwort keine
  Marken.
- **Nicht wählbar:** Marke `disabled`, der Grund als Satz in derselben Zeile („Nicht wählbar —
  für {Anbieter} ist kein API-Schlüssel hinterlegt." / „Nicht wählbar — Eye ist in dieser
  Installation abgeschaltet."), Wortlaute aus `utils/classificationReviewLabels.ts`. Die Fakten
  der Karte bleiben lesbar; `--text-disabled` trägt nur das Bedienelement.
- **Aktuelle Wahl nicht wählbar:** Marke bleibt angehakt und gesperrt, darunter „So eingestellt,
  derzeit nicht wählbar." plus Grund.
- **Aktuelle Wahl nicht mehr in der Registry** (`provider: null`): je betroffener Tätigkeit eine
  Zeile über dem Raster: „{Tätigkeit}: {Modell-ID} — dieses Modell ist nicht mehr wählbar. Wähle
  ein anderes."
- **Kein wählbares Modell für die Sehenswürdigkeits-Erkennung:** Satz am Kopf der Gruppe.

**Speichern** ist ein `Button` unter dem Raster, nicht je Karte: der `PUT` schreibt alle drei
Spalten in einem Commit, und erst diese Atomarität macht „ein fehlgeschlagenes Speichern lässt
die bisherige Wahl unverändert" wahr. Der Knopf ist gesperrt, solange nichts geändert ist, solange
gespeichert wird und solange eine Tätigkeit auf einem nicht mehr wählbaren Modell steht — mit
Grund als Satz daneben. Während des Speicherns sind beide Gruppen gesperrt. **Fehlschlag:**
`Alert` mit `detail` wörtlich und dem Nachsatz „Es wurde nichts geändert; die bisherige Wahl gilt
weiter.", Marken springen auf die Serverantwort zurück; `onRetry` nur bei 5xx/Netzfehler, `409`
zusätzlich mit „Die Wahl lässt sich ändern, sobald der Lauf beendet ist." **Erfolg:** `p
role="status"` „Gespeichert — gilt für künftige Läufe."

### Laufwahl

`components/ClassificationSection.tsx`, Abschnitt an Ort und Stelle (kein Dialog). `fieldset` mit
`legend` „Weg für diesen Durchlauf", Zeilen `min-h-11`, ganze Zeile anklickbar, **genau zwei**:

1. **„Wie im Projekt eingestellt"** — Nebenangabe „Kategorisierung: {Eye | Anbieter, Modell} ·
   Sehenswürdigkeits-Erkennung: {Anbieter, Modell | entfällt — keine Cloud-Einwilligung}", beides
   aus `project.model_choice`, mit `break-words`. Darunter, **außerhalb** des `<label>`, der Link
   „In den Projekteinstellungen ändern" (`PROJECT_ROUTE_PATHS.settings`) — ein Link im `<label>`
   setzte beim Klick zusätzlich die Wahl.
2. **„Nur lokal"** — „Bleibt auf diesem Server · kostenfrei".

Keine Vorauswahl, kein Gedächtnis; ohne Wahl ist der Auslöser gesperrt („Wähle einen Weg — ohne
Wahl startet kein Lauf."). Cloud ohne Einwilligung: Auslöser gesperrt, Grund als Satz mit Link,
die Zeile bleibt anklickbar, „Nur lokal" startklar. Eye ohne Einwilligung: startet; Vorschau und
Kurzfassung sagen, dass die Sehenswürdigkeits-Erkennung entfällt. Eye abgeschaltet/nicht
erreichbar: keine Vorabsperrung, Servertext wörtlich plus „Der Lauf wurde nicht gestartet und es
wurde nichts verändert."; `onRetry` nur bei `503`. Modell nicht mehr wählbar (`409`): Servertext
wörtlich plus Nachsatz plus Link in die Einstellungen.

### Kostenschätzung

`components/ClassificationEstimate.tsx` je nicht-`null` Anteil eine Zeile: Tätigkeit, `{n} Fotos`,
Betrag, darunter die Grundlage („Anthropic, claude-haiku-… · 0,0052 USD je Bild" bzw. „Eye, auf
diesem Server" mit Betrag „kostenfrei"). `null` wird nicht als Zeile gezeigt, sondern als Satz
(„Die Sehenswürdigkeits-Erkennung findet in diesem Durchlauf nicht statt.", bei fehlender
Einwilligung mit dieser Begründung). Beim lokalen Weg: „Dieser Durchlauf ist kostenfrei." Der
Satz „Beide Cloud-Anteile werden mit demselben Preis je Bild gerechnet" **entfällt** — er wäre
falsch, sobald die Tätigkeiten verschiedene Modelle tragen.

Der Datenabfluss-Absatz nennt die Anbieter je Tätigkeit aus `project.model_choice` (bei demselben
Anbieter einmal, mit beiden Tätigkeiten); bei Eye-Kategorisierung: für die Kategorisierung
verlässt kein Foto den Server. Der Einwilligungstext in den Projekteinstellungen nennt statt
„Anthropic-Cloud-API" die Anbieterliste aus `project.model_choice`.

**Wortgleichheit:** „Kategorisierung", „Sehenswürdigkeits-Erkennung", „kostenfrei",
„Nicht wählbar —", „Preis unbekannt" zeichengleich an allen Stellen. Fortschritt und Bilanz
behalten „Kategorie-Vorschläge" (`utils/classificationSteps.ts` unverändert).

### Offene Punkte des Entwurfs

1. Die Eye-Wahl fehlt im Brett (kostenfrei, Nennung, Lizenzmeldung).
2. Der Album-Hinweis zu #621 fehlt.
3. Die Laufwahl zeigt noch drei Wege statt zwei.
4. Die Marken sind als Kontrollkästchen gezeichnet; gebraucht werden Radios.
5. Der Nicht-wählbar-Zustand ist nicht gezeichnet (Grund an der Marke, „Preis unbekannt", Zeile
   für ein entferntes Bestandsmodell).
6. Der Speichervorgang ist nicht gezeichnet (Knopf, laufendes Speichern, Fehlschlag-Satz).

Im Bausteinregister der Design-Datei fehlt eine runde Auswahlmarke (die Bibliothek führt nur ein
Kontrollkästchen).

## Teststrategie

Ebenen je Kriteriengruppe (Unit = reine Funktion; Integration = pytest gegen echte In-Memory-DB
bzw. aufgezeichneten Client; Komponente = vitest + Testing Library; E2E = Playwright):

- **Auswahl in den Einstellungen.** Unit `tests/test_model_choice.py` (Auflösung, `NULL` vs.
  gespeicherte Vorgabe, `is_default`, `UnknownModelChoiceError`, Check-Constraint); Integration
  `tests/test_api_model_choice.py` (Katalog mengengleich zur Registry, `PUT` `200`/`422`/`409`/
  `404`, Differenzprüfung geändert/unverändert, gespeicherte Wahl nach jedem Fehlschlag
  unverändert); Komponente `ModelChoiceSection.test.tsx` (zwei Gruppen, eine Karte je Eintrag,
  fünf Werte, „Preis unbekannt", Eye-Karte samt Nennung und #621-Hinweis, gesperrte Marke mit
  Grund, laden/Fehler/Speicherfehler); E2E ein Fall (Eye in den Einstellungen wählen — Cloud-Karten
  sind im Prüfstack nicht wählbar).
- **Laufwahl.** Integration `test_api_projects.py` (`mode` nur `project`/`local`, andere Werte
  `422`, fehlendes `mode` in der Schätzung `422`); Komponente
  `ClassificationSection.test.tsx` (genau zwei Marken, keine Vorwahl, keine Schätzung ohne Wahl,
  Kurzfassung aus `model_choice`, Link, Sperre ohne Einwilligung).
- **Wirkung.** Unit `build_landmark_client` (Anbieter aus dem Modell, unbekanntes Modell
  `ValueError`); Integration `test_worker_remote_category_classification.py`/
  `test_worker_criterion_scoring.py` (zwei Anbieter mit je eigenem Schrittmacher und Preis, Eye
  ohne Cloud-Foto, Identität angezeigt = aufgerufen = abgerechnet, zwei Projekte gleichzeitig);
  Komponente `ClassificationEstimate.test.tsx`/`ClassificationBalance.test.tsx`.
- **Einwilligung.** Integration `test_api_projects.py`, `test_worker_eye_phase.py` (Cloud ohne
  Einwilligung `403` ohne Job; Eye ohne Einwilligung `202` ohne Landmark-Phase); Komponente
  Grund als Satz mit Link, „Nur lokal" bleibt möglich, Anbieterliste folgt der Wahl ohne Neuladen.
- **Fehlerfälle.** Integration Eye abgeschaltet `403`, nicht erreichbar `503`, je ohne Job,
  Laufzeile oder Zeilenänderung; E2E `e2e/tests/eye-nicht-verfuegbar.spec.ts` auf diesen Ablauf
  umgestellt.
- **Übergang.** Integration Migrationstest (Bestandszeilen `cloud`/`NULL`/`NULL`, Server-Default,
  Check-Constraint; aufgelöste Wahl gleich der Installationsvorgabe, auf den Altwert gepinnt),
  Eye überschreibt kein Cloud-Ergebnis, Alt-Job ohne Modell-Argument löst selbst auf; Fixtures
  `eye_available` → `model_choice`.

Wichtigste Edge Cases, jeweils mit der Lage, die Fehler von der richtigen Umsetzung trennt:

1. **Bestand/Migration** — vor-migriertes Schema mit Bestandszeilen; danach entspricht die
   aufgelöste Wahl der Installationsvorgabe.
2. **Entferntes Registry-Modell** — gespeichert, aber nicht mehr in
   `VISION_MODELS_BY_PROVIDER`: Auslöser und Schätzung `409`, Lesepfade `provider: null`, **kein**
   Aufruf am aufgezeichneten Client; derselbe unveränderte Wert an `PUT` → `200`.
3. **Verschiedene Anbieter, Limit projektübergreifend** — zwei Projekte, je zwei Anbieter,
   verschränkt: jeder Client sieht nur Fotos seiner Tätigkeit, `throttle_for_provider` liefert je
   Anbieter dieselbe Instanz über beide Projekte und verschiedene über zwei Anbieter.
4. **Eye aus / nicht erreichbar** — `403` bzw. `503`, beide mit Vorher-Nachher über Job-Eingang,
   Lauf-, Foto- und Bewertungszeilen und Bilanz; der Statuscode allein belegt keinen fehlenden
   Rückfall.
5. **Einwilligung fehlt** — Cloud-Kategorisierung `403` ohne Job; Eye-Kategorisierung `202`,
   Laufzeile `mode='eye'`, Landmark-Anteil `null`, keine Landmark-Zeile.
6. **Eye überschreibt kein Cloud-Ergebnis** — Cloud-Kopfzeile bleibt mit Anbieter und
   Rückbaudaten; Gegenprobe: Cloud-Kategorisierung ersetzt eine Eye-Kopfzeile.
7. **Preis unbekannt** — Katalogeintrag ohne `MODEL_PRICING`: Preis je Bild und beide Token-Preise
   `null`, Karte „Preis unbekannt", Schätzanteil `null` statt `0.0`, Eye-Anteil `0.0` mit
   „kostenfrei".
8. **Speichern fehlgeschlagen** — `500`/Netzfehler: gespeicherte Wahl bleibt (Lesen über die API)
   **und** die Marke steht weiter auf dem alten Wert, dazu „nichts geändert".
9. **Speichern während eines Laufs** — `409`, gespeicherte Wahl unverändert.

Nicht auf E2E-Ebene prüfbar, bewusst: der Cloud-Weg. Der Prüfstack setzt beide Anbieterschlüssel
leer und startet keinen Worker — zwei Anbieter, zwei Schrittmacher, zwei Preise und mehrere
Projekte bleiben Integrationsnachweis. Damit ist auch „gilt für beide Nutzer" nur auf API-Ebene
belegt.

`specs/architecture/0002-testkonzept.md` ist um die Sektion „Eine Wahl je Projekt und Tätigkeit,
ein gespeicherter Registry-Verweis mit zwei Fehlerzeiten und eine Bindung an zwei Nutzer"
ergänzt.

## Security

**Sicherheitsrelevant, kein Blocker.** Fortschreibung in
[`0003`](../architecture/0003-securitykonzept.md) (neuer Abschnitt „Modellwahl je Projekt und
Tätigkeit", `model_choice.router` in der REST-API-Zeile, Ablösungshinweis an der
Provider-Wahl-Zeile, vier Ankerzeilen). Neu ist: **ein Projektfeld entscheidet erstmals, welcher
der bereits eingewilligten Empfänger ein Foto bekommt und ob es überhaupt hinausgeht**, und ein
neuer Schreibendpunkt nimmt dazu eine Eingabe von außen an. Kein neues Secret, keine neue
Umgebungsvariable, keine neue Abhängigkeit, kein geänderter Datenumfang je Foto.

- **S1 — Geschlossene Eingabe, Empfänger folgt aus dem Modell.** Keine freie Modell-ID:
  `ModelChoiceIn` mit `extra="forbid"`, `category_method` als endlicher Wert, beide Modellfelder
  nur per exaktem Stringvergleich gegen `VISION_MODELS_BY_PROVIDER`; der Anbieter ausschließlich
  über `provider_for_vision_model` — nie aus dem Body, nie als eigene Angabe im Job-Payload, nie
  aus einer Präfix-Heuristik, nie aus `settings.landmark_provider`. Der Modellname geht als
  Body-Feld an einen festen Anbieter-Endpunkt (kein SSRF). Alle drei Spalten in einem Commit.
- **S2 — Der Router hängt am Torwächter und steht im Vollständigkeitstest.**
  `dependencies=[Depends(get_current_user)]` **und** `model_choice.router` in
  `tests/test_auth_guard.py::_protected_router_operations()`; ohne den Listeneintrag bleibt der
  Test grün und prüft den Router nie. Neuer `401`-Fall für `GET` und `PUT` (pfadbenannt).
- **S3 — Die Modellwahl erteilt und entzieht keine Einwilligung.** Der Handler schreibt nur
  `category_method`, `category_model`, `landmark_model`, nie `cloud_vision_detection_enabled`
  oder `cloud_vision_consent_at`; ein Empfängerwechsel setzt den Consent-Zeitstempel nicht
  zurück. Test: nach einem `PUT` sind beide Spalten byte-gleich.
- **S4 — Schlüsselverfügbarkeit verlässt den Server nur als Wahrheitswert.**
  `api_key_for_provider(provider) -> bool` (Umzug aus `api/classification_reviews.py:367`, dort
  heute `-> str`) prüft Anwesenheit und gibt den Wert nie zurück; weder Antwort noch Fehlertext
  noch Log tragen Schlüssel, Präfix, Länge, Variablenname, Basis-URL oder
  Nebenläufigkeitswerte. `requests_per_minute` ist die einzige ausgelieferte Betriebsgröße.
  Begrenzte Weitung des älteren Verbots „Vorhandensein von Keys" (0003, Spec 0304): dieselben
  zwei authentifizierten Nutzer, Präzedenzfall `GET …/classification-reviews/options`.
- **S5 — Kein stiller Rückfall, auch nicht aus Datenbank oder Job.** Gespeichertes, aber
  entferntes Modell: `409` in Auslöser und Schätzung, Lesepfade `provider: null`; der Worker löst
  die Job-Argumente erneut gegen die Registry auf, ein unbekanntes Modell lässt den Lauf sichtbar
  scheitern.
- **S6 — Jedes Foto geht nur an den Anbieter seiner Tätigkeit.** Client je Phase aus dem
  aufgelösten Modell dieser Phase, `throttle_for_provider` aus demselben abgeleiteten Anbieter,
  `compute_cost_usd`, `provider`-Spalte und Bilanz lesen denselben Wert — diese Spalten sind der
  Nachweis, wer die Daten bekommen hat.
- **S7 — Die Einwilligungstexte sind abgeleitet.** Einwilligungstext und Datenabfluss-Text nennen
  alle Anbieter der aktuellen Wahl; der feste Satz „Anthropic-Cloud-API" ist ab hier falsch,
  sobald das Projekt Mistral oder Eye trägt. Beide Texte entstehen serverseitig aus der
  aufgelösten Wahl.
- **S8 — Die Laufwahl nennt kein Modell.** `mode: Literal["project","local"]` ohne Vorgabe,
  fehlt oder unbekannt → `422`; Modell-Ids entstehen ausschließlich in der Auflösung des
  Auslösers. Geprüft ohne Befund: die Eye-`403` hinter der `404` schafft kein Existenz-Orakel,
  weil beide Nutzer mit `GET /projects` ohnehin alle Projekte listen.
- **S9 — Eye: keine Bildinhalte in der Ansicht, Verfügbarkeit als Einstellung.**
  `eye.available`/`eye_disabled` und `no_api_key` kommen aus `Settings`, nie aus einem Testaufruf
  beim Anbieter und nie aus `/health`; `EyeAttribution` feste `https`-Adresse mit
  `rel="noopener noreferrer"`. Eye beim Start weg oder aus: `503`/`403`, kein Ausweichen.
- **S10 — Meldungen nennen keine Infrastruktur und nicht das Falsche.** Feste deutsche Sätze ohne
  Variablenname, Host, URL, Schlüssel oder Stacktrace, auch in `error_message`. Der
  wiederverwendete Wächter `_reject_while_a_criterion_run_is_active` (`api/projects.py:1230`)
  muss für diesen Endpunkt die Modellwahl nennen statt „Der Richtwert kann danach gesetzt
  werden."
- **S11 — Angezeigt = gespeichert.** Nach jedem Schreibversuch wird die Wahl neu vom Server
  gelesen; scheitert das Speichern, bleibt die alte Wahl markiert und die Ansicht sagt das.
- **S12 — Der Check-Constraint ist die zweite Linie.** `category_method = 'cloud' OR
  category_model IS NULL` macht die Zeile „Eye mit Cloud-Modell" unmöglich; die Migration mit
  `NOT NULL`/`server_default 'cloud'` stellt kein Bestandsprojekt still auf Eye.
- **S13 — Sichtbarkeit projektweit, unverändert.** Kein `user_id` an der Wahl, beide Nutzer sehen
  und ändern dieselbe; `ProjectOut.model_choice` ist nutzerunabhängig.

Bekannte Grenze, kein Blocker: zwischen der zuletzt gelesenen Anzeige und dem `POST` kann die
andere Person die Wahl ändern. Der Lauf nutzt die bei der Auflösung gültige Wahl; eingefrorene
Schätzung und Job stammen aus derselben Auflösung, und die Bilanz nennt die tatsächliche
Grundlage je Tätigkeit — die Anzeige kann einmalig veraltet sein, eine stille Abweichung zwischen
aufgerufenem Modell und Abrechnung entsteht nicht.

## Entscheidungen

- **`NULL` bedeutet Installationsvorgabe, die Methode ist NOT NULL `cloud`** — so gilt „Bestand
  verhält sich wie bisher" ohne Datenwanderung.
- **Eine ausdrücklich gespeicherte Vorgabe wird als Wert gespeichert** — sonst wäre „zur
  vorherigen Wahl zurückkehren" nicht eindeutig.
- **Entferntes Registry-Modell gibt `409` ohne Rückfall** — folgt aus „nie still ausweichen".
- **Schreibprüfung differenziert gegen den gespeicherten Stand** — ein unverändert
  durchgereichter, nicht mehr verfügbarer Wert bleibt zulässig, damit niemand festsitzt.
- **Eigener Router `api/model_choice.py`** — verhindert weiteres Wachstum von `projects.py`.
- **Job-Keyword-Argumente mit Rückfall auf die Auflösung** — ein beim Deploy bereits eingereihter
  Job darf nicht scheitern (Muster ADR 0138 Punkt 6).
- **`ProjectOut.eye_available` entfällt** — ohne Eye-Laufzeile hat es keinen Leser mehr.
- **Radio statt Kontrollkästchen, ein Speicherknopf statt Sofortspeichern** — folgt aus der
  NOT-NULL-Methode bzw. aus der Atomarität des `PUT`.
- **Eigener Formatierer `formatUsdPerImage`** — `formatUsd` macht Beträge unter einem Cent
  ununterscheidbar.
- **Architect, UX/UI-Designer, Test-Engineer und Security-Engineer konsultiert** (Schritte 1-3 des
  `spec-writer`-Ablaufs); keine Konsultation übersprungen.

## Offene Fragen

- Keine offene Produktentscheidung.

## Out of Scope

- Album-Entwurf auf Eye-Grundlage (#621) — hier nur der Hinweis an der Eye-Karte.
- Freie Eingabe oder eigene Registrierung weiterer Modelle und Anbieter.
- Änderung des Modellkatalogs, der Preisangaben oder der Anfragelimits selbst.
- Nachträgliches Neu-Bewerten vorhandener Ergebnisse beim Wechsel der Wahl.
- Ein eigenes, projektweises Anfragelimit — das Limit bleibt beim Anbieter und gilt für alle
  Projekte gemeinsam.
