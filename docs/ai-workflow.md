# Wie PhotoSort entwickelt wird

PhotoSort ist ein Experiment: die gesamte Entwicklung — von der ersten Idee bis zum
gemergten Pull Request — wird von KI-Agenten (Claude Code) durchgeführt. Der Mensch hinter
dem Projekt, Daniel, tritt dabei ausschließlich als Stakeholder auf: Er beschreibt
Anforderungen, Ideen und Bugs, beantwortet Rückfragen und gibt Anforderungen frei. Er schreibt
keinen Code und pflegt keine Dokumentation von Hand.

Das funktioniert, weil der Workflow bewusst kleinteilig und nachvollziehbar gehalten ist:
jede fachliche Änderung beginnt als Spezifikation, durchläuft ein festes Rollenmodell aus
spezialisierten Agenten und endet in einem klassischen, von CI abgesicherten Pull Request.
Nichts davon ist unsichtbare Magie — jeder Schritt ist als Text (Spec, ADR, Agenten-Definition)
im Repository nachlesbar.

## Spec first

Keine fachliche oder architekturrelevante Änderung entsteht direkt im Code. Stattdessen wird
zuerst eine Spezifikation unter [`specs/features/`](../specs/features) angelegt, die einen
Lifecycle durchläuft: `Proposed` (Erstentwurf) → `Accepted` (von Daniel freigegeben) →
`Implemented` (umgesetzt, mit Verweis auf den Pull Request). Architekturrelevante
Entscheidungen (neue Technologie, Datenmodell-Grundstruktur, externe Abhängigkeiten) werden
zusätzlich als Architecture Decision Record (ADR) unter [`specs/decisions/`](../specs/decisions)
festgehalten, bevor sie umgesetzt werden.

Bei Unklarheiten fragt die KI aktiv nach, statt zu raten — im Chat oder als Kommentar in einem
GitHub Issue. Erst wenn eine Spezifikation akzeptiert ist, beginnt die Implementierung.

## Ein Team spezialisierter Agenten

Statt eines einzelnen, allzuständigen KI-Entwicklers arbeitet ein Team spezialisierter
Claude-Agenten (definiert unter [`.claude/agents/`](../.claude/agents)), die jeweils ein festes
Aufgabengebiet und ein zugehöriges, lebendes Konzept-Dokument unter
[`specs/`](../specs/README.md) besitzen:

| Agent | Verantwortung | Konzept-Dokument |
|---|---|---|
| `requirements-engineer` | Roadmap & Priorisierung, Anforderungen verfeinern, Review auf Anforderungstreue (kein Scope Creep) | `specs/roadmap.md` |
| `architect` | Architekturentscheidungen (ADRs), Umsetzungsplanung, Review aus drei Blickwinkeln (Pragmatiker / Senior-Entwickler / Pedant) | [`docs/architecture.md`](./architecture.md), [`docs/setup.md`](./setup.md) |
| `ux-ui-designer` | Design-System, UI/UX-Ansatz pro Feature, UI/UX-Review (nur bei Frontend-Änderungen) | `specs/architecture/0004-design-system.md` |
| `test-engineer` | Testkonzept, Teststrategie pro Feature, testfokussiertes Review | `specs/architecture/0002-testkonzept.md` |
| `security-engineer` | Sicherheitskonzept, Security-Einschätzung pro Feature, sicherheitsfokussiertes Review | `specs/architecture/0003-securitykonzept.md` |
| `developer` | Setzt eine akzeptierte Feature-Spec testgetrieben um (TDD-Zyklus, Branch, Pull Request) | — |

Der `idea-sharpener`-Skill begleitet eine rohe Idee bis zur akzeptierten Feature-Spec und zieht
dabei die vier Fachspezialisten der Reihe nach hinzu. Der `developer`-Agent setzt eine
akzeptierte Spec um und lässt sie am Ende von allen zutreffenden Spezialisten parallel
reviewen:

![Workflow-Übersicht: Verfeinern (idea-sharpener) und Umsetzen (developer)](../specs/diagrams/workflow-overview.svg)

<sub>\* `ux-ui-designer` reviewt nur Feature-Branches mit Frontend-/UI-Änderungen.</sub>

<sub>Diagramm-Quelle: [`specs/diagrams/workflow-overview.d2`](../specs/diagrams/workflow-overview.d2), gerendert per `scripts/render-diagrams.sh` (siehe ADR [`decisions/0013-diagram-tooling-d2.md`](../specs/decisions/0013-diagram-tooling-d2.md)).</sub>

## Testgetrieben, mit hartem Gate

Jede Implementierung folgt strikt Test-Driven Development: Kein Code ohne vorher geschriebene,
zunächst fehlschlagende Tests. Ein Coverage-Gate in der CI erzwingt mindestens 80% Backend-Testabdeckung;
unterschreitet ein Pull Request diese Schwelle, kann er nicht gemergt werden.

## Zwei Arbeitsmodi

- **Interaktive Sessions:** Daniel bespricht Anforderungen, Ideen und Bugs direkt mit
  Claude Code im Repository — geeignet für Diskussion, Spec-Verfeinerung und größere oder
  mehrdeutige Themen.
- **Hintergrund-Automatisierung (Ausbaustufe):** GitHub Issues mit einer klar definierten,
  akzeptierten Spec können künftig von einem automatisiert laufenden Agenten selbstständig
  abgearbeitet werden, ohne dass Daniel live mitliest. Blockierende Unklarheiten werden dann
  als Issue-Kommentar zurückgemeldet statt geraten. Diese Automatisierung ist zum
  Zeitpunkt dieser Beschreibung noch nicht eingerichtet.

## Wo die eigentlichen Regeln stehen

Diese Seite erklärt das Prinzip für Außenstehende. Die tatsächlich verbindliche, maschinenlesbare
Regel-Quelle, nach der sich jeder Agent richtet, ist [`CLAUDE.md`](../CLAUDE.md) im Wurzelverzeichnis
des Repositories — im Verfassungsstil geschrieben und die einzige Quelle, die bei Widersprüchen
zwischen dieser Beschreibung und der tatsächlichen Praxis maßgeblich ist.
