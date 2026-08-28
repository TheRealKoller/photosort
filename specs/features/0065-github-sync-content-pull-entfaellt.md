# 0065 - github-project-sync-Tool verschlanken: bidirektionaler Content-Sync entfällt

**Status:** Accepted
**Erstellt:** 2026-08-28
**Bezug:** [GitHub-Issue #240](https://github.com/TheRealKoller/photosort/issues/240) (führt die separat erfasste Idee #219 zusammen, `specs/inbox/0042-adr-0017-content-sync-vereinfachen.md`)

## Ziel

Das Tool `scripts/github-project-sync` (~2300 Zeilen Python, eigener CI-Job mit 216 Tests) synchronisiert seit ADR 0017 Feature-Specs bidirektional mit GitHub Issues — inklusive vollem Content-Rückfluss von Issue-Body in die Spec-Datei samt Hash-basierter Konflikterkennung (`created`/`pushed`/`pulled`/`conflict`/`unchanged`).

Seit der Trennung von Story-Refinement (fachliche Klärung passiert jetzt vorher direkt im GitHub-Issue, Spec 0059/0064) und Spec-Erstellung sind Feature-Specs nur noch technische Umsetzungspläne — niemand bearbeitet diesen Inhalt mehr im GitHub-Issue-Textfeld. Der bidirektionale Content-Sync (Hash-Konflikterkennung, `pulled`/`conflict`-Klassifikation, fachliche Bewertung zurückgespielter Änderungen durch `requirements-engineer`) hat dadurch seinen ursprünglichen Zweck verloren und bindet unnötig Wartungsaufwand.

Die weiterhin aktiv genutzten Funktionen — Status-Synchronisation von Spec-Datei/Story-Issue zum Board, automatische Erkennung gemergter PRs, dateilose Story-Verwaltung — bleiben erhalten, sollen aber mit deutlich weniger Aufwand betrieben werden.

## User Story

Als Daniel, der die Weiterentwicklung von PhotoSort über Specs und ADRs steuert, möchte ich, dass das GitHub-Sync-Tooling nur noch die tatsächlich genutzten Funktionen abbildet, damit die Wartungslast (Codeumfang, Testumfang, eigener CI-Job) im Verhältnis zum echten Nutzen steht und ich nicht länger einen inzwischen ungenutzten bidirektionalen Content-Sync mitschleppe.

## Akzeptanzkriterien

- [x] Der bidirektionale Content-Sync für Feature-Specs (Rückfluss von Issue-Inhalt in die Spec-Datei, Hash-basierte Konflikterkennung, Klassifikation `pulled`/`conflict`) entfällt vollständig.
- [x] Eine manuelle Bearbeitung des Issue-Bodys hat keine Wirkung mehr auf die Spec-Datei — sie kann weiterhin vom Spec-Inhalt abweichen (kein Rückfluss mehr stattfindet), aber die Spec-Datei bleibt bei jeder Abweichung alleinige Quelle für den technischen Inhalt, unabhängig davon, was im Issue steht.
- [x] Die Status-Synchronisation (Spec-Datei/Story-Issue → Board-Spalte je nach Workflow-Schritt, inkl. Laufzeit-Overrides wie "In Progress"/"Review") funktioniert weiterhin unverändert aus Sicht der aufrufenden Skills/Agents (`capture`, `refinement`, `spec-writer`, `ship-feature`, `developer`).
- [x] Die automatische Erkennung gemergter Spec-PRs (Spec wird auf `Implemented`/Board-Spalte `Done` finalisiert) funktioniert weiterhin unverändert.
- [x] Die dateilose Story-Verwaltung (Issue anlegen, Status setzen/lesen, Body schreiben) funktioniert weiterhin unverändert.
- [x] Die `requirements-engineer`-Rolle muss keine aus GitHub zurückgespielten Spec-Inhaltsänderungen mehr fachlich bewerten, weil solche Änderungen durch den Wegfall des Content-Sync nicht mehr entstehen können.
- [x] Testumfang sinkt spürbar (216 → 198 Tests, netto -18: `test_classify.py` -2, `test_issue_body.py` -2, `test_spec_parser.py` -2, `test_hashing.py` -4, `test_cli.py` -4 [1 Test umbenannt statt entfernt], `test_sync_integration.py` -6, dazu 3 neue Regressionstests in `test_state.py`/`test_cli.py`), ohne dass die verbleibende Push-/Status-/Merge-/Story-Testsuite an Prüftiefe verliert.

## Datenmodell-Bezug

Kein PhotoSort-Datenmodell betroffen. Reines internes Tooling: `specs/.github-sync-state.json` (lokale, eingecheckte Sync-Zustandsdatei) verliert das Feld `pulled_body_hash` je Eintrag — kein GitHub-seitiges Feld ändert sich, kein manueller Migrationsschritt nötig (ADR 0041 Abschnitt 4).

## Architektur / Umsetzung

Der Pull-/Hash-Konflikt-Zweig von `scripts/github-project-sync` wird entfernt, der Push-Zweig bleibt unverändert. Vollständige Begründung und Entscheidung in ADR [`0041`](../decisions/0041-feature-spec-content-sync-nur-noch-push.md).

**Betroffene Dateien:**

- `scripts/github-project-sync/src/github_project_sync/issue_body.py`: `extract_content_zone_from_issue_body` entfernen (`build_issue_body`/`parse_marker` bleiben unverändert).
- `scripts/github-project-sync/src/github_project_sync/spec_parser.py`: `replace_content_zone` entfernen (`set_status_line`/`parse_spec_file`/`validate_spec_number` bleiben unverändert).
- `scripts/github-project-sync/src/github_project_sync/classify.py`: `SyncClassification` → `Literal["created", "pushed", "unchanged"]`; `classify()` auf reinen Baseline-Vergleich reduzieren (`stored is None` → `created`; `push_hash_now != stored.pushed_state_hash` → `pushed`; sonst `unchanged`); `SyncStateEntry.pulled_body_hash` entfernen (`runtime_status`/`pr_number` aus ADR 0037 bleiben).
- `scripts/github-project-sync/src/github_project_sync/hashing.py`: toten `push_state_hash_inbox` entfernen (`push_state_hash`/`text_hash` unverändert, ändern sich nicht).
- `scripts/github-project-sync/src/github_project_sync/state.py`: `_parse_namespace`/`_serialize_namespace` lesen/schreiben `pulled_body_hash` nicht mehr (kein Migrationsschritt — Altfeld wird beim Lesen schlicht nicht mehr referenziert, beim nächsten Schreiben verschwindet es selbstheilend).
- `scripts/github-project-sync/src/github_project_sync/sync.py`: in `_sync_one()` den gesamten Pull-/Konflikt-Zweig entfernen (`ConflictDiff`, `resolution`-Parameter, `effective`-Auflösung, `elif effective == "pulled"`-Zweig); `Resolution`-Typalias entfernen; `run_sync()` verliert den `resolutions`-Parameter; `SpecSyncResult` verliert `conflict`/`pulled_content_zone`. Marker-Integritätsprüfung (`parse_marker` gegen erwartete Spec-Nummer) bleibt unverändert. `_adopt_story_and_push_first_content()` bleibt unverändert (nutzt bereits nur den Push-Pfad).
- `scripts/github-project-sync/src/github_project_sync/cli.py`: `--resolve`/`_parse_resolutions` entfernen — nach demselben, bereits etablierten Stub-Muster wie `--supersede-inbox`/`inbox:` (Flag bleibt im Parser registriert mit `help=argparse.SUPPRESS`, liefert bei Verwendung `{"error": "..."}` statt argparse-Absturz); `_result_to_dict` verliert `conflict`/`pulled_content_zone`.
- `.claude/agents/requirements-engineer.md`: "Aufgabe 3" (fachliche Bewertung zurückgespielter Inhalte) vollständig entfernen, Frontmatter-Beschreibung entsprechend kürzen.
- `.claude/skills/github-project-sync/SKILL.md`: Frontmatter-Beschreibung (kein "inhaltliche Änderungen ... fließen zurück" mehr), Abschnitte "Konflikte — nie automatisch auflösen" und "`pulled`-Fälle — Refinement-Bewertung durch `requirements-engineer`" entfernen, "Pro-Spec-Ergebnisse auswerten" entsprechend kürzen (kein `conflict`/`pulled_content_zone` mehr im JSON).
- `specs/inbox/0042-adr-0017-content-sync-vereinfachen.md`: löschen (durch Issue #240/ADR 0041 inhaltlich aufgelöst).
- **Keine** Änderung an `.claude/skills/spec-writer/SKILL.md` (voller Content-Push bei `--adopt-issue` bleibt unverändert gültig, siehe ADR 0041 Abschnitt 2), `docs/architecture.md`, `docs/setup.md`, `README.md`, `docs/ai-workflow.md` — reines Entwickler-/Prozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug.

**Reihenfolge (TDD):**

1. `hashing.py` (toten Code entfernen)
2. `classify.py` (Kern-Vereinfachung, isoliert testbar)
3. `issue_body.py`/`spec_parser.py` (Pull-Bausteine entfernen)
4. `state.py` (Serialisierung)
5. `sync.py` (Orchestrierung, größter Umbau, hängt von 2–4 ab)
6. `cli.py` (Flag-Entfernung + Stub)
7. Agent-/Skill-Markdown (`requirements-engineer.md`, `github-project-sync/SKILL.md`)
8. Inbox-Datei löschen

## UI/UX

Nicht relevant (Schritt 2 übersprungen) — reines internes Python-CLI-Tool ohne sichtbare Oberfläche, keine Frontend-Berührung.

## Security

Nicht relevant (Schritt 3 übersprungen) — reine Vereinfachung/Entfernung von bestehendem internem Sync-Code, keine neue externe Eingabe, keine Auth-/Berechtigungs-/Secret-Änderung, keine Datenmodell- oder Sichtbarkeitsänderung zwischen den beiden Nutzern.

## Teststrategie

Ausschließlich Unit + Integration wie bisher (kein neues Package, keine neue Testebene, `scripts/github-project-sync/` bleibt ohne `--cov-fail-under`, Coverage-Gate-Backend ist nicht betroffen). Details in `specs/architecture/0002-testkonzept.md`, Untersektion "Erweiterung für ADR 0041":

1. **`classify()` (Unit, `test_classify.py`):** Vier-Fall-Matrix (inkl. `pulled`/`conflict`) → Drei-Fall-Matrix (`created`/`pushed`/`unchanged`), `pull_hash_now`-Parameter entfällt aus der Signatur. Die `pulled`/`conflict`-Testfälle werden ersatzlos entfernt.
2. **`--resolve`-Flag-Stub (CLI, `test_cli.py`):** neuer Regressionstest analog zu `test_main_returns_json_error_on_removed_supersede_inbox_flag` — `--resolve NNNN=...` liefert `{"error": "..."}` statt argparse-Absturz.
3. **`state.py`-Rückwärtskompatibilität (Unit + Integration, `test_state.py`):** explizit testen, nicht nur annehmen — (a) eine eingefrorene Alt-Format-Fixture mit noch vorhandenem `pulled_body_hash`-Schlüssel lädt weiterhin fehlerfrei; (b) ein direkt folgender `save_state()`-Aufruf schreibt die Datei danach ohne diesen Schlüssel. Erstes *subtraktives* State-Feld-Entfernungsmuster im Projekt (bisher nur additive Erweiterungen).
4. **Toter-Code-Nachweis:** sicherstellen, dass `extract_content_zone_from_issue_body`/`replace_content_zone` nach dem Umbau nirgends mehr in `sync.py`/`cli.py` aufgerufen werden.
5. **`test_sync_integration.py`:** die komplette `conflict`/`pulled`/`resolution`-Testgruppe wird ersatzlos gelöscht (~8 Tests), kein Ersatzfall — der Push-/Status-/Merge-Erkennungs-/Story-Pfad bleibt unverändert und braucht keine neuen Tests.
6. **Kein Baseline-Selbstheilungs-Testfall nötig** (anders als bei ADR 0039) — `push_state_hash`/`text_hash` selbst ändern sich nicht.

**Coverage-Gate:** keine Gefährdung — `backend/` (das `--cov-fail-under=80`-Gate) ist von dieser Änderung nicht betroffen, `scripts/github-project-sync/` läuft ohnehin ohne Coverage-Gate. Tests werden proportional zum entfernten Code gekürzt, kein Nettoverlust an Prüftiefe für den verbleibenden Push-/Status-Pfad.

## Entscheidungen

- **architect konsultiert (Schritt 1):** konkreter Code-/Komponentenbezug (`scripts/github-project-sync`, mehrere konkrete Module) eindeutig gegeben. Ergebnis: ADR [`0041`](../decisions/0041-feature-spec-content-sync-nur-noch-push.md) angelegt, Pull-Zweig entfällt vollständig, Push-Zweig bleibt bewusst unverändert (keine Kurzfassung entgegen des ursprünglichen Vorschlags aus der zusammengeführten Idee #219 — kein Akzeptanzkriterium fordert das, `spec-writer`s `--adopt-issue`-Verhalten bliebe sonst gebrochen).
- **ux-ui-designer nicht konsultiert (Schritt 2):** kein konkret benennbarer Bezug zu einer sichtbaren Oberfläche — reine GitHub-Prozess-/Automatisierungs-Idee ohne jeden Frontend-Bezug.
- **test-engineer konsultiert (Schritt 3):** konkreter, nicht-trivialer Bezug zu testbarem Verhalten (Rückbau von 216 bestehenden Tests, subtraktives State-Feld-Muster, neuer CLI-Flag-Stub). Ergebnis: Teststrategie oben, `specs/architecture/0002-testkonzept.md` um Untersektion "Erweiterung für ADR 0041" ergänzt.
- **security-engineer nicht konsultiert (Schritt 3):** kein konkret benennbarer Bezug zu Auth, externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, Datenmodell oder Datensichtbarkeit zwischen den beiden Nutzern — reine Entfernung von bestehendem internem Sync-Code.

## Out of Scope

- Reduktion des Content-**Push** auf eine Kurzfassung (Status/Priorität + Link statt vollem Spec-Inhalt) — bewusst nicht umgesetzt, siehe ADR 0041 Abschnitt 2.
- Änderungen an der Status-Synchronisation, der PR-Merge-Erkennung oder der dateilosen Story-Verwaltung selbst — bleiben unverändert.
- Migration bestehender `specs/.github-sync-state.json`-Einträge — nicht nötig, siehe ADR 0041 Abschnitt 4.
