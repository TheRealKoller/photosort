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

## Konventionen

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **PRs:** klein und fokussiert, referenzieren die zugehörige Spec/das Issue (siehe `.github/pull_request_template.md`). Nach dem Eröffnen wird immer ein Copilot-Review angefordert (`gh pr edit <PR> --add-reviewer "@copilot"`); sobald es vorliegt, werden die Findings bewertet und notwendige Fixes umgesetzt (siehe `developer`-Agent, Schritt 8).
- **Backend:** Python 3.12, FastAPI, `ruff` (Lint), `mypy --strict` (Typprüfung), `pytest` (Test).
- **Frontend:** React + TypeScript + Vite, `oxlint` (Lint), `tsc` (Typprüfung), `vitest` (Test).
- Keine Bilddaten der Familie werden je ins Repository committet — Fotos bleiben ausschließlich auf OpenCloud, lokal nur als Cache (siehe `.gitignore`).
- Secrets (App-Tokens, API-Keys) niemals im Code oder in Specs, nur über Umgebungsvariablen (`.env`, nie eingecheckt — siehe `.env.example`).

## Wegweiser

| Frage | Antwort in |
|---|---|
| Was soll gebaut werden? | `specs/features/` |
| Warum wurde X so entschieden? | `specs/decisions/` |
| Wie ist das System aufgebaut? | `specs/architecture/0001-overview.md` |
| Wie wird lokal entwickelt/getestet? | `README.md` |
