# 0009 - Lokal ausprobieren ohne echten OpenCloud-Server

**Status:** Implemented
**Erstellt:** 2026-08-02
**Akzeptiert:** 2026-08-02
**Umgesetzt:** 2026-08-02, [PR #11](https://github.com/TheRealKoller/photosort/pull/11), Feature-Branch `feature/0009-local-opencloud-demo-stack`
**Bezug:** Idea-Sharpening-Gespräch mit Daniel im Chat, 2026-08-02 ("Ich würde die Anwendung gern lokal starten können zum Ausprobieren. Könnte man den OpenCloud-Server dazu ggf. mocken?")

## Ziel

Um PhotoSort lokal per `docker compose up` auszuprobieren, braucht es aktuell einen echten OpenCloud-Server mit echten Zugangsdaten (`OPENCLOUD_BASE_URL`/`OPENCLOUD_USERNAME`/`OPENCLOUD_APP_TOKEN`/`OPENCLOUD_DRIVE_NAME`) — ohne die lassen sich Ordner-Browsing, Foto-Scan und automatische Bewertung (Spec 0003, Implemented) nicht durchspielen. Diese Spec macht das lokale Ausprobieren möglich, ohne Zugriff auf eine echte OpenCloud-Instanz zu benötigen: ein optionaler, zusätzlicher Docker-Compose-Service stellt einen echten OpenCloud-Server mit vorbefüllten Demo-Fotos bereit. Reine Entwicklungs-/Testinfrastruktur, kein Nutzerfeature für Daniel/Ehefrau im Betrieb.

## User Story

Als Entwickler (Daniel) möchte ich PhotoSort lokal starten können, ohne einen echten OpenCloud-Server und echte Zugangsdaten zu benötigen, damit ich neue Funktionen und den Gesamt-Workflow schnell und risikofrei ausprobieren kann.

## Akzeptanzkriterien

- [x] `docker compose -f docker-compose.yml -f docker-compose.demo.yml up` startet ohne Fehler und ohne dass Daniel `OPENCLOUD_*`-Variablen manuell setzen muss (`.env.demo.example` reicht als `.env`).
- [x] Der OpenCloud-Demo-Container ist innerhalb einer definierten Zeitspanne (z.B. 120s) über seine Health-/Login-Route erreichbar; `scripts/seed-opencloud-demo.py` wartet aktiv darauf statt sofort mit Verbindungsfehler abzubrechen.
- [x] Nach erfolgreichem Lauf von `scripts/seed-opencloud-demo.py` existiert im Demo-Space mindestens ein Ordner mit mehreren Beispielfotos, abrufbar über denselben `OpenCloudClient`-Codepfad (Graph-API-Space-Liste + WebDAV-PROPFIND), den auch das Produktiv-Backend nutzt.
- [ ] **Aktuell NICHT demonstrierbar, blockiert durch einen unabhängigen, vorbestehenden Bug außerhalb dieser Spec:** Mit den Werten aus `.env.demo.example` kann Daniel im PhotoSort-Frontend den Demo-Space browsen, ein Projekt anlegen, einen Scan starten und die automatische Bewertung (Spec 0003) durchspielen — ohne Codeänderung, nur andere `.env`. Beim finalen End-to-End-Test (voller Stack, echter Login, `GET /opencloud/browse`) reproduzierbar mit `500 Internal Server Error` fehlgeschlagen: `backend/src/photosort/opencloud/client.py::list_drives` liest `item["webDavUrl"]` auf oberster Ebene der Graph-API-Antwort, der echte Server liefert es aber unter `item["root"]["webDavUrl"]` — `KeyError: 'webDavUrl'` (vollständiger Traceback im Abschlussbericht des zugehörigen PRs). Demo-Container und Seed-Skript selbst funktionieren nachweislich korrekt (siehe voriges AK sowie direkte WebDAV-/Graph-API-Verifikation ohne den Backend-Codepfad) — der Bruch liegt ausschließlich im bereits vor diesem Feature bestehenden Produktivcode, der laut AK unten bewusst nicht angefasst wird. Siehe `specs/roadmap.md` für das daraus resultierende Bugfix-Ticket.
- [x] Erneutes Ausführen von `scripts/seed-opencloud-demo.py` gegen einen bereits geseedeten Container bricht nicht ab und erzeugt keine Duplikate (Idempotenz).
- [x] `scripts/seed-opencloud-demo.py` validiert die Ziel-`OPENCLOUD_BASE_URL` vor dem Schreiben gegen ein erwartetes Demo-Muster und bricht mit klarer Warnung ab, falls sie nicht offensichtlich auf den lokalen Demo-Container zeigt (verhindert versehentliches Schreiben in einen echten Familien-Space bei falscher `.env`).
- [x] `docker-compose.demo.yml` bindet den OpenCloud-Port explizit auf `127.0.0.1`, nicht ungebunden wie der Hauptstack.
- [x] README enthält die drei nötigen Schritte (Overlay starten, Seed-Skript laufen lassen, `.env.demo.example` nutzen) in nachvollziehbarer Reihenfolge.
- [x] Der reguläre Pfad mit echtem OpenCloud-Server bleibt unverändert; kein Produktivcode (`backend/src/photosort/opencloud/*`) wird angefasst, kein neuer "ist das der Mock"-Codepfad.

## Datenmodell-Bezug

Keines. Backend/Worker/Frontend sprechen exakt denselben `OpenCloudClient`-Code-Pfad wie im Produktivbetrieb an — nur `OPENCLOUD_BASE_URL` (und die übrigen `OPENCLOUD_*`-Werte) zeigen auf den lokalen Demo-Container statt auf eine echte Instanz. Siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Architektur / Umsetzung

**Ansatz:** Kein selbstgebauter Mock-Server. Stattdessen ein optionaler zweiter Compose-Stack, der den echten OpenCloud-Server als Container startet und mit Beispielfotos befüllt — siehe [`decisions/0009-local-opencloud-demo-stack.md`](../decisions/0009-local-opencloud-demo-stack.md). Rein additiv: Das bestehende `docker-compose.yml` und der Default-Workflow mit echten Zugangsdaten bleiben unverändert, kein Produktivcode (`backend/src/photosort/opencloud/*`) wird angefasst.

**Neue/betroffene Komponenten:**

- **`docker-compose.demo.yml`** (neue Overlay-Datei, Root): zusätzlicher Service `opencloud-demo` (Image `opencloudeu/opencloud-rolling`), mit `IDM_CREATE_DEMO_USERS=true`, `PROXY_ENABLE_BASIC_AUTH=true`, `OC_INSECURE=true`, **`OC_URL=http://opencloud-demo:9200`** (siehe ADR 0010 — nötig, damit die vom Container zurückgelieferte Selbstreferenz-URL, u.a. `webDavUrl` in der Graph-API-Antwort, für alle Aufrufer im Compose-Netzwerk konsistent auflösbar ist), Port explizit auf `127.0.0.1` gebunden (siehe Security), eigenes Volume für Serverdaten, kein eigenes `networks:` (tritt dem `default`-Netzwerk aus Spec 0010 bei). Aufruf per `docker compose -f docker-compose.yml -f docker-compose.demo.yml up`, ergänzt die bestehenden Services (postgres, redis, backend, worker, frontend), ersetzt keinen davon.
- **`.env.demo.example`** (neu, Root, analog zu `.env.example`): vorausgefüllte `OPENCLOUD_*`-Werte, die zum Demo-Container passen (`OPENCLOUD_BASE_URL=http://opencloud-demo:9200`, `OPENCLOUD_USERNAME=alan`, `OPENCLOUD_APP_TOKEN=demo`, `OPENCLOUD_DRIVE_NAME=<Demo-Space-Name>`) — macht sichtbar, dass hier bewusst Demo-Zugangsdaten stehen, kein Geheimnis. Dieser eine Wertesatz wird konsistent von Backend, Worker **und** dem Seed-Service genutzt (siehe ADR 0010), keine Differenzierung nötig. `.gitignore` erhält eine `!.env.demo.example`-Ausnahme analog zu `!.env.example`, sonst greift die pauschale `.env.*`-Sperre auch hier.
- **`scripts/seed-opencloud-demo.py`** (neu, eigenständiges Skript außerhalb von `backend/src/photosort/`): wartet auf den erreichbaren Demo-Container, legt einen Ordner an und lädt ein kleines Set mitgelieferter Beispielfotos per direktem WebDAV-`PUT` (eigener schlanker `httpx`-Aufruf, nicht über `OpenCloudClient`, da dieser keinen Upload kennt und das auch nach dieser Spec nicht bekommen soll) in den Demo-Space hoch. Validiert vor dem Schreiben, dass `OPENCLOUD_BASE_URL` auf ein erwartetes Demo-Muster passt (siehe Security). **Läuft als eigener, optionaler Compose-Service (`seed`, Profil `seed`) im selben Docker-Netzwerk wie `opencloud-demo` — nicht als bloßer Host-Python-Prozess** (siehe ADR [`0010`](../decisions/0010-demo-seed-script-as-compose-service.md), das diese von Spec/ADR 0009 offen gelassene Netzwerk-Erreichbarkeitsfrage klärt: `OC_URL` ist self-referenziell und nur ein gemeinsames Compose-Netzwerk macht `OPENCLOUD_BASE_URL` für Backend/Worker/Seed-Service konsistent auflösbar). Aufruf: `docker compose -f docker-compose.yml -f docker-compose.demo.yml --profile seed run --rm seed`. Dafür neu: kleines `scripts/Dockerfile` (Python-Basisimage, `httpx`, Skript). Der Unit-Test des Skripts (siehe Teststrategie) bleibt davon unberührt, da das Skript weiterhin ein normales, per `pytest` testbares Python-Modul ist.
- **`README.md`** (Root): neuer Abschnitt "Lokal ausprobieren ohne echten OpenCloud-Server" mit den drei Schritten (Compose-Overlay starten, Seed-Service per `--profile seed run` laufen lassen, `.env.demo.example` nutzen).

**Datenfluss:** Backend/Worker sprechen im Demo-Modus exakt denselben `OpenCloudClient`-Code-Pfad wie im Produktivbetrieb an — nur `OPENCLOUD_BASE_URL` zeigt auf den lokalen Container statt auf die echte Instanz. Keine Verzweigung im Produktivcode, kein "ist das jetzt der Mock"-Flag.

**Wiederverwendete vs. neue Muster:** Wiederverwendet werden die Compose-Overlay-Konvention (analog zum bestehenden Ein-Datei-Setup, nur um eine zweite `-f`-Datei erweitert) und das bestehende, rein Env-Var-basierte OpenCloud-Konfigurationsmuster (`config.py` bleibt unverändert). Neu ist der Seed-Mechanismus (`scripts/seed-opencloud-demo.py`) — bewusst als eigenständiges Skript außerhalb der Produktiv-Codebasis, nicht als neuer Backend-Endpoint oder CLI-Befehl, da Upload/Seed keine Anwendungsfunktion ist, sondern reines Setup-Tooling für diesen Demo-Zweck. Ebenfalls neu, aber bewusst eng auf diesen Demo-Zweck begrenzt: ein eigener, per `profiles: ["seed"]` optionaler Compose-Service samt kleinem `scripts/Dockerfile`, der das Skript im selben Docker-Netzwerk wie `opencloud-demo` ausführt statt es als Host-Prozess laufen zu lassen (siehe ADR [`0010`](../decisions/0010-demo-seed-script-as-compose-service.md)) — löst die self-referenzielle `OC_URL`-Netzwerkfrage strukturell, statt sie mit Host-spezifischer Sonderlogik im Skript zu kaschieren.

**Bezug zur Contract-Drift-Lücke** (`architecture/0002-testkonzept.md`): Adressiert sie nicht automatisiert (kein CI-Integrationstest, dieses Feature bleibt ein manuelles Ausprobier-Tool), reduziert das Risiko aber praktisch, da vor größeren Änderungen jetzt bequem manuell gegen einen echten Server statt nur gegen Fakes geprüft werden kann. Eine automatisierte CI-Anbindung an den Demo-Container wäre eine separate, spätere Spec/ADR.

**Nachtrag aus dem manuellen Smoke-Test (echter Container statt Fake):** Zwei weitere, von ADR 0009 nicht vorweggenommene Startvoraussetzungen des Single-Containers wurden empirisch festgestellt und sind Implementierungsdetail der dort bereits getroffenen Entscheidung (kein neuer Alternativenvergleich nötig, daher hier vermerkt statt als eigene ADR): (1) `opencloud server` startet ohne vorherige, per `opencloud init` erzeugte Config (`/etc/opencloud`, u.a. `OC_JWT_SECRET`/`OC_TRANSFER_SECRET`/`OC_MACHINE_AUTH_API_KEY`) nicht — gelöst per `entrypoint`/`command`-Override in `docker-compose.demo.yml` (`test -f .../opencloud.yaml || opencloud init ...`, idempotent) mit eigenem `opencloud_demo_config`-Volume. (2) Der eingebaute `idp`-Dienst (OIDC) verlangt einen HTTPS-Issuer und verträgt sich nicht mit `PROXY_TLS=false` (reines HTTP, wie von `OPENCLOUD_BASE_URL=http://...` vorausgesetzt) — deaktiviert per `OC_EXCLUDE_RUN_SERVICES=idp`, da PhotoSort ohnehin ausschließlich Basic-Auth nutzt. Details siehe Kommentare in `docker-compose.demo.yml`.

## UI/UX

Nicht relevant. Das Feature ändert keinen App-Code (Frontend/Backend/Worker bleiben unverändert) und führt keine neue Interaktion, Ansicht oder Zustandsdarstellung in PhotoSort selbst ein — reine lokale Entwicklungsinfrastruktur (Docker-Compose-Overlay, Seed-Skript), über die Kommandozeile bedient. Die App zeigt danach lediglich echte, gegen den Demo-Server geladene Fotos über exakt dieselben bestehenden UI-Pfade an.

## Security

Der Demo-Stack führt einen echten OpenCloud-Container mit bewusst geschwächter Absicherung ein (`PROXY_ENABLE_BASIC_AUTH=true`, `OC_INSECURE=true`, öffentlich dokumentierte Demo-Zugangsdaten). Kein Risiko für den Produktivstack (`docker-compose.yml` unverändert, rein additives Overlay). Muss-Kriterien:

1. `docker-compose.demo.yml` bindet den OpenCloud-Port explizit auf `127.0.0.1`, nicht ungebunden wie der Hauptstack — PhotoSort ist bewusst aus dem offenen Internet erreichbar (siehe `architecture/0003-securitykonzept.md`), ein auf allen Interfaces lauschender Container mit öffentlich bekannten Zugangsdaten wäre bei Betrieb auf einem gemeinsam genutzten Host sofort real ausnutzbar. README/`.env.demo.example` weisen zusätzlich explizit auf "nur lokal starten" hin.
2. `scripts/seed-opencloud-demo.py` validiert `OPENCLOUD_BASE_URL` vor dem Schreiben gegen ein erwartetes Demo-Muster und bricht sonst ab, damit ein versehentlicher Lauf gegen die produktive `.env` keine Fotos in den echten Familien-Space schreibt.
3. `.gitignore` erhält eine `!.env.demo.example`-Ausnahme analog zu `!.env.example`.

Details siehe `specs/architecture/0003-securitykonzept.md` ("Docker-Compose-Netzwerk", "Bekannte Lücken").

## Teststrategie

- **Unit:** `scripts/seed-opencloud-demo.py` bekommt einen eigenen, schlanken Test mit gemocktem `httpx`-Transport (`httpx.MockTransport`) für Warte-/Retry-Logik und Idempotenz ("Ordner/Datei existiert bereits → überspringen, kein Fehler") sowie die Demo-URL-Validierung — echte, verzweigte Logik, kein reiner Konfigurationszustand, daher anders als das dreistufige Verifikationsmuster aus Spec 0007.
- **E2E/Smoke:** voller Ablauf (echter Container, echter Upload, Browsing/Scan/Scoring im Frontend) bleibt manueller Smoke-Test vor Merge — kein CI-Job mit echtem `opencloud-rolling`-Container, da Image-Größe/Startzeit für einen rein lokalen, optionalen Ausprobier-Zweck nicht gerechtfertigt sind.
- Details und Edge Cases (Container noch nicht bereit, Skript mehrfach ausgeführt, abweichender Demo-Space-Name, einzelner fehlgeschlagener Upload) siehe neue Sektion "Lokales Dev-/Demo-Tooling außerhalb des Coverage-Gates" in [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md).

## Out of Scope

- Upload-/Export-Funktionalität im Produktivcode (`OpenCloudClient`) — bleibt Spec 0004 vorbehalten, wird durch das Seed-Skript nicht vorweggenommen.
- Automatisierte CI-Integration gegen den Demo-Container (Contract-Test) — mögliche spätere, eigene Spec.
- Ein gepinnter Release-Tag für `opencloudeu/opencloud-rolling` (aktuell bewusst `:rolling`, siehe ADR 0009) — kann bei Bedarf später ohne neue Spec nachgezogen werden.
- Mehrere/parametrisierbare Demo-Datensätze (z.B. verschiedene Fotomengen/-qualitäten je Ausprobier-Szenario) — ein einziger fester Demo-Datensatz reicht für den Zweck dieser Spec.
