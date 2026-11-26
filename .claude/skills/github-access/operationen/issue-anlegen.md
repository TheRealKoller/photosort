## `issue-anlegen` — ein Story-Issue anlegen

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das ein Issue anlegt. Titel, Body und Label gehen als eigene,
typisierte Parameter. Meldet das Issue einen Defekt, trägt die Label-Liste genau den einen Wert
`bug`; sonst wird sie **nicht** übergeben — auch nicht leer. Werkzeugname nicht notiert.
**`gh`:**

```bash
gh issue create --repo TheRealKoller/photosort --title "$(cat <titel-datei>)" --body-file <body-datei> <label-schalter>
```

**Ein Typ-Label wird genau dann vergeben, wenn das Issue einen Defekt meldet**, und dann genau
`bug`: `<label-schalter>` ist in diesem einen Fall `--label bug` und in jedem anderen **leer** —
der Schalter entfällt ersatzlos, kein leeres Labelfeld (ADR
[`0101`](../../../../specs/decisions/0101-ein-label-traegt-eine-unterscheidung.md)). **Ausgeführt
wird je Anlegevorgang genau eine Befehlszeile**; eine zweite legte ein zweites, nicht
zurücknehmbares Issue an.

Die Antwort liefert die **Nummer** des neuen Issues — auf dem `gh`-Weg aus der ausgegebenen URL
geparst, auf dem `mcp`-Weg aus dem strukturierten Zahlenfeld gelesen. Sie wird in **beiden**
Fällen gegen `^[0-9]+$` validiert und danach ausschließlich als Zahl weiterverwendet; die
Issue-URL wird aus der geprüften Zahl **gebildet**, nie übernommen (Regel 4.2, einzige Ausnahme).

Mehrdeutiger Fehlschlag: erst lesend verifizieren, nie blind den nächsten Weg gehen (Wegleiter,
Regel 4).
