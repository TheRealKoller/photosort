## `issue-kommentieren` — einen Kommentar an ein Issue schreiben

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das einen Issue-Kommentar anlegt; der Text geht als eigener,
typisierter Parameter. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh issue comment <NNN> --repo TheRealKoller/photosort --body-file <pfad>
```

In den Kommentar gelangt **ausschließlich selbst erzeugter Inhalt** (Regel 4.3). Mehrdeutiger
Fehlschlag: erst lesend verifizieren, nie blind den nächsten Weg gehen.
