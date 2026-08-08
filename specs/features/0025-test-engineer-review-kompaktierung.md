# 0025 - test-engineer kompaktieren: TDD-Ritual-Check raus, Instruktionen straffen

**Status:** Accepted
**Erstellt:** 2026-08-08
**Bezug:** `specs/inbox/0014-test-engineer-ueberarbeiten-kompakter.md` (Daniel selbst, interaktive Session; Inbox-Notiz nach Aufnahme in diese Spec gelöscht), geschärft im idea-sharpener-Ablauf 2026-08-08.

## Ziel

`.claude/agents/test-engineer.md` prüft im Review eines Feature-Branches (Aufgabe 2) aktuell unter anderem, "ob TDD tatsächlich befolgt wurde" — aus dem fertigen Diff lässt sich die Einhaltung der TDD-Reihenfolge (Test vor Code) aber ohnehin nicht zuverlässig feststellen; der Check ist in der Praxis Ritual ohne belastbares Ergebnis. Zusätzlich soll die Agenten-Datei insgesamt kompakter/fokussierter werden — weniger ausschmückende Prosa, klarer Fokus auf: Spec-Akzeptanzkriterien durch Tests abgedeckt, allgemeine Qualitätsstandards eingehalten (Coverage, Testkonzept-Konformität), Tests ausführbar/Coverage im Blick — ohne die eigentliche Prüftiefe zu verlieren.

## User Story

Als Daniel möchte ich, dass der `test-engineer`-Agent beim Review keine unverifizierbare TDD-Reihenfolge-Prüfung mehr vornimmt und seine Instruktionsdatei kompakter/fokussierter ist, damit jeder Review-Aufruf weniger Kontext/Tokens verbraucht, ohne dass die eigentliche Qualitätssicherung (Spec-Testbedingungen erfüllt, Qualitätsstandards eingehalten, Coverage im Blick) darunter leidet.

## Akzeptanzkriterien

- [ ] AK1: In `.claude/agents/test-engineer.md`, Aufgabe 2/1, ist der Prüfpunkt "Wurde TDD tatsächlich befolgt …" (aktuell Zeile 37) vollständig entfernt, ohne Ersatz-Prüfpunkt mit gleichem Ritual-Fokus (Test-vor-Code-Reihenfolge). Die Phrase "tatsächlich befolgt" kommt in der Datei nicht mehr vor.
- [ ] AK2: Das im gestrichenen Punkt enthaltene beobachtbare Symptom ("Tests wirken nachträglich an bestehenden Code angepasst") geht ausschließlich im bestehenden Testqualitäts-Punkt auf (Ergänzung von "keine übermockten Tests, die nur die Implementierung spiegeln" um "oder erkennbar nachträglich an die Implementierung statt an das beschriebene Verhalten angepasst wirken").
- [ ] AK3: Aufgabe 2/1 enthält danach genau die fünf verbleibenden Prüfpunkte (AK-Abdeckung, Edge Cases, Testqualität inkl. AK2-Ergänzung, Coverage-Gate, Testkonzept-Abgleich) — keiner entfällt inhaltlich, kein neuer sechster Punkt entsteht.
- [ ] AK4: Die Gesamtdatei ist gegenüber dem Ist-Stand (69 Zeilen) messbar kürzer — reines Streichen der einen Zeile aus AK1 allein genügt nicht; die Prosa-Abschnitte ("Warum diese Rolle", Aufgabe 3) sind erkennbar gestrafft. Aufgabe 1 und Aufgabe 3 behalten dabei jeden inhaltlichen Punkt der aktuellen Fassung mit erkennbarer Entsprechung in der neuen Fassung (nur Prosa/Redundanz gekürzt, kein Inhalt still gestrichen). Insbesondere bleiben erhalten: Coverage-Gate-Erwähnung (≥80%), Verweis auf `specs/architecture/0002-testkonzept.md`, Abgrenzung zu `security-engineer` (inkl. des Hinweissatzes "Fällt dir dennoch etwas Sicherheitsrelevantes auf, erwähne es kurz"), und die AskUserQuestion-Eskalationsregel bei Produkt-/Risiko-Trade-offs.
- [ ] AK5: Die Modellzuordnung für `test-engineer`-Reviews bleibt "Standard" — weder ADR 0014 noch die Modelltabelle in `.claude/agents/developer.md` Schritt 4 noch das YAML-Frontmatter von `test-engineer.md` werden verändert. Explizit kein Bestandteil dieser Spec.
- [ ] AK6: `.claude/agents/developer.md` Zeile 76 (Beschreibung des `test-engineer`-Aufrufs in Schritt 4) ist synchron angepasst: "TDD eingehalten" entfällt aus der Aufzählung, die übrigen dort genannten Prüfgegenstände (Abdeckung der Akzeptanzkriterien, Testqualität, Testkonzept-Abgleich, klassische Bugs/Logikfehler, Abweichungen von Code-Konventionen) bleiben unverändert stehen.
- [ ] AK7: Verifiziert per (a) statischem Konsistenz-Check (AK1/AK2/AK3/AK5/AK6 gegen den finalen Diff abgeglichen) und (b) mindestens einem synthetischen Dry-Run-Review-Szenario auf einem Wegwerf-Branch mit einem konstruierten Diff, der bewusst "nachträglich wirkende" Tests enthält (schwache Assertions, die nur die Implementierung spiegeln) — dabei bestätigt sich, dass kein TDD-Ritual-Finding mehr erscheint, stattdessen das erweiterte Testqualitäts-Finding greift, und alle fünf verbleibenden Punkte im Review-Output erkennbar adressiert sind.

## Datenmodell-Bezug

Nicht betroffen — reine Änderung an Agenten-Instruktionsdateien, kein Anwendungscode, kein Datenmodell.

## Architektur / Umsetzung

Reine Instruktions-/Kompaktierungsänderung an zwei bestehenden Agenten-Definitionsdateien. Kein neues System-/Datenmodell, keine neue Technologie, keine neue externe Abhängigkeit — daher keine neue ADR nötig (analog zu Spec 0018/0019, die aus demselben Grund ohne ADR auskamen). Die Trigger-/Modelltabelle aus ADR 0014/Spec 0020 bleibt vollständig unverändert; `test-engineer` bleibt bei Reviews auf Standardmodell.

**Ansatz:**
1. **TDD-Ritual-Check ersatzlos streichen** (`test-engineer.md`, Aufgabe 2, Punkt 1, aktuell Zeile 37): entfällt vollständig. Das darin enthaltene beobachtbare Symptom geht im bestehenden Testqualitäts-Punkt auf (siehe AK2). Aus sechs Punkten werden fünf.
2. **Datei insgesamt kompakter**: Die drei-Aufgaben-Struktur (Testkonzept pflegen / Review / Teststrategie-Konsultation) bleibt unverändert — sie deckt Daniels drei Kernpunkte bereits sauber ab. Gekürzt wird die ausschmückende Prosa drumherum: "Warum diese Rolle" auf einen knappen Absatz reduzieren; verbleibende Punkte in Aufgabe 2/1 auf ihre Kernaussage eindampfen; Aufgabe 3 (5 Schritte) knapper formulieren, inhaltlich beibehalten; Frontmatter-`description` nur sprachlich straffen, keine Trigger-Bedingungen verlieren. Kein hartes Zeilenlimit; Referenzpunkt ist die deutlich größere `developer.md` (~125 Zeilen) als oberer Rahmen, kein Minimalziel.
3. **`developer.md` Zeile 76 synchron ziehen**: "TDD eingehalten" aus der Aufzählung entfernen (siehe AK6).

**Betroffene Dateien:**
- `.claude/agents/test-engineer.md` (Kern: Streichung + Kompaktierung)
- `.claude/agents/developer.md` (Zeile 76, Konsistenz-Fix)
- Keine weitere Datei betroffen (per `grep -rn "TDD"` über `specs/architecture/0002-testkonzept.md`, alle `.claude/agents/*.md`, `.claude/skills/idea-sharpener/SKILL.md`, `docs/*.md` geprüft — keine andere Stelle verweist auf den gestrichenen Prüfpunkt).

**Umsetzungsreihenfolge für `developer`:**
1. `test-engineer.md` zuerst (Kern der Änderung).
2. `developer.md` Zeile 76 danach (Konsistenz-Fix, referenziert den in 1. geänderten Zustand).
3. Kein Lint-/Test-/Coverage-Lauf anwendbar (reine Markdown-Instruktionsdateien ohne ausführbaren Code) — Verifikation per AK7 (statischer Konsistenz-Check + synthetisches Dry-Run-Szenario).

## UI/UX

Nicht relevant. Reine Änderung an Agenten-Instruktionsdateien, keine App-Oberfläche betroffen — analog zu Spec 0018/0019/0020 direkt eingeordnet, ohne gesonderte `ux-ui-designer`-Konsultation.

## Security

Nicht relevant für einen eigenen `## Security`-Abschnitt — kein Anwendungscode, kein Datenmodell, keine Auth-/Secrets-Berührung, analog zu Spec 0018/0019.

Explizit geprüft: das für Spec 0020 dokumentierte Restrisiko (`specs/architecture/0003-securitykonzept.md`, getriggerte statt unbedingte `security-engineer`-Review-Abdeckung seit ADR 0014) bleibt unberührt — diese Spec ändert weder die Trigger-Tabelle noch die Modellzuweisung von `security-engineer`, der selbst nicht editiert wird. Kein neuer/aktualisierter Vermerk in `0003-securitykonzept.md` nötig.

Umsetzungshinweis (kein eigener Prüfpunkt, nur beim Straffen zu beachten): `test-engineer.md` Aufgabe 2, Punkt 2 enthält den Satz "Fällt dir dennoch etwas Sicherheitsrelevantes auf, erwähne es kurz, aber die vertiefte Prüfung ist seine Aufgabe" — ein schwaches, informelles Auffangnetz neben der eigentlichen `security-engineer`-Triggerlogik. Beim Kompaktieren sinngemäß erhalten (siehe AK4), nicht versehentlich mit-wegkürzen.

## Teststrategie

Reine Prozessänderung an einer Agenten-Instruktionsdatei (`.claude/agents/test-engineer.md`, synchron `developer.md` Zeile 76), kein Anwendungscode — `pytest`/`vitest` sind nicht einschlägig, kein Test-Runner interpretiert diese Markdown-Dateien. Verifikation zweistufig (proportionale, einmalige Entsprechung zum dauerhaften Vier-Ebenen-Muster aus `specs/architecture/0002-testkonzept.md`, Sektion "Agenten-Steuerungslogik selbst" — jene Sektion deckt spezifisch die Skip-/Modell-Trigger-Tabelle ab, die hier unverändert bleibt, daher nicht einschlägig):

1. **Statischer Konsistenz-Check** bei der Umsetzung: Phrase-Entfernung, Fünf-Punkte-Struktur, Zeilenzahl-/Inhaltsvergleich Aufgabe 1/3, Modelltabellen unverändert, `developer.md`-Sync — manueller Abgleich, kein Skript nötig für zwei kurze Dateien.
2. **Mindestens ein synthetisches Dry-Run-Review-Szenario** auf einem Wegwerf-Branch (Muster analog Spec 0007/0020: von `main` abgezweigt, nach Verifikation gelöscht) mit einem konstruierten Diff, der bewusst nachträglich wirkende Tests enthält.

Kein neues CI-Gate, kein neues Testframework. `specs/architecture/0002-testkonzept.md` wird durch diese Spec nicht berührt — weder Anwendungscode-Teststrategie noch die Skip-/Modell-Steuerungslogik sind betroffen (Trigger-/Modelltabellen bleiben laut AK5 unverändert).

## Offene Fragen

Keine.

## Out of Scope

- Änderung der Modellzuweisung für `test-engineer`-Reviews (z.B. Herabstufung auf Haiku) — von Daniel bei der Rückfrage im idea-sharpener-Gespräch explizit nicht gewählt; Spec 0020 hatte eine aggressivere Modell-Kalibrierung bereits zuvor bewusst zurückgestellt. Bleibt unverändert Standardmodell.
- Änderung der Trigger-Logik (welche Review-Agenten wann laufen) — unverändert, betrifft nur ADR 0014/Spec 0020.
- Kürzung anderer Projekt-Agenten (`architect`, `security-engineer`, `requirements-engineer`, `ux-ui-designer`, `developer`) — nur `test-engineer.md` (plus der eine Sync-Punkt in `developer.md`) ist Gegenstand dieser Spec; eine projektweite "alle Agenten kompaktieren"-Initiative wäre eine eigene, separate Idee.

## Entscheidungen

- **Ersatzlose Streichung statt Umformulierung** des TDD-Reihenfolge-Checks (architect-Konsultation, 2026-08-08): der Klammerzusatz des alten Prüfpunkts zerfiel bei genauem Lesen in zwei Teile, die beide bereits woanders abgedeckt waren — "Tests decken das beschriebene Verhalten ab" war wortgleich redundant zum direkt folgenden AK-Abdeckungs-Punkt, "wirken nicht nachträglich angepasst" gehörte inhaltlich zum bestehenden Testqualitäts-Punkt. Kein Wortlaut-Verlust, nur Verschiebung an die inhaltlich passende Stelle.
- **Keine neue ADR** (architect-Konsultation): reine Kürzung/Umformulierung bestehender Agenten-Instruktionen ohne neues System-/Datenmodell, neue Technologie oder externe Abhängigkeit — kein CLAUDE.md-Fall, analog Spec 0018/0019.
- **Kein hartes Zeilenlimit**, stattdessen `developer.md` (~125 Zeilen) als oberer Rahmen (architect-Konsultation): verhindert Übertreiben in Richtung eines willkürlichen Minimalziels, das Daniel bei der Rückfrage ausdrücklich nicht wollte ("sollte auch nicht übertrieben werden").
- **Priorität: Ideenspeicher** statt Hochstufung analog Spec 0020 (requirements-engineer-Vorschlag, von Daniel im idea-sharpener-Gespräch bestätigt, 2026-08-08): der Kontingent-Hebel, der Spec 0020 auf "Als Nächstes" hob, entfällt hier bewusst, da explizit keine Modelländerung Teil dieser Spec ist — übrig bleibt eine unabhängig sinnvolle, aber nicht dringende Aufräumarbeit.
- **`security-engineer`-Restrisiko-Vermerk aus Spec 0020 bleibt unverändert** (security-engineer-Konsultation, 2026-08-08): diese Spec rührt weder Trigger-Tabelle noch Modellzuweisung von `security-engineer` an.
- **`developer.md` Zeile 76 als eigenes Akzeptanzkriterium (AK6)** statt impliziter Nebenwirkung (test-engineer-Konsultation, 2026-08-08): stellt sicher, dass die in der Architektur geforderte Synchronisation nicht stillschweigend vergessen wird.
