## `board-status-setzen` — den Board-Status schreiben

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Kein `mcp`-Weg:** Die MCP-Werkzeuge bieten für Projects (V2) keine Operation an —
gemessen, nicht vermutet: Projects V2 spricht ausschließlich GraphQL, und im
Werkzeugkasten liegt nichts, was diese Operation ausführen könnte.
**Diese Operation ist remote auf keinem Weg erreichbar** — dieselbe Ursache wie bei
`board-aufnahme`, dieselbe Einordnung: Eigenschaft der Umgebung, keine offene Aufgabe.
**`gh`:**

```bash
gh project item-edit 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --field "Status" --value "<Wert>"
```

`<Wert>` ist einer der fünf Statuswerte aus der Lebenszyklus-Tabelle in `SKILL.md`, als Literal
aus dem Katalogtext. Namensbasiert, **nie** ID-basiert (`--id`/`--field-id`/`--project-id`) —
das verlangte vier Knoten-IDs als Literale in Skill-Dateien. Die Operation ist
zielzustands-idempotent: Sie setzt einen Zustand und führt keinen Übergang aus, ein zweiter
Versuch ist folgenlos.

Nachhol-Zeile für `## Lokal nachzuholen`:

- `board-status-setzen`: `gh project item-edit 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --field "Status" --value "<Wert>"`
