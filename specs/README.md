# Spezifikations-Workflow

Dieses Verzeichnis ist die "Single Source of Truth" für Anforderungen und Architektur-Entscheidungen von PhotoSort. Jede fachliche oder architekturrelevante Änderung beginnt hier — **nicht** direkt im Code.

## Struktur

- `architecture/` — Systemarchitektur, Datenmodell, Komponentenübersicht (`0001-overview.md`, gepflegt vom `architect`-Agenten), das Testkonzept (`0002-testkonzept.md`, gepflegt vom `test-engineer`-Agenten), das Sicherheitskonzept (`0003-securitykonzept.md`, gepflegt vom `security-engineer`-Agenten), sowie das Design-System (`0004-design-system.md`, gepflegt vom `ux-ui-designer`-Agenten). Wird laufend aktualisiert, wenn sich Architektur, Teststrategie, Sicherheitslage oder Design ändern (kein Lifecycle wie bei Features, sondern lebende Dokumente).
- `decisions/` — Architecture Decision Records (ADRs), verfasst vom `architect`-Agenten. Unveränderlich nach Annahme; eine spätere Änderung der Entscheidung erzeugt eine neue ADR, die die alte als "Superseded" markiert.
- `features/` — Feature-Spezifikationen. Durchlaufen den unten beschriebenen Lifecycle.
- `roadmap.md` — Priorisierung und Status der geplanten Features im Überblick, gepflegt vom `requirements-engineer`-Agenten. Lebendes Dokument, kein Ersatz für die einzelnen Spec-Dateien, sondern die Einordnung/Reihenfolge darüber.

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

Das Root-[`README.md`](../README.md) (außerhalb von `specs/`, lokales Setup/Betrieb) wird ebenfalls vom `architect`-Agenten gepflegt — als operative Kehrseite von `architecture/0001-overview.md`.
