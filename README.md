# PhotoSort

Sortiert, kategorisiert und kuratiert Urlaubsfotos, die auf einer [OpenCloud](https://opencloud.eu)-Instanz liegen. Fotos werden projektbasiert organisiert (z.B. "Costa Rica"), können manuell bewertet werden (Favorit / Album-würdig / Verwerfen) oder per Hybrid-KI (lokale Heuristiken + optionale Cloud-Bewertung) automatisch für ein Album vorgeschlagen werden. Ausgewählte Fotos werden zurück nach OpenCloud exportiert.

Web-App, installierbar als PWA, gehostet per Docker Compose auf einem Homeserver.

## Wie dieses Projekt entwickelt wird

PhotoSort wird vollständig von KI (Claude Code) entwickelt. Die Rolle des Menschen ist die des Stakeholders: Anforderungen, Ideen und Bugs werden im Dialog oder über GitHub Issues beschrieben; die KI klärt Unklarheiten per Rückfrage, arbeitet testgetrieben und dokumentiert Entscheidungen. Der vollständige Workflow ist in [`CLAUDE.md`](./CLAUDE.md) beschrieben, die fachlichen und technischen Spezifikationen liegen unter [`specs/`](./specs/README.md).

## Quick Start (Entwicklung)

```bash
cp .env.example .env
docker compose up --build
```

- Backend: http://localhost:8000 (`/health`)
- Frontend: http://localhost:5173

### Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| `specs/` | Architektur, Entscheidungen (ADRs), Feature-Spezifikationen |
| `backend/` | FastAPI-Backend + Worker (Foto-Verarbeitung, KI-Scoring) |
| `frontend/` | React/Vite PWA |
| `.github/` | Issue-/PR-Templates, CI |

## Status

Frühe Aufbauphase. Siehe [`specs/features/`](./specs/features) für den aktuellen Stand der geplanten Features.
