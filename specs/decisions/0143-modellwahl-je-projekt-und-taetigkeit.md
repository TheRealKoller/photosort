# 0143 - Modellwahl je Projekt und Tätigkeit: Projektspalten, eine Auflösung, Anbieter aus dem Modell

**Status:** Accepted
**Datum:** 2026-11-08
**Bezug:** Issue [#383](https://github.com/TheRealKoller/photosort/issues/383), ADR
[`0059`](./0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md) (Punkt 1 „Betriebseinstellung,
kein Projekt-/Laufparameter" und „ein Schalter für beide Zwecke" wird abgelöst, die übrigen Punkte
gelten weiter), ADR [`0138`](./0138-eye-als-dritte-grundlage-sidecar-schattentabellen.md) (Punkt 6
Laufwahl und Punkt 7 Kostenvorschau werden abgelöst, die übrigen Punkte gelten weiter), ADR
[`0074`](./0074-cloud-vision-schrittmacher-je-anbieter-und-wiederholung-nur-bei-429.md) (Punkt 3,
unverändert), ADR [`0139`](./0139-pruefung-von-klassifizierungsverfahren-in-der-app.md) (Punkt 4,
Anbieter folgt aus dem Modell)
**Umfang:** über dem Richtwert von rund 100 Zeilen, weil Datenmodell, Auflösung, Laufwahl und
Schätzung dieselbe Wahl an vier Stellen tragen und nur gemeinsam „angezeigt = aufgerufen =
abgerechnet" sichern.

## Kontext

Kategorisierung und Sehenswürdigkeits-Erkennung laufen heute für alle Projekte mit einem Modell,
das `LANDMARK_PROVIDER`/`LANDMARK_MODEL` festlegen. Eye ist eine eigene Laufwahl. Künftig wählt
jedes Projekt je Tätigkeit: Kategorisierung über ein Cloud-Modell oder Eye, Sehenswürdigkeiten über
ein Cloud-Modell. Der Lauf kennt nur noch „wie im Projekt eingestellt" und „Nur lokal".

## Entscheidung

### 1. Drei Spalten an `projects`, Modell `NULL` = Installationsvorgabe

`category_method` (`SQLEnum(CategoryMethod, native_enum=False)`, Werte `cloud`/`eye`, NOT NULL,
`server_default 'cloud'`), `category_model: str | None`, `landmark_model: str | None`. Ein Modell
`NULL` heißt „Installationsvorgabe" (`settings.resolved_landmark_model()`). Check-Constraint
`ck_projects_category_model_requires_cloud`: `category_method = 'cloud' OR category_model IS NULL`.

**Was gilt:** Bestandsprojekte bekommen `cloud`/`NULL`/`NULL` und laufen wie bisher; kein Projekt
wird von selbst auf Eye gestellt. **Wo:** Migration und `models.py::Project`. **Bei Verletzung:**
ein Update änderte Kosten und Grundlage laufender Projekte ohne Zutun der Nutzer.

`LANDMARK_PROVIDER`/`LANDMARK_MODEL` bleiben als Installationsvorgabe samt Startvalidator bestehen.
Eine gespeicherte Wahl folgt einer späteren Änderung der Vorgabe nicht; ein `NULL` folgt ihr.

### 2. Genau eine Auflösung, der Anbieter folgt immer aus dem Modell

Neues Modul `backend/src/photosort/model_choice.py` (importiert `config`, nicht umgekehrt):
`resolve_model_choice(project) -> ResolvedModelChoice` mit `category_method`, `category_model`
(`None` bei Eye), `landmark_model` und den Anbietern über `provider_for_vision_model`. Dorthin zieht
`api_key_for_provider` aus `api/classification_reviews.py`.

Steht ein gespeichertes Modell nicht mehr in `VISION_MODELS_BY_PROVIDER` (später entfernt), wirft
die Auflösung `UnknownModelChoiceError`; Auslöser und Schätzung antworten `409` „Das im Projekt
eingestellte Modell ist nicht mehr wählbar. Wähle in den Projekteinstellungen ein anderes." Es
gibt keinen stillen Rückfall auf die Installationsvorgabe. `GET …/model-choice` und `ProjectOut`
zeigen die Modell-ID dann mit `provider: null`.

**Was gilt:** kein Lauf-, Schätz- oder Schreibpfad liest `settings.landmark_provider` oder
`settings.resolved_landmark_model()` für Projektarbeit; einzige Ausnahme ist die Auflösung selbst.
Client-Bau, Schrittmacher, `compute_cost_usd`, Modellspalten der Läufe und die
`provider`-Spalten je Foto bekommen denselben aufgelösten Wert. **Wo:** `worker.py`,
`landmark.py::build_landmark_client`, `api/projects.py`. **Bei Verletzung:** bei zwei Anbietern
ginge ein Foto an den falschen Anbieter, liefe unter fremdem Schrittmacher oder würde mit dem
falschen Preis gebucht.

### 3. Schrittmacher bleibt je Anbieter und Prozess

`throttle_for_provider(provider)` bleibt, nur der Schlüssel wechselt auf den Anbieter des Modells
(Punkt 2). Zwei Tätigkeiten beim selben Anbieter teilen einen Schrittmacher, zwei Anbieter haben
je einen. Die Zusage „auch wenn mehrere Projekte gleichzeitig laufen" trägt, weil alle
Cloud-Aufrufe im einen `worker`-Prozess laufen (ein Compose-Dienst, ohne `replicas`).

**Was gilt:** genau ein Worker-Prozess ruft Cloud-Anbieter. **Wo:** `docker-compose.yml`. **Bei
Verletzung:** ein zweiter Worker-Prozess verdoppelte die Rate je Anbieter; das braucht eine eigene
Entscheidung über einen prozessübergreifenden Schrittmacher.

### 4. Laufwahl `mode=project|local`, aufgelöst im Auslöser, eingefroren im Job

`ClassifyRequest.mode: Literal["project", "local"]` ohne Vorgabe. Der Auslöser löst `project` zum
wirksamen Weg auf (`cloud` bzw. `eye`) und reiht `classify` mit diesem Weg und den aufgelösten
Modellen ein (`mode=`, `category_model=`, `landmark_model=` als Schlüsselwörter).
`criterion_scoring_runs.mode` speichert weiter den wirksamen Weg. Fehlen die Modell-Argumente
(Job aus der Zeit vor dem Update), löst der Job über Punkt 2 auf.

Ablehnungsreihenfolge: Feature-Flag `403` → `404` → die drei `409` → wirksam Eye und `EYE_ENABLED`
aus `403` → wirksam Cloud ohne Einwilligung `403` → wirksam Eye und `/health` ≠ 200 `503`. Die
Eye-`403` steht damit hinter dem Projektzugriff, weil die Wahl am Projekt hängt. Eye ohne
Einwilligung startet; die Sehenswürdigkeits-Erkennung entfällt dann.

**Was gilt:** kein Weg weicht still auf einen anderen aus; was der Auslöser geschätzt hat, ruft der
Worker auf. **Wo:** `api/projects.py::trigger_classify`, `worker.py::classify`. **Bei Verletzung:**
eine Wahländerung zwischen Einreihen und Start ließe den Lauf ein anderes Modell rufen, als die
eingefrorene Schätzung ausweist.

`PUT …/model-choice` antwortet `409`, solange ein Klassifizierungslauf läuft.

### 5. Schätzung je Tätigkeit mit eigener Grundlage

`GET …/classify/estimate?mode=project|local` (ohne Vorgabe). Je Tätigkeit ein Anteil
`categorization`/`landmark` mit `kind` (`cloud`/`eye`), `provider`, `model`,
`price_per_image_usd`, `candidate_count`, `estimated_cost_usd`; ein nicht stattfindender Anteil ist
`null`. Ein Eye-Anteil trägt `provider`/`model` `null`, Preis und Betrag `0.0`; die Oberfläche
schreibt „kostenfrei". Die bisherigen Felder `provider`, `model`, `price_per_image_usd` auf
oberster Ebene entfallen. `null` bei Preis oder Betrag eines Cloud-Anteils heißt weiter
„unbekannt", nie `0`.

### 6. Wahl in den Projekteinstellungen über einen geschlossenen Katalog

`GET /projects/{id}/model-choice` liefert die aktuelle aufgelöste Wahl samt `is_default` und den
Katalog: je Modell aus `VISION_MODELS_BY_PROVIDER` Anbieter, `estimate_usd_per_image`, Ein- und
Ausgabepreis je Million Token aus `MODEL_PRICING` (fehlt der Eintrag: `null`),
`requests_per_minute` aus `resolved_cloud_vision_requests_per_minute(provider)` und
`unavailable_reasons` (`no_api_key`); dazu Eye mit `eye_disabled`. `PUT` nimmt `category_method`,
`category_model: str | None`, `landmark_model: str | None` (drei Pflichtfelder, `null` =
Installationsvorgabe) und schreibt alle drei. **Geprüft wird nur ein geänderter Wert**, gemessen am
gespeicherten Stand; ein unverändert durchgereichter Wert wird nicht neu geprüft. Die Prüfung
sichert gegen eine neue, nicht benutzbare Wahl — sie darf weder den Bestand sperren noch die
Änderung der *anderen* Tätigkeit blockieren. Ein `422` gibt es daher für: ein geändertes
Nicht-`null`-Modell außerhalb `VISION_MODELS_BY_PROVIDER` oder ohne Schlüssel seines Anbieters;
`eye`, wenn `EYE_ENABLED` aus ist und die Methode wechselt; `eye` mit
`category_model != NULL` (Invariante der Zeile, unabhängig vom Wechsel). Ein geändertes `null`
braucht keinen Schlüssel: es ist die Installationsvorgabe, und ohne jeden Cloud-Schlüssel bleiben
„Kategorisierung = Eye" und der Rückweg auf die Vorgabe speicherbar. Nach jedem `422` ist die
gespeicherte Wahl unverändert. `ProjectOut.model_choice` trägt die aufgelöste Wahl (Laufdialog,
Einwilligungstext). `ProjectOut.eye_available` entfällt, weil es keine Eye-Laufzeile mehr gibt.

Der Lauf prüft den Schlüssel nicht neu: fehlt er später, scheitern die Aufrufe wie heute als
Einzelfehler und stehen in `cloud_error_message`.

### 7. Eye überschreibt kein Cloud-Ergebnis

Unverändert ADR 0138 Punkt 4: die Rangfolge `local < eye < cloud` steht in
`motif_strengths.py::upsert_assessment`. Neu ist nur der Weg dorthin (`mode=project` mit
`category_method='eye'`).

## Konsequenzen

- Die Bilanz nennt je Tätigkeit das tatsächliche Modell ohne Änderung am Lesepfad:
  `remote_category_classification_runs.model` und `criterion_scoring_runs.landmark_model` tragen
  den aufgelösten Wert, der Anbieter wird wie bisher daraus abgeleitet.
- Ein Inhaltswächter in `tests/test_cloud_vision_throttle.py`, der
  `throttle_for_provider(settings.landmark_provider)` in `build_landmark_client` verlangt, kehrt
  sich um.
- `.env.example`, `docs/setup.md` und `docs/architecture.md` beschreiben `LANDMARK_*` als
  Installationsvorgabe.
- Eine Installation ohne jeden Cloud-Schlüssel (Prüfstack) hat keinen wählbaren Cloud-Eintrag im
  Katalog (`available: false`, `no_api_key`), kann aber Eye wählen und die Installationsvorgabe
  behalten — genau deshalb prüft `PUT` nur geänderte Werte.
- Der Eye-Hinweis zum Album-Entwurf entfällt mit [#621](https://github.com/TheRealKoller/photosort/issues/621).
