# 0020 - Agenten-Nutzung im Review optimieren (bedingte Review-Agenten + situative Modellzuweisung)

**Status:** Accepted — teilweise umgesetzt ([PR #32](https://github.com/TheRealKoller/photosort/pull/32), gemerged 2026-08-07: nur AK13/Copilot-Review-Bedingung; AK1–AK12 stehen noch aus)
**Erstellt:** 2026-08-07
**Bezug:** `specs/inbox/0005-agenten-nutzung-review-optimieren.md` (Daniel selbst, interaktive Session; Inbox-Notiz nach Aufnahme in diese Spec gelöscht), geschärft im idea-sharpener-Ablauf 2026-08-07. ADR: [`decisions/0014-review-agenten-selektion-und-modellzuweisung.md`](../decisions/0014-review-agenten-selektion-und-modellzuweisung.md).

## Ziel

Daniels Claude-Code-Nutzungskontingent (Subscription) ist schnell aufgebraucht — laut `/status`-Ausgabe sind Subagenten-Aufrufe insgesamt ein großer, nicht granular auf einzelne Agenten aufgeschlüsselter Verbrauchsposten. Der aktuelle `developer`-Workflow ruft in Schritt 4 ("Review") bei **jedem** Feature-Branch unbedingt vier Review-Agenten parallel auf (`test-engineer`, `security-engineer`, `architect`, `requirements-engineer`), unabhängig davon, ob es für die konkrete Änderung überhaupt etwas in ihrem Fachgebiet zu prüfen gibt — `ux-ui-designer` ist bislang das einzige bedingte Beispiel (nur bei Frontend-/UI-Diffs). Diese Spec führt eine feste, dokumentierte Trigger-Logik ein, die Review-Agenten nur noch aufruft, wenn ihr Fachgebiet tatsächlich betroffen ist, und weist einzelnen, überwiegend checklistenartigen Agenten-Aufrufen ein günstigeres Modell (Haiku) zu — beides ohne die Review-Qualität spürbar zu verschlechtern.

## User Story

Als Daniel möchte ich, dass beim Review eines Feature-Branches nur die tatsächlich relevanten Review-Agenten laufen und dass bestimmte Agenten-Aufrufe situativ ein günstigeres Modell verwenden, damit mein Nutzungskontingent nicht durch unnötige oder überdimensionierte Subagenten-Läufe schneller aufgebraucht wird, als es für den tatsächlichen Fortschritt am Projekt nötig wäre — ohne dass die Review-/Ergebnisqualität darunter spürbar leidet.

## Akzeptanzkriterien

- [x] AK1: In `developer` Schritt 4 wird vor dem Review anhand einer festen, in `developer.md` hinterlegten Trigger-Tabelle (identisch zu ADR 0014) mechanisch aus `git diff --name-only main...HEAD` ermittelt, welche der fünf Review-Agenten laufen. `test-engineer` läuft immer außer bei einem Diff aus ausschließlich Nicht-Code-Dateien; `requirements-engineer` läuft immer; `security-engineer`/`architect`/`ux-ui-designer` laufen genau dann, wenn mindestens einer ihrer dokumentierten Trigger zutrifft (Details: ADR 0014, Teil 1, inkl. der nachgeschärften `security-engineer`-Trigger).
- [x] AK2: Der `developer`-Abschlussbericht listet für jeden der fünf Review-Agenten explizit: gelaufen ja/nein; bei "nein" den konkreten Trigger-Tabelleneintrag, der nicht zutraf; bei "ja" das verwendete Modell (Standard/Haiku).
- [x] AK3: Ist unklar, ob ein Trigger zutrifft (z.B. neue Datei an nicht eindeutig zuordenbarer Stelle), läuft der betroffene Agent immer, und die Unklarheit wird im Abschlussbericht explizit benannt ("Trigger unklar, deshalb ausgeführt") statt stillschweigend als "läuft ohnehin" verbucht.
- [x] AK4: Die bestehende `ux-ui-designer`-Bedingung ("Diff enthält Dateien unter `frontend/`") bleibt inhaltlich und in der Formulierung unverändert.
- [x] AK5: Für jeden tatsächlich aufgerufenen Review-Agenten wird das verwendete Modell gemäß der festen Tabelle aus ADR 0014, Teil 2 gewählt (aktuell: Haiku ausschließlich für `requirements-engineer`- und `ux-ui-designer`-Review, alles andere Standard) und im Abschlussbericht dokumentiert. Eine Abweichung ohne begleitende ADR-Änderung gilt als Fehler.
- [x] AK6: `test-engineer` beobachtet fortlaufend (kein einmaliges Gate), ob ein von einer Haiku-Review als erfüllt/konform bewertetes Kriterium sich im selben PR-Zyklus (Copilot-Review, ein anderer Standard-Review-Agent, zeitnaher Folge-Bugfix) als tatsächlich fehlerhaft herausstellt; ein solcher Fall wird im Review-Abschlussbericht vermerkt und ist automatisch Auslöser für eine neue, ADR-0014-ablösende ADR (Rückstufung der betroffenen Aufrufstelle auf Standard).
- [x] AK7: `.claude/skills/idea-sharpener/SKILL.md` (Schritt 2, 6, 7, 8) vermerkt an jeder Agenten-Aufrufstelle explizit `model: Standard` (keine neue Skip-Logik dort — Konsultationen laufen je Feature ohnehin nur einmal, siehe Entscheidungen).
- [x] AK8: `docs/ai-workflow.md` enthält einen neuen, kurzen Abschnitt ("Kosteneffiziente Agenten-Nutzung") mit einer für Außenstehende lesbaren Zusammenfassung der Trigger-/Modelltabellen und Verweis auf ADR 0014.
- [x] AK9: `specs/diagrams/workflow-overview.d2` und das gerenderte `.svg` spiegeln den neuen Zustand wider: die Fußnote im `review`-Knoten kennzeichnet nicht mehr nur `ux-ui-designer` als bedingt, sondern auch `architect` und `security-engineer`; `test-engineer`/`requirements-engineer` bleiben als faktisch unbedingte Basis erkennbar.
- [x] AK10: `specs/architecture/0002-testkonzept.md` enthält die neue Sektion "Agenten-Steuerungslogik selbst" (bereits von `test-engineer` in dieser Schärfungs-Session ergänzt) mit dem beschriebenen Vier-Ebenen-Verifikationsmuster (statischer Konsistenz-Check, synthetische Dry-Run-Diffs, laufende Stichproben-Audits, Qualitäts-Beobachtung).
- [x] AK11: `specs/architecture/0003-securitykonzept.md` enthält einen neuen Restrisiko-Vermerk zur getriggerten (statt unbedingten) Sicherheits-Review-Abdeckung seit ADR 0014 (Formulierungsvorschlag: siehe Security-Konsultation, `architect`/`developer` übernimmt ihn wörtlich oder sinngemäß).
- [x] AK12: Mindestens ein synthetisches Dry-Run-Szenario pro Tabellenzeile aus ADR 0014 wurde real gegen `developer` Schritt 4 getestet (siehe Teststrategie/Edge Cases unten), inkl. der Kombinationsfälle (Frontend+Auth gleichzeitig; neue Top-Level-Datei unter `backend/src/photosort/`; reine `specs/decisions/**`-Änderung ohne Code).
- [x] AK13: `developer` Schritt 8 (Copilot-Review) wird nur noch angefordert, wenn der PR mindestens eine Code-Datei ändert (identische Bedingung wie der `test-engineer`-Skip-Trigger aus AK1). Bei einem PR, der ausschließlich Doku-/Spec-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) ändert, entfällt Schritt 8 vollständig. `CLAUDE.md` (Konventionen-Abschnitt, Zeile zur PR-Konvention) ist entsprechend von "immer ein Copilot-Review anfordern" auf die bedingte Formulierung aktualisiert. Umgesetzt in [PR #32](https://github.com/TheRealKoller/photosort/pull/32).

## Datenmodell-Bezug

Nicht betroffen — reine Workflow-/Prozessänderung am Einsatz der Projekt-Agenten selbst, kein Anwendungscode, kein Datenmodell.

## Architektur / Umsetzung

Reine Workflow-/Prozessänderung am Agenten-Einsatz selbst, siehe ADR [`decisions/0014-review-agenten-selektion-und-modellzuweisung.md`](../decisions/0014-review-agenten-selektion-und-modellzuweisung.md) für die vollständige Herleitung inkl. der im Rahmen dieser Schärfungs-Session nachgeschärften `security-engineer`-Trigger. Kein neues System-/Datenmodell betroffen.

**Ansatz:**
1. **Bedingte Review-Agenten in `developer` Schritt 4:** feste Diff-Trigger-Tabelle pro Agent (nicht freie Einzelfallentscheidung), mechanisch aus `git diff --name-only main...HEAD` ableitbar (mit einer Ausnahme: der `architect`-Trigger "nicht-trivialer Architektur-Abschnitt" erfordert zusätzlich das Lesen des Spec-Abschnitts "Architektur/Umsetzung"). `test-engineer`/`requirements-engineer` bleiben faktisch immer aktiv; `security-engineer`/`architect` werden echt bedingt; `ux-ui-designer` bleibt unverändert (Frontend-Diff). Sicherheitsnetz: im Zweifel läuft der Agent.
2. **Situative Modellzuweisung:** zwei feste Stufen (Standard = kein `model`-Override, Günstig = `model: "haiku"`), als statische Tabelle je Aufrufstelle (siehe ADR 0014, Teil 2). Haiku nur für die beiden checklistenartigsten Review-Aufrufe (`requirements-engineer`, `ux-ui-designer`); alles mit echtem fachlichem Urteilsvermögen (inkl. `developer` selbst, `security-engineer`, alle `idea-sharpener`-Konsultationen) bleibt Standard. Kalibrierung von Daniel bestätigt (2026-08-07, "konservativ reicht").
3. **Bedingtes Copilot-Review in `developer` Schritt 8** (nachträglich ergänzt, siehe ADR 0014, Teil 3): Copilot-Review nur bei mindestens einer Code-Datei im Diff, identische Bedingung wie der `test-engineer`-Skip-Trigger — kein separates, neues Kriterium.

**Betroffene Dateien:**
- `.claude/agents/developer.md` (Schritt 4: Trigger-Tabelle + `model`-Parameter je Aufruf-Anweisung direkt eingetragen, nicht nur als Verweis auf die ADR; Abschlussbericht-Pflicht um Modellwahl/Skip-Begründung ergänzt; Schritt 8: Bedingung "nur bei Code-Diff" ergänzt)
- `CLAUDE.md` (Konventionen-Abschnitt: PR-Zeile von "immer ein Copilot-Review anfordern" auf die bedingte Formulierung aktualisiert)
- `.claude/skills/idea-sharpener/SKILL.md` (Schritt 2/6/7/8: `model: Standard` explizit an jeder Aufrufstelle vermerkt, keine neue Skip-Logik)
- `docs/ai-workflow.md` (neuer Abschnitt, gekürzte Tabelle, Verweis auf ADR 0014 — qualifiziert für Update, da sich Workflow/Rollenmodell selbst ändern, siehe `CLAUDE.md`)
- `specs/diagrams/workflow-overview.d2`/`.svg` (Fußnote im `review`-Knoten erweitert, neu gerendert via `scripts/render-diagrams.sh`)
- `specs/architecture/0002-testkonzept.md` (bereits ergänzt: neue Sektion "Agenten-Steuerungslogik selbst")
- `specs/architecture/0003-securitykonzept.md` (neuer Restrisiko-Vermerk, siehe AK11)
- Keine Änderung an `docs/architecture.md`/`docs/setup.md` — reine Prozessänderung, kein System-/Datenmodell betroffen.

**Umsetzungsreihenfolge für `developer`:**
1. `.claude/agents/developer.md` Schritt 4 (Kern der Idee, größter Kontingent-Hebel).
2. `.claude/skills/idea-sharpener/SKILL.md` (Modell-Parameter).
3. `docs/ai-workflow.md`.
4. Diagramm zuletzt (hängt inhaltlich von 1) ab, damit die Fußnote den finalen Text aus `developer.md` korrekt widerspiegelt).
5. `specs/architecture/0003-securitykonzept.md`-Vermerk.
6. Synthetische Dry-Run-Verifikation (AK12) gegen die fertige Trigger-Tabelle.

## UI/UX

Nicht relevant. Reine Änderung am Agenten-/Entwicklungsworkflow selbst, keine App-Oberfläche betroffen — analog zu Spec 0018/0019 direkt eingeordnet, ohne gesonderte `ux-ui-designer`-Konsultation (offensichtlich keine sichtbare Oberfläche: `.claude/agents/*.md`, ADRs, Doku).

## Security

Reine Workflow-/Prozessänderung ohne neue Angriffsfläche in der App selbst. Sicherheitsrelevant ist sie dennoch, weil sie die Zuverlässigkeit des Sicherheits-Review-Mechanismus selbst verändert (bedingtes statt unbedingtes `security-engineer`-Review) — ein supply-chain-artiges Risiko für den Entwicklungsprozess, nicht für ausgelieferten Code.

**Bedrohung:** Ein sicherheitsrelevanter Diff könnte keinem der definierten Trigger-Pfade entsprechen und würde dann ohne dediziertes Sicherheits-Review gemergt.

**Gegenmaßnahmen:**
- `security-engineer`-Trigger in ADR 0014 wurde bereits in dieser Schärfungs-Session präzisiert (drei geschlossene Lücken, siehe ADR 0014, Abschnitt "Konsequenzen"): explizite Pfadliste statt vager "sonstiger Auth-/Secrets-Code"-Formulierung plus mechanischer Fallback für neue Top-Level-Module; CI-Trigger von "Netzwerkkonfiguration" auf alle `.github/workflows/**`-Änderungen erweitert; neuer eigenständiger `security-engineer`-Trigger für `frontend/src/auth/**`/`frontend/src/api/client.ts` (unabhängig vom `ux-ui-designer`-Trigger, der keine Bedrohungsmodellierung leistet).
- `security-engineer`-Aufrufe (Review wie Konsultation) bleiben ausnahmslos auf Standardmodell.
- Sicherheitsnetz "im Zweifel aufrufen" bleibt die letzte Rückfallebene gegen eine unvollständige Trigger-Liste.
- `specs/architecture/0003-securitykonzept.md` bekommt einen ehrlichen Restrisiko-Vermerk zur getriggerten Review-Abdeckung (AK11).

## Teststrategie

Reine Prozessänderung ohne ausführbaren Anwendungscode — `pytest`/`vitest` greifen nicht, kein Test-Runner ruft `.claude/agents/developer.md` auf. Verifikation auf vier Ebenen (Details: `specs/architecture/0002-testkonzept.md`, neue Sektion "Agenten-Steuerungslogik selbst"):

1. **Statischer Konsistenz-Check:** Trigger-/Modelltabelle in `developer.md` Zeile für Zeile gegen ADR 0014 abgleichen (bei Umsetzung und bei jeder späteren Tabellenänderung).
2. **Synthetische Dry-Run-Diffs:** mindestens ein konstruiertes Szenario pro Tabellenzeile real gegen `developer` Schritt 4 laufen lassen, tatsächliches Agenten-/Modell-Set gegen erwartetes vergleichen (siehe AK12, Edge Cases unten).
3. **Laufende Stichproben-Audits** an echten Feature-Branches (dauerhaft): `test-engineer` prüft ab dem ersten Folge-Branch zusätzlich, ob Abschlussbericht-Protokoll und tatsächlicher Diff zusammenpassen.
4. **Qualitäts-Beobachtung der Haiku-Stufe** gemäß AK6, ebenfalls dauerhaft, kein einmaliges Gate.

Kein neues CI-Gate, kein neues Testframework — konsistent mit allen bisherigen reinen Prozess-Features im Projekt (Spec 0007, 0008, 0018, 0019).

**Edge Cases (müssen die Dry-Run-Szenarien aus AK12 abdecken):**
- Diff ändert gleichzeitig Frontend- **und** Auth-Backend-Code → `ux-ui-designer` UND `security-engineer` müssen beide laufen.
- Neue Datei an unklarer Stelle → betroffener Agent muss laufen (AK3), Ambiguität explizit im Bericht benannt.
- Sehr kleiner Diff (1–2 Zeilen), aber sicherheitsrelevant (z.B. Änderung an einer Auth-Prüfung) → `security-engineer` muss über den Pfad-Trigger laufen, nicht über Diff-Größe (keine größenbasierte Abkürzung).
- Diff berührt ausschließlich `specs/*.md`/`docs/*.md` → einziger echter Skip-Pfad für `test-engineer`; `requirements-engineer` läuft trotzdem.
- Neue Abhängigkeit (`package.json`) → `security-engineer` (Dependency-Datei) UND `architect` (neue externe Abhängigkeit) müssen beide unabhängig triggern.
- Diff nur unter `specs/decisions/**`, kein Code → `architect`/`requirements-engineer` laufen, `test-engineer` korrekt übersprungen.
- Diff trivial, aber Spec-Abschnitt "Architektur/Umsetzung" nicht-trivial → `architect`-Trigger hängt vom Spec-Inhalt ab, nicht rein mechanisch aus `git diff --name-only` ableitbar.
- Neue Top-Level-Datei direkt unter `backend/src/photosort/` → mechanischer `security-engineer`-Fallback-Trigger muss greifen, auch ohne explizite Nennung in der Pfadliste.

## Entscheidungen

- **Priorität explizit auf "Als Nächstes" hochgestuft** statt Ideenspeicher (requirements-engineer-Konsultation, von Daniel bestätigt, 2026-08-07): anders als bei Spec 0018/0019 betrifft der Auslöser (knappes Nutzungskontingent) die Entwicklungsgeschwindigkeit an allen anderen Roadmap-Einträgen, nicht nur ein kosmetisches Detail.
- **Feste Diff-Heuristik statt freier `developer`-Einzelfallentscheidung** (architect-Konsultation, ADR 0014): eine freie "prüfe, ob es diesmal nötig ist"-Entscheidung würde über viele Features hinweg zu Drift führen — genau das Muster, das die `architect`-Rolle selbst verhindern soll.
- **`test-engineer`/`requirements-engineer` bleiben faktisch unbedingt**, kein künstlicher Skip-Pfad nur damit "alle vier gleich bedingt aussehen" (architect-Konsultation): beide decken per Konstruktion (TDD-Zwang, Akzeptanzkriterien-Pflicht) nahezu jedes Mal etwas Prüfenswertes ab.
- **Keine größenbasierte (Zeilenzahl-)Heuristik**: korreliert schwach mit Risiko, ein Ein-Zeilen-Diff kann eine Auth-Prüfung entfernen (architect-Konsultation).
- **Zwei statische Modellstufen statt dynamischem Scoring** (architect-Konsultation): eine feste, kleine Aufrufstellen-Menge ist per Tabelle einfacher zu pflegen/auditieren als Laufzeit-Logik mit eigenem Fehlerpotenzial.
- **Konservative Modell-Kalibrierung** (nur `requirements-engineer`- und `ux-ui-designer`-Review auf Haiku) — von Daniel per Rückfrage im Hauptchat ausdrücklich bestätigt (2026-08-07) gegenüber einer aggressiveren Variante (z.B. auch `test-engineer`/`architect`-Review bei kleinen Diffs).
- **`security-engineer`-Trigger nachgeschärft** (security-engineer-Konsultation, 2026-08-07): vage "sonstiger Auth-/Secrets-Code"-Formulierung durch explizite Pfadliste + mechanischen Fallback ersetzt; CI-Workflow- und Frontend-Auth-Trigger als echte Lücken ergänzt (siehe ADR 0014, Konsequenzen).
- **`security-engineer` nie auf Haiku herabgestuft**, ausnahmslos (security-engineer-Konsultation): Bedrohungsmodellierung ist per Definition kein Checklisten-Abgleich, auch nicht bei kleinen/trivial wirkenden Diffs.
- **Bedingtes Copilot-Review nachträglich ergänzt** (direkte Anweisung von Daniel im Hauptchat, 2026-08-07, nach ursprünglicher Sharpening-Session): PRs, die ausschließlich Doku-/Spec-Dateien ändern, brauchen kein Copilot-Review — keine erneute idea-sharpener-Konsultation nötig, da eindeutig formuliert und ohne Produkt-Trade-off; als Amendment zum bereits Accepted, aber noch nicht implementierten ADR 0014/Spec 0020 aufgenommen statt einer neuen Spec-Nummer, da inhaltlich derselbe Themenbereich (Review-Aufwand pro PR reduzieren).
- **Keine `ux-ui-designer`-Konsultation im Schärfen-Ablauf** (Schärfungs-Session, 2026-08-07): Feature hat unzweifelhaft keine sichtbare Oberfläche (reine Agenten-/Prozessdateien), analog zur Praxis bei Spec 0018/0019 direkt als "nicht relevant" eingeordnet statt einer Konsultation, die dasselbe Ergebnis nur mit zusätzlichem Agenten-Aufwand bestätigt hätte — bewusst konsistent mit dem Ziel dieser Spec selbst (nicht mehr Agenten-Aufwand als nötig).
- **Neue ADR (0014) statt reiner Spec-Entscheidung**, obwohl Workflow-/Prozessänderung im engeren `CLAUDE.md`-Wortsinn kein "neue Technologie/Datenmodell/externe Abhängigkeit"-Fall ist (architect-Konsultation): analog zu bestehenden Prozess-ADRs 0007 und 0013, da eine dauerhafte, projektweite Regel für jedes künftige Feature gesetzt wird.

## Offene Fragen

Keine.

## Out of Scope

- Dynamisches/scoring-basiertes Modell- oder Agenten-Auswahlverfahren zur Laufzeit — bewusst zugunsten einer einfachen, statischen Tabelle verworfen (siehe Entscheidungen/ADR 0014).
- Aggressivere Modell-Kalibrierung (z.B. `test-engineer`/`architect`-Review auf Haiku) — von Daniel explizit abgelehnt zugunsten der konservativen Stufe; bei Bedarf später über eine neue ADR nachziehbar, falls sich die konservative Stufe als zu wenig wirksam erweist.
- Granulare `/status`-Auswertung/Instrumentierung, um den tatsächlichen Kontingent-Effekt dieser Änderung zu messen — Daniel beobachtet die Wirkung informell über zukünftige `/status`-Aufrufe, kein dediziertes Tracking-Feature.
