# PhotoSort

Sortiert, kategorisiert und kuratiert Urlaubsfotos, die auf einer [OpenCloud](https://opencloud.eu)-Instanz liegen. Fotos werden projektbasiert organisiert (z.B. "Costa Rica"), können manuell bewertet werden (Favorit / Album-würdig / Verwerfen) oder per Hybrid-KI (lokale Heuristiken + optionale Cloud-Bewertung) automatisch für ein Album vorgeschlagen werden. Ausgewählte Fotos werden zurück nach OpenCloud exportiert.

Web-App, installierbar als PWA, gehostet per Docker Compose auf einem Homeserver.

## Wie dieses Projekt entwickelt wird

PhotoSort wird vollständig von KI (Claude Code) entwickelt. Die Rolle des Menschen ist die des Stakeholders: Anforderungen, Ideen und Bugs werden im Dialog oder über GitHub Issues beschrieben; die KI klärt Unklarheiten per Rückfrage, arbeitet testgetrieben und dokumentiert Entscheidungen. Der vollständige Workflow ist in [`CLAUDE.md`](./CLAUDE.md) beschrieben, die fachlichen und technischen Spezifikationen liegen unter [`specs/`](./specs/README.md).

### Die Agenten

Statt eines einzelnen KI-Entwicklers arbeitet ein Team spezialisierter Claude-Agenten (definiert unter [`.claude/agents/`](./.claude/agents/)), die jeweils ein festes Aufgabengebiet und ein zugehöriges, lebendes Konzept-Dokument unter [`specs/`](./specs/README.md) besitzen:

| Agent | Verantwortung | Konzept-Dokument |
|---|---|---|
| `requirements-engineer` | Roadmap & Priorisierung, Anforderungen verfeinern, Review auf Anforderungstreue (kein Scope Creep) | `specs/roadmap.md` |
| `architect` | Architekturentscheidungen (ADRs), Umsetzungsplanung, Review aus drei Blickwinkeln (Pragmatiker / Senior-Entwickler / Pedant) | [`specs/architecture/0001-overview.md`](./specs/architecture/0001-overview.md), dieses README |
| `ux-ui-designer` | Design-System, UI/UX-Ansatz pro Feature, UI/UX-Review (nur bei Frontend-Änderungen) | `specs/architecture/0004-design-system.md` |
| `test-engineer` | Testkonzept, Teststrategie pro Feature, testfokussiertes Review | `specs/architecture/0002-testkonzept.md` |
| `security-engineer` | Sicherheitskonzept, Security-Einschätzung pro Feature, sicherheitsfokussiertes Review | `specs/architecture/0003-securitykonzept.md` |
| `developer` | Setzt eine akzeptierte Feature-Spec testgetrieben um (TDD-Zyklus, Branch, Pull Request) | — |

Der `idea-sharpener`-Skill begleitet eine rohe Idee bis zur akzeptierten Feature-Spec und zieht dabei die vier Fachspezialisten der Reihe nach hinzu. Der `developer`-Agent setzt eine akzeptierte Spec um und lässt sie am Ende von allen zutreffenden Spezialisten parallel reviewen:

![Workflow-Übersicht: Verfeinern (idea-sharpener) und Umsetzen (developer)](./specs/diagrams/workflow-overview.svg)

<sub>\* `ux-ui-designer` reviewt nur Feature-Branches mit Frontend-/UI-Änderungen.</sub>

<sub>Diagramm-Quelle: [`specs/diagrams/workflow-overview.d2`](./specs/diagrams/workflow-overview.d2), gerendert per `scripts/render-diagrams.sh` (siehe ADR [`decisions/0013-diagram-tooling-d2.md`](./specs/decisions/0013-diagram-tooling-d2.md)).</sub>

## Quick Start (Entwicklung)

```bash
cp .env.example .env
docker compose up --build
```

- Backend: http://localhost:8000 (`/health`)
- Frontend: http://localhost:8080 (per `docker compose up`, statisch über nginx gebaut; der Vite-Dev-Server aus `npm run dev` läuft dagegen auf http://localhost:5173 — beide Origins sind in `CORS_ALLOWED_ORIGINS`/`VITE_API_BASE_URL` in `.env.example` standardmäßig berücksichtigt)

Bis auf `/health` und `POST /auth/login` verlangt die API ein gültiges Login (siehe [`specs/decisions/0005-auth-implementation.md`](./specs/decisions/0005-auth-implementation.md)). Die beiden Konten werden beim ersten Start per Alembic-Seed-Migration aus `AUTH_SEED_USER1_*`/`AUTH_SEED_USER2_*` (siehe `.env.example`) angelegt.

Das Frontend ruft die API cross-origin auf und braucht dafür zwei zusammenspielende Einstellungen aus `.env.example`: `VITE_API_BASE_URL` (Basis-URL der API aus Sicht des Browsers, wird zur Build-Zeit ins statische Frontend-Bundle eingebacken) und `CORS_ALLOWED_ORIGINS` (welche Frontend-Origin(s) das Backend akzeptiert). Die Defaults passen zueinander und funktionieren ohne weitere Anpassung für `docker compose up --build` auf `localhost`; für einen Deploy hinter einem eigenen Reverse-Proxy (TLS-Terminierung liegt außerhalb dieses Repos, siehe [`specs/architecture/0001-overview.md`](./specs/architecture/0001-overview.md)) beide Werte auf die tatsächlich öffentlich erreichbaren Origins anpassen.

### Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Lokal ausprobieren ohne echten OpenCloud-Server

Für einen ersten Eindruck (Ordner-Browsing, Foto-Scan, automatische Bewertung) braucht es keinen
echten OpenCloud-Server und keine echten Zugangsdaten — ein optionales Compose-Overlay startet
zusätzlich einen echten [OpenCloud](https://opencloud.eu)-Single-Container
(`opencloudeu/opencloud-rolling`) mit fertigen Demo-Nutzern und befüllt ihn mit ein paar
mitgelieferten Beispielfotos (siehe [`specs/features/0009-local-opencloud-demo-stack.md`](./specs/features/0009-local-opencloud-demo-stack.md),
[`specs/decisions/0009-local-opencloud-demo-stack.md`](./specs/decisions/0009-local-opencloud-demo-stack.md)).
Reine Entwicklungs-/Ausprobier-Infrastruktur — kein selbstgebauter Mock, sondern derselbe
Server/Codepfad (Graph-API + WebDAV) wie im echten Betrieb, nur mit `OPENCLOUD_*`-Werten, die auf
den lokalen Container statt auf eine echte Instanz zeigen.

**Nur lokal starten:** Der Demo-Container ist bewusst schwach abgesichert (Basic-Auth mit
öffentlich bekannten Demo-Zugangsdaten, kein TLS) — niemals auf einem gemeinsam genutzten oder
öffentlich erreichbaren Host verwenden.

```bash
cp .env.demo.example .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml --profile seed run --rm seed
```

- Der erste Befehl startet den kompletten Stack (Postgres, Redis, Backend, Worker, Frontend) plus
  den `opencloud-demo`-Container, dessen Port explizit auf `127.0.0.1` gebunden ist.
- Der zweite Befehl seedet den Demo-Space mit Beispielfotos: `scripts/seed-opencloud-demo.py`
  wartet aktiv, bis der Container bereit ist, legt einen Ordner an und lädt die Fotos per WebDAV
  hoch — idempotent, ein erneuter Lauf erzeugt keine Duplikate. Läuft als eigener, einmaliger
  Compose-Service im selben Docker-Netzwerk wie `opencloud-demo` (siehe
  [`specs/decisions/0010-demo-seed-script-as-compose-service.md`](./specs/decisions/0010-demo-seed-script-as-compose-service.md)),
  braucht also kein lokales Python.
- Danach: Frontend unter http://localhost:8080 öffnen, mit den `AUTH_SEED_USER1_*`-Werten aus
  `.env.demo.example` einloggen (Standard: `demo`/`demo-password-1`), ein Projekt gegen den
  Demo-Space anlegen und Scan/Bewertung ausprobieren — ohne Codeänderung, nur die andere `.env`.

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| `specs/` | Architektur, Entscheidungen (ADRs), Feature-Spezifikationen |
| `backend/` | FastAPI-Backend + Worker (Foto-Verarbeitung, KI-Scoring) |
| `frontend/` | React/Vite PWA |
| `scripts/` | Eigenständiges Dev-/Demo-Tooling (z.B. `seed-opencloud-demo.py`), außerhalb der Produktiv-Codebasis |
| `.github/` | Issue-/PR-Templates, CI |

## Status

Frühe Aufbauphase. Siehe [`specs/features/`](./specs/features) für den aktuellen Stand der geplanten Features.
