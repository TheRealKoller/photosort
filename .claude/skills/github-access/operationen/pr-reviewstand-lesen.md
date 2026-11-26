## `pr-reviewstand-lesen` — ist das angeforderte Review da?

**Wege:** `mcp`, `gh`
**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `photosort`
**Auswertungsgrenze:** `reviewRequests`, `reviews` — und nichts sonst. Ausgewertet wird allein,
ob der Copilot-Eintrag aus `reviewRequests` verschwunden bzw. in `reviews` aufgetaucht ist; der
dafür maßgebliche Anmeldename ist das Literal "copilot-pull-request-reviewer" aus diesem
Katalogtext. Review-Freitext wird hier **nicht** gelesen — dafür gibt es
`pr-reviewkommentare-lesen`.
**`mcp`:** das GitHub-MCP-Werkzeug, das den Reviewstand eines Pull Requests liest. Werkzeugname
nicht notiert.
**`gh`:**

```bash
gh pr view <MMM> --repo TheRealKoller/photosort --json reviewRequests,reviews
```
