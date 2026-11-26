## `pr-verknuepfung-lesen` — PR↔Issue-Verknüpfung und Basis-Branch prüfen

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Auswertungsgrenze:** `closingIssuesReferences`, `baseRefName` — und nichts sonst. Ausdrücklich
**nicht** ausgewertet werden Titel, Body, Autor und Head-Branch, auch wenn die Antwort sie
mitliefert.
**`mcp`:** das GitHub-MCP-Werkzeug, das einen Pull Request liest. Werkzeugname nicht notiert. Es
liefert das Objekt mit mehr Feldern in einem Aufruf; die Auswertungsgrenze wirkt erst, wenn die
Daten schon da sind, und ersetzt die strukturelle Verengung des `gh`-Wegs **nicht**
gleichwertig. Entlastend, aber nicht freisprechend: Diese Operation läuft im Ablauf
ausschließlich gegen den eigenen, selbst eröffneten Pull Request.
**`gh`:**

```bash
gh pr view <MMM> --repo TheRealKoller/photosort --json closingIssuesReferences,baseRefName
```
