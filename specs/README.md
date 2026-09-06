# Spezifikations-Workflow

Dieses Verzeichnis ist die "Single Source of Truth" für Anforderungen und Architektur-Entscheidungen von PhotoSort. Jede fachliche oder architekturrelevante Änderung beginnt hier — **nicht** direkt im Code.

## Struktur

- `architecture/` — das Testkonzept (`0002-testkonzept.md`, gepflegt vom `test-engineer`-Agenten), das Sicherheitskonzept (`0003-securitykonzept.md`, gepflegt vom `security-engineer`-Agenten), sowie das Design-System (`0004-design-system.md`, gepflegt vom `ux-ui-designer`-Agenten) — agenteninterne Arbeitsdokumente, die beim Review/bei der Umsetzungsplanung konsultiert werden. Wird laufend aktualisiert, wenn sich Teststrategie, Sicherheitslage oder Design ändern (kein Lifecycle wie bei Features, sondern lebende Dokumente). Die Systemarchitektur/Komponentenübersicht selbst lebt seit Spec 0019 unter [`docs/architecture.md`](../docs/architecture.md) (siehe Abgrenzung unten). Der `research-engineer`-Agent (Spec [`0028`](./features/0028-research-engineer-agent.md)/ADR [`0016`](./decisions/0016-research-engineer-agent.md)) hat bewusst **kein** eigenes Dokument hier — externe Recherche hat keinen projektinternen Dauerzustand, der als lebendes Dokument gepflegt werden müsste; jede Recherche ist für sich abgeschlossen, ihr Ergebnis lebt im jeweiligen Spec-Abschnitt/der jeweiligen ADR statt in einem eigenen Konzept-Dokument.
- `decisions/` — Architecture Decision Records (ADRs), verfasst vom `architect`-Agenten. Unveränderlich nach Annahme; eine spätere Änderung der Entscheidung erzeugt eine neue ADR, die die alte als "Superseded" markiert — bzw., wenn nur ein benannter Teil fällt, als "teilweise abgelöst" (siehe Abschnitt "ADR-Status" unten).
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

## ADR-Status: `Accepted`, `Superseded` — und der Teil-Vermerk

ADRs durchlaufen **nicht** den Feature-Lifecycle oben. Sie kennen zwei Statuswerte und einen Zusatzvermerk:

- **`Accepted`** — die Entscheidung gilt.
- **`Superseded`** — die Entscheidung als solche ist abgelöst. Die Statuszeile nennt die ablösende ADR und schlüsselt auf, was aus der alten weitergilt (Beispiele: ADR [`0017`](./decisions/0017-github-projects-v2-spec-sync.md), [`0052`](./decisions/0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md), [`0056`](./decisions/0056-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md)).
- **Teilweise abgelöst** — der Status bleibt `Accepted`, und eine eigene Kopfzeile `**Teilweise abgelöst:**` benennt die betroffenen Abschnitte und die ablösende ADR. Zulässig **nur**, wenn der abgelöste Teil nicht der Kern der Entscheidung ist und die überwiegende Mehrheit ihrer Abschnitte unverändert weitergilt — sonst gilt `Superseded`. Erstmals angewendet bei ADR [`0057`](./decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md) (zwei von neun Abschnitten abgelöst durch ADR [`0059`](./decisions/0059-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md), Abschnitt 7).

**Warum es diese dritte Form gibt:** Ein `Superseded` auf eine ADR, deren Kernentscheidung unverändert gilt, ist eine falsche Auskunft an den nächsten Leser — es schickt ihn auf die Suche nach einer Nachfolgeentscheidung, die es für den gesuchten Punkt nicht gibt. Die Gegenmaßnahme (die ablösende ADR wiederholt die weitergeltenden Abschnitte wortgetreu, damit `Superseded` ehrlich wird) erzeugt ein zweites Abbild derselben Entscheidung, und zwei Abbilder driften.

**Was der Teil-Vermerk nicht aufweicht:** Der Entscheidungstext einer angenommenen ADR bleibt unverändert. Angefasst wird ausschließlich der Kopf — dieselbe Stelle, die auch bei einem vollen `Superseded` angefasst wird, und der dafür vorgesehene Mechanismus. Wer einen Teil einer ADR ändern will, schreibt weiterhin eine neue ADR; er darf die alte nur nicht mehr falsch etikettieren müssen.

## Namenskonvention

`NNNN-kurzer-titel.md` (z.B. `0262-github-project-sync-tool-entfernen.md`), wobei `NNNN` je nach Verzeichnis unterschiedlich vergeben wird:

- **`features/`**: Die Nummer einer neuen Feature-Spec ist die Nummer ihres GitHub-Issues, auf vier Stellen aufgefüllt (die Spec zu Issue #262 heißt `0262-...`). Dadurch braucht es keine Zuordnung zwischen Spec- und Issue-Nummer — beide sind identisch (ADR [`decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md`](./decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md)). Die Dateiliste ist damit bewusst nicht mehr lückenlos fortlaufend; die Reihenfolge der Arbeit lebt im GitHub-Project-Board, nicht in der Nummer.
- **Bestandsschutz:** Die Specs `0001`–`0065` stammen aus der früheren, eigenständig fortlaufenden Nummerierung und behalten ihre Nummer. Bei ihnen weicht die Issue-Nummer ab; sie steht in der `**Bezug:**`-Zeile der jeweiligen Datei.
- **`decisions/` und `architecture/`**: unverändert fortlaufend nummeriert pro Verzeichnis (sie haben kein zugehöriges Issue).

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
