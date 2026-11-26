## `issue-titel-schreiben` — den Issue-Titel überschreiben

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das ein Issue ändert; der Titel geht als eigener, typisierter
Parameter. Werkzeugname nicht notiert. **Auch dort wird der Titel zuerst als Datei
materialisiert** und an ihr geprüft (Regel 4.4).
**`gh`:**

```bash
gh issue edit <NNN> --repo TheRealKoller/photosort --title "$(cat <titel-datei>)"
```

**Body und Titel bleiben zwei getrennte Operationen.** Beides in einem Aufruf wäre möglich —
bewusst nicht: Der Body wird immer geschrieben, der Titel nur bedingt. Ein kombinierter Aufruf
existierte in zwei Formen, machte die Bedingung zu einem Flag-Detail statt zu einem eigenen
Ablaufschritt, risse den Body mit, wenn nur die Titel-Datei fehlerhaft ist, und ein Fehlschlag
bliebe nicht eindeutig zuordenbar. Bleibt der Titel unverändert, entfällt diese Operation
ersatzlos — es gibt keinen Pfad „unverändert zurückschreiben".
