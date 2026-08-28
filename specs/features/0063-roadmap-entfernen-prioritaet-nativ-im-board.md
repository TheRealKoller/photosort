# 0063 - roadmap.md entfernen, Priorität nativ im GitHub-Project-Board pflegen

**Status:** Accepted
**Erstellt:** 2026-08-28
**Bezug:** GitHub-Issue [#224](https://github.com/TheRealKoller/photosort/issues/224) (Story, Status `Ready`), ADR [`0039`](../decisions/0039-prioritaet-nativ-im-board-roadmap-entfaellt.md)

## Ziel

Priorität und Status offener Arbeit (Feature-Specs, Story-Issues) werden heute an zwei Stellen parallel gepflegt: als Priorität/Status in `specs/roadmap.md` und als Priorität/Status auf dem GitHub-Project-Board. Seit Issues/Board die primäre, tagesaktuelle Sicht auf anstehende Arbeit sind, ist die lokale Datei zusätzlicher Pflege- und Synchronisationsaufwand ohne echten Mehrwert.

Diese Spec macht das GitHub-Project-Board zur alleinigen, verbindlichen Quelle für Priorität, entfernt `specs/roadmap.md` ersatzlos und baut die gesamte Prioritäts-Verdrahtung aus `scripts/github-project-sync` zurück. Das Sync-Tool fasst das Board-Feld `Priorität` danach weder lesend noch schreibend an.

## User Story

Als Daniel (Stakeholder) möchte ich Priorität und Status offener Arbeit ausschließlich auf dem GitHub-Project-Board sehen und pflegen, ohne dass zusätzlich eine lokale Roadmap-Datei synchron gehalten werden muss, damit der Pflegeaufwand sinkt und es nur noch eine einzige verbindliche Quelle gibt.

## Akzeptanzkriterien

- [ ] `specs/roadmap.md` existiert nicht mehr. `scripts/github-project-sync/src/github_project_sync/roadmap_parser.py` und `scripts/github-project-sync/tests/test_roadmap_parser.py` sind gelöscht. Kein Modul unter `scripts/github-project-sync/src` importiert `parse_roadmap_priorities` mehr.
- [ ] Das Sync-Tool schreibt das Board-Feld `Priorität` auf keinem Pfad — kein `set_item_single_select` und kein `clear_item_field` mit `fields.priority_field_id`, weder im Vollauf noch bei `--only NNNN`, `--only issue:NNN`, `--adopt-issue` oder `--only NNNN --runtime-status …`. Ein vor dem Lauf im Board gesetzter Prioritätswert (`Hoch`/`Mittel`/`Niedrig`) ist nach jedem Sync-Lauf unverändert; ein nicht gesetzter bleibt ungesetzt (kein Default).
- [ ] `push_state_hash` hat die Signatur `push_state_hash(*, status, content_zone)` (kein `priority`-Parameter, kein `_MISSING_PRIORITY_MARKER`). Der Hash ändert sich nur bei Status- oder Inhalts-Zonen-Änderung, nie durch eine Board-seitige Prioritätsänderung. `push_state_hash_inbox` bleibt unverändert.
- [ ] Der erste Sync-Lauf nach der Umstellung gegen eine `specs/.github-sync-state.json`, deren `pushed_state_hash` noch mit der alten (prioritätshaltigen) Formel berechnet wurde, klassifiziert jede getrackte Spec bei unverändertem Issue-Body/Inhalt **genau einmal** als `pushed` (nicht `conflict`, nicht `unchanged`); ein unmittelbar folgender zweiter Lauf ergibt `unchanged`. Kein Datenverlust, kein manueller Eingriff.
- [ ] Das Board-Feld `Priorität` wird weiterhin selbstprovisioniert (`gh_adapter.py::ensure_fields` legt das Single-Select-Feld `Priorität` mit `Hoch`/`Mittel`/`Niedrig` an, falls es fehlt) — es wird nur nicht mehr geschrieben.
- [ ] Die bisherige, in `specs/roadmap.md` enthaltene Priorisierungs-Begründungshistorie und die dokumentierten Abhängigkeiten zwischen Specs werden nicht in ein Ersatzformat (keine neue Datei, kein neues Board-Feld) überführt — der Verlust dieser Historie ist eine im Refinement der Story bewusst bestätigte Entscheidung.
- [ ] Die Skills `github-project-sync`, `refinement`, `spec-writer`, `capture` und der Agent `requirements-engineer` verweisen nicht mehr auf `specs/roadmap.md` oder eine dateibasierte Prioritätspflege. `refinement`/`spec-writer` tragen keine Prioritätszeile mehr in eine Datei ein; `requirements-engineer` liefert Priorität nur noch als Empfehlung, die im Board gesetzt wird.
- [ ] `README.md`, `specs/README.md` und `docs/ai-workflow.md` enthalten keinen Verweis mehr auf `specs/roadmap.md`. In `docs/architecture.md` ist der historische Inline-Verweis auf `specs/roadmap.md` (Abschnitt "Letzte Aktualisierung") zu unverlinktem Text entschärft, die historische Aussage bleibt unverändert.

## Datenmodell-Bezug

Kein PhotoSort-Datenmodell betroffen (dev-Prozess-/Tooling-Änderung, siehe [`docs/architecture.md`](../../docs/architecture.md) — analog ADR 0017/0036/0037). Betroffen ist ausschließlich das interne Zustandsschema des Sync-Tools: `push_state_hash` (Priorität entfällt als Hash-Bestandteil) und `SpecSyncResult` (`priority_warning` entfällt). Bestehende `specs/.github-sync-state.json`-Baselines heilen sich beim ersten Lauf selbst (siehe AK4).

## Architektur / Umsetzung

Gewählter Ansatz: Das GitHub-Project-Board wird die alleinige Quelle für Priorität. `scripts/github-project-sync` fasst das Board-Feld `Priorität` künftig **weder schreibend noch lesend** an; `specs/roadmap.md` wird ersatzlos gelöscht. Siehe ADR [`0039`](../decisions/0039-prioritaet-nativ-im-board-roadmap-entfaellt.md) (löst die Prioritäts-Teile von ADR 0017 §4–§6, ADR 0036 §5 und ADR 0037 §5 ab; die drei ADRs bleiben im Übrigen `Accepted`, der Status-Teil der Einbahnstraße und der Hash-Konfliktmechanismus für Status/Inhalt bleiben unangetastet).

Kein `--priority`-Schreibflag: die Priorität setzt Daniel direkt im Board-UI (im Refinement bestätigt). Das Prioritäts-Feld bleibt selbstprovisionierend (`gh_adapter.py::ensure_fields`), damit ein frisches Board die Spalte hat — nur geschrieben wird es nicht mehr.

### Betroffene Dateien und Reihenfolge

1. **`scripts/github-project-sync/` — Kernlogik (zuerst, TDD):**
   - `src/github_project_sync/roadmap_parser.py` + `tests/test_roadmap_parser.py`: **löschen**.
   - `src/github_project_sync/hashing.py`: `push_state_hash(*, status, priority, content_zone)` → `push_state_hash(*, status, content_zone)`; `_MISSING_PRIORITY_MARKER` entfernen. `push_state_hash_inbox` unangetastet lassen (out of scope, weiterhin ohne Aufrufer).
   - `src/github_project_sync/sync.py`: entfernen — `parse_roadmap_priorities`-Import/-Aufrufe, `_apply_priority_only`, `priority`-Parameter aus `_apply_fields`, `_sync_one`, `_adopt_story_and_push_first_content`, `set_feature_runtime_status`, `sync_story`; den Batch-Prioritäts-Push-Block im Vollauf (`run_sync`); `SpecSyncResult.priority_warning` und die zugehörige Warn-Logik; alle `roadmap_path`-Zeilen. `push_state_hash`-Aufrufe an die neue Signatur anpassen. `_apply_fields` schreibt danach nur noch das Status-Feld (Baseline/Runtime-Override-Logik unverändert).
   - `src/github_project_sync/cli.py`: `priority_warning` aus `_result_to_dict` entfernen; `--roadmap`-CLI-Argument entfernen, falls vorhanden.
   - `src/github_project_sync/gh_adapter.py` / `ProjectFields`: **unverändert** — Prioritäts-Feld-Provisionierung (`PRIORITY_FIELD_NAME`/`PRIORITY_OPTIONS`) bleibt.
   - `tests/`: `test_sync_integration.py`, `test_cli.py`, `test_hashing.py` an die neue Signatur/den Wegfall anpassen; Roadmap-Fixtures (`_roadmap_text()`, `roadmap`-Parameter von `_make_repo()`) entfernen. `test_gh_adapter.py` (Feld-Provisionierung) bleibt inhaltlich gültig. Neue Regressionstests siehe Teststrategie.

2. **Skills:**
   - `.claude/skills/github-project-sync/SKILL.md`: Beschreibung ("Status/Priorität … von Spec/`roadmap.md`" → nur Status), `priority_warning`-Behandlung streichen, Batch-Push-Erwähnung streichen, `finalized_from_pr`-Schritt: kein `requirements-engineer`-Aufruf zum Verschieben einer Roadmap-Zeile mehr (Spec-Datei-Statusumschrift durch `sync.py` bleibt).
   - `.claude/skills/refinement/SKILL.md`: Schritt 2 und der Schritt zum Eintragen der `roadmap.md`-Prioritätszeile → stattdessen: `requirements-engineer` liefert eine Prioritäts-**Empfehlung**, die der Skill Daniel nennt, damit er sie im Board setzt. `--only issue:NNN`-Aufruf pusht keine Priorität mehr.
   - `.claude/skills/spec-writer/SKILL.md`: Schritt 4 (Umtragen des Roadmap-Eintrags) entfernen.
   - `.claude/skills/capture/SKILL.md`: Formulierung "kein Roadmap-Eintrag" glätten.

3. **Agent:** `.claude/agents/requirements-engineer.md`: Aufgabe 1 "Roadmap pflegen" → "Priorisierung, Reihenfolge und Abhängigkeiten beraten" ohne Datei-Pflege; Aufgabe 2 Schritt 4 (`roadmap.md`-Eintrag) entfernen; Frontmatter/`description` und die `## Warum diese Rolle`-Passage entsprechend. Die tiefergehende Agenten-/Skill-Grenzklärung bleibt Story [#177](https://github.com/TheRealKoller/photosort/issues/177) (abhängig hiervon).

4. **Doku (im selben PR):**
   - `specs/roadmap.md`: **gelöscht**.
   - `README.md`: `roadmap.md`-Verweis aus der Projektstruktur-Tabelle entfernen.
   - `specs/README.md`: Struktur-Aufzählungszeile `roadmap.md` und "Roadmap" in der `docs/`-vs-`specs/`-Abgrenzung entfernen.
   - `docs/ai-workflow.md`: Agenten-Tabelle, Konzept-Dokument-Zelle für `requirements-engineer` (`specs/roadmap.md` → "—") und die Verantwortungs-Formulierung.
   - `docs/architecture.md`: keine inhaltliche Änderung; nur den historischen Inline-Link `` `specs/roadmap.md` `` in der "Letzte Aktualisierung"-Prosa zu unverlinktem Text machen.

### Einmaliger, selbstheilender Effekt

Beim ersten Sync-Lauf nach der Umstellung weicht der neu berechnete `pushed_state_hash` (ohne Priorität) von der in `specs/.github-sync-state.json` gespeicherten Baseline ab → jede getrackte Spec wird einmalig als `pushed` klassifiziert (Inhalts-Zone unverändert → kein `conflict`). Folge: identischer Re-Push von Issue-Body und Status-Feld, danach stabil. Kein Datenverlust, kein manueller Eingriff. Ein Test deckt das ab; ein weiterer den Fall "Alt-Baseline + gleichzeitige echte Issue-Body-Änderung → `conflict`".

## UI/UX

Nicht relevant. Kein PhotoSort-Frontend berührt; die Prioritätspflege findet in GitHubs eigenem Project-Board-UI statt.

*(ux-ui-designer nicht konsultiert (Schritt 2): kein konkret benennbarer Bezug zu einer sichtbaren PhotoSort-Oberfläche — die Änderung betrifft ausschließlich ein Python-Tooling-Paket, Skill-/Agent-Markdown und Doku; das Board-UI ist GitHubs Oberfläche, nicht Teil des Projekts.)*

## Security

Nicht relevant. Die Änderung entfernt ausschließlich Code-Pfade (Prioritäts-Lesen/-Schreiben, `roadmap.md`-Parsing). Keine neue Eingabe von außen, keine geänderte Auth-/Berechtigungs-/Secret-Stelle, keine Datenmodell-Änderung, keine veränderte Datensichtbarkeit zwischen den beiden Nutzern. Die `gh`-CLI-Anbindung (Listenform-Argumente, kein Shell-String) bleibt unverändert.

*(security-engineer nicht konsultiert (Schritt 3): kein konkret benennbarer Anhaltspunkt — reiner Rückbau von Code ohne neue externe Schnittstelle, Eingabe, Secret- oder Berechtigungsberührung.)*

## Teststrategie

Kein neues Package, keine neue Testebene — reine Reduktion der bestehenden `scripts/github-project-sync/`-Suite plus ein neuer Migrations-Regressionstest. Weiterhin ohne `--cov-fail-under` (eigenständige Vollständigkeits-Konvention des Pakets, kein CI-Gate); Mocking-Grundsatz unverändert (alles gegen `FakeGhAdapter`, nie echtes `gh`/Netzwerk).

### Unit-Ebene (`tests/test_hashing.py`)
- `push_state_hash` neue Signatur `(*, status, content_zone)`: Hash ändert sich mit Status bzw. Inhalts-Zone, ist stabil unter CRLF-/Trailing-Whitespace-Normalisierung.
- **Wegfallende Tests:** `test_push_state_hash_changes_with_priority`, `test_push_state_hash_none_priority_differs_from_empty_string`.
- **Angepasst:** `test_push_state_hash_changes_with_status`, `_changes_with_content`, `_stable_under_...` — `priority=`-Kwarg entfernen.
- `push_state_hash_inbox`-Tests: unverändert.

### Unit-Ebene (roadmap_parser)
- `tests/test_roadmap_parser.py` **komplett gelöscht** (mit `roadmap_parser.py`).

### Integrations-Ebene (`tests/test_sync_integration.py`, `tests/fakes.py`)
- Test-Helper `_roadmap_text()` und der `roadmap`-Parameter von `_make_repo()` entfernt; `_make_repo()` schreibt kein `specs/roadmap.md` mehr.
- Alle `push_state_hash(status=…, priority=…, content_zone=…)`-Baseline-Konstruktionen auf die neue Signatur umgestellt.
- Alle `assert result.specs[i].priority_warning is None`-Zeilen entfernt.
- **Wegfallende Tests:** `test_created_case_sets_status_and_priority_fields` (→ ersetzt durch reine Status-Feld-Assertion), `test_missing_priority_for_open_spec_yields_warning_but_still_syncs`, `test_missing_priority_option_aborts_with_sync_error_instead_of_clearing_field`, `test_state_file_missing_roadmap_still_syncs_with_empty_priorities`, `test_sync_story_sets_status_and_body_and_pushes_priority_from_roadmap` (→ Priority-Teil raus, Status/Body-Teil bleibt), `test_sync_story_without_status_or_body_only_pushes_priority` (→ ersetzt durch "no-arg Story-Sync ist sauberer No-op ohne Board-Schreibzugriff"), `test_sync_story_clears_priority_when_not_in_roadmap`, `test_full_run_pushes_priority_for_issue_referenced_roadmap_rows` + der gesamte Abschnitt "Batch-Prioritäts-Push für issue-referenzierte Roadmap-Zeilen".
- **Neue Regressionstests:**
  1. **Priorität wird nie geschrieben** — je ein Fall für Vollauf, `--only NNNN`, `--only issue:NNN`, `--adopt-issue`, `--only NNNN --runtime-status …`: `FakeGhAdapter` protokolliert `set_item_single_select`/`clear_item_field` mit `field_id`; Assertion: kein Aufruf mit `fields.priority_field_id`. Zusätzlich ein vorab gesetztes `gh.items[item_id]["F_PRIO"] = "P_Hoch"` überlebt den Lauf unverändert.
  2. **Superseded-Pfad fasst nur das Status-Feld an** — `clear_item_field` wird für das Status-Feld aufgerufen, nicht für das Prioritäts-Feld.
  3. **Selbstheilender `pushed`-Effekt** — `.github-sync-state.json` mit einem `pushed_state_hash` aus der alten prioritätshaltigen Formel, sonst unveränderter Issue-Body/Inhalt: erster Lauf → `pushed`, identischer Re-Push, neue Baseline; zweiter Lauf → `unchanged`.
  4. **Signaturänderung verschluckt keinen echten Pull** — Alt-Baseline PLUS echte eingehende Issue-Body-Änderung im selben ersten Lauf → `conflict` (beide Seiten weichen von der Baseline ab), kein stiller `pushed`.
- **Unverändert:** alle Status-Baseline-/`runtime_status`-/PR-Merge-Erkennungs-Tests (nur `push_state_hash`-Signatur nachziehen).

### CLI-Ebene (`tests/test_cli.py`)
- `priority_warning` aus `_result_to_dict`-Output entfernt → betroffene JSON-Output-Assertions anpassen/entfernen.
- roadmap.md-Schreibzeile im Test-Helper entfernen.

### `tests/test_gh_adapter.py`
- Prioritäts-Feld-Provisionierung (`test_ensure_fields_*`): unverändert grün — deckt AK5 ab.
- `test_..._clear_item_field`: fachlich weiter korrekt; optional den Beispiel-`field_id` auf das Status-Feld umstellen. Nicht blockierend.

### E2E/Smoke (manuell, vor Merge)
- Ein realer Sync-Lauf gegen das echte Board mit im Board-UI gesetzter Priorität auf mindestens einem Item; danach prüfen, dass die Priorität unverändert ist.
- Erster Lauf nach der Umstellung: bestätigen, dass jede getrackte Spec einmalig als `pushed` (nicht `conflict`) durchläuft und der zweite Lauf `unchanged` meldet.

### Edge Cases
- Board-Priorität vorab gesetzt → überlebt jeden Pfad. Nicht gesetzt → bleibt ungesetzt (kein Default).
- Alt-Baseline + unveränderter Inhalt → genau ein `pushed`, danach idempotent.
- Alt-Baseline + gleichzeitige echte Issue-Body-Änderung im ersten Lauf → `conflict` (transiente, gutartige Abweichung vom sonst erwarteten `pulled`, nur im einmaligen Migrationsfenster, kein Datenverlust — bewusst akzeptiert).
- `--only issue:NNN` ohne `--status`/`--body-file` → sauberer No-op, kein Board-Schreibzugriff.
- `--adopt-issue`: Prioritäts-Feld des adoptierten Items wird weder geleert noch gesetzt.
- Frisches Board ohne Prioritäts-Feld → `ensure_fields` legt es weiterhin an.
- Repo ganz ohne `specs/roadmap.md` (der neue Normalfall) → Vollauf läuft, kein Crash, keine Warnung.
- `.github-sync-state.json` mit einem `stories`-Eintrag für eine früher issue-referenzierte Roadmap-Zeile → kein Batch-Prioritäts-Push mehr versucht.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) wird ergänzt (neue Untersektion "Erweiterung für ADR 0039" in "Externe CLI-Werkzeuge als dünne Adapter-Schicht", nach dem ADR-0037-Block; zwei über reines Löschen hinausgehende Muster: "Feld wird nie geschrieben" als Regressionsziel über alle Pfade, und einmalige gutartige Baseline-Selbstheilung nach einer `push_state_hash`-Signaturänderung als Vorlage für künftige Hash-Schemaänderungen).

## Offene Fragen

Keine offen. Die einzige Produktentscheidung (Tool fasst Priorität nie an, kein `--priority`-Startwert; bewusster Verlust der Priorisierungs-Begründungshistorie ohne Ersatzformat) ist im Refinement und in einer direkten Rückfrage an Daniel bestätigt.

## Out of Scope

- Der volle bidirektionale Inhalts-Sync für Feature-Specs aus ADR 0017 (Spec-Inhalt komplett in den Issue-Body gespiegelt, inkl. Pull-Mechanismus) — separates, noch ungeschärftes Thema (`specs/inbox/0042`).
- Eine grundsätzlichere Überarbeitung der Zusammenarbeit von `developer`-Agent und `ship-feature`-Skill (`specs/inbox/0027`).
- Die tiefergehende Neuordnung der Agenten-/Skill-Verantwortungen (`requirements-engineer` etc.) — bleibt Story [#177](https://github.com/TheRealKoller/photosort/issues/177), abhängig von dieser Spec. Hier nur der durch den Wegfall der Datei zwingend nötige Minimal-Schnitt.
- Aufräumen der toten `push_state_hash_inbox`-Hilfsfunktion (seit Spec 0059 ohne Aufrufer) — hält den PR fokussiert.
- Eine mögliche komplette Entfernung des Sync-Tools (Daniel-Randbemerkung im Refinement) — eigene Idee, nicht Teil dieser Spec; Status-Sync und Content-Pull bleiben in Betrieb.
