# 0024 - Review-Agenten und PR-/Copilot-Workflow vom Orchestrator statt vom `developer`-Subagenten ausgeführt

**Status:** Accepted
**Datum:** 2026-08-18
**Bezug:** `specs/inbox/0024-review-agenten-vom-orchestrator-statt-developer-aufrufen.md` (nach Aufnahme in diese ADR und die zugehörige Feature-Spec zu löschen); Feature-Spec `specs/features/0046-...md` wird im Anschluss an diese Architektur-Konsultation angelegt. Markiert **Teile** von ADR [`0014`](./0014-review-agenten-selektion-und-modellzuweisung.md) als Superseded (nicht deren Inhalt insgesamt — siehe Abschnitt "Verhältnis zu ADR 0014" unten; 0014 selbst wird dabei **nicht editiert**, exakt wie bereits bei ADR [`0018`](./0018-idea-sharpener-kalibrierung-und-skip-logik.md) gehandhabt).

## Kontext

Bei der Umsetzung von Spec 0041 und Spec 0042 zeigte sich real: ein per Agent-Tool gestarteter `developer`-Subagent hat zur Laufzeit **weder das Agent-Tool selbst** (keine weitere Verschachtelungsebene an Subagenten) **noch GitHub-MCP-Tools** (GitHub-Zugriff bleibt an die oberste Session/den Orchestrator gebunden) — obwohl `.claude/agents/developer.md` beides voraussetzt (Schritt 4 startet fünf Review-Agenten per Agent-Tool, Schritt 7/8 nutzen `gh`/GitHub-MCP für PR-Erstellung und Copilot-Review). In beiden Fällen musste die Review-Runde stattdessen vom `developer`-Agenten selbst aus den jeweiligen Perspektiven simuliert werden (keine echte Delegation), und PR-Erstellung/Copilot-Review-Anforderung wurden von der obersten Ebene nachgeholt.

Daniels bindende Anweisung dazu (Chat, 2026-08-17): *"Die Reviewagents sollen in Zukunft nicht von Developer Agent sondern von der obersten Ebene aufgerufen werden. Die oberste Ebene ist der orchestrator und der Developer soll nur umsetzten und dann zurückgeben."*

Bereits mit Daniel geklärt, hier bindend:

1. `developer` liefert am Ende (statt Schritt 4 selbst auszuführen) einen strukturierten Abschlussbericht zurück — der Orchestrator nutzt ihn, um die Review-Agenten direkt aufzurufen, statt Diff/Spec-Bezug selbst erst zu ermitteln.
2. Bei Findings-Fixes nach der Review-Runde beauftragt der Orchestrator **denselben** bereits laufenden `developer`-Subagenten erneut (SendMessage an den Subagenten, Kontext bleibt erhalten) statt einen neuen Lauf zu starten.
3. Schritt 7/8 (PR-Erstellung, Copilot-Review-Anforderung) wandern im selben Zug offiziell zum Orchestrator (identischer Grund: kein GitHub-Zugriff im Subagenten).

**Zusätzlich vom `architect` bei dieser Konsultation festgestellt, über den ursprünglichen Auslöser hinaus:** Derselbe Root-Cause (kein verschachteltes Agent-Tool im Subagenten) betrifft strukturell identisch auch `developer.md` Schritt 1 — dort ruft `developer` bislang bei fehlender/unzureichender Umsetzungsplanung live den `architect`-Agenten per Agent-Tool auf. Das kann ein `developer`-Subagent aus demselben Grund wie Schritt 4 nicht mehr selbst. Diese Stelle war im ursprünglichen Auslöser (Inbox 0024) nicht benannt, wird aber in derselben ADR mitgelöst — sie unbehandelt zu lassen würde exakt dieselbe Fehlerklasse an einer zweiten Stelle bestehen lassen.

Diese ADR ist wie 0007/0013/0014/0016/0018 eine reine Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst, keine Änderung an Technologie-Stack, Datenmodell oder externer Abhängigkeit im engeren Sinn — dennoch als ADR festgehalten, weil sie eine dauerhafte, projektweite Regel für jeden künftigen `developer`-Lauf setzt (analog zur Begründung in ADR 0014 selbst).

## Entscheidung

### Teil 1: Betroffene Stellen (Bestandsaufnahme)

| Bisherige Stelle in `developer.md` | Problem | Neue Zuständigkeit |
|---|---|---|
| Schritt 1 (Umsetzungsplanung, `architect` live bei Bedarf) | Agent-Tool im Subagenten nicht verfügbar | Orchestrator, nach "Blockiert"-Rückmeldung von `developer` |
| Schritt 4 (Review, 5 Fachagenten) | Agent-Tool im Subagenten nicht verfügbar | Orchestrator, nach Abschlussbericht von `developer` |
| Schritt 5 (Findings beheben) | — (kein struktureller Bruch) | Bleibt bei `developer`, aber jetzt als Folgeauftrag per SendMessage statt intern verkettet |
| Schritt 7 (Commit/Push/PR) | GitHub-Zugriff im Subagenten nicht verfügbar | Orchestrator |
| Schritt 8 (Copilot-Review) | GitHub-Zugriff im Subagenten nicht verfügbar | Orchestrator |

### Teil 2: Neuer struktureller Ablauf

`developer` führt unverändert Schritt 0 (Vorbereitung inkl. Feature-Branch), Schritt 2 (TDD-Zyklus) und Schritt 3 (Codequalität) selbst aus. Zwei Verhaltensänderungen:

**a) Schritt 1 (Planung):** Reicht der Spec-Abschnitt "Architektur / Umsetzung" nicht (fehlt, zu knapp, Komplikation während der Umsetzung), bricht `developer` **nicht** mehr mit einem eigenen Agent-Tool-Aufruf fort, sondern beendet seinen Turn mit einer kurzen Rückmeldung im festen Format:

```
## Blockiert: Architektur-Konsultation nötig

**Feature-Branch:** <Name>
**Grund:** <konkret, z.B. "Spec-Abschnitt fehlt" / "deckt Komplikation X nicht ab">
**Bisheriger Stand:** <was schon committet ist, falls etwas>
```

Der Orchestrator ruft daraufhin `architect` auf (Standard-Modell, wie bisher), gibt das Ergebnis per SendMessage an denselben, weiterhin offenen `developer`-Subagenten zurück, der bei Schritt 1 fortfährt.

**b) Nach Schritt 3 (statt bisherigem Schritt 4 "Review"):** `developer` führt direkt den bisherigen Schritt 6 ("Abschließender Qualitätscheck") aus — kein Review mehr dazwischen — und beendet seinen Turn mit dem Abschlussbericht (Format siehe Teil 3). Der Subagenten-Kontext bleibt für den Orchestrator ansprechbar (kein neuer Lauf bei Folgeaufträgen), bis PR und ggf. Copilot-Review vollständig abgeschlossen sind.

**c) Folgeauftrag (Findings-Fixes):** Erhält `developer` per SendMessage eine Findings-Liste (aus der Review-Runde des Orchestrators oder aus Copilot), arbeitet er sie über den bisherigen Schritt 5 ab, wiederholt Schritt 6 (Qualitätscheck), committet, und schickt einen reduzierten Folge-Abschlussbericht zurück (Format siehe Teil 3).

### Teil 3: Format der Rückmeldungen (Freitext mit fester Gliederung)

Es gibt keine strukturierte Rückgabe-API — nur Freitext am Ende der Agent-Antwort. Um trotzdem zuverlässig maschinell auffindbar zu sein, sind Überschrift und Feldnamen **wörtlich fest**, nicht nur sinngemäß:

**Erstbericht** (nach Schritt 6, vor jedem Review):

```
## Abschlussbericht

**Spec:** <Nummer> - <Titel> (specs/features/NNNN-....md)
**Feature-Branch:** <exakter Branch-Name>
**Commit-Stand:** sauber, alles committet

### Umsetzung
<Freitext: was gebaut wurde>

### Betroffene Dateien
<Ausgabe von `git diff --name-only main...HEAD` als Liste>

### Tests & Codequalität
<Testlauf/Coverage/Lint/Typecheck-Ergebnis, Status>

### Offene Punkte / eigene Annahmen
<Liste, oder "keine">

### Bereit für Review
Ja
```

**Folgebericht** (nach Findings-Fixes):

```
## Abschlussbericht (Folgeauftrag: Findings behoben)

**Feature-Branch:** <Name, zur Bestätigung>
**Commit-Stand:** sauber, alles committet

### Behobene Findings
<Liste>

### Bewusst nicht behoben
<Liste mit Begründung, oder "keine">

### Tests & Codequalität
<erneut grün>
```

Die exakten Anker (`## Abschlussbericht`, `**Feature-Branch:**`, `## Blockiert: Architektur-Konsultation nötig`) sind bindend, weil der Orchestrator reinen Freitext liest und sich auf stabile Textmuster verlassen muss, statt jede Antwort frei zu interpretieren.

### Teil 4: Neue Komponente — Skill `ship-feature` beim Orchestrator

Damit die neue Orchestrator-Verantwortung nicht nur implizit im Hauptchat "irgendwie" passiert (dasselbe Drift-Risiko, das ADR 0014 für die Review-Trigger-Auswahl bereits ausschließt), wird ein neuer Skill `.claude/skills/ship-feature/SKILL.md` eingeführt — bewusst dasselbe Muster wie `idea-sharpener` (ein Skill, der auf oberster Ebene mehrere Fachagenten koordiniert), nur für die Nachbereitungs- statt die Verfeinerungsphase. Trigger: eine `developer`-Subagenten-Antwort, die `## Blockiert: Architektur-Konsultation nötig` oder `## Abschlussbericht` enthält. Inhalt (bindend, Details bei Implementierung auszuformulieren):

1. Bei "Blockiert": `architect` aufrufen (Standard-Modell), Ergebnis per SendMessage an den `developer`-Subagenten zurückgeben.
2. Bei "Abschlussbericht": Branch-/Diff-Verifikation und Review-Runde durchführen (siehe Teil 5), Findings per SendMessage zurückspielen, nach Bestätigung Schritt 7/8 (PR, Copilot) ausführen (siehe Teil 7).

Kein neues Muster für die Trigger-/Modell-Logik selbst — die referenziert unverändert ADR 0014 Teil 1 (Trigger) und die in Teil 6 dieser ADR aktualisierten Aufrufer-Zeilen aus ADR 0014 Teil 2.

### Teil 5: Wie der Orchestrator Diff/Branch verifiziert

`developer`-Subagent und Orchestrator laufen auf derselben Maschine in derselben Arbeitskopie (kein separater Klon, kein Remote-Zwischenschritt) — der vom Subagenten angelegte Feature-Branch samt Commits existiert im selben Checkout, sobald der Subagent zurückkehrt. Die diff-mechanische Trigger-Auswertung bleibt deshalb einfach ausführbar:

1. `git branch --show-current` gegen den im Bericht genannten Branch-Namen prüfen (Sicherheitsnetz gegen unerwarteten Checkout-Zustand); bei Abweichung `git checkout <gemeldeter-branch>`.
2. `git status` muss sauber sein (`developer` bestätigt das im Bericht, der Orchestrator verifiziert es trotzdem selbst, statt dem Bericht blind zu vertrauen).
3. `git diff --name-only main...HEAD` **selbst erneut ausführen** (nicht nur die im Bericht gelistete Datei-Liste übernehmen) — das ist die verbindliche Quelle für die Trigger-Auswertung, der Bericht dient nur der Nachvollziehbarkeit/Plausibilisierung.
4. Trigger-Tabelle (ADR 0014 Teil 1, Inhalt unverändert) auswerten. Für die einzige nicht-mechanische Bedingung (`architect`-Trigger: Abschnitt "Architektur / Umsetzung" nicht trivial) liest der Orchestrator den Spec-Abschnitt direkt selbst, exakt wie es bisher `developer` tat.

### Teil 6: Aktualisierte "Aufrufer → Ziel-Agent"-Zeilen aus ADR 0014 Teil 2

Modell-Spalte und fachliche Begründung je Zeile bleiben inhaltlich identisch zu ADR 0014 — geändert wird ausschließlich die Aufrufer-Spalte:

| Bisherige Zeile (ADR 0014, weiterhin dort so vermerkt) | Ab dieser ADR maßgebliche Zeile | Modell (unverändert) |
|---|---|---|
| `developer` Schritt 1 → `architect` (Umsetzungsplanung, bei Bedarf) | Orchestrator (nach "Blockiert"-Rückmeldung von `developer`) → `architect` | Standard |
| `developer` Schritt 4 → `test-engineer` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `test-engineer` | Standard |
| `developer` Schritt 4 → `security-engineer` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `security-engineer` | Standard |
| `developer` Schritt 4 → `architect` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `architect` | Standard |
| `developer` Schritt 4 → `requirements-engineer` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `requirements-engineer` | Günstig (Haiku) |
| `developer` Schritt 4 → `ux-ui-designer` (Review, bedingt) | Orchestrator (nach `developer`-Abschlussbericht) → `ux-ui-designer` | Günstig (Haiku) |

Alle übrigen Zeilen aus ADR 0014 Teil 2 (die vier `idea-sharpener`-Zeilen, ohnehin bereits durch ADR 0018 eigenständig kalibriert; "Hauptchat/Orchestrator → `developer`"; die `research-engineer`-Zeile) bleiben unverändert gültig und unberührt.

### Teil 7: Schritt 7/8 (PR, Copilot-Review) beim Orchestrator

Kein struktureller Neuentwurf — die bestehenden Anweisungen aus `developer.md` Schritt 7 (Push, `gh pr create`, Spec-Status `Accepted` → `Implemented`, Roadmap-Sync) und Schritt 8 (Copilot anfordern, warten, Kommentare holen/bewerten/fixen/beantworten) werden inhaltlich unverändert vom Orchestrator statt vom `developer`-Subagenten ausgeführt — er hat GitHub-MCP-Zugriff und dieselbe Arbeitskopie (Begründung wie Teil 5). Fixes aus Copilot-Findings laufen über denselben SendMessage-Mechanismus an den weiterhin offenen `developer`-Subagenten (Fix + Commit dort, Rollentrennung bleibt: `developer` implementiert, Orchestrator hat GitHub-Zugriff), danach pusht der Orchestrator erneut (kein neuer PR).

### Teil 8: Verhältnis zu ADR 0014

ADR 0014 wird **nicht editiert** — exakt dieselbe Handhabung wie bereits bei ADR 0018 (siehe dortiger Abschnitt "Verhältnis zu ADR 0014"): Statt die unveränderliche Datei anzufassen, erklärt diese ADR selbst, welche Teile ab sofort nicht mehr maßgeblich sind. Konkret: Teil 1 von ADR 0014 (Trigger-Tabelle) bleibt **inhaltlich vollständig unverändert** — nur der Ausführungsort wandert vom `developer`-Subagenten zum Orchestrator, keine Zeile der Tabelle selbst ändert sich. Die sechs in Teil 6 dieser ADR gelisteten Zeilen aus ADR 0014 Teil 2 sind für den `developer`-Review-/Planungs-Kontext ab sofort durch diese ADR ersetzt (Superseded, nur die Aufrufer-Spalte dieser sechs Zeilen); alle übrigen Zeilen aus ADR 0014 Teil 2, sowie ADR 0014 Teil 3 in seiner ursprünglichen Formulierung ("`developer` Schritt 8"), gelten historisch weiter, sind aber für die tatsächliche Ausführung durch diese ADR (Teil 7) überholt. Wer nur ADR 0014 liest, sieht weiterhin "`developer` Schritt 4/7/8" als Aufrufer — das ist ein bekannter, bewusst in Kauf genommener Stand der unveränderlichen ADR-Historie (identisches Vorgehen wie 0018), maßgeblich ist ab sofort diese ADR.

## Begründung

- **Root-Cause-Fix statt Symptom-Fix:** Der Fehler ist strukturell (Subagenten können keine weitere Verschachtelungsebene an Subagenten starten, kein GitHub-Zugriff außerhalb der obersten Session) — eine Lösung, die nur Schritt 4 anpasst und Schritt 1 unberührt lässt, würde dieselbe Fehlerklasse an einer zweiten, bereits im Code des Agenten vorhandenen Stelle weiterleben lassen. Deshalb wird Schritt 1 im selben Zug mitgelöst, obwohl es im ursprünglichen Auslöser nicht benannt war.
- **Skill statt loser Prosa-Anweisung im Hauptchat:** Ohne einen dedizierten, im Voraus definierten Ort (Skill), an dem die Orchestrator-Verantwortung (Review-Trigger-Auswertung, SendMessage-Fix-Loop, PR/Copilot) verbindlich beschrieben ist, bestünde dasselbe Drift-Risiko, das ADR 0014 für die Review-Agenten-Auswahl bereits ausschließt: mal wird korrekt reviewt, mal vergisst der Orchestrator einen Schritt, weil es "gerade niemand explizit vorschreibt". `idea-sharpener` ist im Projekt bereits das etablierte, bewährte Muster für "ein Skill koordiniert auf oberster Ebene mehrere Fachagenten" — `ship-feature` überträgt dasselbe Muster auf die Nachbereitungsphase, statt eine neue, unbewährte Mechanik zu erfinden.
- **`developer` bleibt bei den TDD-/Codequalitäts-Schritten unverändert:** Diese Schritte hatten nie das strukturelle Problem (kein Agent-Tool-/GitHub-Bedarf) und funktionieren im Subagenten-Kontext nachweislich. Nur die tatsächlich betroffenen Schritte wandern.
- **Feste Freitext-Anker statt freier Interpretation:** Da es keine strukturierte Rückgabe-API gibt, ist die einzige verlässliche Alternative zu freier Prosa-Interpretation ein bewusst enges, wörtlich festgelegtes Überschriften-/Feldformat — dieselbe Logik, die ADR 0014 bereits für die mechanische (statt freien) Trigger-Auswertung begründet.
- **Keine Änderung an ADR 0014 selbst:** Konsistent mit dem bereits etablierten, tatsächlich praktizierten Vorgehen aus ADR 0018 — eine neue ADR erklärt für sich selbst, was nicht mehr maßgeblich ist, statt die unveränderliche alte Datei anzufassen.

## Konsequenzen

Betroffene Dateien, in sinnvoller Bearbeitungsreihenfolge (Umsetzung erfolgt im Rahmen von Feature-Spec 0046, nicht durch diese ADR selbst):

1. `specs/features/0046-...md` (neu, von `idea-sharpener` angelegt, Status `Accepted`, Abschnitt "Architektur / Umsetzung" mit dem Ergebnis dieser Konsultation).
2. `.claude/skills/ship-feature/SKILL.md` (neu) — muss vor der Umschreibung von `developer.md` existieren, da Letzteres darauf verweist.
3. `.claude/agents/developer.md` — Schritt 4 entfällt vollständig; Schritt 1 bekommt die "Blockiert"-Eskalation statt eines eigenen Agent-Tool-Aufrufs; Schritt 6 (Qualitätscheck) und der neue Abschlussbericht (Teil 3 dieser ADR) folgen direkt auf Schritt 3; Schritt 7/8 entfallen vollständig (wandern in `ship-feature`); Restrukturierung/Umnummerierung der Schritte.
4. `CLAUDE.md` — Konventionen-Bullet ("siehe `developer`-Agent, Schritt 8") aktualisieren: Copilot-Review-Bewertung liegt jetzt beim Orchestrator/Skill `ship-feature`, nicht mehr bei `developer`.
5. `docs/ai-workflow.md`, Abschnitt "Kosteneffiziente Agenten-Nutzung" — Aufrufer-Beschreibung von "`developer`-Review (Schritt 4)" auf "Orchestrator (Skill `ship-feature`, nach `developer`-Abschlussbericht)" aktualisieren, Verweis auf diese ADR zusätzlich zu ADR 0014 ergänzen (analog zum bereits bestehenden Muster für ADR 0018).
6. `.claude/agents/architect.md`, `test-engineer.md`, `security-engineer.md`, `requirements-engineer.md`, `ux-ui-designer.md` — je eigene Beschreibung ("wird automatisch vom `developer`-Agenten aufgerufen" / "läuft im developer-Workflow Schritt 4") auf "wird vom Orchestrator nach Abschluss des `developer`-Agenten aufgerufen (Skill `ship-feature`)" aktualisieren; `architect.md` zusätzlich Punkt (4) der eigenen Beschreibung (Umsetzungsplanung) anpassen, da `developer` nicht mehr selbst konsultiert, sondern der Orchestrator nach einer "Blockiert"-Rückmeldung.
7. `specs/diagrams/workflow-overview.d2`/`.svg` — `review`-Knoten (und ggf. `pr`-Knoten) im `implement`-Subgraph so beschriften, dass die Ausführung beim Orchestrator liegt, nicht bei `developer` selbst; neu rendern via `scripts/render-diagrams.sh`.
8. Kein Effekt auf `docs/architecture.md`/`docs/setup.md` — reine Prozess-/Workflow-Änderung, keine System-/Datenmodell-Änderung.

**Laufende Beobachtung statt einmaliges Gate:** Sollte sich in der Praxis zeigen, dass das feste Freitext-Anker-Format (Teil 3) vom Orchestrator zuverlässig falsch/unvollständig gelesen wird, oder dass der SendMessage-Mechanismus den Subagenten-Kontext entgegen der Annahme nicht zuverlässig erhält, ist das ein Grund für eine neue, diese ADR ablösende ADR (z.B. anderes Übergabeformat), nicht für ein stillschweigendes Abweichen vom festgelegten Format.
