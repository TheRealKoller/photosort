# Testkonzept

**Status:** Living Document (kein Lifecycle, wird laufend aktualisiert)
**Letzte Aktualisierung:** 2026-07-20 (Teststrategie-Konsultation zu Spec 0006 "Auth-Implementierung": erste Auth-pflichtige Endpunkte, erster JWT-Umgang in Tests, erster globaler Frontend-Event-Listener — ergänzt die bisher offene Lücke "Auth/JWT existiert noch nicht")

## Zweck

Projektweite, von der jeweiligen Feature-Implementierung unabhängige Teststrategie. Ergänzt (nicht ersetzt) die "Akzeptanzkriterien"/"Architektur"-Abschnitte der einzelnen Feature-Specs — dort steht *was* pro Feature getestet wird, hier steht *wie* projektweit konsistent getestet wird.

## Backend (`backend/`, `pytest`)

**Stand:** etabliert seit Spec 0001, folgende Konventionen gelten für alle künftigen Endpunkte/Jobs.

- **Unit-Ebene:** reine Funktionen ohne I/O — WebDAV-XML-Parsing (`test_webdav_xml.py`), EXIF-Extraktion (`test_exif.py`), Konfiguration (`test_config.py`), Modell-/Constraint-Verhalten (`test_models.py`).
- **Integrations-Ebene (Schwerpunkt):** FastAPI-Endpunkte gegen eine echte In-Memory-SQLite-Instanz (`aiosqlite`, `db_session`-Fixture in `conftest.py`, Tabellen werden pro Test frisch erzeugt) über `httpx.ASGITransport` (`api_client`-Fixture) — kein Mocken der DB-Schicht selbst, nur der externen Abhängigkeit (OpenCloud). Worker-Jobs (`test_worker_scan_project.py`) laufen ebenso gegen die echte In-Memory-DB.
- **Mocking-Grundsatz:** an der Schnittstelle nach außen mocken (FastAPI `dependency_overrides` für `get_opencloud_client`/`get_job_enqueuer`; Fake-Implementierungen wie `FakeClient`/`FakeOpenCloudClient`, die dasselbe Protokoll wie der echte Client erfüllen), nicht den internen Transport (`httpx`) oder die eigene DB-Schicht. Ziel: Tests laufen ohne echtes OpenCloud/Redis, aber mit echtem SQL.
- **Was gegen echte Testinstanzen statt Fakes läuft:** nichts bisher — es gibt kein Docker-Compose-basiertes Integrationstest-Setup gegen eine echte OpenCloud-Instanz. Der manuelle Smoke-Test vor Merge (siehe unten) übernimmt diese Rolle ersatzweise.
- **E2E-/Smoke-Ebene:** kein automatisiertes E2E-Setup (siehe "Was bewusst nicht getestet wird"). `docker-compose-check`-Job in CI validiert nur, dass `docker-compose.yml` syntaktisch gültig ist — kein funktionaler Smoke-Test.
- **Coverage-Gate:** `pytest --cov=photosort --cov-fail-under=80` in CI (`.github/workflows/ci.yml`), Backend-Pflicht laut `CLAUDE.md`. Neue Endpunkte/Jobs brauchen mindestens einen Erfolgsfall und die dokumentierten Fehlerfälle (4xx mit erwartetem `detail`), nicht nur zufällige Coverage durch Getter/Schemas.

### Auth (seit Spec 0006)

- **Unit-Ebene:** `security.py` (`hash_password`/`verify_password`, `create_access_token`/`decode_access_token`) als reine Funktionen ohne I/O testen — Roundtrip, falsches Passwort, abgelaufenes Token und manipuliertes Token. Für abgelaufene/manipulierte Tokens **kein** Freeze-Time-Setup nötig: Token direkt mit `jwt.encode(..., exp=<Vergangenheit>)` bzw. mit falschem Signing-Key bauen und an `decode_access_token` übergeben, statt echte Zeit zu manipulieren oder eine neue Zeit-Mocking-Abhängigkeit einzuführen.
- **Integrations-Ebene:** `POST /auth/login` gegen die echte In-Memory-DB (Testnutzer direkt per SQLAlchemy-Insert angelegt, nicht über die Seed-Migration — die Migration wird separat getestet, siehe unten). `get_current_user` wird für die meisten Tests **nicht** wegen-gemockt (anders als `get_opencloud_client`/`get_job_enqueuer`), da es sich um interne, zu prüfende Logik handelt statt eine externe Abhängigkeit. Stattdessen: neue `conftest.py`-Fixture `authenticated_api_client` (seedet einen Testnutzer, erzeugt ein gültiges Token via `create_access_token`, setzt `Authorization`-Header als Default auf dem `httpx.AsyncClient`) für alle Tests gegen auth-pflichtige Endpunkte; der bestehende `api_client` bleibt für die auth-fokussierten Tests selbst (fehlender Header, abgelaufenes/manipuliertes Token, unbekannter `sub`) sowie für `/health` und `/auth/login`.
- **Retrofit-Migration bestehender Tests:** Mit dem Router-weiten `Depends(get_current_user)` auf `api/projects.py` und `api/opencloud.py` werden die bestehenden Tests in `test_api_projects.py`/`test_api_opencloud_browse.py` von `api_client` auf `authenticated_api_client` umgestellt. Das ist keine nachträgliche Anpassung an fehlerhaftes Verhalten im TDD-Sinn, sondern eine notwendige Fixture-Migration, da sich die Vorbedingung (Auth erforderlich) geändert hat — im Review (Aufgabe 2) darauf achten, dass dabei keine Assertions stillschweigend abgeschwächt wurden.
- **Retrofit-Vollständigkeit:** ein parametrisierter Test, der alle Pfade/Methoden unter den `projects`- und `opencloud`-Routern aufzählt und ohne Token je einen 401 erwartet — verhindert, dass ein künftig neu hinzugefügter Endpunkt versehentlich ungeschützt bleibt, weil das Retrofit pro-Router statt pro-Funktion erfolgt.
- **Seed-Migration:** eigener Test (z.B. `test_migration_seed_users.py`), der die Insert-if-not-exists-Logik direkt als testbare Python-Funktion prüft (nicht durch tatsächliches Ausführen von `alembic upgrade` in der Testsuite) — Empfehlung an die Implementierung: die Seed-Logik in eine eigene, aus der Migration heraus aufgerufene Funktion auslagern, damit sie ohne Alembic-Runtime unit-testbar ist. Fälle: leere DB (beide Nutzer werden angelegt), ein Nutzer existiert bereits (nur der fehlende wird ergänzt, bestehender Passwort-Hash bleibt unverändert), beide existieren bereits (No-op, kein Fehler).

## Frontend (`frontend/`, `vitest` + Testing Library)

**Stand:** vor Spec "Minimales Projekt-Frontend" nur Vite-Scaffold-Test (`App.test.tsx`, reines Rendering, keine Router-/Query-Nutzung). Mit dieser Spec entstehen erstmals echte Konventionen, hier erstmalig festgehalten:

- **Unit-Ebene:**
  - Präsentations-Komponenten, die per Props/Callbacks gesteuert werden (z.B. `FolderBrowser` als kontrollierte Komponente laut ADR `decisions/0004-frontend-app-shell.md`): Rendering + Callback-Aufrufe testen, ohne `QueryClientProvider`/`MemoryRouter`.
  - `api/client.ts` (Fetch-Wrapper): Statuscode-/Fehler-Mapping (`ApiError(status, detail)`) isoliert testen, inkl. Randfall fehlendes/kaputtes `detail`-Feld.
  - Reine Ableitungs-/Utility-Funktionen (z.B. Scan-Kurzstatus aus `last_scan` ableiten).
- **Integrations-Ebene:** Seiten-Komponenten inkl. zugehöriger Hooks im Zusammenspiel mit echtem `QueryClientProvider` und `MemoryRouter`, aber gemockten `api/*.ts`-Funktionen (`vi.mock` auf Modulebene der jeweiligen `api/projects.ts`/`api/opencloud.ts`-Funktionen — **nicht** MSW/Mock-Service-Worker auf Transport-Ebene, konsistent mit dem bewusst dünnen Fetch-Wrapper aus ADR 0004 und dem Backend-Grundsatz "an der Schnittstelle mocken"). Deckt genau die Fälle ab, die reines Komponenten-Rendering nicht könnte: Navigation nach erfolgreichem Submit, Cache-Invalidierung zwischen Mutation und Polling-Query, Cleanup bei Unmount, Doppel-Request-Vermeidung bei Breadcrumb-Navigation.
- **Fixture-/Testdaten-Konvention:** kleine, literale Testobjekte pro Testdatei (analog zu den Backend-`_entry()`-Hilfsfunktionen), keine geteilten globalen Fixture-Dateien nötig, solange der Umfang klein bleibt — bei wachsendem Bedarf (Spec 0002 bringt Foto-/Rating-Daten) `frontend/src/test/fixtures.ts` einführen.
- **E2E-Ebene:** kein dediziertes E2E-Test-Setup (kein Playwright o.ä.) — siehe "Was bewusst nicht getestet wird". Die oben beschriebene Integrations-Ebene (echter Router + echter QueryClient, gemockte API) deckt die eigentliche Sorge bei React Router/TanStack Query (Routing+Polling+mehrstufige Navigation) ab, ohne echten Browser/echtes Backend zu benötigen.
- **Coverage-Gate:** aktuell **kein** Frontend-Coverage-Gate in CI (`npm run test -- --run` ohne `--coverage`/Schwellenwert) — siehe "Bekannte Lücken". `CLAUDE.md` verpflichtet das Gate ausdrücklich nur für das Backend.

### Auth (seit Spec 0006)

- **Unit-Ebene:** `auth/token.ts` (`getToken`/`setToken`/`clearToken` als reiner `localStorage`-Wrapper); `api/client.ts` erweitert um Header-Anhängen bei vorhandenem Token und 401-Verhalten (Token löschen + `CustomEvent("photosort:unauthorized")` dispatchen — per `window.addEventListener`-Spy im Test verifizieren, nicht nur den Aufruf von `clearToken` prüfen).
- **Integrations-Ebene:** `LoginPage` (echter `MemoryRouter` + `QueryClientProvider`, `vi.mock` auf `api/auth.ts`-Modulebene) inkl. Redirect-Ziel-Test bei Tiefenlink (`MemoryRouter initialEntries` mit `state.from` simulieren, nach Login-Erfolg Navigation zu diesem Ziel statt nur zu `/` prüfen); `ProtectedRoute` (kein Token → Redirect zu `/login` mit gesetztem `state.from`; Token vorhanden → `Outlet` rendert); globaler `photosort:unauthorized`-Listener (Event via `window.dispatchEvent` auslösen, **echten** `MemoryRouter` statt gemocktem `useNavigate` verwenden und die tatsächlich gerenderte Route prüfen — konsistent mit dem bestehenden Grundsatz "echter Router" statt Navigation-Mocks) — deckt den Fall "401 mitten in laufender Session durch abgelaufenes Token" ab.
- **Neues Element gegenüber bisheriger Konvention:** erstmals ein globaler, event-basierter Cross-Component-Mechanismus (`CustomEvent` statt Props/Context) — Testkonvention dafür: immer gegen die echte Browser-Event-API testen (`dispatchEvent`/`addEventListener`), nicht durch Mocken der Event-Funktionen selbst, sonst wird nur die Verdrahtung statt des Verhaltens geprüft.

## Was bewusst nicht getestet wird

- Reine UI-Kosmetik (exakte Pixel-/Farbwerte, CSS-Feinheiten) — Design-System-Konformität ist Aufgabe des `ux-ui-designer`-Agenten bei Review/Umsetzung, nicht automatisiert testbar mit sinnvollem Aufwand.
- Drittanbieter-Bibliotheken selbst (React Router, TanStack Query, SQLAlchemy, FastAPI) — deren eigene Testsuiten werden vorausgesetzt; getestet wird nur die eigene Nutzung/Integration.
- Echte OpenCloud-Instanz/echtes Redis/echter Worker-Container im automatisierten Testlauf — dafür kein Docker-Compose-Testsetup, ersetzt durch manuellen Smoke-Test vor Merge (etabliert mit Spec 0002: "Touch/Swipe-Gefühl wird als manueller Smoke-Test vor Merge geprüft", gilt analog für neue externe Integrationen).
- Automatisiertes E2E-Testing (Playwright o.ä.): explizite Entscheidung aus Spec 0002, Aufwand für Zwei-Personen-Projekt aktuell nicht gerechtfertigt. Gilt weiterhin — wird neu bewertet, falls ein Feature auftaucht, dessen Risiko bei einem Regressions-Bug im Zusammenspiel mehrerer Systeme (Backend+Worker+Frontend end-to-end) das nicht mehr rechtfertigt.

## Bekannte Lücken (Stand 2026-07-20)

- Kein Frontend-Coverage-Gate in CI — nicht von `CLAUDE.md` gefordert, aber es gibt aktuell keine Kennzahl, ob die oben beschriebene Strategie tatsächlich eingehalten wird, sobald das Frontend wächst (Spec "Minimales Projekt-Frontend", danach Spec 0002 mit deutlich mehr UI-Logik). Wird neu bewertet, sobald der Frontend-Codeumfang das rechtfertigt — kein Blocker für die aktuelle Spec.
- Kein automatisiertes Integrationstest-Setup gegen eine echte OpenCloud-Testinstanz (Backend) — Vertragskonformität (`DavEntry`-Parsing, WebDAV-Eigenheiten des echten Servers) hängt vom manuellen Smoke-Test ab. Risiko: Contract-Drift zwischen Fake-Client-Verhalten in Tests und echtem OpenCloud-Server bleibt nur durch manuelle Prüfung abgefangen.
- Kein automatisierter Timing-Angriffs-Test für den Dummy-Hash-Vergleich bei unbekanntem Username in `POST /auth/login` (ADR 0005/Spec 0006): Wall-Clock-Timing-Messungen sind in CI unzuverlässig (Rauschen durch geteilte Runner) und werden deshalb bewusst nicht automatisiert getestet — stattdessen nur der Codepfad (Dummy-Verifikation wird tatsächlich aufgerufen) unit-getestet. Die eigentliche Timing-Eigenschaft bleibt Code-Review-Aufgabe.

## Werkzeuge im Überblick

| Ebene | Backend | Frontend |
|---|---|---|
| Unit | `pytest`, reine Funktionen | `vitest`, reine Funktionen/Komponenten |
| Integration | `pytest` + `httpx.ASGITransport` + In-Memory-SQLite + Fake-Clients | `vitest` + Testing Library + `MemoryRouter` + `QueryClientProvider` + `vi.mock` auf API-Modulebene |
| E2E/Smoke | keins (manueller Smoke-Test vor Merge) | keins (manueller Smoke-Test vor Merge) |
| Coverage-Gate | `--cov-fail-under=80` (Pflicht, CI) | keins (bekannte Lücke) |
