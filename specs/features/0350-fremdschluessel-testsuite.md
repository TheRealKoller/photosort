# 0350 - Fremdschlüssel in der Testsuite durchsetzen

**Status:** Implemented ([PR #528](https://github.com/TheRealKoller/photosort/pull/528))
**Erstellt:** 2026-09-23
**Bezug:** [Issue #350](https://github.com/TheRealKoller/photosort/issues/350), ADR
[`0122`](../decisions/0122-fremdschluessel-werden-in-der-testsuite-durchgesetzt.md).

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Akzeptanzkriterien tragen geschützte
Dreiteilungen (Durchsetzungspunkt, Ausnahmen, Nachweise), die Doku-Nachziehliste ist eine Arbeitsliste
mit je betroffener Stelle, und `## Abgelöste Zusagen` muss die abgelöste Zusage namentlich führen —
sonst hält der Umsetzungslauf den ersetzten Test für eine Regression.

## Ziel

Die Backend-Testsuite läuft gegen SQLite In-Memory, das Fremdschlüssel nur bei gesetztem
`PRAGMA foreign_keys` durchsetzt — und bisher setzte niemand dieses Pragma. Damit war die
Testdatenbank nachsichtiger als die Zieldatenbank: eine fehlende ORM-Kaskade, eine falsche
Löschreihenfolge und eine verwaiste Kindzeile blieben unsichtbar, und eine Assertion der Form „kein
`IntegrityError` geflogen" prüfte nichts. Die Projektlöschung musste ihre Zusagen ersatzweise über
Zeilenzählungen und zwei Metadaten-Tests absichern.

Dieselbe Ursache deckt einen Verhaltensfehler auf: `run_criterion_scoring` / `run_classification`
legen die Lauf-Zeile an, **bevor** sie die Herkunft ihres `scoring_run_id` prüfen. Auf der
Zieldatenbank läuft dieses INSERT bei einem verschwundenen Bewertungslauf in eine
Fremdschlüsselverletzung und reißt die Transaktion ab; der bisher geprüfte „saubere Fehlschlag" ist
dort kein erreichbarer Zustand, weil es die Zeile dafür gar nicht gibt.

Ziel ist beides in einem: Der Testboden setzt Fremdschlüssel durch, das ORM kennt die dritte
Löschabhängigkeit, und der Herkunftsverweis wird geprüft, **bevor** die Lauf-Zeile entsteht.

## User Story

Als Entwickler des Projekts möchte ich, dass die Testdatenbank Fremdschlüssel genauso durchsetzt wie
die Produktivdatenbank, damit Kaskaden- und Löschfehler schon im Test auffallen statt erst im
Betrieb — und damit ein Lauf, der sich auf eine nicht mehr vorhandene Grundlage beruft, sauber statt
hart scheitert.

## Akzeptanzkriterien

- [ ] **AK1 — Durchsetzung suiteweit, Durchsetzungspunkt `make_engine`.** Jede Engine, über die die
      Backend-Testsuite Datenbankzugriff hat, setzt Fremdschlüssel durch. Durchsetzungspunkt ist
      ausschließlich `db.py::make_engine` (SQLite: `PRAGMA foreign_keys=ON` je DBAPI-Verbindung;
      Nicht-SQLite-Engines bleiben unangetastet). Erreicht werden damit die Anwendung, die
      `db_session`-Fixture und jeder Test, der seine Engine über `make_engine` baut. `tests/test_seed.py`
      baut seine (synchrone) Engine zwar selbst, setzt dasselbe Pragma aber über denselben Handler.
      **Ausgenommen bleiben ausschließlich** die Migrationstests `tests/test_migration_*.py`, die
      bewusst einen reduzierten Schemastand **ohne** Fremdschlüssel nachbauen, um eine Migration zu
      prüfen. Nachweise: (a) `PRAGMA foreign_keys` liefert `1` an einer über `make_engine` gebauten
      SQLite-Engine — auch auf einer zweiten Verbindung derselben Engine; (b) ein Quelltext-Wächter
      hält fest, dass `create_async_engine` außerhalb `db.py` nicht vorkommt und die Menge der Dateien,
      die eine Engine selbst bauen, genau die Allowliste ist (`db.py`, `tests/test_seed.py`,
      `tests/test_migration_*.py`); (c) an einer konstruierten, nicht verbundenen Postgres-Engine ist
      der `connect`-Handler nicht registriert.
- [ ] **AK2 — Der Nachweis hängt nicht an einer Behauptung, und die Ablehnung kommt nachweislich vom
      Pragma.** Ein eigener Test legt über die `db_session`-Fixture eine Kindzeile an, deren einzige
      verletzbare Zusicherung der Fremdschlüssel ist (übrige NOT-NULL-Spalten gefüllt), und erwartet
      beim `flush`/`commit` `sqlalchemy.exc.IntegrityError`; danach ist die Zeile nachweislich nicht
      vorhanden. **Gegenprobe im selben Test:** dieselbe Anlage über eine rohe SQLite-Engine ohne
      Pragma läuft durch und hinterlässt genau die verwaiste Zeile.
- [ ] **AK3 — Fehlender Bewertungslauf: sauberer Abbruch, kein Datensatz.** Ein Kriterien-Lauf, der
      sich auf einen `ScoringRun` beruft, den es **nicht gibt**, endet sauber statt hart. Beide
      Aufrufer — `run_criterion_scoring` im Direktaufruf **und** `run_classification` im verketteten
      Lauf — prüfen die **Existenz global** (`session.get(ScoringRun, scoring_run_id)`) **vor** dem
      Anlegen irgendeiner Zeile und brechen mit der neuen typisierten Ausnahme
      `CriterionScoringReferenceError` ab, deren Meldung den fehlenden `scoring_run_id` nennt.
      Danach sind `criterion_scoring_runs`, `remote_category_classification_runs`, `events` und
      `photo_rankings` je **0 Zeilen**. Die Ausnahme verlässt die Funktion; sie wird **nicht** als
      `FAILED`-Lauf verschluckt.
- [ ] **AK4 — Vorhandener, aber unpassender Bewertungslauf: unverändert.** Ein Kriterien-Lauf, dessen
      `ScoringRun` zwar existiert, aber nicht mehr der neueste **erfolgreiche** dieses Projekts ist
      (veraltet, nicht erfolgreich oder einem anderen Projekt zugeordnet), verhält sich unverändert
      wie heute: Es entsteht eine `criterion_scoring_runs`-Zeile mit `status == FAILED` — die
      Aktualitätsprüfung (`CriterionScoringGuardError`) bleibt wortgleich hinter dem INSERT. Der
      Unterschied zu AK3 ist genau „Elternteil fehlt" (nichts anzulegen) gegen „Elternteil passt
      nicht" (Zeile anlegen, dann als fehlgeschlagen führen). Belege sind die beiden unveränderten
      Tests `test_guard_fails_run_when_scoring_run_id_is_stale` und
      `…_when_latest_scoring_run_is_not_successful`.
- [ ] **AK5 — Suite grün, nichts übersprungen.** `pytest` endet mit Exit 0 und einer Zusammenfassung
      ohne `failed`, `error`, `skipped` und `xfailed`; gegenüber `origin/main` kommen keine
      Skip-/Xfail-Markierungen hinzu. (Heute existiert im Testbaum keine einzige.)
- [ ] **AK6 — Laufzeit im Rahmen, gemessen statt geschwellt.** Kein messbarer Anstieg: je ein Lauf
      auf `origin/main` und auf der Branch-Spitze auf derselben Maschine, beide Werte im PR genannt;
      Kriterium ist ein Anstieg innerhalb der Streuung zweier Läufe. **Kein** Schwellwert-Test in CI
      (Wanduhr-Messungen in CI sind unzuverlässig).
- [ ] **AK7 — Lücke als geschlossen ausgewiesen.** In `specs/architecture/0002-testkonzept.md` sind
      die beiden Einträge „Testdatenbank setzt keine Fremdschlüssel durch" und „Lauf mit nicht
      existierendem Bewertungslauf" als **geschlossen** ausgewiesen (benannt und auf den neuen
      Abschnitt verweisend, nicht still ersetzt). Die projektweite Regel „‚kein `IntegrityError`' ist
      keine Assertion" wird neu gefasst. Die übrigen Stellen, die den FK-losen Zustand behaupten,
      werden berichtigt (siehe `## Architektur / Umsetzung`, Doku-Nachziehliste). Der dritte, separat
      benannte Lücken-Eintrag — der `409`-Wächter sieht **eingereihte, noch nicht gestartete** Jobs
      nicht — bleibt **wörtlich unverändert** und ist ausdrücklich nicht Teil dieser Story.

## Abgelöste Zusagen

Diese Zusage gilt ab dieser Spec **nicht mehr**. Wer die Umsetzung prüft, hält den daran gebundenen
Test für bewusst umgeschrieben, nicht für eine Regression.

- **Zusage** „Ein Kriterien-Lauf mit einer nicht mehr existierenden `scoring_run_id` endet als
  fehlgeschlagener Lauf in der Historie", gehalten durch
  `tests/test_worker_criterion_scoring.py::test_guard_fails_run_when_scoring_run_id_does_not_exist`.
  An ihre Stelle tritt: **Es entsteht kein Lauf-Datensatz, der Aufruf endet mit einer verständlichen
  Meldung** (AK3). Der Test wird ersetzt. Für den benachbarten Fall (Bewertungslauf existiert, ist
  aber veraltet oder nicht erfolgreich) bleibt das *Aussehen der Historie* — ein `FAILED`-Lauf —
  unverändert zugesagt (AK4).

## Datenmodell-Bezug

**Keine Migration, keine neue Spalte, kein Schemawandel.** Betroffen sind ausschließlich
Relationship-Deklarationen im ORM (`models.py`), das FK-Pragma in `db.py` und der Fehlerpfad in
`worker.py`. Die Änderung ist damit auch unabhängig von der Alembic-Revisionsfolge.

## Architektur / Umsetzung

**Grundlage:** ADR [`0122`](../decisions/0122-fremdschluessel-werden-in-der-testsuite-durchgesetzt.md).
Drei zusammengehörige Änderungen; kein Schemawandel, keine Migration, keine neue Abhängigkeit.

### 1. FK-Durchsetzung — `backend/src/photosort/db.py`

- `make_engine` hängt für SQLite-Engines einen `connect`-Handler an `engine.sync_engine`, der
  `PRAGMA foreign_keys=ON` je DBAPI-Verbindung ausführt. Nicht-SQLite-Engines (Postgres) bleiben
  unangetastet. Der Handler wird als eigene, benannte Funktion geführt, damit `test_seed.py` ihn
  wiederverwenden kann.
- **`tests/test_seed.py`** baut seine synchrone Engine weiterhin selbst (`create_engine`,
  `Base.metadata.create_all`), setzt das Pragma aber über denselben Handler. Es hat keinen
  FK-Schreibpfad (`users` ist reines Elternobjekt), ist also kein Ausnahmefall — die Durchsetzung
  gilt hier wie überall. Damit deckt sich die Umsetzung mit der wörtlichen AK1-Ausnahme: nur die
  Migrationstests bleiben ausgenommen.
- **Bewusst unberührt:** die Migrationstests `backend/tests/test_migration_*.py` bauen ihr reduziertes
  Schema weiterhin mit rohem `create_engine` und bleiben ohne Durchsetzung — das ist der Zweck der
  Ausnahme (ein Schemastand *vor* der jeweiligen Fremdschlüssel-Änderung). `backend/alembic/env.py`
  baut seine Engine ebenfalls selbst (`pool.NullPool`, eigener Migrationspfad) und bleibt außen vor.

### 2. Löschreihenfolge im ORM — `backend/src/photosort/models.py`

`Event` ist der **dritte** Elternteil von `PhotoRanking` (`photo_rankings.event_id`). SQLAlchemy
leitet die Löschreihenfolge von Tabellen aus **Relationships** ab, nicht aus Fremdschlüsseln: ohne
`Event.rankings` löscht ein Flush `events` **vor** `photo_rankings` und läuft in eine
Fremdschlüsselverletzung, sobald die Durchsetzung aktiv ist. Deshalb:

- `CriterionScoringRun.events` und `Event.rankings` mit `cascade="all, delete-orphan"` — dieselbe
  Form wie `Photo.rankings` und `CriterionScoringRun.rankings` daneben. Reine Deklaration, **kein**
  Schemawandel, **keine** Migration.
- Die Reihenfolge in `project_deletion.py` bleibt unverändert: die Mengenlöschung ist der zweite,
  eigenständige Weg und wird von den beiden Metadaten-Tests aus ADR 0062 gehalten. Bulk-`delete`
  umgeht die neuen `cascade`-Einstellungen vollständig; sie wirken nur auf `session.delete(...)`.

### 3. Herkunftsverweis vor der Lauf-Zeile — `backend/src/photosort/worker.py`

- Neue typisierte Ausnahme `CriterionScoringReferenceError` neben dem bestehenden
  `CriterionScoringGuardError`: „der referenzierte Bewertungslauf existiert nicht (mehr)".
- Gemeinsamer Helfer `_start_criterion_scoring_run(session, project, scoring_run_id, *,
  cloud_requested, estimated_cost_usd=None)`: prüft die **globale Existenz** des `ScoringRun` und legt
  danach die Lauf-Zeile an. Beide Aufrufer nutzen ihn — `run_criterion_scoring` (Zweig `run is None`,
  Direktaufruf/Tests) und `run_classification` (verketteter Lauf, **vor** der ersten Phase und damit
  auch vor dem `RemoteCategoryClassificationRun`).
- Die **Aktualitätsprüfung** (`CriterionScoringGuardError`, „nicht mehr der neueste *erfolgreiche*
  Lauf des Projekts") bleibt unverändert hinter dem Insert: dort gibt es eine Zeile, die als
  `FAILED`-Lauf sichtbar wird (AK4). Eine `scoring_run_id`, die global existiert, aber nicht zum
  Projekt gehört oder veraltet ist, fällt in genau diesen Zweig — nicht in den ReferenceError.
- Das INSERT selbst bleibt ungeschützt: ein `IntegrityError` wird **nicht** übersetzt. Das
  Restfenster, in dem der Bewertungslauf zwischen Prüfung und INSERT verschwindet, ist bewusst offen
  (siehe „Grenzen").
- Rückgabe im Fehlerfall: **keine**, sondern die Ausnahme. Ein `CriterionScoringRun` gibt es nicht,
  und `None` zurückzugeben widerspräche der Signatur.

### Umsetzungsreihenfolge (TDD)

1. **Reihenfolge im ORM zuerst** (`models.py`), weil sie Voraussetzung dafür ist, dass die
   Durchsetzung nicht sofort an einer echten Löschung scheitert. Rot-Nachweis:
   `tests/test_models.py::test_deleting_criterion_scoring_run_cascades_to_photo_rankings` mit aktivem
   Pragma.
2. **Pragma in `db.py`** plus neue Datei `backend/tests/test_foreign_keys.py` (AK1/ AK2).
3. **Worker**: Ausnahme und Helfer, dann die beiden Aufrufstellen. Rot-Nachweis: der umgestellte
   Test in `tests/test_worker_criterion_scoring.py` (siehe `## Teststrategie`).
4. **Vollsuite** und Laufzeitvergleich gegen `main` (AK5/AK6); beide Werte gehören in die
   PR-Beschreibung.
5. **Doku-Nachziehliste** im selben PR.

### Erwartete Rot-Stellen (in einem Probelauf bestätigt)

Genau zwei Stellen der Suite werden durch die Durchsetzung rot, beide oben adressiert:
`test_models.py::test_deleting_criterion_scoring_run_cascades_to_photo_rankings` (Löschreihenfolge)
und `test_worker_criterion_scoring.py::test_guard_fails_run_when_scoring_run_id_does_not_exist`
(ersetzt). Alles Weitere, was rot würde, sind die ausgenommenen Migrationstests. Bleibt bei der
Umsetzung eine weitere Stelle rot, ist das ein **Fund**, kein Testartefakt, und gehört in die
PR-Beschreibung.

### Doku-Nachziehliste (im selben PR — sonst steht dort eine falsche Tatsachenaussage)

Alle folgenden Stellen behaupten heute, die Suite liefe ohne `PRAGMA foreign_keys=ON`:

| Stelle | Nachzuziehen |
|---|---|
| `src/photosort/project_deletion.py`, Modul-Docstring und Zeile 120 | Der Satz „nötig, weil die Testsuite ohne Pragma läuft" trägt nicht mehr; die beiden Wächtertests bleiben, ihre Begründung wird „Reihenfolge und Vollständigkeit, die ein Fremdschlüsselfehler nicht nennt" |
| `tests/test_api_projects.py:454` | Die Begründung der Zeilenzählungen bleibt richtig (sie ist die stärkere Form); die Begründung „Fremdschlüssel werden nicht durchgesetzt" wird ersetzt |
| `tests/test_project_deletion.py` (Modul-Docstring und Zeile 234) | dito |
| `tests/test_models.py:613` und `:1655` | dito |
| `tests/test_postgres_ddl_compatibility.py:1153` und `:1283` | Die DDL-Nachweise bleiben; die Begründung „fiele zur Laufzeit nicht auf" wird ersetzt |
| `specs/architecture/0002-testkonzept.md` (Punkt 2, Zeilen um 150/902, und Lückenliste um 2496–2498) | Regel neu fassen (Zeilenzählungen bleiben die stärkere Form, ihre Begründung dreht sich); beide Lücken benannt als geschlossen ausweisen; der dritte Eintrag bleibt wörtlich |
| `specs/architecture/0003-securitykonzept.md:764` | „die Testsuite kann diese Eigenschaft strukturell nicht zeigen" wird ersetzt |
| `docs/architecture.md` (Zeilen um 1236 f.) | dito |
| ADR `0062` | **Nicht anfassen** (nach Annahme unveränderlich); die Berührung ist in ADR 0122 ausgewiesen |

### Grenzen / bewusst offen

- **Restfenster Prüfung-zu-INSERT:** Der Bewertungslauf kann zwischen Existenzprüfung und INSERT
  verschwinden (Projektlöschung in einer anderen Session). Dann läuft es weiterhin in einen
  `IntegrityError`. Bewusst offen — eine Sperre oder eine echte Warteschlangen-Transaktion stünde
  außer Verhältnis zum Nutzen.
- **Eingereihte, noch nicht gestartete Jobs** bleiben unberührt (AK7, zweiter Satz): `trigger_*` legt
  keine Laufzeile an, der `409` sieht die Lücke nicht. Nicht mitgelöst, der Doku-Eintrag bleibt.

## UI/UX

Nicht relevant. Reine Backend-/Testinfrastruktur- und Fehlerpfadänderung ohne sichtbare Oberfläche;
der Issue-Body trägt keinen `## Design`-Abschnitt.

## Security

Nicht relevant. Kein Secret, keine Umgebungsvariable, keine Änderung an Authentifizierung,
Berechtigungen oder der Sichtbarkeit zwischen den beiden Nutzern, keine neue Eingabe von außen und
kein Schemawandel. Das neue `CriterionScoringReferenceError` verlässt den Worker als Job-Fehler; die
HTTP-Antwort des Auslösers bleibt unverändert `202` (der Auslöser validiert den Bezug bereits mit
`409`).

## Teststrategie

**Ebenen:** Backend-Integration ist der Kern (echte In-Memory-DB über die `db_session`-Fixture und
`make_engine`); eine neue Unit-Ebene entsteht nicht (die einzige reine Funktion wäre die
Dialekt-Weiche, die an einer konstruierten Engine billiger zu prüfen ist). Kein Frontend, kein neuer
E2E-Spec.

- **`backend/tests/test_foreign_keys.py` (neu):** `PRAGMA foreign_keys` liefert `1` an einer
  `make_engine`-Engine und **auf einer zweiten Verbindung derselben Engine** (nach `rollback`);
  Kindzeile ohne Elternzeile wird mit `IntegrityError` abgelehnt und ist danach nicht vorhanden
  (AK2); **Gegenprobe** ohne Pragma geht durch; an einer konstruierten
  `postgresql+psycopg://…`-Engine ist der `connect`-Handler nicht registriert; Quelltext-Wächter:
  `create_async_engine` nur in `db.py`, und die Dateien, die eine Engine selbst bauen, sind genau
  {`db.py`, `tests/test_seed.py`, `tests/test_migration_*.py`}.
- **`tests/test_worker_criterion_scoring.py`:** der Test
  `test_guard_fails_run_when_scoring_run_id_does_not_exist` wird **ersetzt** (nicht ergänzt): neue
  Erwartung `CriterionScoringReferenceError` und Zeilenzahl `criterion_scoring_runs == 0`. Die
  beiden benachbarten Guard-Tests bleiben **wörtlich unverändert** — sie sind der Beleg für AK4.
- **`tests/test_worker_classification.py`:** neuer Fall für den verketteten Aufrufer — fehlender
  Bewertungslauf bricht ab, **bevor** sowohl `RemoteCategoryClassificationRun` als auch
  `CriterionScoringRun` entstehen (je 0 Zeilen).
- **`tests/test_models.py`:** zwei zusätzliche Kaskadenaussagen — das Event ist nach dem Löschen des
  Laufs weg, und `session.delete(event)` löscht die Rangzeilen.
- **`tests/test_project_deletion.py`:** die beiden Metadaten-Wächter bleiben; ihre Begründungstexte
  ziehen nach, der Vollgraph-Fall über den Endpunkt hat jetzt echte Zähne.
- **`specs/architecture/0002-testkonzept.md`** wird geändert, nicht nur ergänzt: die
  FK-Durchsetzung samt Durchsetzungspunkt, **tragender** Allowliste und Negativkontrolle als neuer
  Musterabschnitt; die geschlossenen Lücken; die neu gefasste Regel.
- **Nicht automatisiert:** Postgres-Laufzeitverhalten (die Suite fährt kein Postgres; der E2E-Job
  deckt den vollen Stack ab), das Restfenster zwischen Vorprüfung und INSERT und die AK6-Zahl
  (Messung im PR, nicht in CI).

**Wichtigste Edge Cases:** Negativkontrolle ohne Pragma (sonst belegt AK2 nichts); Kindzeile mit genau
einer verletzbaren Zusicherung; die vier Migrationstests, die das volle Schema bauen und Zeilen ohne
Eltern anfügen (die Allowliste ist **tragend**, kein Muster); der zweite Aufrufer mit seinem eigenen
Halbzustand (`RemoteCategoryClassificationRun`); ORM-Kaskade ≠ Bulk-Delete; Pragma je Verbindung;
fremdprojekt-`scoring_run_id` (global existent → Guard, nicht ReferenceError); neuester Lauf mit
`status=RUNNING` („existiert, aber nicht erfolgreich").

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR `0122` angelegt; Pragma in `make_engine`, ORM-Kaskade in
  `models.py`, Existenzprüfung vor der Lauf-Zeile in `worker.py`.
- `ux-ui-designer` nicht konsultiert (Schritt 2): reine Backend-/Testinfrastruktur- und
  Fehlerpfadänderung ohne sichtbare Oberfläche; kein `## Design` im Issue-Body.
- `test-engineer` konsultiert (Schritt 3): Akzeptanzkriterien auf Testbarkeit geschärft, Edge Cases;
  Testkonzept an drei Stellen zu ändern.
- `security-engineer` nicht konsultiert (Schritt 3): kein Bezug zu Auth, externen Schnittstellen,
  Secrets, neuen Eingaben von außen, Berechtigungen, Datenmodell oder Datensichtbarkeit zwischen den
  beiden Nutzern.
- **`tests/test_seed.py` wird mitgezogen statt als Zusatzausnahme geführt** — vom Spec-Autor nach
  wörtlicher AK1-Lesung entschieden: AK1 verlangt die Durchsetzung auch dort, wo ein Test seine
  Datenbank selbst anlegt; ausgenommen sind allein Migrationstests. `test_seed` baut zwar selbst,
  passt aber nicht auf die Ausnahme; es setzt daher dasselbe Pragma über denselben Handler. Der
  `architect` hatte es zunächst als „unberührt" geführt; das ist damit korrigiert.
- **Die Existenzprüfung ist global** (`session.get(ScoringRun, scoring_run_id)`) — vom Spec-Autor
  entschieden gegen eine projektgebundene Prüfung: Ein `ScoringRun` ist global existent; eine
  vorhandene, aber projektfremde oder veraltete `scoring_run_id` „existiert" und gehört damit in den
  Guard-Zweig (FAILED-Lauf, AK4), nicht in den ReferenceError (AK3).
- **Der Quelltext-Wächter prüft `create_async_engine` repo-weit und die Engine-Bau-Allowliste** —
  `create_async_engine` kommt heute nur in `db.py` vor; die vier Migrationstests, die das volle
  Schema bauen, sind der Grund, warum die Allowliste namentlich und nicht als Kategorie geführt wird.
- **Das `IntegrityError` am INSERT wird nicht übersetzt** (ADR 0122 Punkt 5): Das Restfenster wird
  benannt, nicht zugedeckt.
- **`alembic/env.py` bleibt außen vor** — es baut eine eigene Engine (`NullPool`) und prüft
  Schemastände ohne Fremdschlüssel.

## Offene Fragen

Keine.

## Out of Scope

- Die separat benannte Lücke rund um **eingereihte, aber noch nicht gestartete** Jobs — sie bleibt
  bestehen (AK7).
- Der **Migrationspfad** (`alembic/env.py`): Er baut seine Engine weiterhin selbst; das Pragma dort
  zu setzen wäre eine eigene Entscheidung mit eigenem Risiko (Tabellen-Neuaufbau im SQLite-Batch-Modus).
- **Postgres-Laufzeitverhalten** und ein Postgres-Lauf in der Testsuite.
- Das **Restfenster** zwischen Existenzprüfung und INSERT.
