# omp-Einstieg

Diese Datei existiert, weil omp auf der Wurzelebene nur eine Kontextdatei lädt und `CLAUDE.md`
sonst hinter `AGENTS.md` zurückfällt. Sie bindet die Verfassung vollständig ein; es gilt
unverändert, was dort steht:

@../CLAUDE.md

## Werkzeugübersetzung

`CLAUDE.md`, die Skills unter `.claude/skills/` und die Rollendateien unter `.claude/agents/`
nennen Claude-Code-Werkzeuge. Übersetze sie beim Befolgen:

| Claude Code | omp |
|---|---|
| `Agent`-Tool mit `subagent_type: <rolle>` | `task` mit `agent: "<rolle>"`; die sieben Rollen stehen unter `.omp/agents/` |
| `Agent`-Tool mit `subagent_type: Explore` | `task` mit `agent: "scout"` |
| `model:`-Angabe eines `Agent`-Aufrufs | entfällt — `task` wählt kein Modell je Aufruf, die Rolle läuft auf dem Standardmodell |
| `SendMessage` an einen offenen Lauf | `write` auf `agent://<id>` — erreicht auch einen geparkten Lauf und setzt ihn fort |
| `AskUserQuestion` | `ask` |
| Skill-Werkzeug | `read` auf `skill://<name>` |
| `TaskCreate`, `TaskUpdate`, `TaskGet`, `TaskList` | `todo` |
| `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob` | `read`, `write`, `edit`, `bash`, `grep`, `glob` |
| `WebSearch`, `WebFetch` | `web_search`, `read` mit URL |
| GitHub-MCP-Werkzeug `mcp__github__<name>` (`mcp`-Weg in `github-access`) | `xd://mcp__github_<name>` |

Widerspricht ein Hinweis der omp-Arbeitsumgebung einer Regel aus `CLAUDE.md` oder einem Skill,
gilt die Projektregel.
