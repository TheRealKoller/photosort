# Spezifikations-Workflow

Dieses Verzeichnis ist die "Single Source of Truth" für Anforderungen und Architektur-Entscheidungen von PhotoSort. Jede fachliche oder architekturrelevante Änderung beginnt hier — **nicht** direkt im Code.

## Struktur

- `architecture/` — das Testkonzept (`0002-testkonzept.md`, gepflegt vom `test-engineer`-Agenten), das Sicherheitskonzept (`0003-securitykonzept.md`, gepflegt vom `security-engineer`-Agenten), sowie das Design-System (`0004-design-system.md`, gepflegt vom `ux-ui-designer`-Agenten) — agenteninterne Arbeitsdokumente, die beim Review/bei der Umsetzungsplanung konsultiert werden. Wird laufend aktualisiert, wenn sich Teststrategie, Sicherheitslage oder Design ändern (kein Lifecycle wie bei Features, sondern lebende Dokumente). Die Systemarchitektur/Komponentenübersicht selbst lebt seit Spec 0019 unter [`docs/architecture.md`](../docs/architecture.md) (siehe Abgrenzung unten). Der `research-engineer`-Agent (Spec [`0028`](./features/0028-research-engineer-agent.md)/ADR [`0016`](./decisions/0016-research-engineer-agent.md)) hat bewusst **kein** eigenes Dokument hier — externe Recherche hat keinen projektinternen Dauerzustand, der als lebendes Dokument gepflegt werden müsste; jede Recherche ist für sich abgeschlossen, ihr Ergebnis lebt im jeweiligen Spec-Abschnitt/der jeweiligen ADR statt in einem eigenen Konzept-Dokument.
- `decisions/` — Architecture Decision Records (ADRs), verfasst vom `architect`-Agenten. Unveränderlich nach Annahme; eine spätere Änderung der Entscheidung erzeugt eine neue ADR, die die alte als "Superseded" markiert.
- `features/` — Feature-Spezifikationen. Durchlaufen den unten beschriebenen Lifecycle.

Priorität und Status offener Arbeit werden nativ im GitHub-Project-Board gepflegt (dort setzt Daniel die Priorität direkt), nicht in einer eingecheckten Datei. Der `requirements-engineer`-Agent berät dazu (Empfehlung), pflegt aber keine Übersichtsdatei.

## Feature-Lifecycle

```
Proposed → Accepted → Implemented → (ggf.) Superseded
```

- **Proposed**: Erstentwurf, oft von der KI aus einem Stakeholder-Gespräch oder Issue abgeleitet. Enthält typischerweise einen Abschnitt "Offene Fragen".
- **Accepted**: Stakeholder (Daniel) hat die Spec freigegeben, offene Fragen sind geklärt. Erst ab hier wird implementiert.
- **Implemented**: Umgesetzt und über Tests abgesichert. Verweist auf den/die PR(s).
- **Superseded**: Durch eine neuere Spec abgelöst; Verweis auf die Nachfolge-Spec.

## Namenskonvention

Fortlaufend nummeriert pro Verzeichnis: `NNNN-kurzer-titel.md` (z.B. `0001-opencloud-project-connection.md`).

## Regeln für die KI

1. Keine Implementierung einer Anforderung ohne zugehörige Spec im Status *Accepted*.
2. Bei Unklarheiten in einer Spec: Rückfrage an den Stakeholder (Chat oder Issue-Kommentar), nicht raten.
3. Architekturrelevante Entscheidungen (Technologie, Datenmodell-Grundstruktur, externe Abhängigkeiten) werden als ADR in `decisions/` festgehalten, bevor sie umgesetzt werden.
4. Jede Spec-Änderung ist ein eigener, nachvollziehbarer Commit.

Siehe [`TEMPLATE.md`](./TEMPLATE.md) für das Feature-Spec-Format.

## Diagramme

Alle Diagramme im Projekt (README, hier unter `architecture/`, künftige Specs/ADRs) werden mit [D2](https://d2lang.com) statt Mermaid erzeugt (ADR [`decisions/0013-diagram-tooling-d2.md`](./decisions/0013-diagram-tooling-d2.md)). Quelldateien liegen unter `specs/diagrams/<kebab-case-name>.d2`, das gerenderte SVG daneben unter demselben Namen; beide Dateien werden eingecheckt. Generierung lokal über `scripts/render-diagrams.sh` (setzt ein installiertes `d2`-Binary voraus, siehe Skript-Fehlermeldung für den Installationslink).

## Siehe auch

Das Root-[`README.md`](../README.md) sowie [`docs/`](../docs/) (außerhalb von `specs/`, aufbereitete Doku für Nutzung/Außenwirkung: Setup, Architektur, AI-Workflow) werden ebenfalls vom `architect`-Agenten gepflegt — als operative Kehrseite der fachlichen/technischen Quelle der Wahrheit hier in `specs/`.

## `docs/` vs. `specs/`

`specs/` ist die fachliche/technische Quelle der Wahrheit für die Agenten selbst (Features, ADRs, sowie die drei agenteninternen Arbeitsdokumente Testkonzept/Securitykonzept/Design-System). `docs/` ist aufbereitete Dokumentation für Nutzung/Außenwirkung (Setup-Anleitung, Architekturübersicht, AI-Workflow-Beschreibung für Außenstehende) — siehe [`docs/architecture.md`](../docs/architecture.md), [`docs/setup.md`](../docs/setup.md), [`docs/ai-workflow.md`](../docs/ai-workflow.md).
