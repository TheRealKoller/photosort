## `board-aufnahme` — ein Issue ins Projekt aufnehmen

**Wege:** `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Kein `mcp`-Weg:** Die MCP-Werkzeuge bieten für Projects (V2) keine Operation an —
gemessen, nicht vermutet: Projects V2 spricht ausschließlich GraphQL, und im
Werkzeugkasten liegt nichts, was diese Operation ausführen könnte.
**Diese Operation ist remote auf keinem Weg erreichbar** — Eigenschaft der Umgebung, keine offene
Aufgabe: Projects (V2) spricht ausschließlich GraphQL, die Zwischenschicht einer Cloud-Session
bedient GraphQL nur für einen fest verdrahteten Satz von PR-Operationen, eine REST-Entsprechung
existiert nicht, und die MCP-Werkzeuge bieten für Projects V2 keine Operation an.
**`gh`:**

```bash
gh project item-add 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --format json --jq '.id'
```

Die Issue-URL wird aus der validierten Nummer **gebildet**, nie aus einer Ausgabe übernommen. Das
Anlegen und die Aufnahme sind bewusst **zwei** Operationen: Das Issue soll überleben, wenn die
Aufnahme scheitert. Der Statuswert `Unrefined` wird hier **nicht** gesetzt — er entsteht durch
den nativen Workflow `Item added to project`.

Nachhol-Zeile für `## Lokal nachzuholen`:

- `board-aufnahme`: `gh project item-add 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --format json --jq '.id'`
