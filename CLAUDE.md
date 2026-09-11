# CLAUDE.md — Verfassung für die Entwicklung von PhotoSort

PhotoSort wird vollständig von KI (Claude Code) entwickelt. Dieses Dokument definiert Rollen, Workflow und Standards, damit die Codebasis auch nach langer, überwiegend autonomer Entwicklung wartbar, nachvollziehbar und korrekt bleibt.

## Rollenmodell

- **Daniel (Stakeholder):** beschreibt Anforderungen, Ideen und Bugs — im Chat (interaktive Sessions) oder als GitHub Issue. Trifft Produktentscheidungen, wenn die KI nachfragt. Gibt Specs frei (Status `Proposed` → `Accepted`).
- **Claude (Entwickler):** einziger Entwickler des Projekts. Verantwortlich für Spec-Erstellung/-Verfeinerung, Implementierung, Tests, Dokumentation und Entscheidungsfindung innerhalb des durch Specs/ADRs gesteckten Rahmens.

## Grundprinzip: Spec first

Keine fachliche oder architekturrelevante Änderung ohne zugehörige Spec unter `specs/`.

1. Eine Anforderung (Chat oder Issue) wird als Feature-Spec unter `specs/features/` festgehalten (Status `Proposed`), falls noch keine passende existiert.
2. **Bei Unklarheiten: Rückfrage an Daniel** (Chat-Rückfrage oder Issue-Kommentar) — nicht raten, keine impliziten Annahmen zu Produktentscheidungen treffen. Technische Detailentscheidungen innerhalb einer bereits akzeptierten Spec darf die KI eigenständig treffen und dokumentieren.
3. Erst wenn die Spec `Accepted` ist, beginnt die Implementierung.
4. Architekturrelevante Entscheidungen (neue Technologie, Datenmodell-Grundstruktur, externe Abhängigkeiten) werden vor der Umsetzung als ADR in `specs/decisions/` festgehalten.
5. Nach Fertigstellung: Spec-Status auf `Implemented` setzen, Verweis auf den PR ergänzen.

Der vollständige Spec-Lifecycle und die Konventionen stehen in [`specs/README.md`](./specs/README.md).

## Test-Driven Development (strikt)

- Keine Implementierung ohne vorher geschriebene, zunächst fehlschlagende Tests.
- Kein PR ohne Tests für die geänderte/neue Funktionalität.
- Coverage-Gate in CI: Backend ≥ 80% (`--cov-fail-under=80`), darf nicht unterschritten werden.
- CI (`.github/workflows/ci.yml`) muss grün sein, bevor ein PR gemerged wird.

## Workflow-Modi

PhotoSort wird in zwei Modi weiterentwickelt:

- **Interaktive Sessions:** Daniel bespricht Anforderungen/Ideen/Bugs direkt mit Claude Code in diesem Repo. Gut geeignet für Diskussion, Spec-Verfeinerung, größere oder mehrdeutige Themen.
- **Hintergrund-Automatisierung (Ausbaustufe):** GitHub Issues mit klar definierter, akzeptierter Spec können von einem automatisiert laufenden Agent selbstständig abgearbeitet werden. Blockierende Unklarheiten werden als Issue-Kommentar zurückgemeldet statt geraten. Diese Automatisierung ist zum Zeitpunkt des Projekt-Setups noch nicht eingerichtet und ein separater Folgeschritt.
  - **Issue-Freigabe-Policy** (technisch noch nicht durchgesetzt, da die Automatisierung selbst noch nicht existiert): Issues, deren Autor nicht Daniels eigener GitHub-Account ist, dürfen von der künftigen Automatisierung erst bearbeitet werden, nachdem Daniel das Label `approved-for-agent` vergeben hat. Von Daniel selbst erstellte Issues benötigen das Label nicht. Maßgeblich ist der Label-**Zustand zum Zeitpunkt der automatisierten Bearbeitung** — ein zwischenzeitlich wieder entferntes Label gilt nicht mehr als Freigabe, unabhängig davon, ob es früher einmal vergeben war. Die eigentliche technische Prüflogik (Label-Abfrage vor Bearbeitung) ist Teil der künftigen Automatisierungs-Spec, nicht dieser Policy-Vorgabe.

## Konventionen

- **GitHub-Zugriff:** Jeder Zugriff auf Issues, Board und Pull Requests läuft über eine
  Operation des Skills `github-access` — das ist die einzige Stelle im Repository, an der ein
  solcher Zugriff steht. Andere Dateien nennen ausschließlich die Operations-ID. Jede Skill-
  und Agenten-Datei spricht ihre GitHub-Erlaubnisstufe aus (lesend und schreibend / nur
  lesend / kein GitHub-Zugriff). Rein lokales `git` ist davon unberührt.
- **Commits:** Conventional Commits — zehn zulässige Typen: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `build:`, `ci:`, `perf:`, `revert:`.
- **PR-Titel:** trägt dieselbe Form wie eine Commit-Nachricht: `typ(scope)!: Beschreibung`, mit einem der zehn Typen oben, Scope und `!` optional, Kleinschreibung des Typs, Doppelpunkt plus genau ein Leerzeichen plus nicht-leere Beschreibung. Grund: Das Repository squasht mit `COMMIT_OR_PR_TITLE` — der PR-Titel wird zum Titel des Merge-Commits auf `main`, und genau diesen wertet `release-please` aus. Ein Titel ohne zulässiges Präfix wird **still** übergangen: kein Changelog-Eintrag, kein Versions-Bump, keine Fehlermeldung; nach dem Merge ist das nicht mehr korrigierbar. Der Workflow `.github/workflows/pr-titel.yml` (Job-Schlüssel und damit Name des Checks: pr-titel) prüft das bei jedem `opened`/`edited`/`reopened`/`synchronize` und wird rot, wenn der Titel die Form verfehlt.
- **PRs:** klein und fokussiert, referenzieren die zugehörige Spec/das Issue (siehe `.github/pull_request_template.md`). Vor der PR-Erstellung durchläuft der Feature-Branch die Review-Phase über die `review-*`-Skills (Hauptsession, koordiniert vom `review`-Skill statt fünf parallelen Review-Subagenten). Nach dem Eröffnen wird ein Copilot-Review angefordert (Operation `copilot-review-anfordern`), außer der PR ändert ausschließlich Doku-/Spec-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) ohne jede Code-Datei — dann entfällt der Schritt vollständig; sobald ein angefordertes Review vorliegt, werden die Findings bewertet und notwendige Fixes umgesetzt (siehe Skill `ship-feature`/Orchestrator, nicht mehr der `developer`-Agent selbst).
  **Eine Ausnahme, und nur diese eine:** Ein Pull Request, der aus einem Penpot-Entwurfsrundenlauf entsteht (Skill `ship-entwurf`), durchläuft **weder** die Review-Phase **noch** ein angefordertes Copilot-Review. Ein Entwurf wird durch Hinsehen beurteilt, und die Design-Datei, an der er hängt, kann kein Prüfer dieses Projekts lesen. Getragen wird das von einer geschlossenen Pfad-Zulassungsmenge (`design/penpot/**`, `frontend/penpot/**`, `specs/**` — jeder Pfad außerhalb hält den Ablauf an), zwei zusätzlichen Halte-Prüfungen auf demselben Diff, der unverändert laufenden CI und davon, dass Daniel merged.
- **Backend:** Python 3.12, FastAPI, `ruff` (Lint), `mypy --strict` (Typprüfung), `pytest` (Test).
- **Frontend:** React + TypeScript + Vite, `oxlint` (Lint), `tsc` (Typprüfung), `vitest` (Test).
- Keine Bilddaten der Familie werden je ins Repository committet — Fotos bleiben ausschließlich auf OpenCloud, lokal nur als Cache (siehe `.gitignore`).
- Secrets (App-Tokens, API-Keys) niemals im Code oder in Specs, nur über Umgebungsvariablen (`.env`, nie eingecheckt — siehe `.env.example`).
- **Diagramme:** einheitlich mit [D2](https://d2lang.com) (`--sketch`-Modus) statt Mermaid erzeugen. Quelle + gerendertes SVG liegen nebeneinander unter `specs/diagrams/<name>.d2`/`.svg` und werden beide eingecheckt; Generierung über `scripts/render-diagrams.sh`.
- **Skills/Agents:** enthalten keine Verweise auf ADRs/Specs, die nur der historischen Begründung einer Regel dienen — die Regel selbst steht vollständig im Text, das "warum/wie kam es dazu" nicht. Ein Verweis auf eine andere Datei bleibt erlaubt, wenn er funktional nötig ist (die Datei muss gelesen, gegen sie geprüft, oder sie muss gepflegt werden, um die Aufgabe zu erfüllen).

## Werkzeugwahl bei Dateiarbeit

**Vorgabe:** Dateien werden im Regelfall über die dedizierten Werkzeuge gelesen, geändert und angelegt — das Lese-Werkzeug zum Lesen, das Änderungs-Werkzeug zum Ändern, das Schreib-Werkzeug zum Anlegen und vollständigen Ersetzen, die Such-Werkzeuge zum Suchen.

**Grund:** Eine gezielte Änderung über das Änderungs-Werkzeug scheitert **laut**, wenn die zu ersetzende Stelle nicht eindeutig ist; eine Ersetzung über die Shell greift in derselben Lage **still** daneben — sie trifft die erste Fundstelle, oder alle, oder keine, und meldet in allen drei Fällen Erfolg. Dazu kommen die Quoting-Fallen: Ein Heredoc mit nicht maskiertem Inhalt expandiert `$…` und Backticks, ein `sed`-Ausdruck mit ungeschütztem `&` oder `/` schreibt etwas anderes als gemeint. Ausdrücklich **nicht** der Grund ist Kontextsparsamkeit — ein gezielter Ausschnitt ist sparsamer als das vollständige Einlesen.

**Shell ist die bessere Wahl bei:** diesen drei Fällen — sie sind benannt, damit eine Abweichung begründet statt beiläufig ist:

- Versionsverwaltung, Paketmanager, Testläufe, Builds (`git status`, `npm run lint`, `pytest`) — dafür gibt es kein dediziertes Werkzeug.
- gezieltem Lesen eines Ausschnitts einer großen Datei — zum Sichten, nie als Ersatz einer mechanischen Prüfung: Unsichtbare Steuerzeichen sieht kein Blick.
- mehreren zusammengehörigen Schritten, die sich in einem Aufruf bündeln lassen.

**Bündelung:** Wo die Shell zum Einsatz kommt, werden zusammengehörige Aufrufe in **einem** Aufruf abgesetzt statt als Kette einzelner.

**Vorrang:** Diese Vorgabe gilt auch gegen einen Hinweis der Arbeitsumgebung, der von sich aus zur Shell für Dateiarbeit rät; eine Abweichung wird benannt, nicht stillschweigend vollzogen.

**Hintergrund-Läufe:** Lehnt die Arbeitsumgebung eine Änderung am geteilten Arbeitsstand ab, wird der isolierte Arbeitsstand hergestellt, statt auf die Shell auszuweichen.

**Unberührt:** Freitext, der in ein GitHub-Artefakt gelangt (Titel, Bodys, Kommentare), fällt nicht unter diesen Abschnitt, sondern unter Härtungsregel 4.1 in `github-access` — immer über eine Datei, nie als Zeichenkette in einer Kommandozeile. Das ist ein **Verbot, kein Default**: Keiner der oben genannten Gegenfälle gilt dort, auch die Bündelung mehrerer Schritte in einem Aufruf nicht.

## Doku-Pflege

Architektur- oder Setup-relevante Änderungen (neue Komponente, geändertes Datenmodell, neuer
lokaler Setup-Schritt, neue Umgebungsvariable) müssen die betroffene(n) `docs/`-Datei(en)
(`docs/architecture.md`, `docs/setup.md`) im selben Pull Request aktualisieren, nicht in einem
späteren Nachzieh-Commit. Zuständig bleibt dafür der `architect`-Agent (siehe auch
`.claude/agents/architect.md`). `docs/ai-workflow.md` ändert sich dagegen nur, wenn sich der
Workflow/das Rollenmodell selbst ändert, nicht bei jedem Feature.

## Wegweiser

| Frage | Antwort in |
|---|---|
| Was soll gebaut werden? | `specs/features/` |
| Warum wurde X so entschieden? | `specs/decisions/` |
| Wie ist das System aufgebaut? | [`docs/architecture.md`](./docs/architecture.md) |
| Wie wird lokal entwickelt/getestet? | [`docs/setup.md`](./docs/setup.md) |
