# 0046 - Review-Agenten und PR-/Copilot-Workflow vom Orchestrator statt vom `developer`-Subagenten

**Status:** Implemented ([PR #105](https://github.com/TheRealKoller/photosort/pull/105))
**Erstellt:** 2026-08-18
**Bezug:** [`inbox/0024-review-agenten-vom-orchestrator-statt-developer-aufrufen.md`](../inbox/0024-review-agenten-vom-orchestrator-statt-developer-aufrufen.md) (nach Anlage dieser Spec gelöscht), ADR [`decisions/0024-review-agenten-und-pr-workflow-beim-orchestrator.md`](../decisions/0024-review-agenten-und-pr-workflow-beim-orchestrator.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-18

## Ziel

Bei den Umsetzungen von Spec 0041 und Spec 0042 zeigte sich real: ein per Agent-Tool gestarteter `developer`-Subagent hat zur Laufzeit weder das Agent-Tool selbst (keine weitere Verschachtelungsebene an Subagenten) noch GitHub-MCP-Tools (GitHub-Zugriff bleibt an die oberste Session/den Orchestrator gebunden) — obwohl `.claude/agents/developer.md` beides voraussetzt: Schritt 4 startet bislang fünf Review-Agenten per Agent-Tool, Schritt 7/8 nutzen `gh`/GitHub-MCP für PR-Erstellung und Copilot-Review. In beiden Fällen musste die Review-Runde vom `developer`-Agenten selbst aus den jeweiligen Perspektiven simuliert werden (keine echte Delegation), PR-Erstellung/Copilot-Review-Anforderung wurden von der obersten Ebene nachgeholt.

Diese Spec setzt den in ADR 0024 festgelegten Root-Cause-Fix um: Review-Agenten-Aufrufe sowie PR-Erstellung/Copilot-Review wandern strukturell zum Orchestrator (oberste Ebene/Hauptsession), `developer` liefert stattdessen einen fest formatierten Abschlussbericht zurück und bleibt für Folgeaufträge per `SendMessage` ansprechbar. Reine Prozess-/Konfigurationsänderung am KI-Entwicklungsworkflow selbst — kein PhotoSort-Anwendungscode betroffen.

## User Story

Als Orchestrator (oberste Ebene des KI-gestützten Entwicklungsprozesses) möchte ich Review-Agenten direkt aufrufen und die PR-/Copilot-Review-Schritte selbst ausführen, damit `developer` sich auf TDD-Implementierung beschränkt und die Review-/PR-Schritte tatsächlich als echte Delegation funktionieren, statt bei jedem Lauf erneut improvisiert werden zu müssen.

## Akzeptanzkriterien

**Struktur/Format `.claude/agents/developer.md`:**

- [ ] Schritt 1 (Umsetzungsplanung) endet bei unzureichender Planung/Komplikation nicht mehr mit einem eigenen `Agent`-Tool-Aufruf, sondern mit dem wörtlich festen Anker `## Blockiert: Architektur-Konsultation nötig` und den Feldern `**Feature-Branch:**`, `**Grund:**`, `**Bisheriger Stand:**`. Vor der Meldung committet `developer` etwaigen offenen Zwischenstand.
- [ ] Der bisherige Schritt 4 ("Review") entfällt vollständig aus `developer.md`. Nach Schritt 3 (Codequalität) folgt direkt der bisherige Schritt 6 (Qualitätscheck, umnummeriert), danach endet der Turn mit dem wörtlich festen Anker `## Abschlussbericht` (Felder: `**Spec:**`, `**Feature-Branch:**`, `**Commit-Stand:**`, `### Umsetzung`, `### Betroffene Dateien`, `### Tests & Codequalität`, `### Offene Punkte / eigene Annahmen`, `### Bereit für Review`).
- [ ] Ein reduzierter Folgebericht-Anker `## Abschlussbericht (Folgeauftrag: Findings behoben)` (Felder: `**Feature-Branch:**`, `**Commit-Stand:**`, `### Behobene Findings`, `### Bewusst nicht behoben`, `### Tests & Codequalität`) ist als Antwortformat auf einen `SendMessage`-Folgeauftrag dokumentiert.
- [ ] Die bisherigen Schritte 7 (Commit/Push/PR/Spec-Status/Roadmap-Sync) und 8 (Copilot-Review) entfallen vollständig aus `developer.md`.
- [ ] `developer.md` enthält an keiner Stelle mehr einen eigenen `Agent`-Tool-Aufruf der fünf Review-Agenten oder von `architect` in Schritt 1. Die `tools:`-Frontmatter-Zeile verliert den Eintrag `Agent` (täuschte bisher eine zur Laufzeit nicht nutzbare Fähigkeit vor).

**Neue Komponente `.claude/skills/ship-feature/SKILL.md`:**

- [ ] Existiert und deckt mindestens ab: Trigger (`developer`-Antwort enthält `## Blockiert: …` oder `## Abschlussbericht`); Verzweigung Blockiert → `architect` (Standard-Modell) → `SendMessage` zurück an denselben `developer`-Subagenten; Abschlussbericht → Branch-/Diff-Verifikation (siehe unten) → Review-Trigger-/Modelltabelle (ADR 0014 Teil 1 unverändert + aktualisierte Aufrufer-Zeilen aus ADR 0024 Teil 6) → parallele Review-Agenten-Aufrufe → gesammelte Findings per `SendMessage` an denselben `developer`-Subagenten → nach Bestätigung PR-Erstellung (Spec-Status `Accepted` → `Implemented`, Roadmap-Sync) + Copilot-Review anfordern/warten/holen/bewerten/fixen (`SendMessage`-Loop)/beantworten.
- [ ] Der Orchestrator wartet auf **alle** gestarteten Review-Agenten, bevor gesammelte Findings per `SendMessage` verschickt werden (kein Teil-Fix-Loop pro Einzelagent).
- [ ] Branch-/Diff-Verifikation läuft mechanisch: `git branch --show-current` gegen den im Bericht genannten Branch abgleichen (bei Abweichung `git checkout`); `git status` muss sauber sein; `git diff --name-only main...HEAD` wird vom Orchestrator **selbst erneut ausgeführt** (nicht nur die Datei-Liste aus dem Bericht übernommen) — das ist die verbindliche Quelle für die Trigger-Auswertung.
- [ ] Bei nicht-exaktem Match eines erwarteten Ankers (z.B. Tippfehler/abweichende Formatierung) nimmt der Orchestrator **nicht** stillschweigend "fertig, bereit für Review" an, sondern prüft den Bericht inhaltlich und fragt im Zweifel nach.
- [ ] Für einen fehlschlagenden `SendMessage` (Subagenten-Fenster bereits geschlossen/Timeout) ist ein konkreter Recovery-Schritt dokumentiert: neuer `developer`-Lauf mit explizitem Kontext-Reload (Spec, Branch, offene Findings) statt stillschweigenden Scheiterns oder Verlusts der Findings.

**Folgeänderungen (Konsistenz-/Doku-Sync):**

- [ ] `CLAUDE.md` referenziert für die Copilot-Review-Bewertung nicht mehr "`developer`-Agent, Schritt 8", sondern den Skill `ship-feature`/Orchestrator.
- [ ] `docs/ai-workflow.md`, Abschnitt "Kosteneffiziente Agenten-Nutzung": Aufrufer-Spalte aktualisiert, zusätzlicher Verweis auf ADR 0024 neben ADR 0014 (analog zum bestehenden Muster für ADR 0018).
- [ ] `.claude/agents/{architect,test-engineer,security-engineer,requirements-engineer,ux-ui-designer}.md`: je eigene Beschreibungszeile von "wird automatisch vom `developer`-Agenten aufgerufen" auf "wird vom Orchestrator nach Abschluss des `developer`-Agenten aufgerufen (Skill `ship-feature`)"; `architect.md` zusätzlich der Punkt zur Umsetzungsplanung (Orchestrator ruft nach "Blockiert"-Meldung, nicht `developer` selbst).
- [ ] `specs/diagrams/workflow-overview.d2`/`.svg`: `review`-Knoten (und ggf. `pr`-Knoten) im `implement`-Subgraph korrekt dem Orchestrator zugeordnet, neu gerendert via `scripts/render-diagrams.sh`, Quelle+SVG beide committed.
- [ ] `specs/decisions/0014-review-agenten-selektion-und-modellzuweisung.md` bleibt unverändert (`git diff` auf diese Datei ist leer) — konsistent mit dem in ADR 0024 Teil 8 festgelegten "nicht editieren"-Prinzip (exakt wie bei ADR 0018 gegenüber ADR 0014 gehandhabt).
- [ ] `docs/architecture.md`/`docs/setup.md` bleiben unverändert (reine Prozessänderung ohne System-/Datenmodell-Bezug).

## Datenmodell-Bezug

Keines — reine Prozess-/Konfigurationsänderung an Agenten-Steuerdateien (`.claude/agents/`, `.claude/skills/`, `docs/`), keine Berührung der PhotoSort-Datenbank oder Anwendungscode.

## Architektur / Umsetzung

Siehe [`decisions/0024-review-agenten-und-pr-workflow-beim-orchestrator.md`](../decisions/0024-review-agenten-und-pr-workflow-beim-orchestrator.md) (Accepted) für die vollständige Begründung. Diese Spec setzt die dort getroffenen Entscheidungen um, trifft selbst keine neuen Grundsatzentscheidungen mehr.

Gewählter Ansatz: reine Prozess-/Konfigurationsänderung am `developer`-Ablauf und am Orchestrator-Verhalten, kein Anwendungscode betroffen. Root-Cause: ein per Agent-Tool gestarteter `developer`-Subagent hat weder ein verschachteltes Agent-Tool noch GitHub-MCP-Zugriff — beides setzte der bisherige Ablauf in Schritt 1 (Architektur-Konsultation bei Bedarf), Schritt 4 (Review), Schritt 7 (PR) und Schritt 8 (Copilot-Review) voraus.

**Betroffene/neue Komponenten:**
- `.claude/agents/developer.md`: Schritt 4 entfällt vollständig; Schritt 1 bekommt eine "Blockiert"-Eskalation statt eines eigenen Agent-Tool-Aufrufs; nach Schritt 3 folgt direkt der bisherige Qualitätscheck (alter Schritt 6) und ein fest formatierter `## Abschlussbericht`; Schritt 7/8 entfallen vollständig. `developer` bleibt für den Orchestrator per `SendMessage` ansprechbar (Findings-Fix-Folgeaufträge laufen im selben Subagenten-Kontext, kein neuer Lauf).
- `.claude/skills/ship-feature/SKILL.md` (neu): koordiniert auf Orchestrator-Ebene, ausgelöst durch eine `developer`-Rückmeldung mit `## Blockiert: …` oder `## Abschlussbericht` — Architektur-Eskalation, Review-Trigger-/Modellauswertung (ADR 0014 Teil 1 unverändert, Teil 2 gemäß ADR 0024 Teil 6 aktualisiert), `SendMessage`-Fix-Loop, PR-Erstellung, Copilot-Review-Anforderung/-Auswertung. Bewusst dasselbe Muster wie `idea-sharpener` (ein Skill koordiniert auf oberster Ebene mehrere Fachagenten), auf die Nachbereitungsphase übertragen statt eine neue, unbewährte Mechanik zu erfinden.
- `CLAUDE.md`, `docs/ai-workflow.md`, sowie die Beschreibungen der fünf Fachagenten: Verweise auf "wird vom `developer`-Agenten aufgerufen" werden auf "wird vom Orchestrator (Skill `ship-feature`) nach Abschluss des `developer`-Agenten aufgerufen" aktualisiert.
- `specs/diagrams/workflow-overview.d2`/`.svg`: `review`-/`pr`-Knoten im `implement`-Subgraph so beschriften, dass die Ausführung beim Orchestrator liegt, nicht bei `developer` selbst; neu rendern.

**ADR 0014 bleibt unverändert** (keine Datei-Änderung) — ADR 0024 markiert ausschließlich die Aufrufer-Spalte von sechs Tabellenzeilen (Schritt 1 + fünf Schritt-4-Review-Zeilen) sowie Teil 3 (Copilot) als für diesen Kontext überholt, exakt wie bereits bei ADR 0018 praktiziert; Trigger-Tabelle (Teil 1) und Modell-Zuordnung je Zeile bleiben inhaltlich unangetastet.

**Reihenfolge der Umsetzung:** (1) `.claude/skills/ship-feature/SKILL.md` neu anlegen — muss existieren, bevor `developer.md` darauf verweist; (2) `.claude/agents/developer.md` umschreiben (Schritt 4/7/8 entfernen, Schritt 1 + Abschlussbericht-Format ergänzen); (3) `CLAUDE.md`-Konventionen-Bullet aktualisieren; (4) `docs/ai-workflow.md` Abschnitt "Kosteneffiziente Agenten-Nutzung" ergänzen; (5) die fünf Fachagenten-Beschreibungen synchron aktualisieren; (6) Diagramm neu rendern. Reines Doku-/Konfig-Diff ohne Code-Datei — Copilot-Review entfällt (CLAUDE.md-Ausnahme).

## UI/UX

**Nicht relevant** — reine interne Workflow-/Agenten-Orchestrierungsänderung im KI-Entwicklungsprozess, ohne jede sichtbare Oberfläche, auch nicht mittelbar: keine Berührung mit `frontend/src/`, keinem Backend-Endpunkt, keiner PhotoSort-Datenbank, keiner von Daniel/seiner Frau als Endnutzer wahrgenommenen Ansicht. `ux-ui-designer` strukturell nicht konsultiert (siehe Entscheidungen).

## Security

Sicherheitsrelevant im weiteren Sinn (Berechtigungs-/Vertrauensgrenzen, neuer Übergabemechanismus zwischen Agenten-Instanzen), aber ohne neue Angriffsfläche im Sinne des Bedrohungsmodells aus `specs/architecture/0003-securitykonzept.md`. Von `security-engineer` geprüft (Konsultation im idea-sharpener-Ablauf, 2026-08-18):

1. **Kein neues Privileg:** GitHub-Schreibzugriff (Push, PR-Erstellung, Copilot-Review) lag strukturell schon vorher ausschließlich bei der obersten Session — diese ADR formalisiert nur einen bereits empirisch (Spec 0041/0042) festgestellten faktischen Zustand, dokumentiert ihn korrekt statt wie bisher fälschlich `developer.md` zuzuschreiben. Sogar eine leichte Verbesserung im Sinne von Least Privilege: dokumentierte und tatsächliche Berechtigungsmenge des `developer`-Subagenten fallen künftig nicht mehr auseinander.
2. **Freitext-Übergabe (`## Abschlussbericht`) ist kein Injection-Vektor:** Der Bericht stammt vom `developer`-Subagenten selbst, keiner externen/nicht vertrauenswürdigen Quelle — anders als beim (separat behandelten) GitHub-Project-Sync-Fall. Die eigenständige Re-Verifikation von Branch/Status/Diff durch den Orchestrator (statt den Bericht blind zu übernehmen) ist als Gegenmaßnahme gegen fehlerhafte/unvollständige Berichte ausreichend; verbleibendes Restrisiko ist ein Korrektheits-, kein Sicherheitsrisiko.
3. **Review-Unabhängigkeit bleibt erhalten bzw. verbessert sich:** Agent-Tool-Subagenten erhalten nur den im Aufruf mitgegebenen Kontext, unabhängig vom Aufrufer — keine Kontextvermischung mit der Orchestrator-Sitzung zu erwarten. Da `developer` die Review-Agenten zuvor strukturell nicht aufrufen konnte und die Perspektiven selbst simulieren musste, stellt diese Änderung echte Delegation/Unabhängigkeit erstmals verlässlich her.

Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig — reine Prozess-/Tooling-Änderung ohne Berührung der dort verankerten Assets (Fotos, Secrets, Accounts) oder Angriffsflächen (REST-API, WebDAV-Client, Frontend, Docker-Netzwerk).

## Teststrategie

Reine Prompt-/Steuerlogik-Änderung, kein `pytest`/`vitest`-Bezug — Verifikation folgt dem in `specs/architecture/0002-testkonzept.md` etablierten Muster "Agenten-Steuerungslogik selbst" (neuer Punkt 8, bereits ergänzt), dreistufig:

1. **Statischer Konsistenz-Check** (Teil des `test-engineer`-Reviews zum Umsetzungs-PR): Anker in `developer.md` wortgleich mit ADR 0024 Teil 3 (`## Blockiert: Architektur-Konsultation nötig`, `## Abschlussbericht` etc.); Trigger-/Modelltabelle in `ship-feature/SKILL.md` zeilenweise identisch zu ADR 0014 Teil 1 + ADR 0024 Teil 6.
2. **Kein Wegwerf-Branch-Dry-Run möglich** (anders als bei ADR 0014 selbst): das zu prüfende Verhalten ist die echte Interaktion zweier Agenten-Ebenen, nicht am Diff simulierbar. Der erste reale Feature-Branch nach Rollout dient deshalb zugleich als Verifikationslauf: Anker-Erkennung durch den Orchestrator, echte (nicht simulierte) Review-Agenten-Aufrufe, und vor allem — die am wenigsten erprobte Annahme der ADR — ob `SendMessage` an den weiterhin offenen `developer`-Subagenten tatsächlich Kontext (Branch/Commits/Spec) erhält.
3. **Laufende Beobachtung, kein Schwellenwert-Gate:** jeder Fall von Anker-Fehlerkennung oder `SendMessage`-Fehlschlag ist laut ADR 0024 selbst sofortiger Auslöser für eine neue, ablösende ADR. Kein neues CI-Gate, kein neues Testframework.

**Relevante Edge Cases** (siehe Akzeptanzkriterien für die daraus abgeleiteten Anforderungen):
- Leicht abweichender "Blockiert"-/"Abschlussbericht"-Text (Tippfehler, andere Formatierung) — kein stillschweigendes Fehlinterpretieren als Erfolgssignal.
- `SendMessage` schlägt fehl / Subagenten-Fenster bereits geschlossen (insbesondere bei der Wartezeit bis zum Copilot-Review) — konkreter Recovery-Schritt statt stillschweigenden Scheiterns.
- Divergenz zwischen `developer`-Bericht und dem vom Orchestrator selbst erneut ausgeführten `git diff` — eigener `git diff` ist maßgeblich, Diskrepanz wird sichtbar vermerkt statt kommentarlos verworfen.
- Reihenfolge/Parallelität der Review-Agenten — Orchestrator wartet auf alle, bevor gesammelte Findings per `SendMessage` gehen.
- Vertrauen in "Tests & Codequalität: grün" im Bericht: der Orchestrator führt keinen eigenen Testlauf erneut aus (bewusste Entscheidung, konsistent mit bestehender Rollenteilung — TDD bleibt bei `developer`, Testqualität wird vom `test-engineer`-Review geprüft).

**Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md`, Sektion "Agenten-Steuerungslogik selbst", neuer Punkt 8 — neues Testmuster (Freitext-Anker-Übergabe zwischen zwei Subagenten-Ebenen + `SendMessage`-Kontexterhalt), keine reine Anwendung der bestehenden Punkte 1–7.

## Entscheidungen (2026-08-18, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Auslöser:** Daniels bindende Anweisung im Hauptchat (2026-08-17), festgehalten in der Inbox-Notiz: *"Die Reviewagents sollen in Zukunft nicht von Developer Agent sondern von der obersten Ebene aufgerufen werden. Die oberste Ebene ist der orchestrator und der Developer soll nur umsetzten und dann zurückgeben."* — begründet durch real bei Spec 0041/0042 aufgetretene strukturelle Grenzen (kein verschachteltes Agent-Tool, kein GitHub-Zugriff im `developer`-Subagenten).
- **Übergabeformat (Rückfrage im Sharpening-Gespräch):** `developer` liefert künftig einen strukturierten Abschlussbericht (fest formatierte Freitext-Anker, siehe Architektur/Umsetzung) statt der Orchestrator Diff/Spec-Bezug selbst neu ermitteln müsste.
- **Re-Invocation (Rückfrage im Sharpening-Gespräch):** bei Findings-Fixes beauftragt der Orchestrator denselben bereits laufenden `developer`-Subagenten per `SendMessage` erneut (Kontext bleibt erhalten) statt einen neuen Lauf zu starten.
- **Scope-Erweiterung auf Schritt 7/8 (Rückfrage im Sharpening-Gespräch):** PR-Erstellung und Copilot-Review-Anforderung wandern im selben Zug offiziell zum Orchestrator, da derselbe Grund (kein GitHub-Zugriff im Subagenten) zutrifft und beide Schritte laut Inbox-Notiz bereits zweimal improvisiert von der obersten Ebene übernommen werden mussten.
- **Zusätzlich vom `architect` bei der Architektur-Konsultation identifiziert (über den ursprünglichen Auslöser hinaus):** derselbe Root-Cause betrifft strukturell identisch auch `developer.md` Schritt 1 (Live-Konsultation von `architect` bei fehlender Umsetzungsplanung) — im selben Zug mitgelöst, sonst bliebe dieselbe Fehlerklasse an einer zweiten Stelle bestehen. Technische Detailentscheidung des `architect`-Agenten innerhalb der bereits akzeptierten Richtung, keine Rückfrage nötig.
- **Neuer Skill `ship-feature` statt loser Prosa-Anweisung im Hauptchat:** technische Detailentscheidung des `architect`-Agenten — ohne einen dedizierten, im Voraus definierten Ort für die Orchestrator-Verantwortung bestünde dasselbe Drift-Risiko, das ADR 0014 für die Review-Agenten-Auswahl bereits ausschließt. Überträgt das im Projekt bereits bewährte `idea-sharpener`-Muster (Skill koordiniert oberste Ebene) auf die Nachbereitungsphase.
- **ADR 0014 wird nicht editiert:** technische Detailentscheidung, exakt dasselbe Vorgehen wie bereits bei ADR 0018 gegenüber ADR 0014 praktiziert — eine neue ADR (0024) erklärt selbst, welche Teile ab sofort nicht mehr maßgeblich sind, statt die unveränderliche Datei anzufassen.
- **`ux-ui-designer` nicht konsultiert (Schritt 7):** reine interne Workflow-/Agenten-Orchestrierungsänderung ohne jede sichtbare Oberfläche, auch nicht mittelbar — kein einziges plausibles Gegenbeispiel gefunden (kein Frontend-Bezug, analog zur Einordnung bei Spec 0007/0018/0025/0028/0029/0031/0032).
- **`test-engineer` und `security-engineer` bewusst konsultiert statt geskippt (Schritt 8), obwohl reine Prozessänderung ohne Anwendungscode:** Präzedenzfall Spec 0032/ADR 0018 (fast identische frühere Prozess-Idee, `idea-sharpener`-Kalibrierung) wurde ebenfalls konsultiert, weil sie "mittelbar" die Steuerungslogik der Agenten selbst betraf. Diese Idee geht potenziell weiter, da sie zusätzlich konkret ändert, welche Agenten-Instanz GitHub-Schreibzugriff ausübt, und einen neuen Freitext-Übergabemechanismus zwischen zwei Agenten-Ebenen einführt — beides prüfenswert genug, um "im Zweifel eher konsultieren" anzuwenden statt zu skippen. Ergebnis beider Konsultationen: kein neues Risiko, aber jeweils ein eigener Abschnitt (Teststrategie/Security) statt "nicht relevant".
- **Priorität — Mittel (nach Schärfung bestätigt, `requirements-engineer`-Vorschlag aus Schritt 2 übernommen):** direkter struktureller Nachfolger von Spec 0020/ADR 0014, deren eigene Priorisierung ("Als Nächstes"/Mittel im heutigen dreistufigen System) explizit damit begründet wurde, dass der Auslöser die Entwicklungsgeschwindigkeit an *allen* anderen Roadmap-Einträgen betrifft — dieselbe Begründung trägt hier: die Review-/PR-Schritte aus ADR 0014 funktionieren im `developer`-Subagenten-Kontext strukturell nicht wie dokumentiert und mussten bereits zweimal improvisiert werden. Kein Hoch, da Hoch im Projekt konsistent aktiven, von Daniel/seiner Frau im Alltag der PhotoSort-App selbst bemerkten Problemen vorbehalten ist (z.B. Spec 0016/0017/0021/0027/0030) — diese Idee betrifft ausschließlich den internen KI-Entwicklungsprozess, nicht die ausgelieferte Anwendung. **Kein Konflikt mit bereits Geplantem:** Mittel war vor diesem Eintrag mit Spec 0045 besetzt, beide unabhängig (0045 betrifft die Kategorie-Ableitung der Anwendung, keine technische Überschneidung) — verdrängt nichts.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- Jede Änderung am Inhalt der Trigger-Tabelle (ADR 0014 Teil 1) oder der Modell-Zuordnung je Zeile (ADR 0014 Teil 2) selbst — nur der Ausführungsort wandert.
- Die GitHub-Issue-Freigabe-Policy (`approved-for-agent`, Spec 0007/ADR 0007) und die künftige Hintergrund-Automatisierung — kein technischer Bezug, diese Spec betrifft ausschließlich interaktive Sessions.
- Änderungen an ADR 0014 selbst (Datei bleibt unangetastet, siehe Entscheidungen).
- Automatisierte/programmatische Erkennung der Freitext-Anker (z.B. per Skript/Parser) — bleibt manuelle Orchestrator-Interpretation gemäß fest dokumentiertem Format.
