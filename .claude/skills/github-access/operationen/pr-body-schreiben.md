## `pr-body-schreiben` — den PR-Body überschreiben

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das einen Pull Request ändert; der Body geht als eigener,
typisierter Parameter. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh pr edit <MMM> --repo TheRealKoller/photosort --body-file <pfad>
```

Der Body wird immer aus einer Datei übergeben, nie über die Kommandozeile.
