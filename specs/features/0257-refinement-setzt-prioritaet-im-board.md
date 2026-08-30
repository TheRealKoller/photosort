# 0257 - Refinement setzt die Prioritäts-Empfehlung automatisch im Board

**Status:** Implemented ([PR #273](https://github.com/TheRealKoller/photosort/pull/273))
**Erstellt:** 2026-08-30
**Bezug:** [GitHub-Issue #257](https://github.com/TheRealKoller/photosort/issues/257) (Refinement bereits vor dieser Spec-Erstellung abgeschlossen), [`decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md`](../decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md) (neue ADR dieser Spec, löst [`decisions/0039-prioritaet-nativ-im-board-roadmap-entfaellt.md`](../decisions/0039-prioritaet-nativ-im-board-roadmap-entfaellt.md) Abschnitt 2 ab)

## Ziel

Aktuell spricht der `refinement`-Skill nach dem Schärfen einer Idee nur eine Empfehlung zur Priorität (Hoch/Mittel/Niedrig) im Chat aus. Daniel muss diese Priorität danach selbst manuell im GitHub-Project-Board eintragen — ein zusätzlicher, leicht vergessener Handarbeitsschritt. Ziel ist, dass das Board direkt nach einem Refinement-Lauf korrekt befüllt ist, ohne dass Daniel selbst noch ins Board wechseln muss.

Dies revidiert bewusst ADR 0039 Abschnitt 2, die automatisches Setzen der Priorität durch Tooling explizit ausgeschlossen hatte (inkl. einer ausdrücklich abgelehnten `--priority`-Flag-Variante). ADR 0039 selbst sah diesen Fall in ihrem Abschnitt "Konsequenzen" ausdrücklich vor ("Ein späterer Wiedereinstieg... braucht eine neue, diese ADR als 'Superseded' markierende ADR") — die technische Neubewertung ist Teil dieser Spec, siehe [`decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md`](../decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md).

## User Story

Als Daniel möchte ich, dass der `refinement`-Skill die final abgestimmte Prioritäts-Empfehlung direkt und verbindlich im GitHub-Project-Board setzt, damit ich nach einem Refinement-Lauf nicht zusätzlich manuell ins Board wechseln muss, um die Priorität einzutragen.

## Akzeptanzkriterien

- [ ] Nach Abschluss des Refinements ruft der Skill `python3 scripts/gh-board.py set-priority --issue NNN --priority <Hoch|Mittel|Niedrig>` auf; der Aufruf erfolgt zwischen `set-body` und `set-status --status Ready` (Reihenfolge: Body → Priorität → Status).
- [ ] Ist das Board-Feld "Priorität" für das Issue aktuell leer, wird der übergebene Wert geschrieben (`gh project item-edit` mit der passenden Options-ID), der Rückgabewert ist `{"issue_number": NNN, "priority": <Wert>, "changed": true}`.
- [ ] Ist das Board-Feld bereits nicht-leer (first-write-wins) — gleich ob durch einen früheren `refinement`-Lauf oder eine manuelle Board-Änderung Daniels —, erfolgt **kein** Schreibaufruf; der Rückgabewert ist `{"issue_number": NNN, "priority": <vorhandener Wert>, "changed": false}` (der **vorhandene**, nicht der angefragte Wert).
- [ ] Ein unbekannter `--priority`-Wert wird vor jedem Board-Zugriff mit einem Fehler abgelehnt (kein `gh`-Aufruf).
- [ ] Fehlt das Board-Feld "Priorität" komplett, ist das ein Fehler — es wird nicht automatisch angelegt.
- [ ] Der bisherige Ablauf (nur Chat-Empfehlung, Daniel trägt die Priorität manuell im Board ein) ist durch den neuen automatischen Schritt ersetzt — `.claude/skills/refinement/SKILL.md` Schritt 6 beschreibt nicht mehr "Daniel pflegt die Priorität selbst im Board", sondern den automatischen `set-priority`-Aufruf samt Mitteilung an Daniel, ob neu gesetzt oder wegen eines bereits vorhandenen Werts unverändert geblieben.

## Datenmodell-Bezug

Keine Änderung an PhotoSorts Anwendungsdatenmodell — reines Entwicklungsprozess-Tooling (GitHub-Project-Board-Feld), kein Bezug zu `docs/architecture.md`.

## Architektur / Umsetzung

`architect`-Konsultation, 2026-08-30. Vollständige Begründung in der neuen ADR [`0044`](../decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md) (Accepted). Zusammenfassung:

**Ansatz:** `refinement` setzt die final abgestimmte Prioritäts-Empfehlung am Ende von Schritt 6 automatisch als Board-Startwert — first-write-wins, keine laufende Synchronisation. Die tragenden Ablehnungsgründe von ADR 0039 ("kein Gewinn gegenüber einem Board-Klick", "subtile Semantik") tragen unter der neuen Prämisse ("nachweislich vergessener Handarbeitsschritt", "explizit dokumentierter und getesteter Vertrag") nicht mehr. ADR 0039 bleibt im Übrigen unverändert gültig — insbesondere bleibt das Board die alleinige, von Daniel jederzeit überschreibbare Quelle für Priorität.

**Betroffene Dateien:**

- **`scripts/gh-board.py`:**
  - Neue Konstanten `PRIORITY_FIELD_NAME = "Priorität"`, `PRIORITY_VALUES = ("Hoch", "Mittel", "Niedrig")`.
  - Neue `GhBoard`-Methoden analog zu `status_field()`/`_option_id()`/`get_status()`/`set_status()`:
    - `priority_field()` — löst das Feld über `gh project field-list` auf, legt es **nicht** an (gleiche Nicht-Provisionierung wie beim Statusfeld, ADR 0043 Abschnitt 4). Fehlt das Feld: `BoardError`.
    - `get_priority(issue_number) -> str | None` — liest den aktuellen Wert, leerer String zu `None` normalisiert.
    - `set_priority(issue_number, priority)` — unbedingtes Schreiben (`item-edit` mit `--single-select-option-id`), analog `set_status`.
    - `set_priority_if_unset(issue_number, priority) -> tuple[bool, str]` — liest zuerst `get_priority`; ist bereits gesetzt: No-op, Rückgabe `(False, vorhandener_wert)`; sonst `set_priority` aufrufen, `(True, priority)`. Das ist der first-write-wins-Kern, der sicherstellt, dass eine manuelle Board-Änderung Daniels von keinem späteren `refinement`-Lauf zurückgesetzt wird.
  - Neuer Subbefehl `set-priority --issue NNN --priority Hoch|Mittel|Niedrig`: validiert `priority` gegen `PRIORITY_VALUES` (wie `cmd_set_status`) vor jedem Board-Zugriff, ruft `set_priority_if_unset` auf, gibt `{"issue_number": NNN, "priority": WERT, "changed": true|false}` zurück.
  - Kein Parameter an `set-status` — Status (unbedingt überschrieben) und Priorität (first-write-wins) haben unterschiedliche Schreibsemantik, deshalb bewusst getrennte Befehle.

- **`.claude/skills/refinement/SKILL.md`, Schritt 6:** dritter Board-Aufruf zwischen den bestehenden zwei:
  ```bash
  python3 scripts/gh-board.py set-body --issue <NNN> --body-file <pfad>
  python3 scripts/gh-board.py set-priority --issue <NNN> --priority <Hoch|Mittel|Niedrig>
  python3 scripts/gh-board.py set-status --issue <NNN> --status Ready
  ```
  Status-Übergang auf `Ready` bleibt bewusst der letzte Aufruf — scheitert `set-priority`, bleibt das Issue sichtbar "nicht fertig geschärft". Abschlusszusammenfassung an Daniel nennt zusätzlich, ob die Priorität neu gesetzt wurde oder unverändert blieb (`changed`-Feld auswerten). Der bisherige Satz "diese Empfehlung nennst du Daniel; die Priorität pflegt er selbst direkt im Board" entfällt.

- **`.claude/skills/github-board/SKILL.md`:** neue Zeile in der Befehlstabelle für `set-priority` (Wirkung, Rückgabeform, first-write-wins-Hinweis als Abgrenzung zu `set-status`).

**Umsetzungsreihenfolge (TDD):**
1. `scripts/gh-board.py`: neue `GhBoard`-Methoden (`priority_field`, `get_priority`, `set_priority`, `set_priority_if_unset`) inkl. Unit-Tests.
2. Subbefehl `set-priority` (Parser + `cmd_set_priority` + Validierung) inkl. CLI-Dispatch-Test.
3. `.claude/skills/refinement/SKILL.md` Schritt 6 anpassen.
4. `.claude/skills/github-board/SKILL.md` Befehlstabelle ergänzen.

**Keine Änderung an:** `docs/architecture.md` (reines Entwicklungsprozess-Tooling, kein PhotoSort-System-/Datenmodell betroffen, wie schon bei ADR 0039/0043 begründet).

## UI/UX

`ux-ui-designer` nicht konsultiert (Schritt 2): reines Entwicklungsprozess-Tooling (GitHub-Project-Board-Feld über `scripts/gh-board.py`/`refinement`-Skill) ohne jede sichtbare Oberfläche für die beiden PhotoSort-Endnutzer (Daniel, seine Frau) — nicht relevant.

## Security

`security-engineer` nicht konsultiert (Schritt 3): reines Entwicklungsprozess-Tooling, keine neue externe Eingabe, keine Auth-/Berechtigungs-Änderung, keine Datenmodell-Änderung, keine veränderte Datensichtbarkeit zwischen den beiden PhotoSort-Endnutzern — nicht relevant.

## Teststrategie

`test-engineer`-Konsultation, 2026-08-30. `specs/architecture/0002-testkonzept.md` bereits im Rahmen dieser Konsultation ergänzt (neue Unterektion "Erweiterung für ADR 0044" unter "Externe CLI-Werkzeuge als dünne Adapter-Schicht" — erstes bedingtes/first-write-wins-Schreiben im Package).

**Ebene:** Ausschließlich Unit-Tests in `scripts/tests/test_gh_board.py` gegen den injizierten `run`, kein echter `gh`-Aufruf, kein Integrationstest.

**Neue Tests (Kern):**
- `priority_field()`: löst Feld auf; fehlt "Priorität" im Board → `BoardError`, kein `field-create`-Aufruf.
- `get_priority()`: liest den Klartextwert; leerer Wert → `None`.
- `set_priority()`: unbedingtes Schreiben, exakte Argumentliste (`item-edit --field-id ... --single-select-option-id ...`).
- `set_priority_if_unset()` (Kernstück): Feld leer → schreibt, `(True, priority)`; Feld bereits gesetzt → **kein** `item-edit`-Aufruf, `(False, vorhandener_wert)` — nicht der angefragte Wert (leicht zu übersehendes Detail, da naheliegend wäre, einfach den übergebenen Parameter zurückzugeben).
- `cmd_set_priority()`: unbekannter `--priority`-Wert → `BoardError` vor jedem `gh`-Aufruf (kein `item-list` im Log); fehlende Options-ID für einen sonst gültigen Wert → `BoardError`.
- CLI-Ebene: `set-priority --issue N --priority Hoch` liefert korrektes JSON; ungültiger Wert → JSON-Fehler, Exit-Code 1; Ergänzung in `test_cli_kennt_alle_in_den_skills_dokumentierten_befehle`.

**Edge Cases:**
- Rückgabewert bei No-op ist der vorhandene, nicht der angefragte Wert.
- Validierung des `--priority`-Werts muss vor jedem Board-Lesezugriff passieren.
- Reihenfolge Body → Priorität → Status (SKILL.md-Ablaufdetail, kein pytest-Testfall, Prüfung im `review-tests`-Durchlauf des Umsetzungs-PRs).

## Entscheidungen

- **architect konsultiert (Schritt 1):** konkreter Bezug zu `scripts/gh-board.py`/`refinement`-Skill, zusätzlich Revision einer bestehenden ADR (0039) — kein Skip möglich.
- **Neue ADR 0044:** löst ADR 0039 Abschnitt 2 (inkl. des "Bewusst nicht gewählt"-Absatzes) ab; ADR 0039 bleibt im Übrigen Accepted/gültig. Begründung: der ursprüngliche Ablehnungsgrund ("kein Gewinn gegenüber einem Board-Klick") trifft den tatsächlichen Schmerzpunkt (vergessener Handarbeitsschritt, nicht Klickaufwand) nicht.
- **First-write-wins statt Statuscheck:** technische Entscheidung des `architect` — einfacher als eine "nur beim ersten Ready"-Zustandsprüfung, und beantwortet direkt, warum eine spätere manuelle Änderung stabil bleibt, unabhängig davon, wie oft `refinement` künftig auf demselben Issue läuft.
- **Eigener Befehl `set-priority` statt Parameter an `set-status`:** unterschiedliche Schreibsemantik (unbedingt vs. first-write-wins) rechtfertigt getrennte Befehle.
- **ux-ui-designer nicht konsultiert (Schritt 2):** reines Entwicklungsprozess-Tooling ohne sichtbare Oberfläche.
- **security-engineer nicht konsultiert (Schritt 3):** kein neuer externer Eingabe-/Auth-/Datenmodell-Bezug, keine veränderte Datensichtbarkeit zwischen den beiden Nutzern.
- **`docs/architecture.md` unverändert:** reines Entwicklungsprozess-Tooling, kein PhotoSort-System-/Datenmodell betroffen.

## Offene Fragen

Keine — das Refinement-Gespräch (Issue #257, Status `Ready`) sowie die technischen Konsultationen in dieser Spec haben alle Unklarheiten geklärt.

## Out of Scope

- Eine laufende (nicht mehr first-write-wins-begrenzte) Prioritäts-Synchronisation — bewusst nicht gewählt, da das exakt die von ADR 0039 abgelehnte Dauer-Kopplung wieder einführen würde. Ein späterer Wiedereinstieg bräuchte erneut eine eigene ADR.
- Jede Änderung am Board-Feld "Status" — ausschließlich das Feld "Priorität" ist betroffen.
- Automatisches Anlegen des Board-Felds "Priorität", falls es fehlt — bleibt ein manueller Bootstrap-Vorgang wie beim Statusfeld.
