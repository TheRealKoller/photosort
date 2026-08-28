# 0040 - KI-Workflow Schritte 2–8 konsolidiert: Review als Hauptsession-Skills, eine Quelle der Wahrheit

**Status:** Accepted
**Datum:** 2026-08-28
**Bezug:** GitHub-Issue [`#177`](https://github.com/TheRealKoller/photosort/issues/177) ("AI-Workflow Schritte 2–8 konsolidieren"), `architect`-Konsultation im `spec-writer`-Ablauf für die daraus hervorgehende Feature-Spec (Nummer zum Zeitpunkt dieser ADR noch nicht vergeben, voraussichtlich `0064`). Abhängigkeit #224 / ADR [`0039`](./0039-prioritaet-nativ-im-board-roadmap-entfaellt.md) ist umgesetzt.

**Drei bewusst offen gelassene Design-Forks aus #177 — entschieden von Daniel am 2026-08-28:**
1. **Review-Ausführung:** **mehrere Skills, einer je Perspektive** (Test/Bugs/Konventionen, Anforderungstreue/Scope, Security, Architektur, UI/UX), koordiniert durch einen dünnen `review`-Orchestrator-Skill — *nicht* ein einziger gemeinsamer Review-Skill, *nicht* die bisherigen parallelen Subagenten.
2. **`developer`-Ausführung:** bleibt isolierter Subagent, die Freitext-Anker-Übergabe wird entfragilisiert (nicht abgeschafft) — wie vom `architect` empfohlen.
3. **Ablöse-Umfang:** ADR 0024 vollständig, ADR 0014 und 0037 teilweise; ADR 0016/0018/0036/0038 unberührt — wie vom `architect` empfohlen.

## Kontext

Der KI-Implementierungs-Workflow von der akzeptierten Story bis zum Merge (Schritte 2–8: `spec-writer` → Implementierung → Review → PR → Copilot → Merge) ist in drei Wochen über sieben aufeinander aufbauende ADRs (0014, 0016, 0018, 0024, 0036, 0037, 0038) und rund neun Feature-Specs gewachsen. Inhaltlich kohärent, aber:

- **Zu teuer.** Ein einzelner Feature-Lauf verbraucht viele Subagenten-Aufrufe. Für die zuletzt umgesetzte Story #230 (reine Doku-/Skill-Änderung) waren es rund ein Dutzend: `spec-writer` mit drei Fachagenten-Konsultationen, `developer`, bis zu fünf parallele Review-Agenten, `developer`-Folgeauftrag, Finalisierungs-Sync. Diese Kosten fallen bei **jedem** Feature an, unabhängig von seiner Größe.
- **Zu unübersichtlich.** Um den Ist-Zustand zu verstehen, muss man alle sieben ADRs lesen (jede löst Teile der vorigen ab). Drei Stellen stechen als "wirr" heraus:
  1. die parallele Review-Runde mit bis zu fünf Subagenten nach jedem `developer`-Lauf, plus Findings-Rückspielung und Folgeberichte;
  2. das Hin und Her zwischen `developer`-Subagent und Orchestrator über wörtliche Freitext-Anker (`## Abschlussbericht`, `## Blockiert: …`);
  3. die Grenze zwischen "läuft als Subagent" und "läuft in der Hauptsession" bzw. "ist ein Agent" vs. "ist ein Skill" ist nicht auf einen Blick erkennbar.

**Ziel:** ein an **einer** Stelle (`docs/ai-workflow.md`) dokumentierter, spürbar günstigerer Workflow für die Schritte 2–8 bei mindestens gleicher Umsetzungsqualität. Kein Neuentwurf von Grund auf — die bereits getroffenen **Sach-Entscheidungen** (welche Review-Perspektive bei welcher Änderung nötig ist, welches Modell, TDD-Pflicht, Board-Status-Punkte) bleiben inhaltlich gültig; geändert wird, *wie* und *wo* sie ausgeführt und *an welcher Stelle* sie dokumentiert werden.

**In Scope:** Schritte 2–8 (`spec-writer` → Merge).
**Out of Scope, unverändert:** Schritt 1 (`refinement` / fachliche Schärfung, ADR 0036/0038, Specs 0059/0060/0062); die Sach-Entscheidungen selbst; `research-engineer` als Rolle und seine Tool-Isolation (ADR 0016); `capture`.

Diese ADR ist wie 0007/0013/0014/0016/0018/0024/0036/0037/0038/0039 eine reine **Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst** — kein Effekt auf PhotoSort-Anwendungscode, Datenmodell oder Systemarchitektur, deshalb kein Effekt auf `docs/architecture.md` (verifiziert: `docs/architecture.md` beschreibt ausschließlich System­kontext, Komponenten, Datenmodell und bewusste Annahmen der Anwendung, nichts zum Entwicklungsprozess).

## Entscheidung

### Teil 1: Der Ziel-Workflow Schritte 2–8 als eine Tabelle

`docs/ai-workflow.md` wird die **einzige Stelle für den Gesamtüberblick**. Kern ist eine Tabelle mit einer Zeile pro Schritt — Auslöser, Zuständigkeit, Ausführungsort, Modell, Bedingung:

| # | Schritt | Auslöser | Zuständigkeit | Subagent / Hauptsession | Modell | Bedingung |
|---|---|---|---|---|---|---|
| 2 | Spec schreiben | Story-Issue Status `Ready`, Umsetzungswunsch | Skill `spec-writer` | Hauptsession (koordiniert Konsultations-Subagenten) | Standard; Konsultationen nach ADR 0018 Teil 1 / 0038 | immer, wenn eine `Ready`-Story umgesetzt werden soll |
| 3 | Board-Status `In Progress` | direkt vor `developer`-Start | Skill `ship-feature` (bzw. Aufrufer von `developer`) | Hauptsession (GitHub-Zugriff) | — | immer; Fehler nicht blockierend |
| 4 | Implementieren (TDD) | Feature-Spec `Accepted` | Agent `developer` | **Subagent** (Kontext-Isolation) | Standard, nie herabgestuft | immer; TDD-Pflicht nur bei Code, reine Doku ohne |
| 5 | Review | `developer`-Abschluss (`## Abschlussbericht`) | Orchestrator-Skill `review` → ruft die zutreffenden Perspektiven-Skills `review-tests` / `review-requirements` / `review-security` / `review-architecture` / `review-ux` nacheinander auf | **Hauptsession** | Hauptsession-Modell (Standard) | Perspektiven je nach Diff — Trigger-Tabelle Teil 2 |
| 5b | Findings beheben | Review-Findings vorhanden | Agent `developer` (Folgeauftrag per SendMessage) | **Subagent** (derselbe, offen gehaltene Lauf) | Standard | nur wenn Must-Fix-Findings vorliegen |
| 6 | PR erstellen + Board-Status `Review` | Review abgeschlossen / Findings behoben | Skill `ship-feature` | Hauptsession (GitHub-Zugriff) | — | immer |
| 7 | Copilot-Review | direkt nach `gh pr create` | Skill `ship-feature` | Hauptsession | — | nur wenn der Diff mind. eine Code-Datei enthält |
| 8 | Freigabe + Merge | Copilot ausgewertet, CI grün | Daniel gibt frei, Orchestrator merged | Hauptsession | — | Daniel-Freigabe ist Pflicht-Gate |

Zwischenschritt-Rückfrage "Architektur-Konsultation nötig" (`developer` kommt mit dem Spec-Abschnitt "Architektur / Umsetzung" nicht aus): seltener Sonderpfad, siehe Teil 3.

### Teil 2: Review als fünf Perspektiven-Skills + ein dünner `review`-Orchestrator-Skill (ersetzt die 5 parallelen Review-Subagenten)

Die bisher nach jedem `developer`-Lauf parallel gestarteten fünf Review-Subagenten (`test-engineer`, `requirements-engineer`, `security-engineer`, `architect`, `ux-ui-designer`) werden durch **fünf getrennte Hauptsession-Skills** ersetzt, je einen pro Perspektive, koordiniert durch einen **dünnen Orchestrator-Skill**:

| Skill | Perspektive | Konzept-Dokument |
|---|---|---|
| `.claude/skills/review/SKILL.md` | **Orchestrator** — Trigger erkennen, Branch/Diff verifizieren, Trigger-Tabelle auswerten, die zutreffenden Perspektiven-Skills nacheinander aufrufen, Findings konsolidieren, zurückgeben | — |
| `.claude/skills/review-tests/SKILL.md` | Akzeptanzkriterien-Abdeckung, Testqualität, klassische Bugs/Logikfehler, Code-Konventionen (ersetzt das generische Code-Review) | `specs/architecture/0002-testkonzept.md` |
| `.claude/skills/review-requirements/SKILL.md` | Anforderungstreue: alle Akzeptanzkriterien umgesetzt, kein Scope Creep, nichts als "Out of Scope" Ausgeschlossenes gebaut | — |
| `.claude/skills/review-security/SKILL.md` | OWASP-relevante Muster, Secrets, Eingabevalidierung, Auth-Durchsetzung, Abgleich mit dem Sicherheitskonzept | `specs/architecture/0003-securitykonzept.md` |
| `.claude/skills/review-architecture/SKILL.md` | Einhaltung der Architekturentscheidungen (ADRs, `docs/architecture.md`, Spec-Abschnitt "Architektur / Umsetzung"), bewertet aus drei Blickwinkeln (Pragmatiker / Senior-Entwickler / Pedant) | ADRs / `docs/architecture.md` |
| `.claude/skills/review-ux/SKILL.md` | Design-System-Konsistenz, Usability, abgedeckte Zustände (leer/ladend/Fehler), Barrierefreiheit, Responsivität | `specs/architecture/0004-design-system.md` |

**Warum fünf Skills statt einem gemeinsamen (Fork-1-Entscheidung Daniels):** jede Perspektive bleibt eigenständig lesbar, eigenständig testbar (synthetische Dry-Run-Szenarien je Perspektive) und eigenständig pflegbar — analog dazu, dass die fünf Fachagenten heute je eine eigene Datei sind. Der Orchestrator-Skill bleibt dünn (Verifikation + Tabelle + sequenzieller Aufruf + Konsolidierung), damit `ship-feature` nicht mit Review-Logik überladen wird und der Review-Ablauf auch ad hoc (Daniel prüft einen beliebigen Branch) aufrufbar ist.

**Was gleich bleibt (Sach-Entscheidung, inhaltlich unverändert aus ADR 0014 Teil 1):** welche Perspektive bei welchem Diff greift. Die Trigger-Tabelle lebt im `review`-Orchestrator-Skill (mit dieser ADR als Quelle der Wahrheit für den Sync — ein Sync-Paar statt heute `ship-feature` ↔ ADR 0014):

| Perspektive | Verhalten | Trigger (greift, wenn mindestens einer zutrifft) |
|---|---|---|
| Test / Bugs / Konventionen | fast immer | greift immer, **außer** der Diff enthält ausschließlich Nicht-Code-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) und keine Datei unter `backend/src`, `backend/tests`, `frontend/src`, `frontend/tests` |
| Anforderungstreue / Scope | immer | kein Skip-Pfad |
| Security | echt bedingt | Datei unter `backend/src/photosort/api/`, `.../opencloud/`; oder eine der Dateien `main.py`, `security.py`, `rate_limit.py`, `config.py`, `seed.py` unter `backend/src/photosort/`; oder neue Datei direkt unter `backend/src/photosort/`; oder Dependency-Datei (`backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json`); oder `.env.example`; oder `.github/workflows/**`; oder Docker-Compose-Netzwerkkonfiguration; oder `frontend/src/auth/**` bzw. `frontend/src/api/client.ts` |
| Architektur (drei Blickwinkel: Pragmatiker / Senior / Pedant) | echt bedingt | neue Datei / neues Modul; oder `specs/decisions/**`; oder `backend/alembic/**`; oder neue externe Abhängigkeit; oder der Spec-Abschnitt "Architektur / Umsetzung" ist nicht trivial |
| UI/UX | bedingt | Diff enthält Dateien unter `frontend/` |

Sicherheitsnetz unverändert: **im Zweifel läuft die Perspektive.** Eine unklare Zuordnung ist nie ein Grund, eine Perspektive auszulassen. Nicht mechanisch aus `git diff --name-only` ableitbar ist allein der Architektur-Trigger "Abschnitt nicht trivial" — dafür liest der `review`-Orchestrator den Spec-Abschnitt selbst.

**Modell — die Haiku-Zuweisung entfällt (bestätigt, kein Qualitätsverlust):** Die bisher je Review-Aufruf feste Modellzuweisung (ADR 0014 Teil 2: Haiku für `requirements-engineer`- und `ux-ui-designer`-Review, Standard sonst) entfällt. Die Perspektiven-Skills laufen im **Hauptsession-Modell (Standard)** — eine Perspektive wird nicht mehr als eigener, modell-wählbarer Subagent gestartet, es gibt also keine Aufrufstelle mehr, an der ein `model`-Parameter gesetzt werden könnte. Das ist **kein** Qualitätsverlust im Sinne des Akzeptanzkriteriums: die beiden auf Haiku gestellten Perspektiven (Anforderungstreue, UI/UX) waren genau deshalb auf die günstigere Stufe gestellt, weil sie am stärksten checklistenartig gegen bereits fixierte Kriterien (Akzeptanzkriterien-Liste, Design-System-Tokens) prüfen — sie jetzt im stärkeren Hauptsession-Modell zu prüfen, ist eher ein Qualitätsgewinn. Die Kostenersparnis dieser ADR kommt vollständig aus dem Wegfall der fünf Subagenten-Kaltstarts, nicht aus einer Modellstufe.

**Qualitätssicherung gegen "in der Hauptsession geprüft ist oberflächlicher":** jeder `review-*`-Skill ist präskriptiv genug, dass die Tiefe nicht abfällt — ein fester Prüfkatalog, verpflichtende gezielte Konsultation des jeweiligen Konzept-Dokuments, die drei Blickwinkel bei `review-architecture`, und ein einheitliches Ausgabeformat, das Must-Fix von Diskussion trennt. Zusätzlich greift die laufende Beobachtung (Teil 7).

**Kostenabschätzung (mit Annahmen, keine Scheinpräzision):**
- **Token — heute:** ein Review-Subagenten-Kaltstart kostet grob 30–70k Token (CLAUDE.md + `specs/README.md` + Konzept-Dokument-Auszug + Diff + Spec + Reasoning + Bericht). Fünf davon ≈ 200–350k Token pro Feature, jedes Feature.
- **Token — neu:** die fünf Perspektiven-Skills laufen im Hauptsession-Kontext, der CLAUDE.md, Spec und Diff bereits geladen hat (keine Kaltstarts). Jeder Skill fügt seine Skill-Anweisung + Konzept-Dokument-Auszug + Reasoning + Findings hinzu ≈ 15–40k Token, dazu der dünne Orchestrator. Fünf Perspektiven ≈ 90–210k Token, die sich im Hauptfenster akkumulieren; bei einem Doku-Diff mit nur zwei zutreffenden Perspektiven entsprechend ~40–90k.
- **Netto Token:** rund **40–55 % Reduktion der Review-Phase** — weniger als ein einziger gemeinsamer Skill gebracht hätte (dort ~60–75 %), weil fünf getrennte Skill-Anweisungen geladen werden und jeder Skill sein Konzept-Dokument separat konsultiert. Der dominierende Hebel (Wegfall von 5× vollständigem Agenten-Kaltstart) bleibt erhalten.
- **Laufzeit/Latenz:** **schlechter** als heute — fünf sequenzielle Durchläufe in der Hauptsession statt einer parallelen Subagenten-Runde. Für ein Solo-Projekt ohne Latenz-SLA bewusst akzeptiert.
- **Kontext-Akkumulation:** die Findings aller Perspektiven sammeln sich im Hauptfenster und werden in die PR-/Copilot-Phase mitgetragen. Bei einem großen Feature mit allen fünf Perspektiven wächst das Hauptfenster stärker als mit isolierten Subagenten — begrenzt (Findings sind kompakt), aber ein beobachteter Auslöser (Teil 7).
- **Gesamt-Feature-Lauf:** von ~8–12 auf ~3–6 Subagenten-Aufrufe (`spec-writer` + bis zu 3 Konsultationen unverändert + `developer` + ggf. `developer`-Folgeauftrag; Review = 0 Subagenten).

### Teil 3: `developer` bleibt Subagent, Übergabe entschärft

**`developer` bleibt ein isolierter Subagent.** Belastbarer Grund gegen die Hauptsession-Variante: der TDD-Zyklus liest dutzende Dateien, führt Testläufe vielfach aus und iteriert über viele Rot-Grün-Refactor-Runden — in der Hauptsession würde das ihren Kontext sprengen und für Review/PR/Copilot als Ballast liegen bleiben. Die Isolation ist hier deutlich mehr wert als bei den Review-Perspektiven (kurze, urteilsdichte Prüfpässe auf gemeinsamem Input). `developer` wird zudem nie modell-herabgestuft (ADR 0014 Begründung, unverändert).

**Die Freitext-Anker-Übergabe wird nicht abgeschafft, aber entfragilisiert:**
1. **Ein Ort statt drei.** Anker und Feldnamen (`## Abschlussbericht`, `## Abschlussbericht (Folgeauftrag: Findings behoben)`, `## Blockiert: Architektur-Konsultation nötig`, `**Feature-Branch:**` …) sind ab dieser ADR **ausschließlich** in `.claude/agents/developer.md` definiert. `ship-feature`/`review` verweisen funktional darauf ("Format siehe `developer.md`"), tragen keine zweite Kopie mehr (ADR 0024 hatte eine Kopie in `ship-feature` zur "unmittelbaren Ausführbarkeit" — der Verweis genügt, die Datei muss zur Erkennung ohnehin gelesen werden).
2. **Direkter Rückgabewert, kein Log-Scannen.** Der Abschlussbericht ist der **direkte Rückgabewert** des `Agent`-Tool-Aufrufs an die Hauptsession — nicht ein String, der aus einem fortlaufenden Chatverlauf herausgefischt werden muss. Das war schon unter ADR 0024 so, wurde dort aber missverständlich als "Orchestrator liest reinen Freitext" beschrieben. Der Anker klassifiziert nur einen von drei Ausgängen (fertig / blockiert / Folgeauftrag fertig).
3. **Toleranter Abgleich als Sicherheitsnetz** bleibt: kein exakter Anker-Match, aber erkennbar gemeinter Abschluss → per `SendMessage` beim Subagenten rückfragen statt raten (unverändert aus `ship-feature`).
4. **Der "Blockiert"-Sonderpfad ist selten.** Die Architektur-/Umsetzungsplanung entsteht regulär in `spec-writer` Schritt 1 (`architect`-Konsultation) und steht im Spec-Abschnitt "Architektur / Umsetzung". Der Rückfrage-Pfad greift nur, wenn dieser Abschnitt fehlt (ältere Spec) oder eine während der Umsetzung auftretende Komplikation nicht abdeckt. Dann: `developer` beendet den Turn mit dem `## Blockiert`-Anker, `ship-feature` ruft `architect` als Subagent (Standard-Modell, Planung ist echtes Entwurfsurteil, Isolation sinnvoll), gibt das Ergebnis per `SendMessage` an den offenen `developer`-Lauf zurück.

### Teil 4: Rollen-Landkarte — warum Agent oder Skill, wo ausgeführt

Für jede Rolle im Workflow Schritte 2–8 begründet festgehalten (nicht mehr implizit):

| Rolle | Agent oder Skill | Ausführungsort | Modell | Begründung |
|---|---|---|---|---|
| `spec-writer` | Skill | Hauptsession | Standard | koordiniert Konsultationen + legt Spec-Datei an; kein isolierter, langlaufender Arbeitsauftrag, sondern Orchestrierung mit GitHub-Zugriff (Issue adoptieren). Out of Scope, unverändert. |
| `architect` / `test-engineer` / `security-engineer` / `ux-ui-designer` / `requirements-engineer` — **Konsultation** in `spec-writer` | Agent | Subagent | nach ADR 0018 Teil 1 / 0038 (Haiku für ux/requirements, Standard sonst) | echtes fachliches Vorab-Urteil auf einem großen Konzept-Dokument, Kontext-Isolation sinnvoll. Rolle bleibt, unverändert. |
| `developer` | Agent | **Subagent** | Standard, nie herabgestuft | lange, sehr kontextintensive TDD-Umsetzung; Isolation schützt den Hauptkontext (Teil 3). |
| Review — Koordination | **Skill `review`** (Orchestrator) | **Hauptsession** | Hauptsession-Modell | dünn: Trigger erkennen, Branch/Diff verifizieren, Trigger-Tabelle auswerten, Perspektiven-Skills nacheinander aufrufen, Findings konsolidieren. Eigenständig (auch ad hoc) aufrufbar; hält `ship-feature` schlank. |
| Review — 5 Perspektiven | **Skills `review-tests` / `review-requirements` / `review-security` / `review-architecture` / `review-ux`** | **Hauptsession** | Hauptsession-Modell | ein Kontext-Setup statt fünf Subagenten-Kaltstarts (Teil 2). Je Perspektive eigenständig lesbar/testbar/pflegbar. Die Review-Methodik je Perspektive (inkl. der drei Architektur-Blickwinkel) wandert aus den Agenten-Dateien in den jeweiligen `review-*`-Skill. |
| `architect` — **Umsetzungsplanung** bei "Blockiert" | Agent | Subagent | Standard | seltener Sonderpfad, echtes Entwurfsurteil, Isolation sinnvoll (Teil 3 Punkt 4). |
| `ship-feature` | Skill | Hauptsession | Standard | Nachbereitungs-Orchestrierung: Board-Status, `review` aufrufen, Findings-Loop per SendMessage an `developer`, PR, Copilot. GitHub-Schreibzugriff gibt es nur hier. |
| `research-engineer` | Agent | Subagent | Standard | unverändert (ADR 0016); Tool-Isolation (kein `Bash`/`Write`/`Edit`/`Agent`) bleibt unangetastet. |

Die fünf Fachagenten behalten damit zwei bzw. drei Rollen — **entzogen wird nur die Feature-Branch-Review-Rolle** (die Prüf-Methodik wandert in den jeweiligen `review-*`-Skill). Konzept-Dokument-Pflege, `spec-writer`-Konsultation und (nur `architect`) Umsetzungsplanung bleiben in den Agenten-Dateien. In jeder der fünf Agenten-Dateien wird die bisherige Review-Aufgabe durch einen kurzen Verweis ersetzt ("Die Feature-Branch-Review-Perspektive ist als Skill `review-<x>` ausgelagert und läuft in der Hauptsession"), damit die Datei weiterhin vollständig beschreibt, was der Agent tut und was nicht.

### Teil 5: Board-Status-Schreibpunkte (übernommen aus ADR 0037 §3/§4)

Inhaltlich unverändert, hier als Teil des Gesamtbilds festgehalten:
- **`In Progress`:** vom Aufrufer/`ship-feature` unmittelbar vor dem `developer`-Start (`--runtime-status "In Progress"`), nicht von `developer` selbst (kein GitHub-Schreibzugriff im Subagenten). Fehler nicht blockierend.
- **`Review`:** in `ship-feature` direkt nach `gh pr create` (`--runtime-status "Review" --pr-number <N>`).
- **`Done` / Datei-Status `Implemented`:** unverändert über die automatische PR-Merge-Erkennung im regulären `github-project-sync`-Lauf (ADR 0037 §5, `finalized_from_pr`) — **nicht** von dieser ADR berührt.

Die zugrundeliegende Sync-Infrastruktur (`STATUS_OPTIONS`, `runtime_status`/`pr_number` im `SyncStateEntry`, `_sync_one()`-Merge-Erkennung, Story-Status-Migration — ADR 0037 §1, §2, §5) bleibt **vollständig gültig** und wird von dieser ADR nicht abgelöst.

### Teil 6: Qualitäts-Gates bleiben vollständig erhalten

Kein Gate wird abgeschwächt:
- TDD strikt bei Code (reine Doku ohne), Coverage-Gate Backend ≥ 80 % (`--cov-fail-under=80`), CI grün vor Merge — unverändert (`CLAUDE.md`).
- Bedarfsgerechte Abdeckung der fünf Review-Perspektiven — jetzt über den `review`-Skill statt fünf Subagenten, Trigger-Tabelle inhaltlich identisch (Teil 2).
- Copilot-Review nur bei Code-Diff, sonst entfällt Schritt 7 vollständig — unverändert (ADR 0014 Teil 3).
- Daniel-Freigabe vor Merge — unverändert.
- Board-Status `In Progress` / `Review` / `Done` — unverändert (Teil 5).

### Teil 7: Laufende Qualitätsbeobachtung nachgezogen

Die Sektion "Agenten-Steuerungslogik selbst" im Testkonzept (`specs/architecture/0002-testkonzept.md`) wird vom `test-engineer` im Rahmen der `spec-writer`-Teststrategie-Konsultation für die Umsetzungs-Spec **nachgezogen, nicht abgeschwächt**:
- Punkt 1 (statischer Konsistenz-Check): Trigger-Tabelle jetzt `review`-Orchestrator-Skill ↔ **dieser ADR** (statt `developer.md`/`ship-feature` ↔ ADR 0014); Anker jetzt `developer.md` ↔ **dieser ADR** (statt ↔ ADR 0024); zusätzlich je `review-*`-Skill der Abgleich, dass die dorthin verschobene Prüf-Methodik der bisherigen Review-Aufgabe der jeweiligen Agenten-Datei entspricht.
- Punkt 3 (laufende Stichproben-Audits): der `review`-Orchestrator protokolliert je Perspektive "gelaufen / geskippt (welcher Trigger nicht zutraf)". Bei jedem Folge-PR prüft der `review`-Durchlauf des nächsten Features stichprobenartig, ob das im vorigen protokollierte Skip-/Perspektiven-Set zum realen Diff passte.
- Punkt 4 (Haiku-Qualitätsbeobachtung): entfällt in der bisherigen Form (keine Haiku-Review-Stufe mehr, Teil 2). Ersetzt durch: ein von einem `review-*`-Skill als erfüllt/konform bewertetes Kriterium, das sich im selben PR-Zyklus (Copilot, Folge-Bugfix) als nicht erfüllt herausstellt → einzelner belastbarer Fall genügt als Auslöser für eine neue, diese ADR ablösende ADR (z.B. Rückkehr zu einem isolierten Review-Subagenten für die betroffene Perspektive, oder Zusammenlegung/Umschnitt der Skills). Kein Schwellenwert. Zusätzlich beobachtet: übermäßiges Anwachsen des Hauptfensters durch die fünf sequenziellen Perspektiven-Durchläufe bei großen Features (Teil 2, Kontext-Akkumulation).
- Punkt 8 (Freitext-Anker-Übergabe): bleibt, angepasst auf "ein Ort" (Teil 3) und diese ADR als Referenz.

### Teil 8: Rollout als einmaliger Schritt

Die Umstellung betrifft ausschließlich LLM-interpretierte Markdown-Anweisungen (`.claude/skills/**`, `.claude/agents/**`, `docs/`), keinen ausführbaren Code, kein CI-Gate. Rollout:
1. Der Umsetzungs-PR ändert alle betroffenen Dateien (Liste unter Konsequenzen) in einem Zug.
2. **Kein Feature darf beim Merge dieses PRs mitten in der Umsetzung stehen.** In einem Solo-Projekt läuft zu jedem Zeitpunkt höchstens ein `developer`-Subagent. Praktische Regel: der #177-PR wird nicht gemergt, solange ein `developer`-Lauf oder ein offener Feature-PR eines anderen Features aktiv ist — der laufende Vorgang wird zuerst unter dem alten Ablauf (`ship-feature` mit fünf Review-Subagenten) zu Ende geführt.
3. Als Übergangs-Sicherheitsnetz erkennt der neue `ship-feature`-Skill die bisherigen Anker unverändert (sie ändern sich nicht) — ein bereits vor dem Merge gestarteter `developer`-Lauf, der nach dem Merge zurückkehrt, wird korrekt aufgenommen.
4. Der erste Feature-Branch nach Rollout dient zugleich als Verifikationslauf (Testkonzept Punkt 8): erkennt die Hauptsession den Abschlussbericht zuverlässig, wertet der `review`-Orchestrator die Trigger-Tabelle korrekt aus und ruft die zutreffenden `review-*`-Skills der Reihe nach auf, erhält `SendMessage` den `developer`-Kontext.

### Teil 9: Abgelöste Vorentscheidungen

Keine der abgelösten ADRs wird editiert (unveränderlich nach Annahme, `specs/README.md`) — exakt wie ADR 0018/0024/0038 es gehandhabt haben. Diese ADR erklärt für sich selbst, welcher Abschnitt welcher Vorentscheidung ab Annahme nicht mehr maßgeblich ist:

| Vorentscheidung | Abschnitt | Status ab dieser ADR | Ersetzt durch |
|---|---|---|---|
| ADR 0014 | Teil 1 (Review-Trigger-Tabelle) | **Superseded** — Inhalt unverändert übernommen | Teil 2 dieser ADR (Tabelle lebt im `review`-Orchestrator-Skill, ausgeführt in der Hauptsession statt `developer.md` Schritt 4 / `ship-feature`) |
| ADR 0014 | Teil 2, Zeilen zu `developer` Schritt 4 → Review-Agenten (`test-engineer`, `security-engineer`, `architect`, `requirements-engineer`, `ux-ui-designer`) | **Superseded** | Teil 2 dieser ADR — Review läuft in fünf Hauptsession-Skills im Hauptsession-Modell, keine Pro-Perspektive-Modellzuweisung mehr |
| ADR 0014 | Teil 2, Zeile `Hauptchat/Orchestrator → developer` | **Superseded** (nur Verweis-Aktualisierung) | Teil 4 dieser ADR (`developer` bleibt Subagent, Standard, nie herabgestuft) — inhaltlich identisch |
| ADR 0014 | Teil 2, Zeilen zu `idea-sharpener`-Konsultationen und `research-engineer` | **unverändert gültig** | — (schon durch ADR 0018 Teil 1 / 0038 bzw. 0016 geregelt, außerhalb des Scopes) |
| ADR 0014 | Teil 3 (bedingtes Copilot-Review) | **Superseded** — Inhalt unverändert übernommen | Teil 1 (Schritt 7) + Teil 6 dieser ADR |
| ADR 0024 | gesamt (Review/PR/Copilot beim Orchestrator, `ship-feature`-Skill, Freitext-Anker, SendMessage-Fix-Loop, Blockiert-Pfad) | **vollständig Superseded** | Teil 1–4 dieser ADR — `ship-feature` bleibt (schlank), Review wandert in den `review`-Orchestrator + fünf `review-*`-Skills, Anker-Definition an einem Ort |
| ADR 0037 | §3 (`In Progress`-Schreibpunkt), §4 (`Review`-Schreibpunkt in `ship-feature` Schritt 7) | **Superseded** — Inhalt unverändert übernommen | Teil 5 dieser ADR |
| ADR 0037 | §1 (`STATUS_OPTIONS`), §2 (`runtime_status`/`pr_number`-Modell), §5 (PR-Merge-Erkennung in `_sync_one()`), Story-Status-Migration | **unverändert gültig** | — (Sync-Tooling-Infrastruktur, nicht berührt) |
| ADR 0018 | Teil 2 (Skip-Schwelle) | war bereits durch ADR 0038 abgelöst | — (kein erneuter Eingriff) |
| ADR 0018 | Teil 1 (Modellzuweisung Konsultationen), ADR 0038, ADR 0036, ADR 0016 | **unverändert gültig** | — (Schritt 1 / Konsultations-Rolle / research-engineer, außerhalb des Scopes) |

Wer nur eine der abgelösten ADRs liest, sieht weiterhin den alten Ausführungsort — das ist der bewusst in Kauf genommene Stand der unveränderlichen ADR-Historie (identisches Vorgehen wie ADR 0018/0024/0038). Maßgeblich ist ab Annahme diese ADR, für Außenstehende gebündelt in `docs/ai-workflow.md`.

## Begründung

- **Hauptsession-Skills statt Subagenten für Review:** Fünf Subagenten zahlen fünfmal den Kaltstart-Aufwand (CLAUDE.md, `specs/README.md`, Konzept-Dokument, Diff, Spec neu laden) für eine Prüfung, die sich denselben Ausgangskontext teilt. Der `developer`-Lauf davor ist isoliert — die Hauptsession hat zum Review-Zeitpunkt nur den Abschlussbericht und die Spec, ist also schlank genug, den Diff und die Prüfpässe aufzunehmen. Die "fünf frische Blicke" sind bei einem LLM ohnehin teilweise illusorisch; entscheidend ist ein präskriptiver Prüfkatalog je Perspektive, und der lässt sich in einem Skill genauso festhalten wie in einer Agenten-Datei.
- **Fünf getrennte `review-*`-Skills + dünner Orchestrator statt eines gemeinsamen Skills (Daniels Fork-1-Entscheidung):** Ein einziger großer Review-Skill hätte etwas mehr Token gespart (eine Skill-Anweisung, ein Konzept-Dokument-Kontext), aber jede Perspektive wäre nur noch als Abschnitt in einer langen Datei lesbar und nicht mehr einzeln testbar/pflegbar. Fünf Skills spiegeln die bereits bewährte Struktur "ein Fachgebiet, eine Datei" der fünf Fachagenten. Der dünne `review`-Orchestrator hält die Koordinationslogik (Verifikation, Trigger-Tabelle, sequenzieller Aufruf, Konsolidierung) an einer Stelle, damit `ship-feature` schlank bleibt und der Review-Ablauf auch losgelöst vom `ship-feature`-Kontext (Ad-hoc-Prüfung eines Branches) aufrufbar und dokumentierbar ist.
- **`developer` bleibt isoliert, Review nicht:** Der Unterschied ist die Kontext-Last. Eine TDD-Umsetzung liest und schreibt über eine lange Iteration hinweg dutzende Dateien und Testläufe — das gehört nicht in den Hauptkontext. Ein Review-Pass ist kurz und urteilsdicht. Die Isolationsgrenze folgt also der tatsächlichen Kontext-Last, nicht einer pauschalen "Subagenten sind besser"-Regel.
- **Anker beibehalten statt neu erfinden:** Die Fragilität der Übergabe war zu 80 % ein Dokumentations-Problem (drei Dateien, sieben ADRs), nicht ein Mechanismus-Problem — der Abschlussbericht ist der direkte Rückgabewert des Subagenten-Aufrufs. Eine neue strukturierte Übergabe-API gibt es nicht; ein Statusdatei-Mechanismus wäre zusätzliche Maschinerie für ein Problem, das Konsolidierung auf einen Ort weitgehend löst.
- **Eine konsolidierende ADR mit "Sach-Entscheidung bleibt":** Die Trigger-Bedingungen, Modellstufen, die Copilot-Bedingung und die Board-Punkte sind bewusst inhaltlich wortgetreu übernommen — nur die Schichtung über sieben ADRs wird aufgelöst. Eine künftige Änderung am Workflow braucht dann eine Ablöse-ADR über *einen* Vorgänger, nicht über sechs.
- **Minimaler Blast-Radius bei der Ablösung:** ADR 0018 Teil 1, 0038, 0036, 0016 und die Sync-Infrastruktur aus 0037 bleiben unangetastet. Die `spec-writer`-Konsultations-Kalibrierung wurde gerade erst (ADR 0038, #230) getroffen — sie erneut aufzumachen wäre teurer als der Gewinn an Bündelung. `docs/ai-workflow.md` ist der Gesamtüberblick, nicht die einzige Detailregel-Quelle: für die Konsultations-Skip-Logik verweist es auf ADR 0038.

## Konsequenzen

Betroffene Dateien in sinnvoller Bearbeitungsreihenfolge (Umsetzung im Rahmen der Feature-Spec, nicht durch diese ADR):

1. **`specs/features/00NN-...md`** (neu, von `spec-writer` angelegt, Status `Accepted`, Abschnitt "Architektur / Umsetzung" mit dem Ergebnis dieser Konsultation).
2. **`.claude/skills/review-tests/SKILL.md`, `review-requirements/SKILL.md`, `review-security/SKILL.md`, `review-architecture/SKILL.md`, `review-ux/SKILL.md`** (neu) — je Perspektive ein Skill: fester Prüfkatalog, verpflichtende gezielte Konsultation des jeweiligen Konzept-Dokuments, bei `review-architecture` die drei Blickwinkel (Pragmatiker / Senior / Pedant), einheitliches Ausgabeformat (Findings mit Must-Fix vs. Diskussion). Die Prüf-Methodik wird 1:1 aus der bisherigen Review-Aufgabe der jeweiligen Agenten-Datei übernommen.
3. **`.claude/skills/review/SKILL.md`** (neu, Orchestrator) — muss nach den fünf Perspektiven-Skills und vor der Umschreibung von `ship-feature.md` existieren. Enthält: Trigger erkennen (`## Abschlussbericht` als Auslöser); Branch-/Diff-Verifikation (`git branch --show-current`, `git status`, `git diff --name-only main...HEAD` selbst ausführen); die Trigger-Tabelle aus Teil 2 (mit dieser ADR als Sync-Quelle, inkl. Lesen des Spec-Abschnitts "Architektur / Umsetzung" für den nicht-mechanischen Architektur-Trigger); die zutreffenden `review-*`-Skills nacheinander aufrufen; Findings konsolidieren; je Perspektive "gelaufen / geskippt (welcher Trigger)" protokollieren; konsolidierte Findings zurückgeben.
4. **`.claude/skills/ship-feature/SKILL.md`** — umgeschrieben auf die Rolle "Nachbereitungs-Orchestrierung": Board-Status `In Progress`/`Review`; ruft den `review`-Orchestrator-Skill auf (statt fünf Subagenten in Schritt 4); Findings-Loop per `SendMessage` an den offenen `developer`-Subagenten; PR-Erstellung; Copilot-Review. Die kopierte Trigger-/Modelltabelle entfällt (Verweis auf `review/SKILL.md`). "Blockiert"-Pfad (architect-Subagent) bleibt.
5. **`.claude/agents/developer.md`** — Anker-Definition wird die einzige im Repo (Verweise aus `ship-feature`/`review` darauf); Verweis ADR 0024 → diese ADR; Schritt 1 "Blockiert"-Beschreibung unverändert im Mechanismus.
6. **`.claude/agents/architect.md`, `test-engineer.md`, `security-engineer.md`, `requirements-engineer.md`, `ux-ui-designer.md`** — die Feature-Branch-Review-Rolle (je eigene Aufgabe) wird auf einen kurzen Verweis reduziert ("Die Feature-Branch-Review-Perspektive ist als Skill `review-<x>` ausgelagert und läuft in der Hauptsession"); die eigentliche Prüf-Methodik wandert in den jeweiligen `review-*`-Skill (Schritt 2). Die übrigen Rollen (Konzept-Pflege, `spec-writer`-Konsultation, nur `architect` zusätzlich Umsetzungsplanung) bleiben. Beschreibungs-Frontmatter entsprechend anpassen ("wird vom Orchestrator … aufgerufen" → "Review-Perspektive als Skill `review-<x>` in der Hauptsession").
7. **`docs/ai-workflow.md`** — vom `developer` im Umsetzungs-PR neu geschrieben: die Schritt-Tabelle aus Teil 1 als zentrales Element; Rollen-Landkarte aus Teil 4; Abschnitt "Kosteneffiziente Agenten-Nutzung" auf den neuen Stand (Review in Hauptsession-Skills) plus Kostenabschätzung aus Teil 2; Verweise auf diese ADR statt auf 0014/0024, Verweis auf ADR 0018/0038 nur noch für die `spec-writer`-Konsultations-Skip-Logik.
8. **`CLAUDE.md`** — Konventionen-Bullet zum Copilot-Review / `ship-feature`: Verweis-Aktualisierung; Wortlaut "von allen zutreffenden Spezialisten parallel reviewen" → "über die `review-*`-Skills (Hauptsession, koordiniert vom `review`-Skill)".
9. **`specs/architecture/0002-testkonzept.md`** — vom `test-engineer` in der Teststrategie-Konsultation nachgezogen (Teil 7).
10. **`specs/diagrams/workflow-overview.d2` / `.svg`** — der `shipfeature`-Subgraph: `review`-Knoten wird "Review — Hauptsession (Skill `review` → 5 `review-*`-Skills)" statt "parallel, 5 Subagenten"; neu rendern via `scripts/render-diagrams.sh`.
11. **Kein Effekt auf `docs/architecture.md` / `docs/setup.md`** — reine Prozess-/Workflow-Änderung.

**Laufende Beobachtung statt einmaliges Gate:** Zeigt sich, dass ein `review-*`-Skill eine Perspektive systematisch flacher prüft als der frühere Subagent, oder dass die Hauptsession bei großen Features durch die fünf sequenziellen Review-Durchläufe zu stark kontextbelastet wird, ist das Auslöser für eine neue, diese ADR ablösende ADR (z.B. Rückkehr zu einem isolierten Review-Subagenten für einzelne Perspektiven oder ein anderer Skill-Schnitt) — kein stillschweigendes Abweichen.

## Entscheidungen (Daniel, 2026-08-28)

Die drei bewusst in #177 offen gelassenen Design-Forks wurden von Daniel entschieden (der `architect` konnte `AskUserQuestion` im Ausführungskontext nicht nutzen; die Klärung lief über den Orchestrator):

1. **Review-Ausführung:** **mehrere Skills, einer je Perspektive**, koordiniert durch einen dünnen `review`-Orchestrator-Skill — nicht ein gemeinsamer Skill, nicht die bisherigen Subagenten. Umgesetzt in Teil 2 / Teil 4.
2. **`developer`-Ausführung:** **Subagent behalten**, Anker-Übergabe entfragilisieren (nicht abschaffen) — wie vom `architect` empfohlen. Umgesetzt in Teil 3.
3. **Ablöse-Umfang:** **0024 ganz + 0014/0037 teilweise; 0018/0038/0016/0036 unberührt** — wie vom `architect` empfohlen. Umgesetzt in Teil 9.
