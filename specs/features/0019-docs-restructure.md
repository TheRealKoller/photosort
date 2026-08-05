# 0019 - Doku-Restrukturierung: neuer `docs/`-Ordner, schlanke README

**Status:** Accepted
**Erstellt:** 2026-08-05
**Bezug:** Neue Idee aus interaktiver Session mit Daniel (2026-08-05), kein Inbox-Eintrag

## Ziel

Die bestehende Dokumentation ist über README.md (Projektbeschreibung, AI-Workflow-Kurzfassung, Agenten-Tabelle, Workflow-Diagramm, Setup-Anleitung, Demo-Stack-Anleitung, Projektstruktur) und `specs/architecture/0001-overview.md` (Projekt-/Komponentenübersicht mit ASCII-Diagramm) verteilt, README ist dadurch unübersichtlich lang. Diese Spec etabliert einen neuen Top-Level-Ordner `docs/` als zentrale Anlaufstelle mit drei Dokumenten (Setup, Architektur, AI-Workflow), reduziert README auf die wichtigsten Punkte + Links, und macht Doku-Pflege explizit Teil des Development-Workflows.

## User Story

Als Entwickler (Claude, im Auftrag von Daniel als Stakeholder) möchte ich eine dedizierte `docs/`-Ordnerstruktur mit Setup-Anleitung, Projekt-Doku (inkl. echtem D2-Komponentendiagramm) und einer eigenständig erzählenden AI-Workflow-Beschreibung, damit `README.md` schlank bleibt und sowohl Daniel als auch externe Besucher (z.B. auf GitHub) zielgruppengerechte Dokumentation vorfinden.

## Akzeptanzkriterien

- [ ] `docs/setup.md`, `docs/architecture.md`, `docs/ai-workflow.md` existieren; README verlinkt genau diese drei Dateien mit auflösbaren relativen Pfaden.
- [ ] `docs/setup.md` enthält den vollständig migrierten Inhalt der bisherigen README-Abschnitte "Quick Start (Entwicklung)" und "Lokal ausprobieren ohne echten OpenCloud-Server" (alle Codeblöcke, insbesondere der Warnhinweis "Nur lokal starten" zu Basic-Auth mit öffentlich bekannten Demo-Zugangsdaten/kein TLS/`127.0.0.1`-Bindung) — kein inhaltlicher Verlust.
- [ ] `docs/architecture.md` entsteht per `git mv specs/architecture/0001-overview.md docs/architecture.md` (Git-Historie bleibt über `git log --follow` nachvollziehbar) — ersetzt die alte Datei vollständig, keine Duplizierung. Status-Header "Living Document" und die im Dokument geführte Änderungshistorie bleiben erhalten.
- [ ] Der bisherige ASCII-Systemkontext-Block in `docs/architecture.md` ist durch `specs/diagrams/component-overview.d2`/`.svg` (D2-Tooling aus Spec 0018/ADR 0013, gerendert via `scripts/render-diagrams.sh`) ersetzt und enthält inhaltlich mindestens dieselben Komponenten/Beziehungen (Frontend, Backend, Worker, Postgres, Redis, OpenCloud + deren Verbindungen).
- [ ] `scripts/render-diagrams.sh` läuft mit jetzt zwei `.d2`-Dateien in `specs/diagrams/` in einem Lauf fehlerfrei durch (Regressionscheck für den `nullglob`-Array-Mechanismus bei mehreren Dateien).
- [ ] `docs/ai-workflow.md` ist ein neuer, eigenständig erzählender Text für ein externes Publikum (kein bloßer Verweis auf `CLAUDE.md`), der erklärt, wie PhotoSort vollständig von Claude Code entwickelt wird, und migriert dabei die bisherige Agenten-Tabelle sowie das Workflow-Diagramm (`specs/diagrams/workflow-overview.svg`) aus README (nicht dupliziert).
- [ ] `README.md` ist reduziert auf: kurze Projektbeschreibung, kurzen "Wie entwickelt"-Absatz mit Link auf `docs/ai-workflow.md`, Link auf `docs/setup.md`, Projektstruktur-Tabelle (inkl. neuer Zeile für `docs/`), Status — keine Setup-Details, keine Agenten-Tabelle, kein Workflow-Diagramm mehr.
- [ ] `CLAUDE.md` enthält eine neue explizite Regel: Architektur-/Setup-relevante Änderungen müssen die betroffene(n) `docs/`-Datei(en) im selben PR aktualisieren (Zuständigkeit weiterhin beim `architect`-Agenten). Wegweiser-Tabelle zeigt auf `docs/architecture.md`/`docs/setup.md`.
- [ ] `specs/README.md` verweist auf `docs/` mit klarer Abgrenzung: `specs/` = fachliche/technische Quelle der Wahrheit für Agenten (Features, ADRs, Roadmap, Testkonzept/Securitykonzept/Design-System), `docs/` = aufbereitete Doku für Nutzung/Außenwirkung.
- [ ] Alle **aktiven** Dokumente mit echtem Markdown-Hyperlink oder normativer Prosa-Erwähnung von `architecture/0001-overview.md` (README, CLAUDE.md, `specs/README.md`, `specs/TEMPLATE.md`, `specs/roadmap.md`, alle `.claude/agents/*.md`, `.claude/skills/idea-sharpener/SKILL.md`, `specs/architecture/0003-securitykonzept.md`, `specs/architecture/0004-design-system.md`, sowie die zwei Accepted-aber-nicht-implementierten Specs 0008 und 0016) zeigen danach auf `docs/architecture.md` mit korrekter, pro Datei neu berechneter Relativpfad-Tiefe (kein pauschales String-Replace).
- [ ] **Bereits Implemented-Feature-Specs** (0001, 0002, 0005, 0006, 0009 mit echtem Hyperlink; weitere mit reiner Prosa-Erwähnung) bleiben unverändert — historische Momentaufnahmen des Zustands zur jeweiligen Umsetzungszeit werden bewusst nicht nachträglich umgeschrieben, auch wenn dadurch die 5 echten Hyperlinks zu toten Links werden (siehe Entscheidungen/Out of Scope).
- [ ] Baseline-Grep (`grep -rn "architecture/0001-overview" --include="*.md" .`) vor der Änderung dokumentiert den Ausgangszustand; derselbe Grep danach liefert ausschließlich noch Treffer in den bewusst unveränderten Implemented-Specs.

## Datenmodell-Bezug

Nicht betroffen — reine Doku-/Repo-Struktur-Änderung, kein Anwendungscode, kein Datenmodell.

## Architektur / Umsetzung

**Ansatz:** Ein neuer Top-Level-Ordner `docs/` wird zentrale Anlaufstelle für aufbereitete Projekt-Dokumentation (Setup, Architektur, AI-Workflow), während `specs/` die fachliche/technische Quelle der Wahrheit für Agenten bleibt (Features, ADRs, Roadmap, sowie die drei agenteninternen Arbeitsdokumente Testkonzept/Securitykonzept/Design-System, die in `specs/architecture/` verbleiben). Keine neue ADR nötig — reine Doku-Reorganisation, keine neue Technologie, kein Datenmodell-Bezug.

**Abgrenzung `docs/` vs. `specs/`** (Faustregel für künftige Doku-Entscheidungen): Ist ein Dokument primär Entscheidungsgrundlage/Arbeitsmaterial für die Agenten selbst (wird beim Review/bei der Umsetzungsplanung konsultiert) → `specs/`. Ist es primär aufbereitete Erklärung für einen menschlichen Leser von außen oder für den Betrieb (Daniel beim lokalen Setup) → `docs/`. `docs/architecture.md` ist ein bewusster Sonderfall: es ersetzt `specs/architecture/0001-overview.md` komplett (nicht dupliziert), da dieselbe Übersicht für beide Zwecke dient.

**Betroffene/neue Dateien:**
- `docs/setup.md` (neu) — 1:1-Verschiebung der README-Abschnitte "Quick Start (Entwicklung)" und "Lokal ausprobieren ohne echten OpenCloud-Server".
- `docs/architecture.md` (neu, per `git mv specs/architecture/0001-overview.md docs/architecture.md`). Zusätzlich: ASCII-Systemkontext-Diagramm wird ersetzt durch `specs/diagrams/component-overview.d2` + `.svg` (Name nach Diagrammzweck, Konvention aus ADR 0013), gerendert über `scripts/render-diagrams.sh`.
- `docs/ai-workflow.md` (neu) — eigenständig erzählender Text (neuer Inhalt, kein Copy-Paste), migriert die Agenten-Tabelle und das Workflow-Diagramm (`specs/diagrams/workflow-overview.svg`, bereits vorhanden aus Spec 0018 — nur das einbettende Dokument wechselt).
- `README.md` — gekürzt (siehe Akzeptanzkriterien).
- `CLAUDE.md` — Wegweiser-Tabelle aktualisiert, neue explizite Doku-Pflege-Regel.
- `specs/README.md` — Abschnitt "Struktur": `0001-overview.md` aus der Aufzählung entfernen, Verweis auf `docs/architecture.md` + Abgrenzungstext `docs/` vs. `specs/`.
- `specs/TEMPLATE.md` — Verweis auf `architecture/0001-overview.md` → `docs/architecture.md`.
- `.claude/agents/architect.md`, `.claude/agents/security-engineer.md`, `.claude/agents/ux-ui-designer.md`, `.claude/agents/test-engineer.md`, `.claude/agents/developer.md`, `.claude/skills/idea-sharpener/SKILL.md` — Textverweise korrigiert.
- `specs/architecture/0003-securitykonzept.md`, `specs/architecture/0004-design-system.md` — dieselbe Textkorrektur (lebende Dokumente).
- Echte Hyperlink-Reparatur (Pfad, nicht Inhalt) in den zwei Accepted-Specs 0008 und 0016.
- **Bewusst unverändert:** reine Text-Erwähnungen in bereits Implemented-Feature-Specs (0001, 0002, 0005, 0006, 0009, sowie Specs 0008/0010–0018 mit "Nicht betroffen: ..."-Erwähnungen) — historische Momentaufnahmen, kein aktuell gültiger Verweis.

**Migrationsreihenfolge für `developer`:**
1. `grep -rn "0001-overview" .` (außerhalb `.git`) als definitive, aktuelle Trefferliste ausführen — die obige Liste als Ausgangspunkt, nicht als abschließend behandeln.
2. `docs/`-Ordner anlegen, `docs/setup.md` aus README befüllen (unabhängig, risikoarm).
3. `git mv specs/architecture/0001-overview.md docs/architecture.md`.
4. `specs/diagrams/component-overview.d2` erstellen (Übersetzung des ASCII-Blocks), mit `scripts/render-diagrams.sh` rendern, ASCII-Block in `docs/architecture.md` durch SVG-Einbettung ersetzen.
5. `docs/ai-workflow.md` neu verfassen (Text + migrierte Tabelle/Diagramm-Referenz).
6. `README.md` kürzen (hängt an 2/3/5, da es dorthin verlinkt — nicht vorher, sonst zeigen neue Links kurzzeitig ins Leere).
7. Alle Link-/Text-Referenzen aus der Trefferliste reparieren (korrekte Relativpfad-Tiefe pro Datei, kein pauschales String-Replace), danach erneuter Grep zur Kontrolle — verbleibende Treffer dürfen ausschließlich die bewusst unveränderten historischen Text-Erwähnungen sein.
8. `CLAUDE.md` um die neue Regel ergänzen.
9. Manuelle Kontrolle: Links lokal/auf GitHub-Preview stichprobenartig anklicken.

## UI/UX

Nicht relevant. Reine Entwickler-/Repo-Dokumentation, keine App-Oberfläche betroffen.

## Security

Nicht relevant. Reine Umstrukturierung von Markdown-Dateien, kein Anwendungscode, kein Endpunkt, kein Datenmodell, keine neue Abhängigkeit, keine neue Angriffsfläche. Einziger sicherheitsrelevanter Inhalt (Demo-Stack-Warnhinweis: Basic-Auth mit öffentlich bekannten Zugangsdaten, kein TLS, "nur lokal starten", `127.0.0.1`-Bindung) bleibt inhaltlich identisch bestehen, wechselt nur den Ort (README → `docs/setup.md`) — Migrations-Sorgfaltspflicht, kein neues Sicherheitsproblem. Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig.

## Teststrategie

Reines Doku-/Repo-Struktur-Feature, kein automatisiertes Testframework einschlägig. Verifikation über Review-Checkliste statt Assertions:

- **Existenz/Verlinkung:** `test -f` für die drei neuen Dateien, README-Links auflösbar.
- **`git mv` statt Kopieren+Löschen:** verifizierbar über `git log --follow --oneline docs/architecture.md`.
- **Diagramm-Vollständigkeit:** Review-Checkliste, dass `component-overview.d2`/`.svg` alle Komponenten/Beziehungen des alten ASCII-Blocks enthält — objektiv prüfbar. Die subjektive Optik-Frage bleibt wie bei Spec 0018 Daniels eigenes Urteil, kein Schwellenwert.
- **Render-Regression:** `scripts/render-diagrams.sh` mit zwei `.d2`-Dateien in einem Lauf testen (bisher nur mit einer Datei erprobt).
- **Link-Korrektur klassifiziert statt pauschal:** Baseline-Grep vor/nach der Änderung (siehe Akzeptanzkriterien) — kein generisches Markdown-Link-Checker-Tool eingeführt, da es ohnehin nur echte Hyperlinks erkennen würde, nicht die ebenso relevanten Prosa-Erwähnungen; bei einem Solo-Projekt mit seltenen Restrukturierungen lohnt sich die Tooling-Investition nicht.
- **README-Kürzung:** Positivliste (was bleibt) / Negativliste (was entfernt wird) statt Zeilen-Schwellenwert, Review-Checkliste.
- **`CLAUDE.md`-Regelergänzung:** reine Prozessregel für künftige PRs, Verifikation ist Eindeutigkeit des Texts (Dokumentations-Review) — kein CI-Gate dafür (schwer definierbare Heuristik "ist diese Änderung architekturrelevant", hohes False-Positive/Negative-Risiko für ein Solo-Projekt).

`specs/architecture/0002-testkonzept.md` wurde bereits um eine neue Sektion "Repo-weite Doku-Restrukturierung / Pfadänderungen (kein Anwendungscode)" ergänzt (test-engineer-Konsultation, 2026-08-05) — erstes Mal, dass ein zentrales, dutzendfach referenziertes Dokument im Projekt verschoben wird, braucht ein wiederverwendbares Verifikationsmuster.

## Entscheidungen

- **`docs/`-Ordner statt Erweiterung von `specs/`:** neue zentrale Anlaufstelle für aufbereitete Doku, getrennt von der fachlichen/technischen Agenten-Quelle in `specs/` (Schärfungsgespräch, 2026-08-05).
- **`docs/architecture.md` ersetzt `specs/architecture/0001-overview.md` komplett** statt eines separaten, schlankeren Dokuments daneben — eine Quelle statt zwei synchron zu haltende Kopien; `architect` pflegt künftig `docs/architecture.md` (Schärfungsgespräch, nach explizitem Abwägen der Alternative "neues Dokument daneben").
- **`docs/ai-workflow.md` ist neuer, eigenständig erzählender Text**, kein Verweis auf `CLAUDE.md` — bewusst andere Zielgruppe/Ton (Außenstehende/GitHub-Besucher vs. Verfassungsstil für Agenten) (Schärfungsgespräch, 2026-08-05).
- **Explizite neue Regel in `CLAUDE.md`** statt impliziter Erwartung — Doku-Pflege wird fester Teil des Development-Workflows, nicht nur stillschweigend erwartet (Schärfungsgespräch, 2026-08-05).
- **Historische Implemented-Specs bleiben unverändert**, auch wenn dadurch 5 echte Hyperlinks zu toten Links werden — nachträgliches Umschreiben würde die historische Aussage verfälschen, analog zur Unveränderlichkeit von ADRs nach Annahme (architect-Konsultation, 2026-08-05). Die zwei Accepted-aber-nicht-implementierten Specs (0008, 0016) werden dagegen aktualisiert, da sie noch aktive Umsetzungs-Anleitung sind.
- **Kein Markdown-Link-Checker-Tool eingeführt:** würde nur echte Hyperlinks erkennen, nicht die ebenso relevanten Prosa-Erwähnungen; Grep-gestützter manueller Schritt bleibt ohnehin nötig, Tooling-Investition lohnt sich nicht für ein Solo-Projekt mit seltenen Restrukturierungen (test-engineer-Konsultation, 2026-08-05).
- **In Ideenspeicher/niedrige Priorität eingeordnet:** wie Spec 0018 reine interne Doku-Verbesserung ohne App-Nutzer-Auswirkung (requirements-engineer-Konsultation, 2026-08-05). Baut auf Spec 0018 (Implemented, D2-Tooling) auf, vollständig entsperrt.

## Offene Fragen

Keine.

## Out of Scope

- Nachträgliches Umschreiben bereits Implemented-Feature-Specs, auch wenn deren Links auf `0001-overview.md` dadurch technisch tot werden (siehe Entscheidungen).
- Ein automatisiertes Markdown-Link-Checker-Tool/CI-Gate für tote Links oder für die neue `CLAUDE.md`-Doku-Pflege-Regel — bei Bedarf später per eigener Spec nachziehbar, falls die Regel in der Praxis wiederholt ignoriert wird.
