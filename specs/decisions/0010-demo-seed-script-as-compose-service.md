# 0010 - Seed-Skript für den OpenCloud-Demo-Stack läuft als eigener Compose-Service

**Status:** Accepted
**Datum:** 2026-08-02

## Kontext

Spec 0009 / ADR 0009 legen fest, dass ein echter `opencloudeu/opencloud-rolling`-Container (`opencloud-demo`) als optionales Compose-Overlay läuft und `scripts/seed-opencloud-demo.py` ihn per direktem WebDAV-`PUT` mit Beispielfotos befüllt — über denselben Graph-API-Codepfad (`GET /graph/v1.0/me/drives` → Feld `webDavUrl`), den auch `OpenCloudClient` im Backend nutzt. Weder Spec noch ADR 0009 entscheiden, **von wo** dieses Skript läuft, und genau das ist während der Umsetzung zu einer echten Weggabelung geworden:

Der OpenCloud-Container hat eine Selbstreferenz-Konfiguration (`OC_URL`), aus der er self-referenzielle URLs baut (u.a. das von der Graph-API zurückgelieferte `webDavUrl`). `OC_URL` kann nur einen Wert haben, aber zwei Aufrufer müssen den Container erreichen:

1. **Backend/Worker** — laufen im Docker-Compose-Netzwerk, erreichen `opencloud-demo` per Docker-DNS unter `http://opencloud-demo:9200`. `.env.demo.example` setzt entsprechend `OPENCLOUD_BASE_URL=http://opencloud-demo:9200` (siehe Spec 0009, Architektur/Umsetzung).
2. **Das Seed-Skript** — bei Ausführung direkt auf dem Host (`python scripts/seed-opencloud-demo.py`, wie der Wortlaut von Spec/ADR 0009 nahelegt) kann `opencloud-demo` nicht per Docker-DNS auflösen, nur den auf `127.0.0.1` gebundenen Host-Port (AK aus Spec 0009).

Setzt man `OC_URL=http://opencloud-demo:9200` (nötig für Backend/Worker), liefert die Graph-API dem Host-Skript ein `webDavUrl`, das vom Host aus nicht erreichbar ist — selbst wenn der initiale Graph-API-Call noch über den Host-Port gelingt. Ein rein Host-erreichbarer `OC_URL`-Wert wiederum macht das Ergebnis für Backend/Worker unbrauchbar.

Zusätzlicher Kontext aus Spec 0010 ("Explizites IPv4-only Docker-Netzwerk", bereits Accepted): `opencloud-demo` deklariert bewusst **kein eigenes `networks:`** und tritt damit automatisch dem gemeinsamen `default`-Netzwerk bei, in dem Backend/Worker es per Servicename erreichen — die Netzwerktopologie des Demo-Stacks ist also bereits explizit auf "ein gemeinsames Compose-Netzwerk, Erreichbarkeit per Servicename" ausgelegt.

Geprüfte Optionen:

1. Seed-Skript als eigener, optionaler Compose-Service im selben Netzwerk wie `opencloud-demo`.
2. Seed-Skript bleibt Host-Prozess, überschreibt/normalisiert den von der Graph-API gelieferten `webDavUrl`-Host client-seitig auf den tatsächlich für den Request genutzten Host.
3. Seed-Skript bleibt Host-Prozess, `/etc/hosts`-Eintrag `opencloud-demo -> 127.0.0.1` wird als Voraussetzung im README verlangt.

## Entscheidung

Wir verwenden Option 1: Das Seed-Skript läuft als eigener, optionaler Compose-Service (`seed`) in `docker-compose.demo.yml`, im selben Docker-Compose-Netzwerk wie `opencloud-demo`/`backend`/`worker` — nicht als Host-Python-Prozess.

Konkret:

- `docker-compose.demo.yml` erhält einen zusätzlichen Service `seed`: `build: ./scripts` (neues, kleines `scripts/Dockerfile`, Python + `httpx` + das Skript), `profiles: ["seed"]` (kein Teil des normalen `up`, da es ein einmaliger Job ist, kein Dauer-Service, und beim ersten Start ohnehin auf den noch nicht bereiten `opencloud-demo`-Container warten müsste). Kein eigenes `networks:` (Konsistenz mit Spec 0010) — tritt automatisch dem `default`-Netzwerk bei.
- `opencloud-demo` erhält zusätzlich zu den bereits in ADR 0009 genannten Env-Vars (`IDM_CREATE_DEMO_USERS`, `PROXY_ENABLE_BASIC_AUTH`, `OC_INSECURE`) explizit `OC_URL=http://opencloud-demo:9200` — ohne das ist die Selbstreferenz-URL des Containers Implementierungsdetail-abhängig/unbestimmt, das war in ADR 0009 nicht erwähnt, ist aber die Wurzel des hier gelösten Problems.
- `.env.demo.example` behält exakt den in Spec 0009 bereits vorgesehenen Wert `OPENCLOUD_BASE_URL=http://opencloud-demo:9200` — dieser eine Wert wird jetzt konsistent von Backend, Worker **und** dem `seed`-Service genutzt, kein zweiter, abweichender Env-Wert nötig.
- Aufruf laut README wird zu `docker compose -f docker-compose.yml -f docker-compose.demo.yml --profile seed run --rm seed` statt `python scripts/seed-opencloud-demo.py`.
- Der Unit-Test des Skripts (`httpx.MockTransport`, siehe Teststrategie in Spec 0009) ist davon unberührt — das Skript bleibt ein normales, per `pytest` testbares Python-Modul; nur die *Laufzeit-Invocation* im Demo-Workflow ändert sich.

## Begründung

- **Ein einziger, konsistenter `OC_URL`/`OPENCLOUD_BASE_URL`-Wert für alle drei Konsumenten** statt eines zweiten, abweichenden Werts nur fürs Skript — direkte Konsequenz aus AK 1 der Spec ("ohne dass Daniel `OPENCLOUD_*`-Variablen manuell setzen muss") und AK 4 ("ohne Codeänderung, nur andere `.env`"), die beide von genau einem Satz Werte ausgehen.
- **Keine Host-Netzwerk-Sonderlogik im Produktiv-adjazenten Code:** Option 2 (URL-Rewriting) würde eine demo-spezifische Workaround-Logik ("ersetze den vom Server gemeldeten Host durch den Host, den ich tatsächlich benutzt habe") ins Skript einführen, die real nur ein Symptom des gewählten Netzwerklayouts behebt. Option 1 macht das Problem strukturell verschwinden, statt es zu kaschieren.
- **Keine manuellen Host-Eingriffe** (Option 3, `/etc/hosts`) — OS-abhängig, widerspricht dem in Spec 0009 explizit gewünschten reibungsarmen "einfach `docker compose up`"-Erlebnis.
- **Konsistent mit der bereits akzeptierten Netzwerktopologie aus Spec 0010:** `opencloud-demo` ist explizit dafür ausgelegt, im gemeinsamen `default`-Netzwerk per Servicename erreichbar zu sein — ein weiterer Service im selben Netzwerk ist die naheliegende Fortführung dieses bereits getroffenen Designs, kein neues Muster.
- **Zusätzlicher Nebennutzen:** Daniel braucht kein lokales Python/`httpx` auf dem Host, um den Demo-Stack auszuprobieren — passt zum "risikofrei ausprobieren"-Ziel von Spec 0009 (rein Docker-basiert, keine Host-Toolchain-Voraussetzung).
- Diese Entscheidung ändert nichts an der Kernentscheidung aus ADR 0009 (echter Container statt Mock) — sie klärt ausschließlich eine dort offen gelassene Frage zur Netzwerk-Erreichbarkeit des Seed-Skripts.

## Konsequenzen

- Neue Datei `scripts/Dockerfile` (klein: Python-Basisimage, `pip install httpx`, Skript kopieren).
- Neuer Service `seed` in `docker-compose.demo.yml`, mit `profiles: ["seed"]`, ohne Port-Publishing (kein zusätzliches Sicherheitsrisiko, da kein neuer offener Port).
- `opencloud-demo` erhält zusätzlich `OC_URL=http://opencloud-demo:9200` (Ergänzung zu den in ADR 0009 bereits genannten Env-Vars).
- README-Schritt "Seed-Skript laufen lassen" wird als `docker compose ... --profile seed run --rm seed`-Aufruf dokumentiert, nicht als direkter `python`-Aufruf.
- Kein Einfluss auf die Unit-Teststrategie des Skripts (bleibt normales, per `pytest` testbares Python-Modul, unabhängig von der Laufzeit-Invocation).
- Kein Einfluss auf Spec 0010 (IPv4-only-Netzwerk) — der neue `seed`-Service dekleriert bewusst ebenfalls kein eigenes `networks:` und bestätigt damit deren Design weiter.
