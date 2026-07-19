# 0001 - Technologie-Stack

**Status:** Accepted
**Datum:** 2026-07-19

## Kontext

PhotoSort wird als Docker-Compose-Anwendung auf einem CPU-only-Homeserver betrieben, soll Bildverarbeitung/lokale KI-Heuristiken ausführen können, eine als PWA installierbare Web-Oberfläche bieten und komplett von einer KI entwickelt/gewartet werden. Der Stakeholder hat keine Technologie-Präferenz vorgegeben.

## Entscheidung

- **Backend:** Python 3.12, FastAPI, SQLAlchemy + Alembic, Postgres.
- **Hintergrund-Jobs:** Redis + `arq`.
- **Frontend:** React + TypeScript + Vite, `vite-plugin-pwa`, Vitest + React Testing Library.
- **Monorepo:** `backend/` und `frontend/` in einem Repository, gemeinsam über `docker-compose.yml` orchestriert.

## Begründung

- Python bietet das mit Abstand ausgereifteste Ökosystem für die benötigte Bildverarbeitung (Pillow, OpenCV, imagehash, mediapipe) und lässt sich gut mit async I/O für WebDAV-Calls kombinieren.
- FastAPI ist gut dokumentiert, typisiert (Pydantic) und testfreundlich — wichtig, da die Codebasis primär von einer KI gewartet wird und gute Trainingsdaten/Konventionen die Wartbarkeit erhöhen.
- React/Vite/TypeScript ist der verbreitetste, am besten dokumentierte Stack für PWAs und bietet ausgereifte Tooling-Unterstützung (Vitest, vite-plugin-pwa).
- Ein Monorepo hält Specs, Backend und Frontend im selben Kontext — relevant, da die KI beide Seiten eigenständig entwickelt.

## Konsequenzen

- Zwei Sprach-Ökosysteme (Python + TypeScript) müssen gepflegt werden (zwei Lint-/Test-Toolchains in CI).
- Bildverarbeitung läuft serverseitig, nicht im Client — Backend/Worker müssen für CPU-only-Betrieb performant genug sein (siehe [0002](./0002-hybrid-ai-scoring.md)).
