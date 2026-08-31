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

### Design-Labor (temporär, Spec 0287)

Zum Vergleich der fünf Gestaltungsrichtungen gibt es einen **dev-only Zweiteinstieg** neben der
eigentlichen Anwendung. Er ist ein Wegwerf-Artefakt und wird nach der Entscheidung wieder
entfernt (siehe [`specs/features/0287-design-richtungen-vergleich.md`](../specs/features/0287-design-richtungen-vergleich.md)).

```bash
cd frontend && npm run dev
# danach im Browser: http://localhost:5173/design-lab/
```

Das Labor läuft ausschließlich im Vite-Dev-Server: `npm run build` erzeugt kein Labor-Artefakt in
`dist/`, es ist also weder im nginx-Image noch im PWA-Precache enthalten. Es braucht kein Backend,
ruft keine API auf und speichert nichts.

Optional lassen sich echte Fotos statt der generierten Motive anzeigen: beliebige JPG/PNG in
`frontend/design-lab/photos-local/` ablegen (per `.gitignore` ausgeschlossen, zusätzlich durch
einen Guard-Test abgesichert — Familienfotos gehören nie ins Repository). Die Labor-Kopfzeile zeigt
an, ob und wie viele lokale Fotos gefunden wurden.

**Achtung beim Ansehen auf dem Handy:** Der Vite-Dev-Server bindet standardmäßig nur an
`localhost`. Wer ihn mit `npm run dev -- --host` im Netz freigibt (naheliegend, weil die
Vergleichsrahmen bewusst Mobilbreite haben), macht damit **auch `photos-local/` für jedes Gerät im
selben Netz abrufbar**. Das ist eine bewusste Entscheidung im Moment des Aufrufs, keine
Voreinstellung.

## Cloud-Bilderkennung (optional)

Zwei Kriterien/Funktionen verlassen den Homeserver — beide über denselben, projektweiten
Einwilligungs-Schalter gegated (`Project.cloud_vision_detection_enabled`, Settings-Seite
`/projects/:id/settings`): das Kriterium "Sehenswürdigkeit" (`landmark`, siehe
[`specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](../specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md),
[`specs/decisions/0025-cloud-landmark-erkennung.md`](../specs/decisions/0025-cloud-landmark-erkennung.md))
und die optionale Remote-Kategorie-Klassifizierung (offene Schlagworte statt eines festen
Kategorie-Enums, siehe [`specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md),
[`specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md)).
Beide sind ein direkter `httpx`-Aufruf gegen die Anthropic Messages API (Default) oder wahlweise
gegen die Mistral Chat Completions API ([`specs/features/0054-mistral-provider-option-cloud-landmark.md`](../specs/features/0054-mistral-provider-option-cloud-landmark.md),
[`specs/decisions/0031-mistral-provider-option-cloud-landmark.md`](../specs/decisions/0031-mistral-provider-option-cloud-landmark.md)).
Für den Quick-Start/Demo-Stack **nicht nötig**: der Schalter ist projektweit per Default
deaktiviert (`PUT /projects/{id}/cloud-vision-consent`), ohne aktivierte Einwilligung wird kein
API-Key verwendet und kein Netzwerkaufruf ausgeführt (die Env-Variablen selbst werden wie jede
andere `Settings`-Konfiguration bereits beim Prozessstart eingelesen, das ist unabhängig von
Einwilligung/Provider). Die Remote-Kategorie-Klassifizierung braucht zusätzlich ein lokales,
gepinntes Text-Embedding-Modell (`onnxruntime`+`tokenizers`, keine Cloud-Abhängigkeit zur
Laufzeit). Das ONNX-Modell-Asset selbst überschreitet GitHubs 100-MB-Push-Limit und ist daher
**nicht** im Repository eingecheckt (siehe [`specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md`](../specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md)) —
`docker compose up --build` lädt es automatisch beim Image-Build (`backend/Dockerfile` ruft
`scripts/fetch-label-embedder-model.sh` auf, SHA256-verifiziert). Nur für ein Bare-Metal-Dev-Setup
ohne Docker (`pip install -e .` direkt im `backend/`-Ordner) einmalig manuell nötig:

```bash
scripts/fetch-label-embedder-model.sh
```

Um beide Funktionen tatsächlich zu nutzen, in `.env`:

- `LANDMARK_PROVIDER` wählt den Cloud-Provider (für beide Funktionen gemeinsam, kein separates
  Setting) — `anthropic` (Default, USA, DPA-/Datenschutzlage geklärt siehe ADR 0025) oder
  `mistral` (EU-hosted Alternative, Sitz Frankreich; DPA-/Zero-Data-Retention-Lage für
  Privatkonten laut Recherche unklar, bewusst akzeptiertes Restrisiko siehe ADR 0031). Eine reine
  Betreiber-/Deployment-Entscheidung, kein Feld pro Projekt.
- Je nach gewähltem Provider `ANTHROPIC_API_KEY` bzw. `MISTRAL_API_KEY` auf einen echten API-Key
  setzen (leer = beide Funktionen bleiben für alle Projekte unbenutzbar, auch bei aktivierter
  Einwilligung schlägt der Aufruf dann fehl).
- Optional `LANDMARK_API_CONCURRENCY` (Default `2`) anpassen — Obergrenze der parallelen Anfragen
  für `landmark`.
- Optional `REMOTE_CATEGORY_CLASSIFICATION_CONCURRENCY` (Default `2`) anpassen — eigenständige
  Obergrenze für die Remote-Kategorie-Klassifizierung (unabhängig von `LANDMARK_API_CONCURRENCY`,
  da dieser Job auf einem größeren, ungefilterten Kandidatenpool läuft).

Danach die Einwilligung für das jeweilige Projekt einmalig über die Settings-Seite
(`/projects/:id/settings`) aktivieren.

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
