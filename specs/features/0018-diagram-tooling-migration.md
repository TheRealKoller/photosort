# 0018 - Diagramm-Tooling: Migration von Mermaid zu D2

**Status:** Implemented ([PR #29](https://github.com/TheRealKoller/photosort/pull/29))
**Erstellt:** 2026-08-05
**Bezug:** Idee aus `specs/inbox/0003-bessere-diagramm-generierung-als-mermaid.md`, geschärft in interaktiver Session mit Daniel (2026-08-05); Inbox-Notiz nach Aufnahme in diese Spec gelöscht, daher hier nur noch als Text statt als Link genannt.

## Ziel

Das einzige bisher existierende Diagramm im Repository — das Workflow-Flowchart in `README.md` (Mermaid, live gerendert von GitHubs Markdown-Viewer) — wirkt sowohl optisch generisch als auch beim Rendern auf GitHub zu groß/unhandlich. Diese Spec etabliert eine generelle Richtlinie samt Werkzeugwahl für alle künftigen Diagramme im Projekt (README, `specs/architecture/`, künftige Specs/ADRs) und migriert das bestehende Diagramm als ersten Anwendungsfall. Werkzeugwahl und Begründung stehen in ADR [`decisions/0013-diagram-tooling-d2.md`](../decisions/0013-diagram-tooling-d2.md).

## User Story

Als Entwickler (Claude, im Auftrag von Daniel als Stakeholder) möchte ich eine dokumentierte Richtlinie plus etabliertes Tooling für Diagramme im gesamten Projekt, damit neue Diagramme durchgängig optisch stimmig und kompakt sind — statt wie das bestehende Mermaid-Flowchart generisch und unhandlich groß zu wirken.

## Akzeptanzkriterien

- [x] Eine ADR (`decisions/0013-diagram-tooling-d2.md`) dokumentiert die Werkzeugwahl (D2) mit begründetem Trade-off gegenüber Mermaid, PlantUML und Graphviz — bereits erledigt (architect-Konsultation, 2026-08-05).
- [ ] `scripts/render-diagrams.sh` existiert, iteriert über `specs/diagrams/*.d2`, ruft `d2 --sketch <name>.d2 <name>.svg` auf, und erzeugt daraus reproduzierbar (strukturell/inhaltlich gleich, nicht notwendigerweise byte-identisch — `--sketch` streut ohne fixierten Seed einen zufälligen Hand-Zeichen-Jitter ein) ein SVG.
- [ ] Fehlt das `d2`-Binary im `PATH`, bricht das Skript sauber ab (Exit ≠ 0) mit einer Fehlermeldung inkl. Link zur offiziellen D2-Installationsanleitung, statt undefiniert zu scheitern.
- [ ] Ist `specs/diagrams/` leer (kein `.d2` vorhanden), läuft das Skript ohne Fehler durch (kein Bash-Glob-Fallstrick, bei dem `for f in *.d2` ohne `nullglob` einmal mit dem literalen String `*.d2` iteriert).
- [ ] Sowohl die `.d2`-Quelldatei als auch das gerenderte `.svg` werden im selben Commit eingecheckt (kein `.gitignore`-Ausschluss für `specs/diagrams/*.svg`).
- [ ] Das bestehende Mermaid-Diagramm in `README.md` ist nach `specs/diagrams/workflow-overview.d2`/`.svg` migriert; `README.md` bindet das SVG per Markdown-Bild-Referenz ein statt eines ` ```mermaid `-Codeblocks.
- [ ] Vorher/Nachher-Vergleich (Screenshot des aktuellen Mermaid-Renderings auf github.com neben dem migrierten README mit eingebettetem SVG, gleiche Browserbreite/Zoomstufe) zeigt sichtbar (a) eine weniger generische Optik und (b) einen geringeren vertikalen Platzverbrauch. Abnahme erfolgt durch Daniels eigenes Urteil beim Betrachten im PR, kein numerischer Schwellenwert (siehe Entscheidungen).
- [ ] `CLAUDE.md` und `specs/README.md` verweisen kurz auf ADR 0013 (Ablageort, Generierungsmechanismus), damit künftige Diagramme (auch von anderen Agenten) die Konvention automatisch befolgen.

## Datenmodell-Bezug

Nicht betroffen — reine Doku-/Tooling-Konvention, kein Anwendungscode, kein Datenmodell.

## Architektur / Umsetzung

**Ansatz:** D2 (`--sketch`-Modus) löst Mermaid als Diagramm-Tool ab, siehe [`decisions/0013-diagram-tooling-d2.md`](../decisions/0013-diagram-tooling-d2.md). Diagramme werden als Text-Quelle gepflegt und als SVG vorgerendert eingecheckt statt live im Markdown-Viewer gerendert.

**Konventionen:**
- Quelldateien: `specs/diagrams/<kebab-case-name>.d2`
- Gerenderte Bilder: `specs/diagrams/<kebab-case-name>.svg` (gleicher Name, neben der Quelle)
- Beide Dateien werden eingecheckt, kein Live-Rendering mehr im Markdown.
- Generierung über neues Skript `scripts/render-diagrams.sh` (Bash, unabhängig vom bestehenden Python-Paket unter `scripts/`), iteriert über `specs/diagrams/*.d2`, ruft `d2 --sketch <name>.d2 <name>.svg` auf, bricht mit Fehlermeldung + Link zur D2-Installationsanleitung ab, falls `d2` nicht im `PATH` ist. Kein CI-Job, keine Docker-Compose-Integration (reines lokales Doku-Tooling).

**Betroffene/neue Dateien:**
- `specs/decisions/0013-diagram-tooling-d2.md` (neu, bereits angelegt)
- `scripts/render-diagrams.sh` (neu)
- `specs/diagrams/workflow-overview.d2` + `.svg` (neu, migriertes README-Diagramm)
- `README.md` (Mermaid-Codeblock durch Markdown-Bild-Referenz auf das SVG ersetzen)
- `CLAUDE.md` (Konventionen-Abschnitt: kurzer Verweis auf ADR 0013)
- `specs/README.md` (kurzer Verweis auf ADR 0013)

**Migrationsplan für das bestehende README-Diagramm:**
1. `specs/diagrams/workflow-overview.d2` anlegen — Übersetzung des bestehenden Mermaid-Flowcharts (Subgraphs `Refine`/`Implement` → D2-Container) in D2-Syntax.
2. Mit `scripts/render-diagrams.sh` nach `specs/diagrams/workflow-overview.svg` rendern.
3. Mermaid-Codeblock in `README.md` durch das eingebettete SVG ersetzen (Fußnote zu `ux-ui-designer`s bedingtem Review bleibt als Text erhalten).
4. Visuell prüfen (lokal/GitHub-Preview): (a) weniger generisch als vorher, (b) kompakter beim Rendern.
5. `CLAUDE.md`/`specs/README.md` um den kurzen Verweis auf ADR 0013 ergänzen.

**Reihenfolge für `developer`:** Skript zuerst (testbar unabhängig vom Inhalt: mit einem Minimal-`.d2` prüfen, dass SVG entsteht bzw. Fehlermeldung bei fehlendem Binary erscheint) → danach das eigentliche Migrations-Diagramm → danach README/CLAUDE.md/specs/README.md-Verweise.

Kein Update an `specs/architecture/0001-overview.md` nötig — Diagramm-Tooling verändert keine Systemkomponente/kein Datenmodell, sondern ist eine Doku-Konvention.

## UI/UX

Nicht relevant. Reine Entwickler-Dokumentation/Repo-Tooling, keine App-Oberfläche für Daniel/seine Frau betroffen.

## Security

Nicht relevant. Reines lokales Dev-Tooling: kein Netzwerkzugriff zur Laufzeit, keine CI-/Docker-Compose-Integration, keine Eingabe von außen (Diagramm-Quellen werden ausschließlich von Daniel/Claude im Repo gepflegt), kein Bezug zu Auth/Datenmodell/Secrets. Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig. Hygiene-Hinweis (kein Risiko, nur Best Practice): `d2`-Binary über offizielle GitHub-Releases von `terrastruct/d2` installieren.

## Teststrategie

Kein Anwendungscode im klassischen Sinn betroffen. Für `scripts/render-diagrams.sh` (einzige Logik: PATH-Check + Schleife über `*.d2`) wird bewusst **kein** neues Bash-Testframework eingeführt — unverhältnismäßig für ein kurzes Skript ohne nennenswerte Verzweigung. Stattdessen drei benannte manuelle Smoke-Test-Szenarien vor Merge:

1. Happy Path (`d2` installiert, ≥1 `.d2`-Datei vorhanden) → SVG entsteht/aktualisiert sich, Exit 0.
2. `d2` fehlt im `PATH` → sauberer Abbruch, Exit ≠ 0, Fehlermeldung + Link zur Installationsanleitung.
3. Leeres `specs/diagrams/` (kein `.d2` vorhanden) → kein Fehler durch den klassischen Bash-Glob-Fallstrick (`for f in *.d2` ohne `nullglob` iteriert sonst einmal mit dem literalen String `*.d2`).

Die beiden visuellen Akzeptanzkriterien ("weniger generisch", "kompakter") sind nicht automatisiert testbar; Verifikation über Vorher/Nachher-Screenshot-Vergleich mit expliziter Abnahme durch Daniels eigenes Urteil, kein numerischer Schwellenwert (siehe Entscheidungen). Dokumentations-Referenzen (`CLAUDE.md`/`specs/README.md`) werden per Review-Checkliste geprüft.

`specs/architecture/0002-testkonzept.md` wurde bereits um eine neue Sektion "Reine Bash-Wrapper-Skripte ohne Testframework (`scripts/*.sh`)" ergänzt (test-engineer-Konsultation, 2026-08-05) — dies ist das erste Bash-Skript des Projekts, bestehende Muster passten nicht direkt.

## Entscheidungen

- **Generelle Richtlinie statt Einzelfix:** Daniel hat sich bewusst dafür entschieden, jetzt eine vollständige neue Tool-Entscheidung zu treffen (statt nur das eine bestehende Mermaid-Diagramm zu verbessern), obwohl aktuell nur ein Diagramm existiert — zahlt sich aus, sobald weitere Diagramme dazukommen (Schärfungsgespräch, 2026-08-05, nach explizitem Gegenwind zu Aufwand-vs-Nutzen).
- **D2 statt PlantUML/Graphviz:** löst das Optik-Problem am direktesten (kuratierte Themes, `--sketch`-Modus), bleibt vollständig CLI-generierbar. Installationsreibung (kein npm-/PyPI-Paket, eigenständiges Go-Binary) bewusst in Kauf genommen gegenüber Graphviz' sauberer `npm`-Integration, da die Optik explizit Daniels Hauptbeschwerde war (architect-Konsultation, siehe ADR 0013).
- **Kein numerischer Schwellenwert für "weniger generisch"/"kompakter":** Daniels eigenes Urteil beim Vorher/Nachher-Vergleich reicht als Abnahme — passt zum bisherigen Projektmuster für rein visuelle/Geschmackskriterien (test-engineer-Konsultation, 2026-08-05).
- **Kein CI-Check auf Quelle-Bild-Konsistenz:** würde ein D2-Binary in CI voraussetzen, nur um ein noch nicht eingetretenes Risiko abzudecken — bei Bedarf später per neuer ADR nachziehbar (architect-Konsultation, siehe ADR 0013).
- **In Ideenspeicher/Priorität "niedrig" eingeordnet:** reine interne Tooling-/Doku-Hygiene ohne Nutzer-Auswirkung, rangiert daher unter jedem Eintrag mit echter Nutzer-/Sicherheits-/Betriebsrelevanz (requirements-engineer-Konsultation, 2026-08-05).

## Offene Fragen

Keine.

## Out of Scope

- Automatisiertes CI-Gate, das Quelldatei-vs-Bild-Drift erzwingt — kann als spätere, eigene Spec nachgezogen werden, falls es zum Problem wird.
- Rückwirkende Pflicht, allen bisher rein textbasierten Architektur-Docs (0001–0004) jetzt ein Diagramm zu spendieren.
