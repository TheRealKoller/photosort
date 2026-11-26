## `pr-reviewkommentar-beantworten` — in einem bestehenden Inline-Thread antworten

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**`mcp`:** das GitHub-MCP-Werkzeug, das in einem bestehenden Inline-Thread antwortet (am
2026-09-06 in der Hauptsession beobachteter Name:
`mcp__github__add_reply_to_pull_request_comment` — Hinweis, keine Vorschrift). Kommentar-ID und
Text gehen als eigene, typisierte Parameter.
**`gh`:**

```bash
gh api repos/TheRealKoller/photosort/pulls/<MMM>/comments/<KOMMENTAR-ID>/replies --input <pfad>
```

Die Kommentar-ID stammt aus `pr-reviewkommentare-lesen` und wird gegen `^[0-9]+$` validiert. Der
Antworttext wird zuvor mit dem Schreib-Werkzeug in eine Datei geschrieben und als solche
übergeben — nie als Zeichenkette in der Kommandozeile.

**Wie der `mcp`-Weg hierher kam — der Mechanismus, nicht eine Korrektur.** Diese Operation war
bis zum 2026-09-06 als einzige ohne `mcp`-Weg geführt: Es war nicht belegt, dass ein Werkzeug sie
ausführt, und der Katalog hat das ausgewiesen, statt einen Namen zu raten. Am 2026-09-06 scheiterte
der `gh`-Weg in einer Cloud-Session mit `HTTP 403`; in derselben Session lag ein passendes Werkzeug
vor und hat die Antwort geschrieben. Damit war der Weg **belegt** — und genau so war es
vorgesehen: Ein ausgewiesen fehlender Weg scheitert an der richtigen Stelle und sagt dem nächsten
Leser, was zu tun ist, während ein geratener Name leise gescheitert wäre und die Diagnose
verschoben hätte.
