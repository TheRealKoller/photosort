# 0032 - idea-sharpener: differenzierte Modellzuweisung und Skip-Logik

**Status:** Implemented ([PR #64](https://github.com/TheRealKoller/photosort/pull/64))
**Erstellt:** 2026-08-09
**Bezug:** [`inbox/0013-idea-sharpener-tokenverbrauch-senken.md`](../inbox/0013-idea-sharpener-tokenverbrauch-senken.md), ADR [`decisions/0018-idea-sharpener-kalibrierung-und-skip-logik.md`](../decisions/0018-idea-sharpener-kalibrierung-und-skip-logik.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-09

## Ziel

Der `idea-sharpener`-Ablauf ruft aktuell bei jedem geschärften Feature fünf Fachagenten-Konsultationen (Schritt 2/6/7/8: `requirements-engineer`, `architect`, `ux-ui-designer`, `test-engineer`, `security-engineer`) sowie optional zwei parallele Explore-Agenten (Schritt 3) auf — alle sieben durchgängig auf "Standard"-Modell, unabhängig davon, wie viel echtes fachliches Abwägen die konkrete Idee tatsächlich braucht. Über mehrere Sessions hinweg beobachtet Daniel einen spürbaren Kontingent-Verbrauch dadurch. Diese Spec kalibriert Modellwahl und Konsultationsumfang differenzierter, ohne die Qualität der geschärften Specs spürbar zu verschlechtern und ohne den bereits bewusst konservativ kalibrierten `developer`-Review-Workflow (ADR [`0014`](../decisions/0014-review-agenten-selektion-und-modellzuweisung.md)) anzutasten.

Reines Entwickler-/Prozess-Tooling für den KI-gesteuerten Entwicklungsworkflow selbst (analog zu Spec 0020/0025/0031), ohne jede Berührung mit der eigentlichen PhotoSort-Anwendung oder ihren Endnutzern.

## User Story

Als Daniel, der `idea-sharpener` bei jeder neuen Feature-Idee nutzt, möchte ich, dass der Ablauf spürbar weniger Kontingent verbraucht, damit mir über eine Session bzw. mehrere Sessions hinweg mehr Kontingent für die eigentliche Umsetzungsarbeit (`developer`-Agent) bleibt — ohne dass die Qualität der geschärften Feature-Specs dabei spürbar leidet.

## Akzeptanzkriterien

- [x] **Modellzuweisung in `SKILL.md`:** Schritt 2 (`requirements-engineer`) und Schritt 7 (`ux-ui-designer`) tragen `model: "haiku"` statt der bisherigen Standard-Anweisung; beide Explore-Aufrufe in Schritt 3 tragen `model: "haiku"`; Schritt 6 (`architect`) und Schritt 8 (`test-engineer`, `security-engineer`) bleiben unverändert Standard. Alle sieben Aufrufstellen verweisen auf ADR 0018 statt (nur) auf ADR 0014.
- [x] **Skip-Logik in `SKILL.md`:** vor Schritt 6/7/8 steht jeweils eine exakte, eng gefasste Ja/Nein-Frage (kein offenes Ermessen), ob die jeweilige Konsultation für die konkrete Idee offensichtlich nicht anwendbar ist — frühestens prüfbar nach Abschluss von Schritt 3 (Code-/Spec-Recherche), Aufwand/Umfang der Idee ist explizit **keine** gültige Begründung für einen Skip. Schritt 2 (`requirements-engineer`) bekommt **keine** Skip-Option — läuft immer.
- [x] **Sicherheitsnetz unverändert:** "Im Zweifel eher konsultieren" gilt für jede der vier Skip-Fragen; bei erkennbarer Restunsicherheit läuft der Agent.
- [x] **Security-Skip-Frage mit erweiterten Leitplanken** (siehe Security-Konsultation): die Formulierung für `security-engineer` enthält explizit "auch nur mittelbar" sowie "Sichtbarkeit von Daten zwischen den beiden Nutzern" als eigenes Beispiel, nicht nur implizit unter "Berechtigungen" subsumiert; zusätzlich ein Hinweis, dass "wird ohnehin später im `developer`-Review geprüft" **keine** gültige Erwägung für die Skip-Schwelle ist.
- [x] **Dokumentationspflicht:** jede Skip-Entscheidung wird im Spec-Abschnitt "Entscheidungen" einzeln (kein Sammel-Vermerk) im Format `<Agent> nicht konsultiert (Schritt X): <strukturelle Begründung>` festgehalten.
- [x] **Recherchetiefe Schritt 3 unverändert:** ausschließlich Modellwechsel auf Haiku, keine Reduktion von Umfang/Gründlichkeit der Code-/Spec-Konfliktrecherche.
- [x] **`docs/ai-workflow.md`** erhält im Abschnitt "Kosteneffiziente Agenten-Nutzung" einen kurzen Absatz zur differenzierten `idea-sharpener`-Kalibrierung mit Verweis auf ADR 0018.
- [x] **ADR 0014 bleibt unverändert:** keine Datei-Änderung an `specs/decisions/0014-review-agenten-selektion-und-modellzuweisung.md`; der `developer`-Review-Workflow (Schritt 4) ist von dieser Spec nicht betroffen.
- [x] **Diff-Eingrenzung bei Umsetzung:** ausschließlich `.claude/skills/idea-sharpener/SKILL.md` und `docs/ai-workflow.md` geändert — kein `backend/`, kein `frontend/src/`.
- [x] **Laufende Qualitätsbeobachtung mit konkretem Verantwortlichen:** `test-engineer` prüft ab Umsetzung bei jedem eigenen `developer`-Review (Aufgabe 2) eines aus `idea-sharpener` hervorgegangenen Feature-Branches zusätzlich, ob ein dort dokumentierter Skip sich im Review als Fehlgriff erweist (der eigentlich geskippte Agent liefert substanzielle Findings zum geskippten Thema); ein einzelner belastbarer Fall reicht als Auslöser für eine ADR-0018-ablösende ADR, kein Schwellenwert-Gate.

## Datenmodell-Bezug

Keines — reine Prozess-/Prompt-Konfiguration (`SKILL.md`, `docs/`), keine Berührung der PhotoSort-Datenbank oder Anwendungscode.

## Architektur / Umsetzung

Siehe [`decisions/0018-idea-sharpener-kalibrierung-und-skip-logik.md`](../decisions/0018-idea-sharpener-kalibrierung-und-skip-logik.md) (Accepted) für die vollständige Begründung. Diese Spec setzt die dort getroffenen Entscheidungen um, trifft selbst keine neuen Grundsatzentscheidungen mehr.

Gewählter Ansatz: reine Prozess-/Konfigurationsänderung am `idea-sharpener`-Ablauf, kein Anwendungscode betroffen. ADR 0018 ergänzt ADR 0014 um eine differenzierte Modellzuweisung für die fünf `idea-sharpener`-Konsultationen sowie die Explore-Agenten in Schritt 3, und führt eine urteilsbasierte (nicht diff-mechanische) Skip-Logik für vier der fünf Konsultationen ein. ADR 0014 selbst bleibt unverändert und für den `developer`-Review-Workflow uneingeschränkt maßgeblich.

**Modellzuweisung** (Kriterium aus ADR 0014 Teil 2 übernommen, je Aufrufstelle einzeln angewendet):

| Aufrufstelle | Modell | Begründung |
|---|---|---|
| Schritt 2 → `requirements-engineer` | **Günstig (Haiku)**, war Standard | Roadmap-Abgleich + AC-Erstfassung, wird downstream (Schritt 8/9) ohnehin verfeinert/bestätigt |
| Schritt 3 → Explore (Code) | **Günstig (Haiku)**, neu | reine Retrieval-Aufgabe, keine Bewertung |
| Schritt 3 → Explore (Specs) | **Günstig (Haiku)**, neu | dito |
| Schritt 6 → `architect` | Standard, unverändert | echtes Abwägen, Grundlage für alle Folgeschritte |
| Schritt 7 → `ux-ui-designer` | **Günstig (Haiku)**, war Standard | überwiegend Abgleich gegen dokumentiertes Design-System |
| Schritt 8 → `test-engineer` | Standard, unverändert | Edge-Case-/Testtiefen-Urteil ohne feste Checkliste |
| Schritt 8 → `security-engineer` | Standard, unverändert | Bedrohungsmodellierung, nie herabstufen |

**Skip-Logik:** eng geführte, pro Agent fest formulierte Ja/Nein-Frage für `architect`/`ux-ui-designer`/`test-engineer`/`security-engineer` — `requirements-engineer` ausgenommen, läuft immer. Schwelle "offensichtlich", geprüft frühestens nach Schritt 3, Aufwand/Größe ist keine gültige Begründung, jeder Skip wird im Spec-Abschnitt "Entscheidungen" dokumentiert. Risikoargument: der spätere `developer`-Review (ADR 0014 Teil 1, mechanisch diff-basiert) deckt Architektur/UX/Security ohnehin erneut ab, sobald echter Code entsteht — ein falscher Skip in `idea-sharpener` kostet frühzeitige Design-Anleitung, nicht die Abwesenheit der Prüfung.

**Betroffene/neue Dateien:**
- `.claude/skills/idea-sharpener/SKILL.md` — Schritt 2/7: `model`-Hinweis auf Günstig (Haiku) ändern; Schritt 3: `model: "haiku"` an beiden optionalen Explore-Agenten ergänzen (Recherchetiefe/-umfang bleibt unverändert); Schritt 6/8: `model`-Hinweis unverändert, Verweis auf ADR 0018 aktualisiert; Schritt 6/7/8: je eine eng gefasste Skip-Frage vor dem jeweiligen Agenten-Aufruf ergänzen (siehe oben, Security-Frage mit erweiterten Leitplanken); Schritt 9: Hinweis auf Dokumentationspflicht für Skip-Entscheidungen im Abschnitt "Entscheidungen".
- `docs/ai-workflow.md`, Abschnitt "Kosteneffiziente Agenten-Nutzung" — kurzer Absatz zur differenzierten `idea-sharpener`-Kalibrierung, Verweis auf ADR 0018.
- `specs/decisions/0014-...md` — keine Änderung.

**Umsetzungsreihenfolge:** `SKILL.md` zuerst (operative Quelle, unmittelbar ausführbar), danach `docs/ai-workflow.md` (nachgelagerte, für Außenstehende lesbare Zusammenfassung) — keine Code-/Testabhängigkeiten, da reine Markdown-/Prompt-Änderung ohne Anwendungslogik; ein klassischer TDD-Rot-Grün-Zyklus entfällt, `developer` beginnt direkt mit den Datei-Edits (siehe Teststrategie unten für die stattdessen greifende Verifikation).

## UI/UX

**Nicht relevant** — reine Prozess-/Konfigurationsänderung an `.claude/skills/idea-sharpener/SKILL.md` und `docs/ai-workflow.md`, keine Berührung mit `frontend/src/`, keinem Backend-Endpunkt, keiner PhotoSort-Datenbank. Bestätigt durch `ux-ui-designer`, analog zur Einordnung bei Spec 0007/0031.

## Security

**Nicht sicherheitsrelevant.** Die Idee ändert ausschließlich Agenten-Steuerdateien (`SKILL.md`, `docs/ai-workflow.md`), keinen Anwendungscode — keine Berührung von Auth, externen Schnittstellen, Secrets, neuen Nutzereingaben, Berechtigungen oder Datenmodell.

**Einzige mittelbare Sicherheitsrelevanz, im Security-Gespräch geprüft:** die Idee ändert, wann und mit welchem Modell `security-engineer` selbst künftig im `idea-sharpener`-Ablauf konsultiert wird. Kritische Prüfung ergab: die Absicherung aus ADR 0018 (enge Skip-Frage, Sicherheitsnetz "im Zweifel konsultieren", zweite mechanische Instanz im späteren `developer`-Review) ist im Grundsatz ausreichend. Benannte, nicht neu eingeführte, aber leicht verschärfte Lücke: der `security-engineer`-Trigger im `developer`-Review (ADR 0014 Teil 1) ist eine Pfadliste und deckt eine sicherheitsrelevante Änderung an einer bereits bestehenden Datei außerhalb der bekannten Pfade nicht zuverlässig ab — mit der neuen `idea-sharpener`-Skip-Option könnten in diesem (bereits vorher bestehenden) blinden Fleck jetzt potenziell zwei statt einer Kontrolle denselben Fall verpassen. Für dieses private Familienprojekt (kleine Codebasis, zwei Nutzer, kein Angreifermodell mit hoher Motivation) als geringes Restrisiko bewertet, kein Blocker — als bekannte Lücke für eine spätere Aktualisierung von `specs/architecture/0003-securitykonzept.md` vorgemerkt, nicht Teil dieser Spec.

Als Gegenmaßnahme in die Akzeptanzkriterien/Umsetzung übernommen: die `security-engineer`-Skip-Frage in `SKILL.md` bekommt gegenüber der ADR-0018-Rohformulierung zwei zusätzliche Leitplanken (siehe Akzeptanzkriterien) — "auch nur mittelbar" sowie "Sichtbarkeit von Daten zwischen den beiden Nutzern" als eigenes, leicht zu übersehendes Beispiel, plus ein expliziter Hinweis, dass der spätere `developer`-Review keine gültige Erwägung für die Skip-Schwelle selbst ist (sonst würde das Sicherheitsargument aus ADR 0018 implizit die Skip-Schwelle in der Praxis aufweichen).

## Teststrategie

Reine Prompt-/Markdown-Änderung ohne `pytest`/`vitest`-Bezug — Verifikation folgt dem im Testkonzept etablierten Muster "Agenten-Steuerungslogik selbst" (bisher nur für `developer.md` Schritt 4/`research-engineer`), erweitert um einen neuen Punkt 7:

- **Statischer Konsistenz-Check** (Teil des `test-engineer`-Reviews des Umsetzungs-PR): Modellhinweise und Skip-Fragen in `SKILL.md` Wort für Wort gegen ADR 0018 sowie die geschärften Leitplanken aus dieser Spec abgleichen.
- **Synthetische Trockenlauf-Szenarien statt Wegwerf-Branch-Diff** (vor Schritt 9 des `idea-sharpener`-Ablaufs existiert kein Code-Diff, das getestet werden könnte): mindestens fünf konstruierte Beispiel-Ideen real durch Schritt 1–8 des aktualisierten `SKILL.md` laufen lassen.
- **Relevante Edge Cases:**
  1. Rein technische Backend-Idee ohne UI → `ux-ui-designer` korrekt geskippt.
  2. Idee mit sichtbarer Oberfläche → `ux-ui-designer` korrekt konsultiert.
  3. Reine Prozess-Idee ohne Codeberührung → mehrere Agenten gleichzeitig geskippt, aber einzeln dokumentiert, kein Sammel-Vermerk.
  4. Grenzfall-Idee mit knapp nicht eindeutigem UI-/Architektur-Bezug → Sicherheitsnetz greift, kein Skip trotz Restunsicherheit.
  5. Idee mit echtem Datenmodell-/Auth-/UI-Bezug → alle vier Konsultationen laufen, kein Skip trotz vorhandener Skip-Frage (Test gegen "Skip-Bias" durch die bloße Existenz der Frage).
  6. Fehlende Skip-Begründung im Nachlauf-Review wird als Muss-Fix-Finding behandelt.
- **Laufende Qualitätsbeobachtung mit konkretem Verantwortlichen/Zeitpunkt** (kein vages "wird beobachtet"): zwei Anker — (a) die in `SKILL.md` Schritt 9 vorgesehene Sofortkorrektur durch den Hauptagenten selbst, läuft bei jedem Sharpening automatisch mit; (b) `test-engineer` prüft ab jetzt bei jedem eigenen `developer`-Review (Aufgabe 2) eines aus `idea-sharpener` hervorgegangenen Feature-Branches zusätzlich, ob ein dort dokumentierter Skip sich als Fehlgriff erweist (siehe Akzeptanzkriterien).
- Kein neues CI-Gate, kein Testframework.

**Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md`, Sektion "Agenten-Steuerungslogik selbst", neuer Punkt 7 (das oben beschriebene Verfahren inkl. der beiden Beobachtungs-Anker) — neues, wiederverwendbares Muster (Steuerungslogik ohne wiederkehrenden Review-Anlass), keine reine Anwendung eines bestehenden Musters.

## Entscheidungen (2026-08-09, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Auslöser:** kein einzelnes Ereignis, sondern ein allgemeiner, über mehrere Sessions beobachteter Trend beim Kontingent-Verbrauch.
- **Scope-Abgrenzung zu ADR 0014, zentral und bindend:** ADR 0014 (Kalibrierung des `developer`-Review-Workflows, von Daniel bereits als "konservativ reicht" bestätigt) bleibt komplett unangetastet. Diese Idee bewegt sich ausschließlich auf der Fläche, die ADR 0014 bewusst offen gelassen hatte (`idea-sharpener`-Konsultationen, keine Skip-Logik dort).
- **Betroffene Agenten:** sowohl die fünf Fachagenten-Konsultationen (Schritt 2/6/7/8) als auch die optionalen Explore-Agenten (Schritt 3) — beide Gruppen bestätigt im Klärungsgespräch.
- **Devil's-Advocate-Fund 1 (technischer Unterschied zu ADR 0014):** eine mechanische, diff-basierte Skip-Heuristik wie in ADR 0014 Teil 1 funktioniert in `idea-sharpener` nicht, da zum Zeitpunkt von Schritt 2/6/7/8 noch kein Code-Diff existiert. Daniel hat sich daraufhin bewusst für eine urteilsbasierte Skip-Logik mit Pflicht-Dokumentation entschieden statt eines starren mechanischen Musters.
- **Devil's-Advocate-Fund 2 (Recherchetiefe):** eine Reduktion der Gründlichkeit der Schritt-3-Konfliktrecherche wurde von Daniel bewusst abgelehnt — der Bedarf an gründlicher Duplikat-/Konflikterkennung nimmt mit wachsendem Projekt (aktuell 32 Feature-Specs) eher zu als ab. Sparpotenzial in Schritt 3 liegt daher ausschließlich in der Modellwahl (Haiku), nicht in reduziertem Recherche-Umfang.
- **Priorität — Mittel:** direkter thematischer Nachfolger von Spec 0020/ADR 0014, gleicher Auslöser (spürbar knappes Kontingent, bremst laufend weitere Sessions) — unterscheidet die Idee von den rein qualitätsverbessernden, Niedrig eingeordneten Tooling-Einträgen (0018/0019/0025/0028/0029/0031). Schwächer gewichtet als 0020 selbst, da der hier adressierte Aufruf-Umfang (einmalig pro Feature in der Schärfungsphase) kleiner ist als der von ADR 0014 bereits adressierte `developer`-Review-Workflow, der bei jedem Feature-Branch-Review läuft — daher Mittel statt einer erneuten Hochstufung auf Hoch. Bestätigt nach Abschluss der Schärfung (requirements-engineer-Vorschlag aus Schritt 2 unverändert übernommen).
- **Neue ADR statt Ergänzung von ADR 0014:** eine eigene ADR (0018) war nötig statt einer reinen additiven Ergänzung von 0014, weil (a) die Modellzuordnung für vier bestehende `idea-sharpener`-Zeilen inhaltlich geändert wird (nicht nur neue Zeilen hinzukommen) und (b) ein Grundprinzip eingeführt wird, das ADR 0014 für sich selbst explizit ausgeschlossen hatte (urteilsbasierte statt mechanische Skip-Logik). Technische Detailentscheidung des `architect`-Agenten, keine Rückfrage nötig.
- **Umsetzung, Ergänzung zu AK "Diff-Eingrenzung":** der tatsächliche Umsetzungs-Diff umfasst neben `.claude/skills/idea-sharpener/SKILL.md` und `docs/ai-workflow.md` zusätzlich `specs/architecture/0002-testkonzept.md` (neuer Punkt 7 in der Sektion "Agenten-Steuerungslogik selbst") — der Abschnitt "Teststrategie" dieser Spec fordert diese Ergänzung explizit ("Testkonzept ergänzt: ... neuer Punkt 7"), obwohl sie im "Betroffene/neue Dateien"-Abschnitt oben nicht separat aufgeführt war. Technische Detailentscheidung des `developer`-Agenten (Auflösung eines internen Widerspruchs zwischen zwei Spec-Abschnitten zugunsten der expliziteren, spezifischeren Teststrategie-Anforderung), keine Rückfrage nötig — kein `backend/`/`frontend/src/` betroffen, AK-Kernaussage ("keine Anwendungscode-Änderung außerhalb des Prozess-Tooling") bleibt gewahrt.
- **Review-Fund (developer-Workflow, Schritt 4):** `architect` und `test-engineer` fanden unabhängig voneinander, dass Testkonzept-Punkt 7 ursprünglich pauschal "Wort für Wort"-Übereinstimmung aller vier Skip-Fragen mit ADR 0018 forderte, was für die bewusst erweiterte `security-engineer`-Skip-Frage (siehe AK "Security-Skip-Frage mit erweiterten Leitplanken") nicht zutrifft — behoben durch eine explizite Ausnahme-Formulierung in Testkonzept-Punkt 7 (verhindert einen künftigen Fehlalarm beim dort selbst vorgeschriebenen statischen Konsistenz-Check).

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- Jede Änderung am `developer`-Review-Workflow oder an ADR 0014 selbst.
- Mechanische, diff-basierte Skip-Logik für `idea-sharpener` (technisch nicht möglich vor Schritt 9, siehe Devil's-Advocate-Fund 1).
- Reduzierte Recherchetiefe/-umfang in Schritt 3 (bewusst abgelehnt, siehe Devil's-Advocate-Fund 2).
- Modell-Downgrade für `architect`/`test-engineer`/`security-engineer` in Schritt 6/8 — bleiben Standard, da echtes fachliches Abwägen ohne feste Checkliste.
- Schließen der benannten, bereits vorbestehenden Sicherheits-Lücke im `developer`-Review-Trigger (Pfadliste statt vollständiger Diff-Analyse) — vorgemerkt für eine spätere Aktualisierung von `specs/architecture/0003-securitykonzept.md`, kein Bestandteil dieser Spec.
