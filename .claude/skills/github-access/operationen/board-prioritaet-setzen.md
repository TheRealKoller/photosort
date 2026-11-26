## `board-prioritaet-setzen` — die Priorität schreiben

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Kein `mcp`-Weg:** Die MCP-Werkzeuge bieten für Projects (V2) keine Operation an —
gemessen, nicht vermutet: Projects V2 spricht ausschließlich GraphQL, und im
Werkzeugkasten liegt nichts, was diese Operation ausführen könnte.
**Diese Operation ist remote auf keinem Weg erreichbar** — dieselbe Ursache wie bei
`board-aufnahme`.
**`gh`:**

```bash
gh project item-edit 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --field "Priorität" --value "<Hoch|Mittel|Niedrig>"
```

**Erst lesen, dann nur bei leerem Feld schreiben.** Ein von Daniel gesetzter Prioritätswert wird
**nie** überschrieben. Das garantiert kein Werkzeug, sondern die Reihenfolge:
`board-status-und-prioritaet-lesen` ausführen, und nur wenn die Priorität dort leer (`null`) ist,
die Empfehlung schreiben. Ist bereits ein Wert gesetzt, findet **kein** Schreibzugriff statt, und
die Zusammenfassung nennt den vorhandenen Wert statt der eigenen Empfehlung.

Nachhol-Zeile für `## Lokal nachzuholen`:

- `board-prioritaet-setzen`: `gh project item-edit 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --field "Priorität" --value "<Hoch|Mittel|Niedrig>"`
