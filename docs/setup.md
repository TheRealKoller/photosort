# Setup

Anleitung zum lokalen Entwickeln und Ausprobieren von PhotoSort.

## Quick Start (Entwicklung)

```bash
cp .env.example .env
docker compose up --build
```

- Backend: http://localhost:8000 (`/health`)
- Frontend: http://localhost:8080 (per `docker compose up`, statisch über nginx gebaut; der Vite-Dev-Server aus `npm run dev` läuft dagegen auf http://localhost:5173 — beide Origins sind in `CORS_ALLOWED_ORIGINS`/`VITE_API_BASE_URL` in `.env.example` standardmäßig berücksichtigt)

Bis auf `/health` und `POST /auth/login` verlangt die API ein gültiges Login (siehe [`specs/decisions/0005-auth-implementation.md`](../specs/decisions/0005-auth-implementation.md)). Die beiden Konten werden beim ersten Start per Alembic-Seed-Migration aus `AUTH_SEED_USER1_*`/`AUTH_SEED_USER2_*` (siehe `.env.example`) angelegt.

Das Frontend ruft die API cross-origin auf und braucht dafür zwei zusammenspielende Einstellungen aus `.env.example`: `VITE_API_BASE_URL` (Basis-URL der API aus Sicht des Browsers, wird zur Build-Zeit ins statische Frontend-Bundle eingebacken) und `CORS_ALLOWED_ORIGINS` (welche Frontend-Origin(s) das Backend akzeptiert). Die Defaults passen zueinander und funktionieren ohne weitere Anpassung für `docker compose up --build` auf `localhost`; für einen Deploy hinter einem eigenen Reverse-Proxy (TLS-Terminierung liegt außerhalb dieses Repos, siehe [`architecture.md`](./architecture.md)) beide Werte auf die tatsächlich öffentlich erreichbaren Origins anpassen.

### Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Cloud-Sehenswürdigkeit-Erkennung (optional)

Das Kriterium "Sehenswürdigkeit" (`landmark`, siehe [`specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](../specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md), [`specs/decisions/0025-cloud-landmark-erkennung.md`](../specs/decisions/0025-cloud-landmark-erkennung.md)) ist die einzige Stelle im Projekt, an der Fotos den Homeserver verlassen — ein direkter `httpx`-Aufruf gegen die Anthropic Messages API (Default) oder wahlweise gegen die Mistral Chat Completions API ([`specs/features/0054-mistral-provider-option-cloud-landmark.md`](../specs/features/0054-mistral-provider-option-cloud-landmark.md), [`specs/decisions/0031-mistral-provider-option-cloud-landmark.md`](../specs/decisions/0031-mistral-provider-option-cloud-landmark.md)). Für den Quick-Start/Demo-Stack **nicht nötig**: das Kriterium ist projektweit per Default deaktiviert (Einwilligungs-Schalter auf der Projekteinstellungsseite, `PUT /projects/{id}/cloud-landmark-consent`), ohne aktivierte Einwilligung wird kein API-Key verwendet und kein Netzwerkaufruf ausgeführt (die Env-Variable selbst wird wie jede andere `Settings`-Konfiguration bereits beim Prozessstart eingelesen, das ist unabhängig von Einwilligung/Provider).

Um das Kriterium tatsächlich zu nutzen, in `.env`:

- `LANDMARK_PROVIDER` wählt den Cloud-Provider — `anthropic` (Default, USA, DPA-/Datenschutzlage geklärt siehe ADR 0025) oder `mistral` (EU-hosted Alternative, Sitz Frankreich; DPA-/Zero-Data-Retention-Lage für Privatkonten laut Recherche unklar, bewusst akzeptiertes Restrisiko siehe ADR 0031). Eine reine Betreiber-/Deployment-Entscheidung, kein Feld pro Projekt.
- Je nach gewähltem Provider `ANTHROPIC_API_KEY` bzw. `MISTRAL_API_KEY` auf einen echten API-Key setzen (leer = Feature bleibt für alle Projekte unbenutzbar, auch bei aktivierter Einwilligung schlägt der Aufruf dann fehl).
- Optional `LANDMARK_API_CONCURRENCY` (Default `2`) anpassen — Obergrenze der parallelen Anfragen an den gewählten Provider, bewusst konservativ wegen realer Kosten pro Anfrage und externem Rate-Limit.

Danach die Einwilligung für das jeweilige Projekt einmalig über die neue Settings-Seite (`/projects/:id/settings`) aktivieren.

## Lokal ausprobieren ohne echten OpenCloud-Server

Für einen ersten Eindruck (Ordner-Browsing, Foto-Scan, automatische Bewertung) braucht es keinen
echten OpenCloud-Server und keine echten Zugangsdaten — ein optionales Compose-Overlay startet
zusätzlich einen echten [OpenCloud](https://opencloud.eu)-Single-Container
(`opencloudeu/opencloud-rolling`) mit fertigen Demo-Nutzern und befüllt ihn mit ein paar
mitgelieferten Beispielfotos (siehe [`specs/features/0009-local-opencloud-demo-stack.md`](../specs/features/0009-local-opencloud-demo-stack.md),
[`specs/decisions/0009-local-opencloud-demo-stack.md`](../specs/decisions/0009-local-opencloud-demo-stack.md)).
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
  [`specs/decisions/0010-demo-seed-script-as-compose-service.md`](../specs/decisions/0010-demo-seed-script-as-compose-service.md)),
  braucht also kein lokales Python.
- Danach: Frontend unter http://localhost:8080 öffnen, mit den `AUTH_SEED_USER1_*`-Werten aus
  `.env.demo.example` einloggen (Standard: `demo`/`demo-password-1`), ein Projekt gegen den
  Demo-Space anlegen und Scan/Bewertung ausprobieren — ohne Codeänderung, nur die andere `.env`.
