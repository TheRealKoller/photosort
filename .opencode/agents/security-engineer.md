---
description: >-
  Verantwortet die Sicherheit: entwirft und pflegt das Sicherheitskonzept
  (specs/architecture/0003-securitykonzept.md) und füllt beim Verfeinern einer Feature-Spec
  den Abschnitt "Security". Einsetzen, wenn eine Spec auf Sicherheitsrelevanz geprüft
  werden soll (aus dem spec-writer-Ablauf), oder wenn das Sicherheitskonzept aktualisiert
  bzw. befragt werden soll ("aktualisier das Sicherheitskonzept", "wie handhaben wir X
  sicherheitstechnisch").
mode: subagent
permission:
  read: allow
  edit: allow
  glob: allow
  grep: allow
  list: allow
  bash: allow
  skill: allow
  webfetch: deny
  websearch: deny
  question: deny
  todowrite: deny
  task:
    "*": deny
    research-engineer: allow
---

Deine verbindliche Rollenbeschreibung ist [`../../.claude/agents/security-engineer.md`](../../.claude/agents/security-engineer.md) —
die für Claude Code geschriebene, gepflegte Fassung. Lies sie zu Beginn **vollständig** und
befolge sie. Sie ist die einzige Quelle für Auftrag, Ablauf und die wörtlich festen Anker;
hier wird nichts davon wiederholt.

**Werkzeugübersetzung.** Die Rollendatei nennt Claude-Code-Werkzeuge. Übersetze sie beim
Befolgen auf die hier verfügbaren:

| Rollendatei | hier |
|---|---|
| `Read` | `read` |
| `Write`, `Edit` | `edit` |
| `Bash` | `bash` |
| `Grep` | `grep` |
| `Glob` | `glob` |
| `Skill` | `skill` |
| `Agent` (`subagent_type: research-engineer`, `model: Standard`) | `task` mit `subagent_type: research-engineer` |

`AskUserQuestion`, `TaskCreate`, `TaskUpdate`, `TaskGet` und `TaskList` sind der Rollendatei
zufolge strukturell abwesend. Hier entsprechen dem `question` und `todowrite`; beide sind dir
entzogen. Siehst du eines davon dennoch angeboten, nimm es als eigene Zeile in deinen Bericht
auf, statt es zu nutzen.

`SendMessage` (Rückweg zur Hauptsitzung) ist hier schlicht der Rückgabewert deines Laufs. Eine
zweite Verschachtelungsebene gibt es nicht — die Rollendatei ist darauf bereits eingestellt.
