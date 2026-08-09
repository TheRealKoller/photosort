# 0029 - Roadmap: Umstellung auf drei Prioritätsstufen (Hoch/Mittel/Niedrig)

**Status:** Implemented ([PR #59](https://github.com/TheRealKoller/photosort/pull/59))
**Erstellt:** 2026-08-09
**Bezug:** Idea-Sharpening-Gespräch mit Daniel am 2026-08-09 (direkte Chat-Idee, keine Inbox-Notiz beteiligt)

## Ziel

`specs/roadmap.md` kategorisiert offene Specs aktuell in vier Stufen: "Jetzt", "Als Nächstes", "Später", "Ideenspeicher". Daniel empfindet diese Einordnung als unpassend — sie vermischt Dringlichkeit mit einer vagen Zeitachse und hat in der Praxis zu Fehleinordnungen geführt (z.B. stand Spec 0028 zuletzt unter "Ideenspeicher", obwohl sie aktiv umgesetzt wurde). Diese Spec ersetzt die vier Kategorien durch drei echte Prioritätsstufen — **Hoch, Mittel, Niedrig** — und legt fest, wann eine Anforderung eine Priorität bekommen muss: Ideen und ungeschärfte Stories bleiben unpriorisiert in `specs/inbox/`; sobald eine Story geschärft ist (Spec mit Status `Proposed`/`Accepted`), bekommt sie sofort eine der drei Stufen, ohne Zwischenzustand.

## User Story

Als Requirements Engineer (KI) möchte ich Anforderungen in `specs/roadmap.md` mit genau einer von drei klaren Prioritätsstufen (Hoch/Mittel/Niedrig) statt der bisherigen vier Kategorien einordnen, damit jede geschärfte Anforderung eindeutig und ohne Zwischenzustand priorisiert ist und Daniel die Dringlichkeit verschiedener Vorhaben unmittelbar vergleichen kann.

## Akzeptanzkriterien

- [x] `specs/roadmap.md` verwendet für alle offenen Specs (Status `Proposed`/`Accepted`) ausschließlich die drei Kategorien **Hoch/Mittel/Niedrig** — sowohl als Tabellen-Abschnittsüberschriften unter "Status auf einen Blick" ("Offen — Hoch"/"Offen — Mittel"/"Offen — Niedrig") als auch als `###`-Zwischenüberschriften im Abschnitt "## Priorisierung". `grep -n "Offen — \(Jetzt\|Als Nächstes\|Später\|Ideenspeicher\)" specs/roadmap.md` liefert danach 0 Treffer.
- [x] Kein leerer "Offen — Mittel"-Abschnitt, solange keine offene (Proposed/Accepted) Spec dieser Stufe existiert — analog zum bisherigen Fehlen einer "Offen — Als Nächstes"-Tabelle. Die `###`-Zwischenüberschrift "Mittel" unter "## Priorisierung" bleibt trotzdem bestehen, auch wenn dort aktuell nur bereits-Implemented-Rückblicke stehen (z.B. Specs 0020/0024).
- [x] Migration der bestehenden offenen Einträge nach dem mit Daniel bestätigten Mapping: Jetzt → Hoch, Als Nächstes → Mittel, Später + Ideenspeicher → gemeinsam Niedrig. Konkret: Spec 0027 → Hoch, Spec 0004 → Niedrig, Spec 0028 → Niedrig (0004 und 0028 in derselben "Offen — Niedrig"-Tabelle, Reihenfolge: erst die ehemaligen "Später"-, dann die ehemaligen "Ideenspeicher"-Einträge).
- [x] Historische Inline-Begründungstexte in bestehenden Spec-Bullets (z.B. "**Priorisierung — Ideenspeicher:** analog zu Spec 0018/0019...") werden **nicht** rückwirkend umgeschrieben — nur Markdown-Überschriften (`##`/`###`) und Tabellenabschnitts-Label ("Offen — X") ändern sich. Ein Diff-Review zeigt ausschließlich Überschriften-/Tabellenzeilen-Änderungen, keine Wortänderungen innerhalb bestehender Fließtext-Absätze.
- [x] Jede Spec mit Status `Proposed` oder `Accepted` steht nach der Migration in **genau einer** "Offen — *"-Tabelle — kein Zwischenzustand "hat Spec, aber keine Priorität", kein Doppel-Eintrag.
- [x] Wechselt eine Spec von `Proposed`/`Accepted` auf `Implemented`, entfällt ihre Priorität ersatzlos (Umzug nach "Bereits umgesetzt", das war schon bisher so und bleibt unverändert).
- [x] Nebenbefund-Bereinigung: Spec 0025 (Status **Implemented**, PR #56) steht aktuell fälschlich noch in einer "Offen — *"-Tabelle statt unter "Bereits umgesetzt" — wird im selben Zug korrigiert. Nach der Migration steht keine Zeile mit Status `Implemented` mehr in einer "Offen — *"-Tabelle.
- [x] Inbox-Einträge (`specs/inbox/*.md`, noch nicht durch `idea-sharpener` geschärft) bleiben unpriorisiert — der Abschnitt "Inbox — ungeschärfte Ideen" bleibt strukturell unverändert.
- [x] `.claude/agents/requirements-engineer.md`, Aufgabe 1: "grobe Priorität (z.B. Jetzt / Als Nächstes / Später / Ideenspeicher)" wird zu einem geschlossenen Pflicht-Set "eine von drei Prioritätsstufen (Hoch / Mittel / Niedrig)" — kein "z.B." oder sonstiger Offenheits-Hinweis mehr.
- [x] `.claude/skills/idea-sharpener/SKILL.md`, Schritt 9: bekommt einen Satz, der eine verpflichtende Bestätigung/Finalisierung der in Schritt 2 vom `requirements-engineer` vorläufig vergebenen Priorität verlangt — unmittelbar bevor der Roadmap-Eintrag mit dem finalen Spec-Pfad nachgetragen wird. Keine stillschweigende Übernahme des vorläufigen Werts, kein impliziter Default.

## Datenmodell-Bezug

Keines — reine Prozess-/Doku-Änderung am Spec-/Roadmap-Umgang selbst, kein PhotoSort-System-/Datenmodell betroffen.

## Architektur / Umsetzung

Reine Textbearbeitung dreier bestehender Dateien, kein Code, kein Datenmodell, kein neuer Diagrammbezug (verifiziert: `specs/diagrams/` enthält nur `component-overview.d2/.svg` und `workflow-overview.d2/.svg` — die frühere `roadmap-overview.d2`-Kanban-Grafik aus Spec 0026 wurde bereits in einer früheren Iteration wieder entfernt und lebt nicht wieder auf). Keine ADR nötig — reine Doku-/Prozesskonvention, keine neue Technologie, kein Datenmodell, keine externe Abhängigkeit (kein ADR-Kriterium aus `CLAUDE.md` erfüllt).

**Betroffene Dateien, in dieser Reihenfolge:**

1. `.claude/agents/requirements-engineer.md` — Zeile mit "z.B. Jetzt / Als Nächstes / Später / Ideenspeicher" auf das geschlossene Set Hoch/Mittel/Niedrig anpassen. Zuerst, weil es die Instruktionsquelle ist, an der sich die folgenden Anpassungen begrifflich orientieren.
2. `.claude/skills/idea-sharpener/SKILL.md`, Schritt 9 — Satz zur verpflichtenden Prioritäts-Bestätigung ergänzen.
3. `specs/roadmap.md` — der eigentliche Migrationsschritt, zuletzt:
   - `## Status auf einen Blick`: "Offen — Jetzt" → "Offen — Hoch"; "Offen — Später" und "Offen — Ideenspeicher" zu einer gemeinsamen Tabelle "Offen — Niedrig" zusammenführen (Zeilenreihenfolge beibehalten).
   - Spec 0025 aus der "Offen"-Tabelle entfernen, nach "Bereits umgesetzt" verschieben (analog zu den übrigen Einträgen dort, inkl. PR-#56-Link).
   - Konkrete Migration: 0027 → Hoch, 0004 → Niedrig, 0028 → Niedrig (Tabellen + Prosa-Abschnittsüberschriften).
   - `## Priorisierung`: "### Jetzt" → "### Hoch", "### Als Nächstes" → "### Mittel", "### Später" + "### Ideenspeicher" → gemeinsam "### Niedrig" (Bullet-Reihenfolge beibehalten).

**Sequenzierung:** Ursprünglich als Risiko identifiziert (PR #57 zu Spec 0028 könnte `roadmap.md` parallel ändern) — verifiziert und entfallen: PR #57 ist bereits gemerged, kein offener PR rührt `roadmap.md` an. Migration kann direkt in einem PR erfolgen.

## UI/UX

Nicht relevant — bestätigt vom `ux-ui-designer`: reine interne Prozess-/Doku-Dateien, keine PhotoSort-App-UI betroffen.

## Security

Nicht relevant — bestätigt vom `security-engineer`: reine Markdown-Prozessänderung ohne Code, Auth-Logik, externe Schnittstelle, Secrets, Eingabevalidierung oder Datensichtbarkeitsänderung.

## Teststrategie

Reine Markdown-Prozessänderung ohne Anwendungscode (analog Spec 0025/0028) — kein `pytest`/`vitest` anwendbar, keine Ergänzung von `specs/architecture/0002-testkonzept.md` nötig (das etablierte Muster "Dokumentations-Review" deckt diesen Fall bereits generisch ab, kein neues eigenständiges Testmuster). Verifikation über manuellen Konsistenz-Check:

1. `grep -n "Offen — \(Jetzt\|Als Nächstes\|Später\|Ideenspeicher\)" specs/roadmap.md` → 0 Treffer.
2. Manueller Abgleich jeder Zeile in den "Offen — *"-Tabellen gegen den tatsächlichen Status der referenzierten Spec-Datei — keine `Implemented`-Zeile mehr in einer Offen-Tabelle (deckt insbesondere die Spec-0025-Altlast ab).
3. Manueller Abgleich, dass jede `Proposed`/`Accepted`-Spec unter `specs/features/` in genau einer Offen-Tabelle auftaucht (Soll bei Umsetzung: 0004, 0027, 0028).
4. Diff-Review, beschränkt auf Überschriften-/Tabellenzeilen — keine Wortänderungen innerhalb bestehender Fließtext-Begründungen.
5. Grep/Review von `.claude/agents/requirements-engineer.md` (kein "z.B." mehr) und `.claude/skills/idea-sharpener/SKILL.md` Schritt 9 (verpflichtende Prioritäts-Bestätigung vorhanden).

## Entscheidungen (2026-08-09, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Auslöser:** Daniels grundsätzliches Unbehagen mit der bisherigen Zeitachsen-artigen Kategorisierung, verstärkt durch einen konkreten Fehleinordnungsfall (Spec 0028 stand zuletzt unter "Ideenspeicher", obwohl sie aktiv umgesetzt wurde).
- **Priorität dieser Idee selbst — Niedrig:** reine interne Prozess-/Tooling-Verbesserung ohne jede Auswirkung auf Daniel/seine Frau als Endnutzer der App, analog zu den Präzedenzfällen 0018/0019/0025/0028.
- **Mapping der vier alten auf die drei neuen Stufen — per Rückfrage entschieden:** Jetzt → Hoch, Als Nächstes → Mittel, Später + Ideenspeicher → gemeinsam Niedrig (statt der Alternative "Jetzt+Als Nächstes → Hoch" oder einer komplett fallweisen Neubewertung ohne festes Mapping).
- **Historische Begründungstexte bleiben unverändert:** nur Strukturüberschriften wandern, nicht die Wortwahl in bereits verfasster Prosa vergangener Roadmap-Einträge — Konsistenz mit dem bisherigen Umgang mit historischen Einträgen (z.B. Spec 0026, dessen Grafik-Rücknahme ebenfalls nur als Nachtrag dokumentiert wurde, nicht rückwirkend umgeschrieben).
- **Sequenzierung nach PR #57 zunächst als Risiko eingeplant, dann verifiziert und verworfen:** PR #57 (Spec 0028) war zum Zeitpunkt der Architektur-Konsultation bereits gemerged, kein Merge-Konflikt-Risiko mehr.
- **Status-Nachtrag (2026-08-09, Roadmap-Konsistenz-Audit):** [PR #59](https://github.com/TheRealKoller/photosort/pull/59) hat alle zehn Akzeptanzkriterien vollständig umgesetzt (verifiziert per Diff-Review gegen jedes einzelne AK, inkl. `grep`-Probe), der Spec-Status wurde danach jedoch nicht wie in `CLAUDE.md`/`specs/README.md` vorgesehen auf `Implemented` gesetzt — reiner Statuspflege-Nachtrag durch den `requirements-engineer`, keine inhaltliche Änderung.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

Weitere Prioritätsabstufungen (z.B. "Hoch-Kritisch"); automatisierte Neuberechnung/Vorschlag von Prioritäten; rückwirkendes Umschreiben historischer Begründungstexte in bereits abgeschlossenen Roadmap-Einträgen; Änderung an D2-Diagramm-Tooling (nicht betroffen, siehe Architektur-Abschnitt).
