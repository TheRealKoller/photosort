# 0044 - Refinement setzt die Prioritäts-Empfehlung automatisch als Board-Startwert (first-write-wins)

**Status:** Accepted
**Datum:** 2026-08-30
**Bezug:** GitHub-Issue [`#257`](https://github.com/TheRealKoller/photosort/issues/257) ("Refinement soll Priorität direkt im Board setzen", Status `Ready`), `architect`-Konsultation im `spec-writer`-Ablauf für die zugehörige künftige Feature-Spec `specs/features/0257-*.md`. Löst ADR [`decisions/0039-prioritaet-nativ-im-board-roadmap-entfaellt.md`](./0039-prioritaet-nativ-im-board-roadmap-entfaellt.md) Abschnitt 2 (inkl. des zugehörigen "Bewusst nicht gewählt"-Absatzes) ab (siehe Abschnitt "Abgelöste Vorentscheidungen"). ADR 0039 bleibt im Übrigen `Accepted` und gültig. Berührt `scripts/gh-board.py` (ADR [`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md)) und `.claude/skills/refinement/SKILL.md`.

**Nachtrag (2026-09-05):** **Abschnitt 3** (ein eigener Befehl `set-priority` im Werkzeug) ist durch ADR [`0057`](./0057-board-lebenszyklus-nativ-statt-eigenbau.md) abgelöst: `gh-board.py` entfällt, die Priorität setzt `refinement` mit `gh project item-edit … --field "Priorität"`. **Abschnitt 2 (first-write-wins) bleibt als Zusicherung unverändert in Kraft** — ein von Daniel gesetzter Wert wird nie überschrieben —, wird aber nicht mehr vom Werkzeug garantiert, sondern durch die Ablaufreihenfolge in `refinement`: erst lesen, dann nur bei leerem Feld schreiben. Verloren geht allein die Atomarität (ADR 0057, Abschnitt 5.3); folgenlos, weil es genau einen Schreiber gibt. **Die Abschnitte 1 und 4 bleiben unverändert gültig.** Diese ADR bleibt `Accepted`. Reiner Verweis, kein nachträgliches Editieren der ursprünglichen Entscheidung/Begründung unten.

## Kontext

ADR 0039 hat festgelegt, dass die Priorität (`Hoch`/`Mittel`/`Niedrig`) eines Story-Issues ausschließlich und manuell im GitHub-Project-Board gepflegt wird, und explizit eine Variante verworfen, bei der ein neues CLI-Flag (`--priority Hoch|Mittel|Niedrig`) einen Startwert setzt — mit der Begründung, das erzeuge "eine neue, subtile 'danach nie wieder anfassen'-Semantik ... ohne echten Gewinn gegenüber einem Board-Klick".

Seitdem hat sich in der Praxis gezeigt: Der `refinement`-Skill spricht am Ende jedes Laufs eine finale Prioritäts-Empfehlung im Chat aus, die Daniel danach selbst manuell im Board einträgt — ein zusätzlicher, leicht vergessener Handarbeitsschritt, der bei jedem einzelnen Refinement-Lauf anfällt. Genau das ist der in Issue #257 beschriebene Schmerzpunkt: nicht "das Board ist umständlich zu bedienen", sondern "ein separater manueller Schritt nach jedem Lauf wird vergessen".

Die beiden tragenden Gegen-Argumente aus ADR 0039 tragen unter dieser neuen Prämisse nicht mehr:

- **"Kein echter Gewinn gegenüber einem Board-Klick":** Der Board-Klick selbst war nie das Problem — das Vergessen, ihn überhaupt zu tätigen, ist es. Der Gewinn ist nicht weniger Klickaufwand pro Klick, sondern der Wegfall eines eigenen, separaten Arbeitsschritts nach jedem Lauf.
- **"Subtile 'danach nie wieder anfassen'-Semantik":** Diese Semantik wird mit dieser ADR nicht mehr heimlich durch ein Nebenprodukt eines CLI-Flags erzeugt, sondern ist der explizit in Issue #257 geforderte, dokumentierte und getestete Vertrag (Akzeptanzkriterium: eine manuell gesetzte Priorität bleibt stabil, kein späterer Lauf setzt sie zurück). "Subtil" war das Problem in ADR 0039, nicht "danach nie wieder anfassen" an sich.

Die dritte Sorge aus ADR 0039 (zusätzliche Tool-/Test-Oberfläche) bleibt unverändert wahr, ist aber ein normaler Implementierungsaufwand, kein Ablehnungsgrund für sich genommen.

## Entscheidung

### 1. `refinement` setzt die Priorität am Ende von Schritt 6 automatisch — als Startwert, nicht als laufende Synchronisation

Direkt nachdem `refinement` die finale Prioritäts-Empfehlung festgelegt hat (Schritt 6, bisher nur Chat-Ausgabe), ruft der Skill `scripts/gh-board.py set-priority --issue NNN --priority <Hoch|Mittel|Niedrig>` auf — zusätzlich zu (nicht anstelle von) `set-body` und `set-status --status Ready`.

### 2. Das Setzen ist first-write-wins: nur wenn das Board-Feld aktuell leer ist

`gh-board.py` liest den aktuellen Wert des Board-Felds `Priorität` vor jedem Schreibversuch. Ist er bereits gesetzt — gleich ob durch einen früheren `refinement`-Lauf oder durch eine manuelle Board-Änderung Daniels —, wird **nicht** geschrieben; der Aufruf ist ein No-op und meldet den vorhandenen Wert zurück. Ist er leer, wird der übergebene Wert einmalig gesetzt.

Das ist die technische Lösung für das dritte Akzeptanzkriterium der Story (eine spätere manuelle Board-Änderung bleibt stabil, auch wenn `refinement` danach erneut auf demselben Issue liefe, z.B. bei einer Nachschärfung): Die Bedingung ist nicht "läuft `refinement` nur einmal pro Issue", sondern "das Feld ist nach dem ersten Schreiben nie wieder leer" — und ein nie wieder leeres Feld wird von der first-write-wins-Regel nie wieder angefasst, unabhängig davon, wie oft `refinement` künftig auf demselben Issue läuft. Es ist bewusst **keine** laufende Synchronisation (kein Zurückschreiben eines geänderten Empfehlungswerts bei jedem erneuten Lauf) — das wäre exakt die von ADR 0039 abgelehnte Kopplung "Tool verwaltet Priorität dauerhaft".

### 3. Neuer, eigener Befehl `set-priority` statt eines Flags an `set-status`

`scripts/gh-board.py` bekommt einen eigenen Subbefehl `set-priority --issue NNN --priority Hoch|Mittel|Niedrig` (Ergebnis `{"issue_number": NNN, "priority": WERT, "changed": true|false}`), statt die Priorität in `set-status` mit hineinzunehmen. Status und Priorität sind zwei unabhängige Board-Felder mit unterschiedlicher Schreibsemantik (Status wird bei jedem Lifecycle-Übergang unbedingt überschrieben, Priorität nur first-write-wins) — ein gemeinsamer Befehl würde diese beiden Semantiken in einem Parameter vermengen.

Analog zu `status_field()`/`_option_id()`/`get_status()`/`set_status()` bekommt `GhBoard` die Gegenstücke `priority_field()`, `get_priority()`, `set_priority()` sowie eine Verbund-Operation `set_priority_if_unset()`, die Lesen und bedingtes Schreiben kapselt. Das Board-Feld `Priorität` wird dabei nur **aufgelöst, nicht angelegt** — dieselbe bewusste Nicht-Provisionierung wie beim Statusfeld (ADR 0043, Abschnitt 4): Das Feld existiert auf dem produktiven Board bereits; ein fehlendes Feld ist ein klarer, an Daniel zu meldender Fehler, kein automatischer Anlegepfad.

### 4. Reihenfolge der drei Schritt-6-Aufrufe: Body, dann Priorität, dann Status

`set-body` → `set-priority` → `set-status --status Ready`. Der Status-Übergang auf `Ready` bleibt der letzte, sichtbar abschließende Schritt: Scheitert `set-priority` (z.B. fehlendes Board-Feld), bleibt das Issue auf seinem bisherigen Status stehen und signalisiert damit unverändert "noch nicht fertig geschärft", statt fälschlich als `Ready` zu erscheinen, obwohl die Prioritäts-Automatisierung nicht durchgelaufen ist.

## Abgelöste Vorentscheidungen

- **ADR 0039, Abschnitt 2, zweiter Absatz** ("Bewusst nicht gewählt: eine Variante, bei der das Tool über ein neues, rein schreibendes CLI-Flag (`--priority Hoch|Mittel|Niedrig`) einen Startwert setzt") ist hiermit **superseded**: Genau diese Variante wird jetzt bewusst eingeführt, weil sich die tragenden Gegen-Argumente (siehe Kontext) unter der neuen Prämisse — automatisches Setzen ersetzt einen nachweislich vergessenen Handarbeitsschritt, statt einen ohnehin trivialen Board-Klick einzusparen — nicht mehr halten.
- **ADR 0039, Abschnitt 2, erster Absatz** (`github-project-sync` fasst das Feld nie an) ist durch ADR 0043 ohnehin bereits gegenstandslos (das Tool existiert nicht mehr); diese ADR stellt für den Nachfolger `gh-board.py` klar, dass er das Feld jetzt gezielt, aber nur first-write-wins anfasst — keine laufende, sondern eine einmalige Schreiboperation pro Issue.
- **ADR 0039, Abschnitt 1** ("Board ist alleinige Quelle für Priorität, von Daniel dort gepflegt") bleibt inhaltlich gültig: Der Board-Wert bleibt maßgeblich und von Daniel jederzeit überschreibbar; `refinement` liefert lediglich den initialen Wert, damit Daniel nicht bei null anfängt.
- **ADR 0039, Abschnitt 5** (`requirements-engineer` berät nur, pflegt keine Datei) bleibt unverändert — die Empfehlung entsteht weiterhin dort, `refinement` übernimmt sie am Ende nur zusätzlich in einen Board-Schreibaufruf.

## Begründung

- **Der eigentliche Schmerzpunkt ist ein vergessener Schritt, nicht ein umständliches UI:** Ein automatischer Startwert beseitigt genau das, ohne die in ADR 0039 gewollte Eigenschaft "Board ist die Stelle, an der Priorität lebt und gepflegt wird" aufzugeben — er liefert nur den ersten Wert dorthin.
- **First-write-wins statt laufender Sync ist die minimale Kopplung, die die Story verlangt:** Eine laufende Synchronisation (jeder `refinement`-Lauf schreibt den aktuellen Empfehlungswert) würde exakt die 2026-08 abgelehnte Dauer-Kopplung "Tool verwaltet Priorität" wieder einführen und Daniels manuelle Overrides regelmäßig gefährden. First-write-wins tut das nicht: Nach dem ersten Schreiben ist das Tool endgültig raus.
- **Eigener Befehl statt Flag an `set-status`:** hält die Schreibsemantik pro Feld eindeutig (unbedingt vs. first-write-wins) und vermeidet einen Parameter, dessen Wirkung vom übrigen Zustand des Aufrufs abhinge.
- **Keine Selbst-Provisionierung des Feldes:** konsistent mit der in ADR 0043 getroffenen Entscheidung für das Statusfeld — ein Board-Feld anzulegen ist ein einmaliger, manueller Bootstrap-Vorgang, kein Dauerbetrieb-Pfad.

## Konsequenzen

- **`scripts/gh-board.py`:** neuer Subbefehl `set-priority --issue NNN --priority Hoch|Mittel|Niedrig`; neue `GhBoard`-Methoden `priority_field()`, `get_priority()`, `set_priority()`, `set_priority_if_unset()`; neue Konstante `PRIORITY_FIELD_NAME`/`PRIORITY_VALUES`. `scripts/tests/test_gh_board.py` bekommt Tests für: Setzen bei leerem Feld, No-op bei bereits gesetztem Feld (inkl. Rückgabe des vorhandenen statt des angefragten Werts), unbekannter Prioritätswert, fehlendes Board-Feld (kein Anlegeversuch).
- **`.claude/skills/refinement/SKILL.md`, Schritt 6:** dritter Board-Aufruf (`set-priority`) zwischen `set-body` und `set-status`; die Abschlusszusammenfassung an Daniel nennt zusätzlich, ob die Priorität neu gesetzt oder wegen eines bereits vorhandenen Werts unverändert gelassen wurde.
- **`.claude/skills/github-board/SKILL.md`:** neue Zeile in der Befehlstabelle für `set-priority`, kurzer Hinweis auf die first-write-wins-Semantik (Unterschied zu `set-status`, das immer unbedingt überschreibt).
- **`docs/architecture.md`:** keine Aktualisierung nötig — wie schon bei ADR 0039/0043 handelt es sich um Prozess-/Entwicklungswerkzeug für den KI-Workflow selbst, nicht um PhotoSorts System- oder Datenmodell.
- Ein späterer Wiedereinstieg in eine laufende (nicht mehr first-write-wins-begrenzte) Prioritäts-Synchronisation bleibt architekturrelevant und braucht wiederum eine eigene, diese ADR als "Superseded" markierende ADR.
