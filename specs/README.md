# Spezifikations-Workflow

Dieses Verzeichnis ist die "Single Source of Truth" für Anforderungen und Architektur-Entscheidungen von PhotoSort. Jede fachliche oder architekturrelevante Änderung beginnt hier — **nicht** direkt im Code.

## Struktur

- `architecture/` — Systemarchitektur, Datenmodell, Komponentenübersicht. Wird laufend aktualisiert, wenn sich die Architektur ändert (kein Lifecycle wie bei Features, sondern lebendes Dokument).
- `decisions/` — Architecture Decision Records (ADRs). Unveränderlich nach Annahme; eine spätere Änderung der Entscheidung erzeugt eine neue ADR, die die alte als "Superseded" markiert.
- `features/` — Feature-Spezifikationen. Durchlaufen den unten beschriebenen Lifecycle.

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
