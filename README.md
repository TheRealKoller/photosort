# PhotoSort

Sortiert, kategorisiert und kuratiert Urlaubsfotos, die auf einer [OpenCloud](https://opencloud.eu)-Instanz liegen. Fotos werden projektbasiert organisiert (z.B. "Costa Rica"), können manuell bewertet werden (Favorit / Album-würdig / Verwerfen) oder per Hybrid-KI (lokale Heuristiken + optionale Cloud-Bewertung) automatisch für ein Album vorgeschlagen werden. Ausgewählte Fotos werden zurück nach OpenCloud exportiert.

Web-App, installierbar als PWA, gehostet per Docker Compose auf einem Homeserver.

## Wie dieses Projekt entwickelt wird

PhotoSort wird vollständig von KI (Claude Code) entwickelt. Die Rolle des Menschen ist die des Stakeholders: Anforderungen, Ideen und Bugs werden im Dialog oder über GitHub Issues beschrieben; die KI klärt Unklarheiten per Rückfrage, arbeitet testgetrieben und dokumentiert Entscheidungen. Eine ausführliche Beschreibung des Agenten-Teams und des Workflows steht unter [`docs/ai-workflow.md`](./docs/ai-workflow.md); die verbindlichen Regeln selbst in [`CLAUDE.md`](./CLAUDE.md), die fachlichen und technischen Spezifikationen unter [`specs/`](./specs/README.md).

## Loslegen

Anleitung zum lokalen Entwickeln und Ausprobieren (inkl. Demo-Stack ohne echten OpenCloud-Server) steht unter [`docs/setup.md`](./docs/setup.md). Für die optionale Cloud-Sehenswürdigkeit-Erkennung wird zusätzlich die Umgebungsvariable `ANTHROPIC_API_KEY` benötigt, sobald die Einwilligung dafür in einem Projekt aktiviert wird (Details ebenfalls in `docs/setup.md`).

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| [`docs/`](./docs/) | Aufbereitete Dokumentation: [Setup](./docs/setup.md), [Architektur](./docs/architecture.md), [AI-Workflow](./docs/ai-workflow.md) |
| `specs/` | Architektur, Entscheidungen (ADRs), Feature-Spezifikationen, [Roadmap](./specs/roadmap.md) |
| `backend/` | FastAPI-Backend + Worker (Foto-Verarbeitung, KI-Scoring) |
| `frontend/` | React/Vite PWA |
| `scripts/` | Eigenständiges Dev-/Demo-Tooling (z.B. `seed-opencloud-demo.py`), außerhalb der Produktiv-Codebasis |
| `.github/` | Issue-/PR-Templates, CI |

## Status

Frühe Aufbauphase. Siehe [`specs/features/`](./specs/features) für den aktuellen Stand der geplanten Features.
