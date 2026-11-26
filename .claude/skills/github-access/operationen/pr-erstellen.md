## `pr-erstellen` — Pull Request eröffnen

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das einen Pull Request anlegt (am 2026-09-06 in der
Hauptsession beobachteter Name: `mcp__github__create_pull_request` — Hinweis, keine Vorschrift).
Titel und Body gehen als eigene, typisierte Parameter.
**`gh`:**

```bash
gh pr create --repo TheRealKoller/photosort --base main --title "$(cat <titel-datei>)" --body-file <pfad>
```

Der Body folgt `.github/pull_request_template.md` und enthält die **ausgefüllte** Zeile
`Closes #<NNN>`; nur sie erzeugt die strukturierte Verknüpfung. Das Keyword gehört ausschließlich
in den Body — nie in eine Commit-Nachricht, nie in den PR-Titel.

**Ausnahme: PR ohne Issue-Bezug (reine Doku-/Chore-PRs) — Zeile löschen.** Wortgleich mit der
Vorlage, und ab jetzt auch hier, weil `ship-feature` nicht mehr der einzige Aufrufer ist: Ein
Entwurfsrundenlauf ist jederzeit aufrufbar, auch ohne Story, und `ship-entwurf` eröffnet den Pull
Request dann trotzdem. Der Preis steht dort: Ohne die Zeile wandert die Karte nicht von selbst
auf `Review` — das wird gemeldet, nicht durch ein eigenmächtiges Setzen verdeckt. Ein
**Platzhalter** `Closes #NNN` bleibt in beiden Fällen unzulässig; die Zeile ist ausgefüllt oder
sie fehlt. Die PR-Nummer aus der Antwort
wird wie bei `issue-anlegen` gegen `^[0-9]+$` validiert und ausschließlich als Zahl
weiterverwendet.

Der **Titel** trägt dieselbe Form wie eine Commit-Nachricht — `typ(scope)!: Beschreibung`, Typ
klein geschrieben aus `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`,
`revert`, `test`, Scope und `!` optional, nach dem Doppelpunkt genau ein Leerzeichen und eine
nicht-leere Beschreibung. Grund: Das Repository squasht mit `COMMIT_OR_PR_TITLE`, der Titel wird
damit zum Titel des Merge-Commits auf `main` und ist die einzige Grundlage, auf der die Änderung
für Changelog und Version klassifiziert wird; ohne zulässiges Präfix fällt sie still heraus. Ein
Titel, der die Form verfehlt, lässt den Check pr-titel rot werden — und, sobald pr-titel als
Required Status Check auf `main` eingetragen ist, blockiert er zusätzlich den Merge.

Mehrdeutiger Fehlschlag: erst lesend verifizieren, nie blind den nächsten Weg gehen.
