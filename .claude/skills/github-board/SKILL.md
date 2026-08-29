---
name: github-board
description: Führt einzelne Operationen auf dem gemeinsamen GitHub Project (V2) aus — Story-Issue anlegen, Issue-Body schreiben, Board-Status setzen/lesen, eine Feature-Spec finalisieren. Dünner Wrapper um das getestete Script `scripts/gh-board.py`, das die gesamte Projects-V2-Logik bündelt. Nutze diesen Skill, wenn `capture`/`refinement`/`spec-writer`/`developer`/`ship-feature` an ihren jeweiligen Stellen einen Board-Zugriff brauchen, oder wenn Daniel direkt danach fragt ("setz Issue #NNN auf Ready", "welchen Status hat #NNN", "finalisier Spec NNNN").
---

# GitHub Board — einzelne Board-Operationen

Dünner Wrapper um `scripts/gh-board.py`. Der Skill trifft keine fachliche Anforderungsentscheidung — er ruft das Script auf und wertet die Ausgabe aus.

Es wird nichts "synchronisiert": Es gibt keine Zustandsdatei, kein Nummern-Mapping und keinen Content-Push des Spec-Inhalts in den Issue-Body. Die Zuordnung Spec ↔ Issue ist eine Identität — **die Spec-Nummer einer neuen Spec *ist* die Nummer ihres Issues** (`specs/features/0262-*.md` gehört zu Issue #262). Nur die Altspecs `0001`–`0065` folgen dieser Regel nicht; für sie gibt es beim Finalisieren `--issue`.

Klare Aufgabenteilung, die nicht aufgeweicht wird:

- **Issue-Body = Story** (Ziel, User Story, Akzeptanzkriterien) — geschrieben von `refinement`.
- **Spec-Datei = Technik** (Architektur, UI/UX, Security, Teststrategie) — lebt nur im Repo.

## Aufruf

Aus dem Repo-Root heraus, immer genau ein Befehl pro Aufruf:

```bash
python3 scripts/gh-board.py <befehl> [optionen]
```

| Befehl | Wirkung |
|---|---|
| `create-issue --type idee\|bug --title TITEL --body-file PFAD` | Legt ein neues Story-Issue an (Label `idee`/`bug`, ins Board aufgenommen, Status `Unrefined`). Gibt `{"issue_number": NNN}` zurück. |
| `set-body --issue NNN --body-file PFAD` | Überschreibt den Issue-Body. Gibt `{"issue_number": NNN}` zurück. |
| `set-status --issue NNN --status WERT` | Setzt die Board-Spalte. Gibt `{"issue_number": NNN, "status": WERT}` zurück. |
| `show-status --issue NNN` | Rein lesend. Gibt `{"issue_number": NNN, "status": WERT\|null}` zurück. |
| `finalize --spec NNNN [--issue NNN] [--pr-number MMM]` | Schreibt die `**Status:**`-Zeile der Spec-Datei auf `Implemented ([PR #MMM](url))`, setzt die Board-Spalte auf `Done` und schließt das Issue. Gibt `{"spec_number", "issue_number", "pr_number", "status_line", "status"}` zurück. |

Bodies werden **immer** über `--body-file` übergeben, nie als Kommandozeilenargument — Rohtext in eine temporäre Datei schreiben (z.B. unter dem Scratchpad-Verzeichnis).

### Statuswerte

`Unrefined` → `Ready` → `Todo` → `In Progress` → `Review` → `Done`. Wer welchen Wert setzt:

| Wert | Gesetzt von | Zeitpunkt |
|---|---|---|
| `Unrefined` | `capture` | automatisch beim Anlegen |
| `Ready` | `refinement` | Story fachlich geschärft |
| `Todo` | `spec-writer` | Spec angelegt und akzeptiert |
| `In Progress` | `developer` | vor dem Start der Umsetzung |
| `Review` | `ship-feature` | direkt nach `gh pr create` |
| `Done` | `ship-feature` (über `finalize`) bzw. `refinement` | Spec finalisiert bzw. Story verworfen |

`Done` schließt das Issue zusätzlich nativ — sowohl für eine umgesetzte als auch für eine ohne Umsetzung verworfene Story (kein eigener Statuswert für den Unterschied). Alle anderen Werte fassen den Issue-Zustand nicht an; ein Wiedereröffnen passiert nativ auf GitHub.

### `finalize` — Regelweg und Ausnahmepfad

**Regelweg** (Pre-Merge-Finalisierung, `ship-feature` Schritt 8): mit `--pr-number`, während der Feature-PR noch offen ist. Damit ist die Statuszeile Teil des Feature-PRs statt eines Nachzieh-PRs.

**Ausnahmepfad**: ohne `--pr-number`. Das Script sucht dann den gemergten, das Issue schließenden Pull Request selbst. Das deckt den Fall ab, dass ein PR ohne vorherige Finalisierung gemergt wurde (Merge außerhalb des üblichen Ablaufs, abgebrochene Session) — die dabei entstehende lokale Änderung braucht dann ein kleines Folge-PR.

Bedingungen in beiden Fällen: Der Datei-Status der Spec muss `Accepted` sein, und der PR muss `open` (Regelfall) oder `merged` (Nachzug) sein — ein ohne Merge geschlossener PR wird abgelehnt.

`--issue` nur für Altspecs `0001`–`0065` setzen, deren Nummer nicht der Issue-Nummer entspricht (die Issue-Nummer steht in der `**Bezug:**`-Zeile der Spec-Datei). Ohne die Angabe gilt Spec-Nummer = Issue-Nummer.

## Fehler zuerst behandeln

Die Ausgabe ist immer **ein** JSON-Objekt auf stdout. Enthält es den Schlüssel `error` (Exit-Code 1), ist nichts passiert bzw. der Aufruf wurde vor dem Schreibzugriff abgebrochen:

- Verweist die Meldung auf `gh auth refresh -s project` (fehlender `project`-Scope der lokalen `gh`-Session): das **nicht** selbst zu beheben versuchen (erfordert i.d.R. interaktive Browser-Bestätigung) — Daniel den Befehl klar mitteilen und abbrechen.
- Jeder andere Fehler: die Meldung **unverändert** an Daniel weitergeben, keinen eigenen Lösungsversuch unternehmen, der über das Offensichtliche hinausgeht. Insbesondere nicht umgehen, indem eine Spec-Datei oder ein Board-Wert von Hand nachgezogen wird.
- **Nur bei `finalize`:** Das Script schreibt zuerst die Spec-Datei um und setzt danach das Board. Scheitert der Board-Zugriff, bleibt die umgeschriebene Datei als Arbeitskopie-Änderung stehen. Mit `git status` prüfen und die Änderung in dem Fall verwerfen (`git checkout -- specs/features/NNNN-*.md`), bevor es weitergeht — der Aufruf ist wiederholbar, solange der Datei-Status noch `Accepted` ist.

Meldet das Script, dass Projekt oder Statusfeld nicht gefunden wurde, legt es bewusst nichts an: Dann wurden Board-Titel oder Feld-Optionen manuell verändert, und das ist ein einmaliger manueller Reparaturschritt von Daniel, kein automatischer Dauerbetrieb-Pfad.

## Zusammenfassung an Daniel

Kompakte Chat-Antwort, kein separater Report: welcher Befehl mit welchem Ergebnis gelaufen ist, jede Fehlermeldung wörtlich.
