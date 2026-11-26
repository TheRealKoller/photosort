## `issue-verwerfen` — Issue ohne Umsetzung schließen

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das ein Issue schließt; der Grund geht als geschlossener,
typisierter Wert. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh issue close <NNN> --repo TheRealKoller/photosort --reason "not planned"
```

Der Grund `not planned` ist **Pflicht**: Er ist die einzige Stelle, an der „verworfen" von
„geliefert" unterscheidbar bleibt — der Board-Wert kennt den Unterschied nicht. Die Karte zieht
danach von selbst nach `Done` (nativer Workflow `Item closed`); es wird kein Statuswert von Hand
gesetzt.
