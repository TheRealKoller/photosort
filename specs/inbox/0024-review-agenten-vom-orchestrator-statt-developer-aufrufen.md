# 0024 - Review-Agenten vom Orchestrator statt vom developer-Agenten aufrufen

**Typ:** Idee
**Erfasst:** 2026-08-17
**Status:** Unrefined

## Rohtext

Review-Agenten sollen künftig nicht mehr vom developer-Agenten selbst aufgerufen werden, sondern von der obersten Ebene (Orchestrator/Hauptsession). Der developer-Agent soll nur noch umsetzen (TDD, Codequalität) und dann zurückgeben, statt in Schritt 4 selbst die Review-Agenten (test-engineer, requirements-engineer, security-engineer, architect, ux-ui-designer) per Agent-Tool zu starten.

Hintergrund/Auslöser: Bei den Umsetzungen von Spec 0042 und Spec 0041 hat sich gezeigt, dass ein per Agent-Tool gestarteter developer-Subagent zur Laufzeit weder das Agent-Tool selbst noch GitHub-MCP-Tools zur Verfügung hat, obwohl developer.md beides in seiner tools:-Liste nennt (Agent) bzw. der Workflow es voraussetzt (gh/GitHub für PR-Erstellung und Copilot-Review). Grund: ein Subagent kann offenbar keine weitere Verschachtelungsebene an Subagenten starten, und GitHub-Zugriff bleibt an die oberste Session gebunden. In beiden Fällen musste die Review-Runde stattdessen vom developer-Agenten selbst aus den jeweiligen Perspektiven durchgeführt werden (statt echter Delegation), und die PR-Erstellung sowie Copilot-Review-Anforderung wurden von der obersten Ebene nachgeholt.

Daniels Anweisung dazu (Chat, 2026-08-17): "Die Reviewagents sollen in Zukunft nicht von Developer Agent sondern von der obersten Ebene aufgerufen werden. Die oberste Ebene ist der orchestrator und der Developer soll nur umsetzten und dann zurückgeben."

Betroffen wären voraussichtlich: `.claude/agents/developer.md` (Schritt 4 "Review" müsste aus dem developer-Ablauf heraus und in die oberste Ebene wandern, developer gibt stattdessen einen strukturierten Bericht zurück), `CLAUDE.md` (Verweis auf "developer-Agent, Schritt 8" für Copilot-Review-Findings), ADR 0014 (Trigger-/Modelltabelle für die Review-Agenten-Auswahl bleibt inhaltlich vermutlich gleich, wandert aber in die Zuständigkeit des Orchestrators). Offen für die spätere Schärfung: wie gibt developer die für die Review-Runde nötigen Infos (Diff-Umfang, Spec-Bezug) strukturiert an den Orchestrator zurück; ruft der Orchestrator developer nach Findings-Fixes erneut auf (SendMessage an denselben Subagenten) oder startet er einen neuen Lauf; betrifft das auch Schritt 7/8 (PR-Erstellung, Copilot-Review), die im aktuellen Workflow ebenfalls beim developer-Agenten liegen, aber aus demselben Grund (kein GitHub-Zugriff im Subagenten) bereits zweimal von der obersten Ebene übernommen werden mussten.
