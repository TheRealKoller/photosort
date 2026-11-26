## `issue-body-schreiben` — den Issue-Body überschreiben

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Aufrufer:** `refinement` Schritt 6 sowie `story-entwurf` mit **zwei getrennten** Vorgängen (die
fachliche Nachbesserung und das Anheften des Design-Abschnitts). Vor jedem Vorgang steht dort eine
mechanische Selbstprüfung des erzeugten gegen den gelesenen Body.
**`mcp`:** das GitHub-MCP-Werkzeug, das ein Issue ändert; der Body geht als eigener, typisierter
Parameter. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh issue edit <NNN> --repo TheRealKoller/photosort --body-file <pfad>
```

Der Body wird **immer** aus einer zuvor mit dem Schreib-Werkzeug angelegten Datei übergeben, nie
als Zeichenkette in eine Kommandozeile (Regel 4.1).
