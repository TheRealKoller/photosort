## `copilot-review-anfordern` — Copilot als Reviewer eintragen

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das einen Reviewer anfordert. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh pr edit <MMM> --repo TheRealKoller/photosort --add-reviewer "@copilot"
```

Der Reviewer-Name ist ein Literal aus diesem Katalogtext, nie aus einer Antwort übernommen.

**Ein erschöpftes Copilot-Guthaben meldet sich nicht als Fehler.** Beide Wege nehmen die
Anforderung mit Erfolg an (HTTP `200` bzw. Exit `0`); ein Eintrag erscheint danach aber nicht in
`reviewRequests`, und ein Review kommt nie. **Was gilt:** Nach dem Anfordern wird der Stand über
`pr-reviewstand-lesen` geprüft — fehlt der Copilot-Eintrag dort, gilt das Review als **nicht
angefordert**, nicht als „läuft noch", und bleibt ein Befund an Daniel. **Bei Verletzung:** Der
Ablauf wartet sein Zeitfenster auf ein Review ab, das nie kommt, und meldet am Ende einen offenen
Punkt, der nicht im Ablauf liegt.
