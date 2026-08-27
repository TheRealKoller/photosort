# 0060 - Status-Lebenszyklus mit Umsetzungsfortschritt (Ready/Todo/In Progress/Review/Done)

**Status:** Implemented ([PR #229](https://github.com/TheRealKoller/photosort/pull/229))
**Erstellt:** 2026-08-27
**Bezug:** GitHub-Issue [`#222`](https://github.com/TheRealKoller/photosort/issues/222) ("Status-Lebenszyklus: Umsetzungsfortschritt statt Proposed/Accepted"), `architect`/`test-engineer`/`security-engineer`-Konsultation im `idea-sharpener`-Ablauf am 2026-08-27. Löst [ADR 0037](../decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) um; diese ADR löst Abschnitt 2 von [ADR 0036](../decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md) ab (alle übrigen Abschnitte von ADR 0036 bleiben unverändert gültig).

## Ziel

Das native GitHub-Project-Statusfeld (gerade erst über Spec [0059](./0059-story-lebenszyklus-github-issues.md)/ADR 0036 auf ein 5-Werte-Modell umgestellt) bildet aktuell nicht ab, in welcher technischen Umsetzungsphase sich ein Issue befindet — "Accepted" und "Implemented" sagen nichts darüber aus, ob gerade aktiv daran gearbeitet wird oder ein Pull Request auf Review wartet. Diese Spec führt einen granuleren, dem tatsächlichen Bearbeitungsstand folgenden Lebenszyklus ein, damit auf dem Board jederzeit erkennbar ist, ob ein Issue noch wartet, gerade bearbeitet wird, im Review hängt, oder abgeschlossen ist.

## User Story

Als Daniel (Stakeholder) möchte ich am nativen GitHub-Project-Statusfeld eines Issues auf einen Blick erkennen, ob es unbearbeitet ist, technisch geplant, gerade aktiv umgesetzt wird, im Pull-Request-Review hängt, oder abgeschlossen ist — damit ich den Fortschritt laufender Arbeit sehe, ohne dafür Issues/PRs einzeln öffnen zu müssen.

## Akzeptanzkriterien

- [ ] Das native Statusfeld (`STATUS_OPTIONS`) bildet den Lebenszyklus `Unrefined` → `Ready` → `Todo` → `In Progress` → `Review` → `Done` ab; `Story`/`Proposed`/`Accepted`/`Implemented` sind keine Board-Werte mehr (der lokale Spec-Datei-Lebenszyklus in `specs/README.md` — `Proposed → Accepted → Implemented → Superseded` — bleibt davon unberührt).
- [ ] Ein neu per `capture` erfasstes Issue steht in `Unrefined`.
- [ ] Nach fachlichem Refinement (`story-refiner`) steht das Issue in `Ready` (ersetzt den heutigen Wert `Story`).
- [ ] Für eine Feature-Spec mit Datei-Status `Proposed` **oder** `Accepted` ohne aktiven Laufzeit-Override ist der auf das Board gepushte Wert `Todo`.
- [ ] Ein per `--only NNNN --runtime-status "In Progress"` gesetzter Override macht das Board-Feld `In Progress`, solange die Datei-Status-Baseline `Todo` ist; wer den `developer`-Subagenten startet, setzt diesen Override unmittelbar davor (der Subagent selbst hat weiterhin keinen GitHub-Schreibzugriff).
- [ ] Ein per `--only NNNN --runtime-status "Review" --pr-number <NNN>` gesetzter Override (von `ship-feature` direkt nach `gh pr create`) macht das Board-Feld `Review`.
- [ ] Sobald der referenzierte Pull Request gemerged ist, erkennt der nächste reguläre Sync-Lauf das automatisch (`gh pr view`), schreibt die lokale Spec-Datei auf `Implemented ([PR #NNN](url))`, pusht `Done` und leert den Laufzeit-Override — kein dedizierter manueller Zusatzbefehl nötig.
- [ ] Sobald die Baseline `Done` wird (Datei-Status `Implemented`), gewinnt sie immer über einen ggf. noch gespeicherten Override, der dabei defensiv geleert wird.
- [ ] Ein Story-Issue, das ohne technische Umsetzung geschlossen wird (z.B. weil es obsolet geworden ist oder im Refinement bewusst verworfen wurde), steht ebenfalls in `Done` (`sync_story` schließt bei `--status Done` zusätzlich das Issue) — der Doppelbedeutung wird nicht mit einem eigenen Statuswert begegnet.
- [ ] Ein voller Sync-Lauf ohne `--only` stellt für jede bestehende Feature-Spec automatisch die korrekte Baseline (`Todo`/`Done`) aus dem jeweiligen Datei-Status wieder her (Grundlage für die Feld-Migration).
- [ ] Zum Zeitpunkt des Rollouts offene Story-Issues (aktuell `#222`, `#224`) werden einmalig manuell anhand ihres Issue-Inhalts auf `Ready`/`Unrefined` nachgezogen (kein Automatismus — naturgemäß kleine, zeitlich auf den Rollout-Moment begrenzte Menge, siehe ADR 0037 Abschnitt 7).

## Datenmodell-Bezug

Kein Bezug zu einem PhotoSort-Datenmodell bzw. [`docs/architecture.md`](../../docs/architecture.md) — reines Entwickler-Tooling für den eigenen KI-Entwicklungsprozess (Claude-Code-Skills/Agents, Python-CLI-Paket `scripts/github-project-sync`, GitHub Project V2).

## Architektur / Umsetzung

Siehe ADR [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](../decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) für die vollständige Begründung. Zusammenfassung des gewählten Ansatzes: der lokale Spec-Datei-Lebenszyklus (`Proposed`/`Accepted`/`Implemented`/`Superseded`, `specs/README.md`) bleibt unverändert — das native Board-`Status`-Feld wird stattdessen aus einer Baseline (`Proposed`/`Accepted` → `Todo`, `Implemented` → `Done`) plus einem optionalen, in `specs/.github-sync-state.json` persistierten Laufzeit-Override (`In Progress`/`Review`, nur wirksam solange die Baseline `Todo` ist) berechnet. `Done` wird **nicht** über eine native GitHub-Projects-Workflow-Automatisierung erkannt, sondern durch eine PR-Merge-Prüfung, die bei jedem regulären Sync-Lauf automatisch für Specs mit offenem PR mitläuft — bewusst gegen native Board-Automatisierung entschieden (ein zweiter, unkontrollierter Schreiber würde die Einbahnstraßen-Garantie aus ADR 0017 brechen).

### Betroffene/neue Dateien

- `scripts/github-project-sync/src/github_project_sync/gh_adapter.py`: `STATUS_OPTIONS = ["Unrefined", "Ready", "Todo", "In Progress", "Review", "Done"]`; neue Methode `get_pull_request(pr_number) -> PullRequestView(state, url)` (Protokoll + `GhCliAdapter`, wraps `gh pr view <NNN> --json state,url`), Pendant in `FakeGhAdapter` (tests/fakes.py).
- `scripts/github-project-sync/src/github_project_sync/classify.py`: `SyncStateEntry` um `runtime_status: str | None = None` und `pr_number: int | None = None` erweitert.
- `scripts/github-project-sync/src/github_project_sync/state.py`: `_parse_namespace`/`_serialize_namespace` lesen/schreiben die beiden neuen Felder rückwärtskompatibel (fehlen sie in einer alten Zustandsdatei: `None`).
- `scripts/github-project-sync/src/github_project_sync/spec_parser.py`: neue Funktion `set_status_line(text, new_status) -> str` (ersetzt nur das Schlüsselwort der `**Status:**`-Header-Zeile, analog zu `replace_content_zone`, aber für den Header statt die Inhalts-Zone).
- `scripts/github-project-sync/src/github_project_sync/sync.py`:
  - `_BOARD_STATUS_BASELINE`/`_RUNTIME_OVERRIDE_STATUSES` (neue Modul-Konstanten).
  - `_apply_fields()` bekommt einen `runtime_status`-Parameter — einziger Änderungspunkt, wirkt automatisch für `_sync_one()` **und** `_adopt_story_and_push_first_content()` (beide rufen `_apply_fields()` bereits auf).
  - `_sync_one()`: neue Merge-Erkennung ganz am Anfang der Funktion (vor der Status-Validitätsprüfung) — nur aktiv, wenn `stored_entry is not None`, `status == "Accepted"`, `stored_entry.runtime_status == "Review"` und `stored_entry.pr_number is not None`. Bei `gh.get_pull_request(pr_number).state == "merged"`: Spec-Datei via `spec_parser.set_status_line()` auf `Implemented ([PR #NNN](url))` umschreiben, `status` lokal auf `"Implemented"` setzen, `runtime_status`/`pr_number` im neuen State-Eintrag leeren. `SpecSyncResult` bekommt ein neues Feld `finalized_from_pr: int | None`.
  - Neue Funktion `set_feature_runtime_status(*, repo_root, gh, spec_number, runtime_status, pr_number=None, now=...)` — leichtgewichtiger, zielgerichteter Schreibzugriff (lädt Spec-Datei nur zur Bestimmung der Baseline, pusht Status+Priorität über `_apply_fields`, kein voller Content-Abgleich).
  - `sync_story()`: Statuswert-Validierung auf `{"Unrefined", "Ready", "Done"}` verengt (bisher fälschlich der komplette `STATUS_OPTIONS`); bei `status="Done"` zusätzlich `gh.set_issue_state(issue_number, open=False)`.
- `scripts/github-project-sync/src/github_project_sync/cli.py`: neue Flags `--runtime-status {In Progress,Review}`, `--pr-number` (nur mit `--only NNNN`, bare Feature-Scope).
- `.claude/agents/developer.md`: Schritt 0 bekommt einen an den Aufrufer (nicht an `developer` selbst) gerichteten Hinweis, vor dem Start `--only NNNN --runtime-status "In Progress"` zu setzen — nicht-blockierend bei Fehlschlag.
- `.claude/skills/ship-feature/SKILL.md`: Schritt 7 — neuer Teilschritt direkt nach `gh pr create` (`--only NNNN --runtime-status "Review" --pr-number <NNN>`); bisherige Teilschritte 7.4/7.5 (verfrühter `Implemented`-Bump + Roadmap-Update) entfallen ersatzlos.
- `.claude/skills/story-refiner/SKILL.md`: Schritt 5 — Ergänzung für den "verwerfen"-Fall (`--only issue:<NNN> --status Done`, schließt das Issue).
- `.claude/skills/idea-sharpener/SKILL.md`: Schritt 0 prüft ab jetzt gegen `"Ready"` statt `"Story"`.
- `.claude/skills/github-project-sync/SKILL.md`: dokumentiert `--runtime-status`/`--pr-number` sowie den neuen Fall `finalized_from_pr` (löst einen Aufruf von `requirements-engineer`, Haiku, zum Verschieben der Roadmap-Zeile in "Bereits umgesetzt" aus).
- `docs/ai-workflow.md`: Erwähnungen von `Story`/dem alten 5-Werte-Modell aktualisieren (kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md` — reines Prozess-Tooling).
- `scripts/github-project-sync/tests/fakes.py`: `FakeGhAdapter` um `get_pull_request()` erweitern.

### Sinnvolle Reihenfolge

1. `classify.py`/`state.py` (neue State-Felder, rückwärtskompatibles Lesen) — Grundlage für alles Weitere.
2. `spec_parser.set_status_line()` — isoliert testbar, keine Abhängigkeiten.
3. `gh_adapter.py` (`STATUS_OPTIONS`, `get_pull_request()`, `FakeGhAdapter`-Pendant).
4. `sync.py`: zuerst `_BOARD_STATUS_BASELINE`/`_apply_fields()`-Erweiterung (betrifft bestehende Tests für `_sync_one`/`_adopt_story_and_push_first_content` — hier zuerst die Baseline-Umstellung isoliert grün bekommen), danach die Merge-Erkennung in `_sync_one()`, danach `set_feature_runtime_status()`, zuletzt `sync_story()`-Verengung.
5. `cli.py` (neue Flags, dünne Verdrahtung).
6. Skill-/Agent-Dokumentation (`developer.md`, `ship-feature`, `story-refiner`, `idea-sharpener`, `github-project-sync`) sowie `docs/ai-workflow.md`.
7. Rollout zuletzt: Feld-Migration + voller Sync-Lauf + manueller Story-Status-Nachzug für `#222`/`#224` (siehe ADR 0037, Abschnitt 7) — kein Testcode dafür nötig, reiner Ablaufschritt gegen das echte Project.

## UI/UX

Nicht relevant — reine GitHub-Projects-Board-Automatisierung und internes Dev-Tooling (Claude-Code-Skills/Agents, Python-CLI), keinerlei PhotoSort-Frontend-Bezug. `ux-ui-designer` nicht konsultiert (Schritt 2, eindeutig kein Gegenbeispiel: keine sichtbare Oberfläche in der PhotoSort-App, auch nicht mittelbar).

## Security

**Sicherheitsrelevant: ja, aber eng begrenzt** — reines Entwickler-/Prozess-Tooling (`github-project-sync`), keine neue Angriffsfläche im PhotoSort-Laufzeitsystem selbst, keine Änderung an Auth-Modell oder Datensichtbarkeit zwischen den beiden App-Nutzern. Vollständige Herleitung im Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`, Abschnitt "GitHub-Project-Sync"), hier die für die Spec relevante Kurzfassung:

- **`--pr-number` als neue CLI-Eingabe:** kein Spoofing-Vektor — wird ausschließlich vom vertrauenswürdigen `ship-feature`-Skill unmittelbar nach dessen eigenem `gh pr create` gesetzt, kein Kanal für Dritte. Da `TheRealKoller` einziger Collaborator mit Merge-Recht ist, kann der die automatische `Done`-Erkennung auslösende Zustand `state: "merged"` nur durch Daniels eigene Aktion entstehen. Verbleibendes Restrisiko ist reine Datenintegrität (Tippfehler bei manuellem Aufruf könnte fälschlich eine unbeteiligte, aber gemergte PR referenzieren) — kein Angriffsszenario, kein Blocker.
- **Keine neue Sichtbarkeitsasymmetrie zwischen den beiden PhotoSort-Nutzern:** das GitHub-Board ist Entwickler-Tooling, getrennt vom Auth-/Sichtbarkeitsmodell der Anwendung; die neuen Statuswerte betreffen keine Foto-/Projektdaten.
- **Automatische Spec-Datei-Schreibaktion bei Merge-Erkennung:** bleibt innerhalb der bestehenden Einbahnstraßen-Garantie (`_sync_one()` einziger Schreiber, ADR 0017 Abschnitt 4), kein zweiter unkontrollierter Schreiber, kein automatisierter Hintergrund-Trigger (weiterhin ausschließlich Daniel-/Claude-initiierte Sync-Läufe).
- **`--runtime-status`/`--pr-number`:** kein Injection-Risiko — `--runtime-status` über `argparse choices` auf `{"In Progress", "Review"}` begrenzt, `--pr-number` ist `int`, beide fließen ausschließlich in bereits etablierte Listenform-`subprocess`-Aufrufe (kein `shell=True`).
- **`set_status_line()`-Schreibinhalt:** `pr_url` stammt ausschließlich aus der `gh pr view`-JSON-Antwort, nie aus Nutzereingabe — kein Injection-/XSS-Risiko, Spec-Dateien werden nirgends gegenüber einem nicht vertrauenswürdigen Betrachter gerendert.
- **Keine neuen Secrets.**
- **`developer`-Subagent-GitHub-Schreibgrenze bewusst nicht aufgeweicht** (ADR 0037 Abschnitt 3) — bestätigt konsistent mit der bestehenden Grundregel.

`specs/architecture/0003-securitykonzept.md` wurde im Zuge dieser Konsultation bereits ergänzt (neuer Absatz unter "GitHub-Project-Sync"/"Angriffsflächen").

## Entscheidungen

- Board-Status wird eine Baseline+Override-Projektion statt eines dritten, komplett neuen Zustandsmodells — kleinstmögliche Erweiterung des bereits bestehenden Sync-Modells, Einbahnstraßen-Garantie aus ADR 0017 bleibt strukturell erhalten (Details: ADR 0037 Abschnitt 1–2).
- `Done` wird bewusst **nicht** über eine native GitHub-Projects-Workflow-Automatisierung erkannt, sondern über eine explizite PR-Merge-Prüfung im getesteten `sync.py`-Layer — ein nativer Workflow wäre ein zweiter, unkontrollierter Schreiber auf dasselbe Feld (ADR 0037 Abschnitt 5). Diese im Issue explizit offen gelassene Entscheidung wurde damit zugunsten von Konsistenz mit der bestehenden Architektur getroffen.
- `In Progress` wird vom Aufrufer des `developer`-Subagenten gesetzt, nicht von `developer` selbst — dessen GitHub-Schreibgrenze wird nicht für einen einzelnen, vermeintlich harmlosen Statuswert aufgeweicht (ADR 0037 Abschnitt 3).
- Migration bestehender Feature-Specs läuft automatisch über einen vollen Sync-Lauf nach der einmaligen, manuellen Feld-Neuanlage (wie bei allen vorherigen Statusfeld-Migrationen, ADR 0030/0036); die Migration der aktuell zwei offenen Story-Issues (`#222`, `#224`) läuft dagegen manuell, da ihr Status naturgemäß nicht aus einer lokalen Datei rekonstruierbar ist (ADR 0037 Abschnitt 7).
- `Superseded` bleibt für Feature-Specs ein eigenständiger Board-Zustand (Feld leeren + Label) und wird nicht durch `Done` ersetzt — transportiert ein zusätzliches, für Daniel wertvolles Signal ("ersetzt durch etwas anderes", nicht nur "fertig"); für eine ohne Umsetzung verworfene Story existiert dieses Signal dagegen nicht, dort ist `Done` die einzig sinnvolle Wahl.
- `ux-ui-designer` nicht konsultiert (Schritt 2): reine GitHub-Projects-Board-Automatisierung und internes Dev-Tooling ohne jede sichtbare Oberfläche in der PhotoSort-App.
- Akzeptanzkriterien gegenüber dem rohen Issue-Text geschärft (`test-engineer`): Baseline/Override-Interaktion, insbesondere der Fall eines stehengebliebenen `Review`-Overrides nach Merge, sowie Trennung des Migrations-Kriteriums in "automatisch für Feature-Specs" vs. "manuell für offene Story-Issues" explizit ausformuliert, um sie testbar zu machen.
- `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md` wurden im Zuge dieser Konsultation bereits ergänzt (siehe jeweilige Abschnitte oben).

## Offene Fragen

Keine — alle in den Konsultationsschritten (Architektur, Test, Security) geklärt.

## Out of Scope

- Eine grundsätzlichere Überarbeitung der Zusammenarbeit von `developer`-Agent und `ship-feature`-Skill (siehe `specs/inbox/0027-ai-workflow-ueberarbeiten.md`) — diese Spec beschränkt sich auf das Statusfeld selbst und die dafür minimal nötigen Anpassungen an den bestehenden Automatisierungs-Touchpoints.
- Ein automatisierter Wiederherstellungspfad für den Status offener Story-Issues bei der Feld-Migration (bleibt bewusst ein manueller Einzelschritt, siehe ADR 0037 Abschnitt 7).
