# 0038 - Gelockerte Skip-Schwelle für die `spec-writer`-Konsultationen, verstärkte Devil's-Advocate-Vorfilterung in `refinement`

**Status:** Accepted
**Datum:** 2026-08-27
**Bezug:** GitHub-Issue [`#230`](https://github.com/TheRealKoller/photosort/issues/230) ("Kosteneffizientere Ideen-Pipeline: härtere Vorfilterung in `refinement` + gelockertes Konsultations-Sicherheitsnetz in `spec-writer`", löst inhaltlich auch Issue #232 mit ab), `architect`-Konsultation im `spec-writer`-Ablauf für die aus #230 hervorgehende Feature-Spec am 2026-08-27. Löst **Teil 2 von ADR [`0018`](./0018-idea-sharpener-kalibrierung-und-skip-logik.md)** ab (die dortige Skip-Schwellen-Kalibrierung "offensichtlich" / "im Zweifel eher konsultieren" für die vier Konsultationen) — Teil 1 (Modellzuweisung je Aufrufstelle) und Teil 3 (Verhältnis zu ADR 0014) von ADR 0018 bleiben unverändert gültig, ADR 0018 bleibt `Accepted` und erhält einen Nachtrag-Verweis. ADR [`0014`](./0014-review-agenten-selektion-und-modellzuweisung.md) bleibt vollständig unangetastet.
**Bestätigt (Daniel, Hauptchat, 2026-08-27):** Die im `architect`-Entwurf zunächst vorläufig markierte Security-Sonderbehandlung (Teil 2) ist **nicht** übernommen — Daniel hat entschieden, dass **alle vier** Konsultationen gleich behandelt werden, `security-engineer` eingeschlossen. Teil 2 unten ist entsprechend auf diese Entscheidung umgeschrieben; das damit verbundene Sicherheits-Restrisiko ist ausdrücklich akzeptiert.

## Kontext

Seit ADR [`0036`](./0036-github-issue-natives-story-refinement-inbox-entfaellt.md) / Spec [`0059`](../features/0059-story-lebenszyklus-github-issues.md) ist der frühere monolithische `idea-sharpener`-Ablauf in zwei Skills getrennt:

- `refinement` — die rein fachliche Schärfung einer Idee zur Story (Verständnis, Roadmap-Einordnung über `requirements-engineer`, Code-/Spec-Konfliktrecherche, Devil's Advocate), Ergebnis ist ein strukturierter GitHub-Issue-Body mit Status `Ready`.
- `spec-writer` — die technische Ausarbeitung einer bereits `Ready`-Story zur akzeptierten Feature-Spec, mit vier Fachagenten-Konsultationen: `architect` (Schritt 1), `ux-ui-designer` (Schritt 2), `test-engineer` und `security-engineer` (Schritt 3).

ADR 0018 Teil 2 hatte für die vier `spec-writer`-Konsultationen eine bewusst **konservative**, urteilsbasierte Skip-Logik eingeführt: eine eng gefasste Ja/Nein-Frage pro Agent, Schwelle "offensichtlich nicht zuständig" (Skip nur, wenn sich *kein einziges plausibles Gegenbeispiel* findet), jede noch so schwache Restunsicherheit führt zum Aufruf — wörtlich identisch zum Sicherheitsnetz "im Zweifel eher konsultieren" aus ADR 0014 Teil 1.

Daniel beobachtet weiterhin einen spürbaren Kontingent-Verbrauch durch den Prozess-Overhead der Ideen-Pipeline. In der Praxis führt die "im Zweifel konsultieren"-Schwelle dazu, dass die vier Konsultationen fast immer laufen, auch wenn sie für viele Ideen nur ein "nicht relevant" zurückliefern — der theoretische Zweifel ("ganz ausschließen kann man es nie") ist fast nie vollständig ausräumbar. Im Klärungsgespräch (Issue #230) wurden zwei ergänzende, bewusst zusammengehörige Hebel festgelegt:

1. **Härtere Vorfilterung in `refinement`:** unreife oder nicht lohnende Ideen sollen früh, in der billigen fachlichen Phase, aussortiert werden, bevor sie überhaupt in die kostenintensivere technische Phase (`spec-writer` mit vier Konsultationen) gelangen.
2. **Gelockerte Skip-Schwelle in `spec-writer`:** bei echter Restunsicherheit darf künftig öfter geskippt werden. Mehr Restrisiko wird bewusst in Kauf genommen; ein übersehener Konsultationsbedarf wird als Zweitlinie vom späteren `developer`-Review (ADR 0014 Teil 1, mechanisch diff-basiert) sowie von der bereits bestehenden laufenden Qualitätsbeobachtung (Spec [`0032`](../features/0032-idea-sharpener-kalibrierung-und-skip-logik.md), Testkonzept Punkt 7) aufgefangen.

Diese ADR ist wie ADR 0014/0016/0018/0024/0036/0037 eine reine Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst — kein Effekt auf PhotoSort-Anwendungscode, Datenmodell oder Systemarchitektur.

Bindende, im Klärungsgespräch festgelegte Rahmenbedingungen:

- ADR 0014 und der gesamte `developer`-Review-Workflow (Skill `ship-feature`) bleiben unangetastet — Datei nicht anfassen, Trigger-/Modelltabelle unverändert.
- Die **Modellzuweisung** aus ADR 0018 Teil 1 / Spec 0032 (Haiku für `requirements-engineer`/`ux-ui-designer`/Explore-Agenten, Standard für `architect`/`test-engineer`/`security-engineer`) bleibt unverändert — diese ADR ändert **nur die Skip-Schwelle**, nicht die Modellwahl.
- Die Dokumentationspflicht für jede Skip-Entscheidung (Format `<Agent> nicht konsultiert (Schritt X): <Begründung>`, einzeln, kein Sammel-Vermerk) bleibt unverändert.
- `requirements-engineer` in `refinement` bleibt von jeder Skip-Logik ausgenommen und läuft immer.
- Die laufende Qualitätsbeobachtung aus Spec 0032 (Testkonzept Punkt 7 (b): `test-engineer` prüft im späteren `developer`-Review, ob sich ein dokumentierter Skip als Fehlgriff erweist) bleibt bestehen und wird **nicht** abgeschwächt.
- Issue #177 / `specs/inbox/0027` ("AI-Workflow überarbeiten") bleibt eine separate, breiter angelegte Idee, nicht Teil dieser Entscheidung.

## Entscheidung

### Teil 1: Gelockerte Skip-Schwelle für alle vier `spec-writer`-Konsultationen (`architect`, `ux-ui-designer`, `test-engineer`, `security-engineer`)

Die pro Agent fest formulierte Ja/Nein-Skip-Frage aus ADR 0018 Teil 2 **bleibt** inhaltlich bestehen (Zuständigkeits-Frage: berührt die Story Code/Komponenten/Datenmodell? / hat sie eine sichtbare Oberfläche, auch mittelbar? / entsteht testbares Verhalten? / berührt sie Auth/Schnittstellen/Secrets/Berechtigungen/Datenmodell/Datensichtbarkeit zwischen den Nutzern?). Was sich ändert, ist ausschließlich die **Schwelle**, ab der ein verbleibender Zweifel zum Aufruf zwingt:

| | ADR 0018 Teil 2 (bisher) | Diese ADR (neu) |
|---|---|---|
| Skip zulässig, wenn … | *kein einziges plausibles Gegenbeispiel* existiert | die Story **keinen konkret benennbaren** Bezug zur Zuständigkeit des Agenten hat |
| Zwang zum Aufruf | *jede* verbleibende Restunsicherheit, "und sei sie schwach" | erst wenn es **mindestens einen konkreten, benennbaren Anhaltspunkt** gibt, dass der Agent etwas Substanzielles beitragen würde |
| rein theoretischer Zweifel ("ganz ausschließen kann man es nie") | zwingt zum Aufruf | zwingt **nicht** mehr zum Aufruf |

Der konkrete Anhaltspunkt ist z.B.: eine bestimmte Datei/Komponente/Datenmodell-Berührung (für `architect`); eine bestimmte Stelle, an der etwas angezeigt oder eingegeben wird (für `ux-ui-designer`); ein bestimmtes nicht-triviales Verhalten, das getestet werden müsste und über die reine Existenz von Code hinausgeht (für `test-engineer`); eine bestimmte neue Eingabe von außen, eine berührte Auth-/Berechtigungs-/Secret-Stelle, eine Datenmodell-Änderung oder eine veränderte Datensichtbarkeit zwischen den beiden Nutzern (für `security-engineer`).

**Unverändert übernommen aus ADR 0018 Teil 2:**

- Aufwand, Umfang oder gefühlte Einfachheit der Story ist **weiterhin keine** gültige Skip-Begründung. Es geht allein um das Vorhandensein bzw. Fehlen eines konkreten fachlichen Anhaltspunkts, nie um dessen Größe.
- Der Zeitpunkt der Prüfung bleibt: unmittelbar vor dem jeweiligen Agenten-Aufruf.
- Jede Skip-Entscheidung wird einzeln im Abschnitt "Entscheidungen" der entstehenden Spec dokumentiert (Format `<Agent> nicht konsultiert (Schritt X): <konkrete Begründung>`), plus "nicht relevant" + Begründung im jeweiligen Spec-Abschnitt.
- Die Modellzuweisung (ADR 0018 Teil 1) ist unberührt.

### Teil 2: `security-engineer` wird mit gelockert — bewusst akzeptiertes Sicherheits-Restrisiko

Der `architect`-Entwurf dieser ADR sah vor, `security-engineer` (Schritt 3) vorläufig bei der strengeren Schwelle zu belassen (Grundprinzip ADR 0014 Teil 2 "Sicherheitsurteil nie herabstufen"; in Spec 0032 dokumentierter blinder Fleck der Security-Zweitlinie; kleiner Kostenhebel). **Daniel hat im Hauptchat (2026-08-27) entschieden, dass alle vier Konsultationen gleich behandelt werden** — `security-engineer` fällt damit vollständig unter die "konkreter Anhaltspunkt"-Schwelle aus Teil 1:

- Skip zulässig, wenn die Story **keinen konkret benennbaren** Bezug zu Auth, externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, dem Datenmodell oder der Sichtbarkeit von Daten zwischen den beiden Nutzern hat.
- Aufruf erst, sobald **mindestens ein konkreter, benennbarer Anhaltspunkt** vorliegt (siehe Beispiele in Teil 1).
- Rein theoretischer Zweifel ("ganz ausschließen kann man es nie") zwingt **nicht** mehr zum Aufruf.

**Bewusst in Kauf genommenes Restrisiko:** Die Security-Zweitlinie im nachgelagerten `developer`-Review (ADR 0014 Teil 1) ist eine **Pfadliste** und deckt eine sicherheitsrelevante Änderung an einer bestehenden Datei außerhalb der bekannten Pfade nicht zuverlässig ab (in Spec 0032 dokumentiert). Ein falscher `security-engineer`-Skip in `spec-writer` kann daher seltener von der Zweitlinie aufgefangen werden als ein falscher Architektur-/UX-Skip. Daniel hat dieses Restrisiko ausdrücklich akzeptiert. Als Korrektiv bleibt die laufende Qualitätsbeobachtung (Teil 4, Spec 0032 / Testkonzept Punkt 7 (b)) unverändert bestehen — ein einzelner belastbarer Fehlgriff-Fall (auch für Security) löst eine neue, diese ADR ablösende ADR aus.

### Teil 3: Verstärkte Devil's-Advocate-Vorfilterung in `refinement`

Der Devil's-Advocate-Schritt in `refinement` (aktuell Schritt 5) wird von einer der Ergebnisformulierung vorgelagerten "Gegenwind"-Übung zu einem **eigenständigen, immer durchlaufenden Lohnenswert-Gate** mit explizitem Urteil:

- Der Schritt prüft eine Idee explizit und dokumentiert auf **Lohnenswert**, mindestens entlang: (a) echtes, benennbares Problem — oder nur ein vermutetes? (b) Aufwand im Verhältnis zum Nutzen — lohnt sich das *jetzt*? (c) gibt es einen einfacheren Weg zum selben Ergebnis? (d) Widerspruch zu einer bestehenden Priorität, einem MVP-Zuschnitt oder einer bestehenden Entscheidung (`specs/decisions/`, `specs/roadmap.md`)?
- Der Schritt endet mit einem **expliziten Urteil**: "hält stand → weiter zur Ergebnis-Formulierung" oder "hält nicht stand → verworfen".
- Beim Urteil "verworfen": die Idee wird **mit dokumentierter Begründung** verworfen — die Begründung wird sichtbar festgehalten (Kommentar am Issue bzw. kurzer Abschnitt im Issue-Body), *dann* das Issue über `github-project-sync --only issue:<NNN> --status Done` geschlossen (schließt das Issue nativ, Board-Status `Done`). Kein stillschweigendes Durchreichen zu `Ready`.
- Die Prüfung ist ausdrücklich **keine Formsache** mehr, die kurz vor dem Schreiben des Issue-Bodys abgehakt wird, sondern ein bewusster Gate-Schritt mit zwei möglichen Ausgängen.

`requirements-engineer` (Roadmap-Einordnung, Schritt 2 in `refinement`) bleibt davon unberührt und läuft weiterhin immer — die härtere Vorfilterung setzt *nach* der Roadmap-Einordnung an, nicht davor.

### Teil 4: Kompensierende Kontrollen — unverändert, bewusst als Zweitlinie eingerechnet

Die Lockerung in Teil 1 ist nur vertretbar, weil folgende Kontrollen **unverändert** bestehen bleiben und hier explizit als Auffangnetz eingerechnet werden:

- **`developer`-Review (ADR 0014 Teil 1):** deckt Architektur/UX/Security erneut ab, sobald echter Code entsteht — mechanisch diff-basiert, unabhängig davon, ob die Konsultation in `spec-writer` lief. Ein falscher Skip kostet frühzeitige Design-Anleitung, nicht die vollständige Abwesenheit der Prüfung — mit der Einschränkung, dass die Security-Zweitlinie pfadlistenbasiert und damit löchriger ist (Teil 2, bewusst akzeptiert).
- **Laufende Qualitätsbeobachtung (Spec 0032 / Testkonzept Punkt 7 (b)):** `test-engineer` prüft bei jedem `developer`-Review eines aus der Ideen-Pipeline hervorgegangenen Feature-Branches, ob ein dokumentierter Skip sich als Fehlgriff erweist (der geskippte Agent liefert substanzielle Findings zum geskippten Thema). Ein einzelner belastbarer Fall reicht als Auslöser für eine neue, diese ADR ablösende ADR.
- **Devil's-Advocate-Gate in `refinement` (Teil 3):** reduziert die Menge an Ideen, die überhaupt in `spec-writer` ankommen — je weniger grenzwertige Ideen die technische Phase erreichen, desto weniger schadet dort eine großzügigere Skip-Entscheidung.
- **Dokumentationspflicht:** jede Skip-Entscheidung bleibt einzeln und begründet in der Spec nachvollziehbar — Voraussetzung dafür, dass die Qualitätsbeobachtung überhaupt greifen kann.

## Begründung

- **Warum eine neue ADR und nicht eine technische Detailentscheidung innerhalb von ADR 0018:** ADR 0018 Teil 2 legt die Schwelle "offensichtlich" / "im Zweifel eher konsultieren" als bewusstes Grundprinzip fest und hält in den Konsequenzen selbst fest, dass ein Wechsel dieses Grundprinzips eine neue, ablösende ADR braucht. Die Schwelle ist außerdem eine projektweite, für jede künftige Idee geltende Regel — genau der Fall, für den ADRs existieren.
- **Warum "konkreter Anhaltspunkt" statt einer offenen "entscheide, ob nötig"-Anweisung:** Freies Urteil driftet über viele Ideen hinweg (dasselbe Anti-Drift-Argument wie in ADR 0014/0018). Die Lockerung ersetzt nicht die eng geführte Ja/Nein-Frage, sondern nur den Umgang mit Restzweifel: von "jeder Zweifel zählt" zu "nur ein benennbarer Anhaltspunkt zählt". Das bleibt eine eng geführte Prüfung, keine offene Abwägung.
- **Warum `refinement`-Vorfilterung und `spec-writer`-Lockerung zusammengehören:** Die Risiko-Rechtfertigung der Lockerung stützt sich darauf, dass die Zweitlinien (developer-Review, Qualitätsbeobachtung) greifen. Diese Zweitlinien sind für *gute* Ideen zuverlässiger als für halbgare — eine unreife Idee produziert oft diffusen Code, bei dem auch der mechanische Trigger unsauber greift. Härtere Vorfilterung erhöht also die Wirksamkeit der Zweitlinie, auf die sich die Lockerung verlässt. Beide Hebel einzeln wären schwächer.
- **Warum `security-engineer` mit gelockert wird (statt ausgenommen):** der `architect`-Entwurf empfahl eine vorläufige Ausnahme (ADR-0014-Grundprinzip "Sicherheitsurteil nie herabstufen" plus dokumentierter blinder Fleck in der Security-Zweitlinie). Daniel hat die Frage als Risiko-/Produktentscheidung im Hauptchat entschieden: alle vier gleich behandeln, das dünnere Security-Auffangnetz wird bewusst in Kauf genommen (Teil 2). Die laufende Qualitätsbeobachtung greift auch für Security-Fehlgriffe.
- **Warum Modellzuweisung unangetastet:** ausdrückliche Rahmenbedingung; die Modellkalibrierung aus ADR 0018 Teil 1 hat sich nicht als Problem gezeigt, nur die Aufruf-*Häufigkeit*.

## Konsequenzen

- **`.claude/skills/spec-writer/SKILL.md`:**
  - Schritt 1 (`architect`), Schritt 2 (`ux-ui-designer`) und Schritt 3 (`test-engineer` **und** `security-engineer`): die Skip-Prüfung jeder der vier Konsultationen wird auf die neue Schwelle aus Teil 1 umformuliert — Skip, wenn kein konkret benennbarer Bezug; Aufruf erst bei mindestens einem konkreten Anhaltspunkt; rein theoretischer Zweifel zwingt nicht mehr zum Aufruf. Die Klausel "Aufwand/Umfang/gefühlte Einfachheit ist keine gültige Begründung" und die Dokumentationspflicht bleiben wortgleich. Der Spec-0032-Zusatz beim `security-engineer` ("auch nur mittelbar"; Datensichtbarkeit zwischen den Nutzern als eigenes Beispiel; "wird ohnehin später im `developer`-Review geprüft" ist keine gültige Erwägung) bleibt als inhaltliche Präzisierung der Zuständigkeitsfrage erhalten — nur der Umgang mit Restzweifel wird gelockert.
  - Die Formulierung darf keinen reinen Herkunfts-/Begründungsverweis auf diese ADR enthalten (CLAUDE.md-Konvention) — die Regel steht vollständig im `SKILL.md`-Text.
- **`.claude/skills/refinement/SKILL.md`:** Schritt 5 wird zum eigenständigen Lohnenswert-Gate nach Teil 3 umgeschrieben (expliziter Prüfkatalog a–d, explizites Ja/Nein-Urteil, dokumentierte Begründung beim Verwerfen vor dem `--status Done`-Aufruf). Der bereits vorhandene Verwerfen-Pfad (Issue schließen) bleibt, wird nur um die Dokumentationspflicht ergänzt.
- **`specs/architecture/0002-testkonzept.md`, Sektion "Agenten-Steuerungslogik selbst", Punkt 7:** der `test-engineer` aktualisiert Punkt 7 — (a) die neue Skip-Schwelle im statischen Konsistenz-Check gegen diese ADR statt gegen ADR 0018 Teil 2 abgleichen; (b) bei der Gelegenheit die noch auf `idea-sharpener` lautende Terminologie in Punkt 7 auf `refinement`/`spec-writer` nachziehen (vorbestehende Unschärfe seit der Skill-Umbenennung). Die konkrete Ausgestaltung entscheidet der `test-engineer` in der Teststrategie-Konsultation dieser Spec.
- **`specs/decisions/0018-idea-sharpener-kalibrierung-und-skip-logik.md`:** erhält einen kurzen **Nachtrag-Verweis** (analog zu ADR 0036 → 0037): Teil 2 (Skip-Schwellen-Kalibrierung) ist durch diese ADR abgelöst, Teil 1/Teil 3 bleiben gültig, ADR 0018 bleibt `Accepted`. Kein inhaltliches Editieren der ursprünglichen Entscheidung.
- **`docs/ai-workflow.md`, Abschnitt "Kosteneffiziente Agenten-Nutzung":** der Absatz zur Ideen-Pipeline-Kalibrierung wird angepasst — Skip-Schwelle jetzt "konkreter Anhaltspunkt" statt "im Zweifel eher konsultieren" für **alle vier** `spec-writer`-Konsultationen (`architect`/`ux-ui-designer`/`test-engineer`/`security-engineer`); kurzer Hinweis auf das verstärkte Devil's-Advocate-Gate in `refinement`. Nebenbei den vorbestehenden toten Link-Namen (`0018-spec-writer-...` → `0018-idea-sharpener-...`) korrigieren.
- **Kein Effekt auf `docs/architecture.md`, `docs/setup.md`, Root-`README.md`** — reine Prozess-/Workflow-Änderung, keine System-/Datenmodell-Änderung.
- **`specs/diagrams/workflow-overview.d2`/`.svg`:** keine zwingende Änderung — Modellstufe und Skip-Bedingung der Konsultationen werden im Diagramm nicht auf dieser Ebene dargestellt.
- **Bestätigungs-Nachtrag (erledigt):** Daniel hat die Security-Frage am 2026-08-27 im Hauptchat entschieden — alle vier Konsultationen gleich lockern, `security-engineer` eingeschlossen (siehe **Bestätigt**-Zeile im Kopf und Teil 2). Kein separater ADR-Zyklus nötig.
- Ein späterer Wechsel des Grundprinzips (z.B. zurück zu "im Zweifel konsultieren", oder eine mechanische statt urteilsbasierte Skip-Logik, oder eine erneute Sonderbehandlung von `security-engineer`) bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
