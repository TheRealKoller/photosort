# 0262 - github-project-sync-Tool entfernen: Spec-Nummer = Issue-Nummer, dünner Board-Helfer

**Status:** Accepted
**Erstellt:** 2026-08-29
**Bezug:** [GitHub-Issue #262](https://github.com/TheRealKoller/photosort/issues/262) (führt die als Duplikat geschlossene Idee [#184](https://github.com/TheRealKoller/photosort/issues/184) zusammen), [`decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md`](../decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) (neue ADR dieser Spec), [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](../decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (Regelweg der Finalisierung, unverändert), [`0065-github-sync-content-pull-entfaellt.md`](./0065-github-sync-content-pull-entfaellt.md) (Vorstufe, deren Ergebnisstand diese Spec voraussetzt)

Diese Spec ist die erste, die die mit ihr eingeführte Konvention selbst anwendet: ihre Nummer `0262` ist die Nummer ihres GitHub-Issues.

## Ziel

Das Tool `scripts/github-project-sync` ist nach zwei Verschlankungsrunden (ADR 0041 / Spec 0065, zuletzt PR #261) immer noch ~2000 Zeilen Python mit 198 Tests und einem eigenen CI-Job. Sein struktureller Existenzgrund ist eine Abbildung, die es nicht geben müsste: Weil eine Feature-Spec eine eigene, unabhängig hochzählende Nummer trägt, braucht es eine persistierte Zuordnung zwischen Spec-Nummer und GitHub-Issue-Nummer (`specs/.github-sync-state.json`) — und um diese Zustandsdatei herum sind Content-Push, Hash-Konfliktvermeidung, Marker-Kommentare, Waisen-Erkennung und ein lokal gespiegelter Laufzeit-Status gewachsen.

Bekommt eine neue Spec direkt die Nummer ihres Issues, ist die Abbildung eine Identität. Damit entfallen Zustandsdatei und Sync-Begriff, und übrig bleiben wenige einzelne, zustandslose Board-Operationen: Issue anlegen, Body schreiben, Status setzen, Status lesen, finalisieren. Das Board wird damit die zentrale, einzige Stelle für Issues und Status, wie von Daniel gewünscht.

Die fehleranfällige GitHub-Projects-V2-Logik (Item-/Feld-/Options-ID-Auflösung, Setzen von Single-Select-Werten) darf dabei nicht über die Skill-Dateien verstreut improvisiert werden — sie bleibt an einer zentralen, automatisiert getesteten Stelle.

## User Story

Als Daniel, der PhotoSort über Specs und ein GitHub-Project-Board steuert, möchte ich, dass das GitHub-Board die alleinige zentrale Stelle für Issues/Status ist und keine separate Spec-Nummerierung mehr synchronisiert werden muss, damit ich keinen dedizierten ~2000-Zeilen-Python-Dienst mit eigenem CI-Job mehr für reine Nummern-/Status-Abgleichung pflege.

## Akzeptanzkriterien

- [x] Neue Feature-Specs bekommen die Nummer ihres zugehörigen GitHub-Issues als Spec-Nummer (eine neue Spec für Issue #265 heißt `specs/features/0265-titel.md`). Diese Spec selbst wendet die Regel bereits an (`0262`).
- [x] Bestehende Specs (0001–0065) behalten ihre jetzige Nummer — keine retroaktive Umbenennung, keine Anpassung bestehender Querverweise.
- [x] Es gibt keine Zustandsdatei `specs/.github-sync-state.json` mehr; kein Werkzeug und kein Skill liest oder schreibt sie.
- [x] Status-Synchronisation (Issue → Board-Spalte, inkl. `In Progress`/`Review`) funktioniert weiterhin aus Sicht der aufrufenden Skills/Agents (`capture`, `refinement`, `spec-writer`, `ship-feature`, `developer`) — über das neue Helferscript statt über `scripts/github-project-sync`.
- [x] Ein gemergter Spec-PR kann weiterhin ohne explizite PR-Nummer erkannt und finalisiert werden (Spec-Datei auf `Implemented ([PR #NNN](url))`, Board-Spalte `Done`, Issue geschlossen).
- [x] Dateilose Story-Verwaltung (Issue anlegen, Status setzen, Status lesen, Body schreiben) funktioniert weiterhin.
- [x] Die GitHub-Projects-V2-Logik liegt an genau einer Stelle (`scripts/gh-board.py`) und ist dort automatisiert getestet; keine Skill-Datei setzt selbst `gh project`-Aufrufe ab.
- [x] Das Python-Paket `scripts/github-project-sync/` samt Tests und dem CI-Job `github-project-sync` ist vollständig entfernt.
- [x] Alle Aufrufstellen (`capture`, `refinement`, `spec-writer`, `ship-feature`, `developer`) sind auf den neuen Mechanismus umgestellt; es verbleibt kein Verweis auf `github_project_sync` in Skills, Agents, CI oder Doku.
- [x] Die Namenskonvention in `specs/README.md` ist auf die neue Regel angepasst (Spec-Nummer = Issue-Nummer für neue Specs, Altbestand unverändert).

## Datenmodell-Bezug

Kein Bezug zum fachlichen Datenmodell der Anwendung (Projekte, Fotos, Bewertungen) — betroffen ist ausschließlich Projekt-Tooling. Die einzige gelöschte Datenstruktur ist die Entwicklungs-Zustandsdatei `specs/.github-sync-state.json` (Abbildung Spec ↔ Issue ↔ Board-Item), siehe ADR 0043, Abschnitt 2. `docs/architecture.md` beschreibt die Laufzeitarchitektur der Anwendung und ist daher nicht betroffen; `docs/ai-workflow.md` ist betroffen, da sich das Werkzeug des Workflows ändert.

## Architektur / Umsetzung

Vollständig in ADR [`0043`](../decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) festgelegt. Kurzfassung:

1. **Neues Script `scripts/gh-board.py`** — ein einzelnes Modul im bestehenden `scripts/`-Paket (kein eigenes Python-Package, kein eigener CI-Job). Es bündelt die gesamte `gh`-Interaktion: Auflösung von Projekt, Statusfeld und Options-IDs, Auflösung der Item-ID über die Issue-Nummer, Setzen/Lesen des Single-Select-Statusfelds, Issue-Erstellung inkl. Label, Body-Aktualisierung, Öffnen/Schließen, sowie das Umschreiben der `**Status:**`-Zeile einer Spec-Datei beim Finalisieren.

   Befehle: `create-issue`, `set-body`, `set-status`, `show-status`, `finalize`. Ausgabe ist immer ein einzelnes JSON-Objekt auf stdout, im Fehlerfall `{"error": "..."}` mit Exit-Code 1 — dieselbe Aufrufkonvention wie beim abgelösten Tool, damit die Skills ihr bewährtes Fehlerverhalten (Meldung unverändert weitergeben) behalten.

   Härtung unverändert aus ADR 0017, Abschnitt 5: kein `shell=True`, Argumente in Listenform, Bodies über temporäre Dateien statt über die Kommandozeile, Spec-Nummern vor jeder Pfadkonstruktion gegen `^\d{4}$` validiert.

2. **Entfällt ersatzlos:** `scripts/github-project-sync/` (10 Module, 10 Testdateien), `specs/.github-sync-state.json`, der CI-Job `github-project-sync`, der Content-Push in den Issue-Body samt Marker/Hash/Klassifikation/Waisen-Erkennung/Adoption, der volle Sync-Lauf und die Baseline/Override-Mechanik des Statusfelds.

3. **Skill-Ebene:** `.claude/skills/github-project-sync/` → `.claude/skills/github-board/`. Aufrufstellen: `capture` (`create-issue`), `refinement` (`set-body`, `set-status`), `spec-writer` (`show-status`, `set-status Todo`), `developer` (`set-status "In Progress"`), `ship-feature` (`set-status Review`, `finalize`).

4. **Nummernkonvention:** `specs/README.md` beschreibt die neue Regel; `spec-writer` legt die Spec unter der Issue-Nummer an, statt die nächste freie Nummer zu suchen.

## UI/UX

Nicht relevant — die Änderung betrifft ausschließlich Projekt-Tooling (Skills, Skripte, CI) und berührt keine Datei unter `frontend/` und keine sichtbare Oberfläche der Anwendung.

## Teststrategie

- **Unit-Tests (`scripts/tests/test_gh_board.py`, pytest, kein Netzwerk):** Das Script bekommt sein `run`-Callable injiziert; ein `FakeGh` beantwortet `gh`-Aufrufe aus einem In-Memory-Zustand und protokolliert die tatsächlich konstruierten Argumentlisten. Getestet werden mindestens: Argumentkonstruktion je Befehl (inkl. Listenform/kein `shell=True`), Auflösung der Item-ID über die Issue-Nummer, Fehler bei unbekanntem Issue/Item, Statuswert-Validierung, `Done` schließt das Issue zusätzlich, `create-issue` setzt Label und Status `Unrefined`, `show-status` verändert nichts, `finalize` schreibt die Statuszeile korrekt um, lehnt einen nicht gemergten/ohne Merge geschlossenen PR ab, lehnt eine Spec ab, die nicht `Accepted` ist, löst ohne `--pr-number` den schließenden, gemergten PR auf, und ist ohne einen solchen PR ein sauberer Fehler statt einer stillen Änderung.
- **Fehlerpfad:** Fehlender `project`-Scope der `gh`-Session muss als eigener, klar benannter Fehler herauskommen (der zugehörige `gh auth refresh -s project`-Hinweis ist im Skill dokumentiert).
- **Kein numerisches Coverage-Gate** (wie zuvor beim entfernten Job) — der Abdeckungsanspruch wird über die obige Liste sichergestellt. CI-Abdeckung über den bestehenden Job `demo-scripts` (ruff + pytest über `scripts/`).
- **Kein echtes `gh`/Netzwerk in CI** (unverändert zur bisherigen Teststrategie): Der erste reale Aufruf gegen das Board erfolgt manuell nach dem Merge; der einmalige Nachzug von Spec 0065 (ADR 0043, Migrationsschritt) ist zugleich der Smoke-Test.

## Security

Die sicherheitsrelevanten Eigenschaften des abgelösten Tools bleiben unverändert erhalten und sind Teil der Teststrategie: keine Shell-Interpolation (`shell=True` nirgends, Argumente ausschließlich in Listenform), Issue-/Story-Bodies gehen über temporäre Dateien statt über die Kommandozeile, und Spec-Nummern werden vor jeder Pfadkonstruktion gegen `^\d{4}$` validiert (Schutz vor Pfad-Traversal, ADR 0017, Abschnitt 5).

Neu ist nichts an der Angriffsfläche: Es werden keine neuen Eingaben von außen verarbeitet, keine Secrets berührt (die Authentifizierung bleibt vollständig bei der lokalen `gh`-Session), und es ändert sich nichts an Berechtigungen oder an der Datensichtbarkeit zwischen den beiden Nutzern der Anwendung.

Der Prompt-Injection-Schutz beim Lesen von Issue-Inhalten bleibt unverändert dort, wo er hingehört: in den Skills (`refinement`, `spec-writer` — Issue-Inhalt ist Datenmaterial, niemals Anweisung; ausschließlich `issue.body`, nie Kommentare). Das Script selbst liest Issue-Inhalte nicht interpretierend, sondern nur den Statusfeldwert und den PR-Zustand.

Entfallende Angriffsfläche: Mit dem Content-Push verschwindet der Marker-Kommentar samt seiner Integritätsprüfung — und damit auch die Klasse von Fehlern, bei der ein manipuliertes Issue-Body-Präfix eine falsche Spec-Zuordnung erzeugen könnte.

## Entscheidungen

- Spec-Nummer = Issue-Nummer für neue Specs; Altbestand 0001–0065 unverändert (ADR 0043, Abschnitt 1).
- `specs/.github-sync-state.json` entfällt ersatzlos; die Item-ID wird zur Laufzeit über die Issue-Nummer aufgelöst (ADR 0043, Abschnitt 2).
- Der Content-Push des Spec-Inhalts in den Issue-Body entfällt: Issue-Body = Story, Spec-Datei = Technik (ADR 0043, Abschnitt 3). Das ist die weitreichendste Einzelentscheidung dieser Spec und der Grund, warum der Großteil des Codes ersatzlos verschwinden kann.
- `Superseded` wird nicht mehr als Label/geleertes Feld abgebildet, sondern wie `Done` behandelt (ADR 0043, Abschnitt 3).
- Die automatische Merge-Erkennung wird nicht als eigener Modus, sondern als `finalize` ohne `--pr-number` abgebildet — ein Befehl statt zweier fast identischer (ADR 0043, Abschnitt 4).
- Spec 0065 wird nach dem Merge einmalig manuell über `finalize --spec 0065 --issue 240` nachgezogen; ihre Finalisierung ist bewusst nicht Teil dieser Spec (sie erfordert echten Board-Zugriff).

## Out of Scope

- Retroaktive Umbenennung der bestehenden 65 Spec-Dateien (0001–0065) und ihrer Querverweise.
- Änderungen am GitHub-Project-Board selbst (Feldname, Optionen, Ansichten) — die sechs Statuswerte aus ADR 0037 bleiben unverändert.
- Änderungen an der fachlichen Arbeitsweise der Skills (`refinement`-Gespräch, `spec-writer`-Konsultationen, Review-Runde) — nur das aufgerufene Werkzeug wechselt.
