# 0016 - SPA-Fallback in der Frontend-nginx-Konfiguration

**Status:** Accepted
**Erstellt:** 2026-08-05
**Bezug:** Bug-Report von Daniel selbst (interaktive Session, 2026-08-05), geschärft direkt im Gespräch. Die ursprüngliche Inbox-Notiz (`specs/inbox/0002-f5-refresh-404.md`) wurde nach Aufnahme in diese Spec gelöscht.

## Ziel

Ein Browser-Refresh (F5), nachdem einmal client-seitig innerhalb der React-Router-SPA navigiert wurde, liefert aktuell "404 Not Found" statt die Anwendung korrekt neu zu laden. Root Cause: `frontend/Dockerfile` kopiert das Vite-Build in ein `nginx:1.27-alpine`-Image, nutzt dabei aber die nginx-Default-Config, die keinen SPA-Fallback kennt — ein direkter Request auf einen client-seitigen Pfad (z.B. `/projects/3`) sucht nach einer gleichnamigen Datei im statischen Bundle, findet keine, und liefert 404 statt `index.html` auszuliefern. Diese Spec behebt das durch eine eigene, minimale nginx-Konfiguration mit SPA-Fallback.

## User Story

Als Daniel (und seine Frau als Endnutzerin) möchte ich, dass ein Browser-Refresh (F5) auf einer beliebigen Route der Anwendung diese korrekt neu lädt, damit ich nicht durch einen scheinbaren Absturz ("404 Not Found") verunsichert werde und nicht gezwungen bin, über die Startseite neu zu navigieren.

## Akzeptanzkriterien

- [ ] `GET /` liefert `200` mit dem Inhalt von `index.html`.
- [ ] `GET /projects/3` (erfundene, aber syntaktisch gültige Detail-Route) liefert `200` mit zu `GET /` byte-identischem Body statt `404`.
- [ ] `GET /this/path/does/not/exist` (erfundener, generischer Pfad) liefert `200` mit zu `GET /` byte-identischem Body statt `404` — React-Routers bestehende Catch-all-Route (`App.tsx`, `path="*"` → `Navigate to="/"`) übernimmt danach client-seitig.
- [ ] Ein echtes statisches Asset aus dem Vite-Build (z.B. `/assets/<hash>.js`) wird weiterhin direkt ausgeliefert (`200`, korrekter `Content-Type`, Body ungleich `index.html`-Inhalt) — der SPA-Fallback darf reale Assets nicht verschlucken.
- [ ] Ein nicht existierendes, aber asset-artig aussehendes Pfad (z.B. `/assets/definitiv-nicht-vorhanden.js`) bleibt `404` statt fälschlich auf `index.html` zurückzufallen — Lackmustest dafür, dass die `try_files`-Regel nicht zu breit gefasst ist.
- [ ] Der Fix wirkt identisch in `docker-compose.yml` und `docker-compose.demo.yml`, da beide denselben einzigen `frontend`-Service/dasselbe Image nutzen (kein eigenes `frontend`-Override im Demo-Overlay).
- [ ] Bestehende Backend-API-Calls (separates, zur Build-Zeit gebackenes `VITE_API_BASE_URL`, kein Reverse-Proxy über denselben nginx) bleiben unberührt.
- [ ] "F5 zeigt nach Client-Navigation wieder die erwartete Ansicht" ergibt sich aus obigem Server-Verhalten plus der bereits bestehenden, unveränderten Frontend-Routing-Testabdeckung (`App.test.tsx` u.a. rendern beliebige Pfade bereits korrekt via `MemoryRouter`) — kein zusätzlicher Browser-/E2E-Test nötig.
- [ ] `docker-compose-check`-CI-Job bleibt grün, inkl. neuem funktionalen Smoke-Test-Schritt (siehe Teststrategie).

## Datenmodell-Bezug

Nicht betroffen — reine Deployment-/Serving-Konfiguration, kein Datenmodell-Bezug.

## Architektur / Umsetzung

**Ansatz:** `frontend/Dockerfile` erhält eine eigene `nginx.conf`, die die nginx-Default-Config (`/etc/nginx/conf.d/default.conf`) ersetzt und einen expliziten SPA-Fallback definiert (`try_files $uri $uri/ /index.html;`). Kein neuer Service, keine Compose-Änderung, keine Änderung an der Build-Pipeline (Vite-Build in Stufe 1 unverändert) — reine Ergänzung der finalen nginx-Stufe des bestehenden Multi-Stage-Dockerfiles.

**Betroffene Dateien:**

- **Neu:** `frontend/nginx.conf`

  ```nginx
  server {
      listen 80;
      server_name _;

      root /usr/share/nginx/html;
      index index.html;

      location /assets/ {
          try_files $uri =404;
      }

      location / {
          try_files $uri $uri/ /index.html;
      }
  }
  ```

  **Abweichung von der ursprünglichen Planung (bei Umsetzung entdeckt, siehe "Entscheidungen"):** der zusätzliche `location /assets/ { try_files $uri =404; }`-Block vor dem allgemeinen Fallback stand in der ursprünglichen Fassung dieses Abschnitts noch nicht — ohne ihn hätte die reine `try_files $uri $uri/ /index.html;`-Regel das eigene, weiter unten formulierte Akzeptanzkriterium "nicht existierendes, asset-artiges Pfad bleibt 404" verletzt (jeder fehlende Pfad, auch unter `/assets/`, wäre auf `index.html` zurückgefallen).

- **`frontend/Dockerfile`:** eine Zeile in der finalen Stufe ergänzt, nach `COPY --from=build /app/dist /usr/share/nginx/html`:

  ```dockerfile
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  ```

- **Nicht betroffen:** `docker-compose.yml`, `docker-compose.demo.yml`, `docs/architecture.md`, `README.md` — keine strukturelle Architektur-/Setup-/Datenmodelländerung.

**Reihenfolge der Umsetzung (Test First, Infrastruktur-Ebene, analog Spec 0013):**

1. Neuen funktionalen CI-Schritt im bestehenden `docker-compose-check`-Job ergänzen und gegen den *aktuellen* (noch ungefixten) `frontend`-Service laufen lassen — muss rot sein (404 auf `/projects/3`).
2. `frontend/nginx.conf` anlegen.
3. `frontend/Dockerfile` um die `COPY`-Zeile ergänzen.
4. CI-Schritt erneut laufen lassen — jetzt grün. Zusätzlich manueller Smoke-Test lokal (`docker compose up --build frontend`, F5 nach Client-Navigation im Browser).

**Out of Scope:** eigener Reverse-Proxy/TLS-Terminierung, Änderungen am Backend-Routing, allgemeine nginx-Härtung über den reinen SPA-Fallback hinaus (Security-Header, Caching-Strategie, `server_tokens off`) — bei Bedarf eigene spätere Spec.

## UI/UX

Nicht relevant. Reine Server-/Deployment-Konfigurationsänderung ohne neue Komponente, ohne neuen Lade-/Fehler-/Leerzustand und ohne Einfluss auf bestehendes Nutzerverhalten. Die bestehende Catch-all-Route (`App.tsx`, `path="*"` → `Navigate to="/"`) deckt den einzigen denkbaren Randfall (ungültiger Pfad) bereits client-seitig ab — nach dem Fix verhält sich F5 exakt wie ein normaler Direktaufruf der URL im Browser (z.B. per Lesezeichen), ein Ablauf, der schon heute existiert.

## Security

Nicht relevant. Zwei geprüfte Punkte:

1. **Kein Verlust von Default-Security-Verhalten:** `server_tokens`, MIME-Type-Behandlung etc. liegen in der nginx-Haupt-Config (`/etc/nginx/nginx.conf`), nicht in der ersetzten `default.conf`. Die Stock-`default.conf` des offiziellen `nginx:1.27-alpine`-Images setzt zudem selbst keine Security-Header — es geht also nichts verloren.
2. **`try_files $uri $uri/ /index.html;` ist nicht path-traversal-anfällig:** nginx normalisiert `.`/`..`-Segmente vor der `try_files`-Auswertung, `root` bleibt auf das Vite-Build-Verzeichnis beschränkt, das keine Secrets/Server-Config enthält. Der Fallback öffnet keine neue Angriffsfläche, keinen neuen Lesezugriff, keine neue Eingabeverarbeitung.

Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig.

## Teststrategie

Kein klassischer Unit-Test möglich (reine nginx-Config, kein Anwendungscode). Test-First auf Infrastruktur-Ebene: neuer funktionaler CI-Schritt im bestehenden `docker-compose-check`-Job (`.github/workflows/ci.yml`), analog zu Spec 0010/0013 — muss vor dem Fix rot laufen.

`docker compose up -d --no-deps --build frontend` (bewusst ohne Backend-Abhängigkeiten hochfahren, da SPA-Fallback rein nginx-seitig ist und nicht von `backend`/`postgres`/`redis` abhängt), dann per `curl`:

- `/`, eine erfundene Client-Route, ein generischer erfundener Pfad → jeweils `200` + byte-identischer `index.html`-Body.
- Ein echtes Asset (Dateiname aus dem tatsächlichen Build-Output ermittelt, nicht hartkodiert, da Vite-Hashes pro Build wechseln) → `200`, kein `index.html`-Body, korrekter `Content-Type`.
- Ein nicht-existentes, asset-artig aussehendes Pfad → `404` (verhindert, dass `try_files` versehentlich auch echte fehlende Assets als "funktioniert" verschleiert).

Kein separater statischer Config-Diff-Schritt nötig (anders als bei Spec 0013) — der funktionale Test deckt "COPY nginx.conf wirkt" bereits vollständig ab, ein zusätzlicher Schritt wäre Redundanz ohne Zusatznutzen. Kein E2E-/Browser-Test (Playwright) nötig, konsistent mit der bestehenden Testkonzept-Entscheidung.

`specs/architecture/0002-testkonzept.md` wird nach Umsetzung um eine kurze Cross-Referenz ergänzt: dies ist der erste Fall, in dem das etablierte Muster "funktionaler Compose-Check in CI" (bisher nur Backend/Netzwerk/Migration, Spec 0010/0013) auch auf die Frontend-Serving-Schicht angewendet wird.

## Entscheidungen

- **Keine eigene ADR:** reine Implementierungsdetail-Entscheidung, keine architekturrelevante. nginx als statischer Server ist bereits seit dem ersten `frontend/Dockerfile` gesetzt (keine neue Technologie), kein Datenmodell-Bezug, keine neue externe Abhängigkeit, und `try_files $uri $uri/ /index.html;` ist das einzige etablierte Muster für SPA-Fallback hinter nginx — kein echter Alternativen-Trade-off, der eine ADR rechtfertigen würde (architect-Konsultation, 2026-08-05).
- **`--no-deps` beim CI-Smoke-Test** ist eine bewusste Testdesign-Entscheidung: stellt sicher, dass der Test wirklich nur die nginx-Serving-Eigenschaft prüft, unabhängig von Backend-Verfügbarkeit (test-engineer-Konsultation, 2026-08-05).
- **Zusätzlicher `location /assets/ { try_files $uri =404; }`-Block, abweichend vom ursprünglichen Umsetzungsvorschlag** (developer-Entscheidung während der Implementierung, 2026-08-07, bestätigt im nachfolgenden Review durch `architect`/`security-engineer`/`test-engineer`): die wörtlich vorgegebene, minimale `try_files $uri $uri/ /index.html;`-Regel allein wurde lokal gegen den echten Vite-Build getestet und verletzte dabei nachweisbar das eigene Akzeptanzkriterium zum "Lackmustest" (nicht existierendes, asset-artiges Pfad muss 404 bleiben) — jeder fehlende Pfad fiel auf `index.html` (200) zurück, auch unter `/assets/`. Behoben durch eine engere, dem allgemeinen Fallback vorgelagerte Location speziell für den Vite-Asset-Präfix `/assets/` (dort liegen alle gehashten Build-Assets), die bei einer fehlenden Datei explizit `404` statt eines impliziten Fallbacks liefert. Reine technische Detailkorrektur innerhalb der bereits akzeptierten Spec (kein neuer Trade-off, kein neues architektonisches Muster, `try_files`-basierter SPA-Fallback bleibt der Ansatz) — keine neue ADR nötig, `architect`-Review bestätigt das. Lehre für künftige Specs mit konkret vorgegebenem Umsetzungscode: Code-Vorschläge im Abschnitt "Architektur / Umsetzung" vor Übernahme gegen alle eigenen Akzeptanzkriterien der Spec durchspielen, nicht nur auf Plausibilität prüfen.
- **Kein separater statischer Config-Diff-CI-Schritt** (anders als Spec 0013): kein eigenständiger Erkenntniswert gegenüber dem funktionalen Test, daher weggelassen (test-engineer-Konsultation, 2026-08-05).

## Offene Fragen

Keine.

## Out of Scope

- Eigener Reverse-Proxy, TLS-Terminierung oder Änderungen am Backend-Routing.
- Allgemeine nginx-Härtung über den reinen SPA-Fallback hinaus (Security-Header, Caching-Strategie, `server_tokens off`) — bei Bedarf eigene spätere Spec.
