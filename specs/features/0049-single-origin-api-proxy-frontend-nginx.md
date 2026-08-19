# 0049 - Nur Frontend nach außen exposen: Single-Origin-API-Proxy über Frontend-nginx

**Status:** Accepted
**Erstellt:** 2026-08-19
**Bezug:** Ursprünglich `specs/inbox/0018-nur-frontend-nach-aussen-exposen.md` (nach Anlage dieser Spec gelöscht), geschärft im `idea-sharpener`-Ablauf (interaktive Session mit Daniel, 2026-08-19). ADR [`decisions/0027-single-origin-api-proxy-ueber-frontend-nginx.md`](../decisions/0027-single-origin-api-proxy-ueber-frontend-nginx.md).

## Ziel

Daniel muss aktuell in seinem externen Reverse Proxy (Homeserver, nicht Teil dieses Repos) zwei Routen pflegen — eine auf den `frontend`-Container, eine auf den `backend`-Container — weil der Browser die Backend-API cross-origin direkt anspricht. Diese Spec macht das Frontend-nginx zum alleinigen extern erreichbaren Einstiegspunkt: API-Requests werden intern über das Docker-Netzwerk an das Backend weitergeleitet, der Backend-Port entfällt komplett. Daniel braucht danach nur noch eine Route/eine Origin in seinem Reverse Proxy.

## User Story

Als Daniel (Betreiber der Anwendung auf seinem Homeserver) möchte ich PhotoSort hinter nur einer extern erreichbaren URL/einem Port betreiben, damit ich in meinem Reverse Proxy nur noch eine Route statt zwei pflegen muss.

## Akzeptanzkriterien

- [ ] `POST http://localhost:${FRONTEND_PORT:-8080}/api/auth/login` mit gültigen Seed-Credentials liefert `200` + `access_token` im Body (End-to-End-Nachweis des `/api`-Proxy-Pfads über das Docker-Netzwerk).
- [ ] Der `backend`-Service hat in `docker-compose.yml` kein `ports:`-Mapping mehr; ein Verbindungsversuch zu `localhost:${BACKEND_PORT:-8000}` vom Host schlägt mit *Connection refused* fehl (nicht Timeout).
- [ ] Ein Backend-only-Neustart bei weiterlaufendem Frontend-Container (`docker compose up -d --force-recreate backend`) unterbricht den Proxy-Pfad nicht dauerhaft: nach `resolver`-`valid`-Zeit plus kurzer Pufferzeit liefert `/api/auth/login` wieder `200` (Nachweis der dynamischen DNS-Auflösung gegen den bekannten nginx+Docker-DNS-Caching-Fallstrick).
- [ ] `GET /projects/3` (Frontend-SPA-Route, kein `/api`-Präfix) liefert weiterhin den bestehenden SPA-Fallback (`index.html`, Spec 0016) statt an das Backend weitergeleitet zu werden — Regressionstest für die Pfad-Kollisions-Lösung.
- [ ] Ein authentifizierter Endpunkt-Aufruf mit `Authorization: Bearer <token>` über den neuen Proxy-Pfad liefert eine erfolgreiche Antwort (verifiziert, dass der Header korrekt durchgereicht wird).
- [ ] `VITE_API_BASE_URL`-Default (Compose-Build-Arg, `.env.example`, `.env.demo.example`) ist `/api` (relativ) statt `http://localhost:8000`.
- [ ] `docker compose up` (Haupt-Compose sowie mit Demo-Overlay) startet alle Services fehlerfrei, `RestartCount` `0` je Container innerhalb des CI-Timeouts.
- [ ] Bestehende CORS-Middleware im Backend bleibt unverändert bestehen und funktioniert weiterhin für den lokalen Vite-Dev-Server-Workflow (Regressionsnachweis, kein neuer Testfall).
- [ ] `docs/setup.md` und `docs/architecture.md` dokumentieren den neuen internen API-Proxy-Pfad, den Wegfall des Backend-Host-Ports und die Override-Anleitung für `npm run dev` gegen einen dockerisierten Backend.
- [ ] `.gitignore` enthält einen Eintrag für `docker-compose.override.yml` (persönliches, nicht eingechecktes Override für den lokalen Dev-Workflow gegen dockerisierten Backend).
- [ ] `docker-compose-check`-CI-Job bleibt grün: bestehender Login-Funktionstest wechselt auf einen internen Check (`docker compose exec` im `backend`-Container statt `curl` gegen den entfallenden Host-Port), zusätzlich neuer funktionaler CI-Schritt für den Single-Origin-Proxy-Pfad inkl. Negativ-Assertion gegen den entfallenden Backend-Host-Port.

## Datenmodell-Bezug

Nicht betroffen — reine Deployment-/Netzwerk-/Serving-Konfiguration, kein Backend-Code, keine Migration.

## Architektur / Umsetzung

Siehe ADR [`decisions/0027-single-origin-api-proxy-ueber-frontend-nginx.md`](../decisions/0027-single-origin-api-proxy-ueber-frontend-nginx.md) für die vollständige Begründung und verworfene Alternativen. Kurzfassung:

Das Frontend-nginx bekommt einen zusätzlichen `location /api/`-Block, der Requests intern (Docker-Netzwerk, Service-Name `backend`) an den Backend-Container weiterleitet und dabei den `/api`-Präfix strippt (`proxy_pass` mit abschließendem `/`) — der Browser ruft `/api/projects` auf, nginx leitet an `http://backend:8000/projects` weiter, identisch zum bestehenden Backend-Routing. Kein `/api`-Präfix im Backend selbst, keine Backend-Code-Änderung. Löst die Pfad-Kollision zwischen der SPA-Route `/projects/:projectId` und dem Backend-Router-Präfix `/projects`, ohne dass beide je denselben Pfadraum teilen.

**Betroffene Dateien:**

- `frontend/nginx.conf`: neuer `location /api/`-Block **vor** dem bestehenden SPA-Fallback (`location /`). Dynamische DNS-Auflösung statt literalem Host: `resolver 127.0.0.11 valid=10s;` + `set $backend_upstream backend:8000;` + `proxy_pass http://$backend_upstream/;` (schützt gegen einen Backend-only-Redeploy bei laufendem Frontend-Container — bekannter nginx+Docker-Fallstrick). Zusätzlich `proxy_set_header X-Real-IP $remote_addr;` / `X-Forwarded-For $proxy_add_x_forwarded_for;` (Logging-Hygiene, siehe Security-Abschnitt).
- `docker-compose.yml`: `ports:` beim `backend`-Service entfällt vollständig (kein `BACKEND_PORT` mehr referenziert). `frontend`-Build-Arg-Default `VITE_API_BASE_URL` wechselt von `http://localhost:8000` auf `/api`.
- `.env.example` und `.env.demo.example`: `BACKEND_PORT`-Zeile entfernen, `VITE_API_BASE_URL`-Default auf `/api` mit angepasstem Kommentar.
- `.gitignore`: neuer Eintrag `docker-compose.override.yml` — für den optionalen, persönlichen lokalen Workaround (siehe unten).
- `.github/workflows/ci.yml`:
  - Bestehender Login-Check (Spec 0013) wechselt von `curl ... localhost:${BACKEND_PORT:-8000}/auth/login` auf einen internen Check innerhalb des `backend`-Containers (`docker compose exec -T backend python -c "..."` mit `urllib.request`, kein `curl` im Backend-Image installiert).
  - Neuer, eigenständiger Schritt "Functional check — single-origin API proxy via frontend nginx (spec 0049)": startet `backend`+`worker`+`frontend`, ruft `http://localhost:${FRONTEND_PORT:-8080}/api/auth/login` vom Runner-Host auf (`200` + `access_token`), zusätzlich ein `docker compose up -d --force-recreate backend` gefolgt von einem erneuten Aufruf nach `resolver`-`valid`-Zeit + Puffer (Nachweis der dynamischen DNS-Auflösung), ein `GET /projects/3`-Regressionscheck gegen den SPA-Fallback, ein authentifizierter Aufruf mit `Authorization: Bearer`, sowie eine Negativ-Assertion, dass eine Verbindung zu `localhost:${BACKEND_PORT:-8000}` mit *Connection refused* fehlschlägt.
- CORS (`CORS_ALLOWED_ORIGINS`, `backend/src/photosort/main.py`): **unverändert**. Wird für den `docker compose up`-Vollstack-Pfad nicht mehr gebraucht, bleibt aber nötig für den Vite-Dev-Server (Port 5173) und ein eigenständiges `uvicorn`-Backend ohne Docker.
- `docs/architecture.md`, `docs/setup.md` (Owner: `architect`, im selben PR): Ergänzung um den neuen internen API-Proxy-Pfad, den Wegfall des Backend-Host-Ports und die Override-Anleitung für `npm run dev` gegen einen dockerisierten Backend.
- `specs/architecture/0002-testkonzept.md`: neuer Unterabschnitt zum wiederverwendbaren Muster "nginx `proxy_pass` mit dynamischem Resolver — Verifikation via `--force-recreate`-Neustart", Ergänzung der E2E/Smoke-Tabellenzeile um den neuen CI-Schritt.
- `specs/architecture/0003-securitykonzept.md`: neuer Bullet unter "Angriffsflächen" (Backend-Port entfällt, einziger Ingress ist Frontend-nginx) sowie unter "Bewusst akzeptierte Restrisiken" der Rate-Limit-Bucket-Punkt (siehe Security-Abschnitt unten).

**Lokaler `npm run dev`-Workflow gegen den dockerisierten Backend:** kein neuer Mechanismus im Repo (kein Vite-Dev-Server-Proxy). Wer diesen Workflow braucht, legt sich eine eigene, nicht eingecheckte `docker-compose.override.yml` mit demselben `ports:`-Eintrag an, der jetzt aus dem Haupt-File entfernt wird, und setzt lokal `VITE_API_BASE_URL=http://localhost:8000`.

**Reihenfolge der Umsetzung (Test First, Infrastruktur-Ebene, analog Spec 0016):**

1. Neue funktionale CI-Schritte gegen den *aktuellen* (noch ungefixten) Stand ergänzen — müssen rot sein.
2. `frontend/nginx.conf` (Proxy-Block) — isoliert testbar (`--no-deps`, analog zum bestehenden SPA-Fallback-Check).
3. `docker-compose.yml` + `.env.example`/`.env.demo.example` (Port-Entfernung, `VITE_API_BASE_URL`-Default).
4. `.gitignore`-Eintrag.
5. `.github/workflows/ci.yml` (beide Anpassungen).
6. CI-Schritte erneut laufen lassen — jetzt grün.
7. `docs/architecture.md`/`docs/setup.md` (architect), `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`.

Kein Backend-Code betroffen, keine Migration, keine neue externe Abhängigkeit.

## UI/UX

Nicht relevant — reine Deployment-/Netzwerkänderung ohne jede sichtbare Oberfläche, keine neue Komponente, kein neuer Lade-/Fehler-/Leerzustand. Für Endnutzer (Daniel, Ehefrau) funktional identisches Verhalten der Anwendung im Browser.

## Security

Sicherheitsrelevant (Netzwerk-Exposure-, Routing- und Header-Weiterleitungs-Änderung). Bedrohungen/Gegenmaßnahmen:

- **Backend-Port-Entfernung reduziert die Angriffsfläche:** der Backend-Container ist danach ausschließlich vom `frontend`-Container über das interne, IPv4-only-isolierte Docker-Netzwerk (Spec 0010) erreichbar, nie vom Host oder von außen. Bewusst die vollständige Entfernung statt nur einer `127.0.0.1`-Bindung (wie beim Demo-Stack) — dort ist die Bindung nötig, weil `opencloud-demo` auch direkt vom Host/Setup-Tooling erreichbar sein muss, dieser Grund entfällt hier vollständig.
- **`Authorization`-Header-Weiterleitung:** `proxy_pass` leitet Client-Header inkl. `Authorization` (JWT-Bearer-Token) standardmäßig unverändert durch, kein Stripping-Risiko. Explizit durch einen CI-Testfall verifiziert (authentifizierter Aufruf über den Proxy-Pfad), statt nur implizit angenommen.
- **Bekanntes, akzeptiertes Restrisiko — Rate-Limit-Bucket-Sharing:** nginx setzt `X-Real-IP`/`X-Forwarded-For` nicht automatisch; `backend/src/photosort/rate_limit.py` nutzt `slowapi.get_remote_address` (`request.client.host`, keine `X-Forwarded-For`-Auswertung) für das Login-Rate-Limit. Nach der Umstellung sieht das Backend für alle über den Proxy laufenden Requests dieselbe interne Docker-Quell-IP des `frontend`-Containers statt der echten Client-IP — das Login-Rate-Limit wird faktisch zu einem projektweit geteilten statt einem pro-Client-Bucket. Schwächt den Brute-Force-Schutz selbst nicht (der Zähler-Schwellwert greift weiterhin für alle Anfragen gemeinsam), kann aber dazu führen, dass ein Nutzer den anderen versehentlich aussperrt (Verfügbarkeits-, kein Auth-Bypass-Problem). Für das Zwei-Personen-Familienprojekt geringe reale Relevanz — als akzeptiertes Restrisiko dokumentiert, kein Blocker. Gegenmaßnahme (Hygiene, kein Muss): `frontend/nginx.conf` setzt `X-Real-IP $remote_addr;`/`X-Forwarded-For $proxy_add_x_forwarded_for;`, damit die echte Client-IP zumindest im Logging sichtbar bleibt. Ein Umbau des Rate-Limit-`key_func` auf `X-Forwarded-For` ist bewusst Out of Scope dieser Spec (siehe unten).
- **Keine neu exponierten Endpunkte:** `/api/` macht keinen Backend-Endpunkt erreichbar, der vorher nicht schon über den offenen Backend-Port erreichbar war (z.B. `/health`, unauthentifiziert, keine sensiblen Daten) — strukturell eine Reduktion, keine Erweiterung der Angriffsfläche.
- **`resolver 127.0.0.11 valid=10s;` (Docker-Embedded-DNS) unbedenklich:** löst ausschließlich Servicenamen im eigenen, isolierten Compose-Netzwerk auf; das Proxy-Ziel ist statisch (`backend:8000`), nicht aus Nutzereingabe abgeleitet — kein SSRF-/Cache-Poisoning-Vektor.

`specs/architecture/0003-securitykonzept.md` wird entsprechend ergänzt (siehe Architektur/Umsetzung oben).

## Offene Fragen

Keine — alle im Gespräch mit Daniel und in den Fachagenten-Konsultationen geklärt.

## Out of Scope

- Eigener externer Reverse-Proxy/TLS-Terminierung — bleibt weiterhin Daniels Homeserver-Setup, unverändert (siehe `docs/architecture.md`, "Bewusste Annahmen").
- Ein `/api`-Präfix im Backend selbst (`APIRouter(prefix="/api")`) — der Präfix-Strip passiert ausschließlich im nginx, kein Backend-Code-Eingriff.
- Ein Vite-Dev-Server-Proxy-Eintrag in `vite.config.ts` für `npm run dev` gegen einen dockerisierten Backend — bewusst als persönliches, nicht eingechecktes `docker-compose.override.yml` gelöst statt als Repo-Mechanismus.
- Umbau des Login-Rate-Limits auf `X-Forwarded-For`-basierte Client-Erkennung — akzeptiertes Restrisiko (siehe Security-Abschnitt), bei Bedarf eigene spätere Spec.

## Entscheidungen

- **Priorität: Niedrig** (requirements-engineer-Konsultation, 2026-08-19, vom Hauptagenten nach Architektur-/Test-/Security-Konsultation bestätigt): reines Infrastruktur-/DevOps-Feature, kein Kundenfeature, kein Blocker — Daniel hat einen funktionierenden Workaround (zwei separate Reverse-Proxy-Routen). Keine Roadmap-Konflikte gefunden.
- **Devil's-Advocate-Ergebnis (Hauptagent, 2026-08-19):** verworfene Alternative — Daniel routet stattdessen rein extern in seinem eigenen Reverse Proxy pfadbasiert zu zwei internen Zielen (ein Hostname, aber weiterhin zwei Upstream-Ziele/zwei exponierte Docker-Host-Ports). Verworfen, weil das sein eigentliches Ziel ("nur einen Port/eine URL") nicht wirklich erfüllt (er bräuchte weiterhin zwei interne Proxy-Ziele und müsste die Pfad-Kollision selbst außerhalb des Repos lösen) und nicht reproduzierbar/testbar im Repo wäre.
- **architect-Konsultation (Schritt 6, 2026-08-19):** ADR 0027 angelegt (architekturrelevante Änderung am Netzwerk-/Exposing-Modell, revidiert bewusst die Scope-Grenze aus Spec 0016 AC 7/Out of Scope "kein Reverse-Proxy über denselben nginx" — kein Widerspruch, sondern explizite Weiterentwicklung). Zwei vorab identifizierte, sonst leicht übersehene Fallstricke strukturell gelöst: Pfad-Kollision zwischen SPA-Route `/projects/:id` und Backend-Router-Präfix `/projects` (gelöst durch `/api`-Präfix-Strip im nginx statt im Backend), Docker-DNS-Caching bei einem Backend-only-Redeploy (gelöst durch dynamischen `resolver` statt literalem Host in `proxy_pass`).
- **ux-ui-designer nicht konsultiert (Schritt 7):** reine Deployment-/Netzwerkänderung ohne jede sichtbare Oberfläche, kein neuer Zustand, keine neue Komponente, funktional identisches Verhalten für Endnutzer — eindeutiger Fall ohne plausibles Gegenbeispiel.
- **test-engineer-Konsultation (Schritt 8, 2026-08-19):** Akzeptanzkriterien auf konkrete HTTP-Codes/Bodies/Verhalten geschärft (analog Spec 0016). Reiner funktionaler Compose-/CI-Test, kein Unit-/Integrations-/E2E-Test im klassischen Sinn (kein Anwendungscode geändert, kein Coverage-Gate-Impact). Wichtigster Edge Case: ein bloßer `docker compose restart backend` beweist die DNS-Resolver-Lösung nicht (Container-IP bleibt dabei meist unverändert) — der CI-Test muss `--force-recreate` nutzen, um den eigentlichen Risikofall tatsächlich zu belegen. `specs/architecture/0002-testkonzept.md` wird um das neue, wiederverwendbare Testmuster ergänzt.
- **security-engineer-Konsultation (Schritt 8, 2026-08-19):** sicherheitsrelevant eingestuft (Netzwerk-Exposure/Routing/Header-Weiterleitung). Vollständige Backend-Port-Entfernung (statt nur `127.0.0.1`-Bindung) als konsequenteste, richtige Wahl bestätigt. Rate-Limit-Bucket-Sharing durch fehlende `X-Forwarded-For`-Auswertung als bewusst akzeptiertes, nicht-blockierendes Restrisiko dokumentiert (siehe Security-Abschnitt). `resolver 127.0.0.11` als unbedenklich eingestuft (kein SSRF-Vektor, statisches Proxy-Ziel).
