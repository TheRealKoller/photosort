# 0012 - Alembic-Migrationen laufen nur noch im `backend`-Service, `worker` wartet auf dessen Healthcheck

**Status:** Accepted
**Datum:** 2026-08-03

## Kontext

`docker-compose.yml` lässt `backend` und `worker` bisher unabhängig voneinander `alembic upgrade head && ...` als Teil ihres Start-`command` ausführen (Zeile 48 bzw. 76). Beide hängen per `depends_on` nur an `postgres`/`redis` (`condition: service_healthy`), nicht aneinander. Gegen eine frisch angelegte, leere Datenbank starten beide Container ihre Migration praktisch gleichzeitig; Alembic nimmt beim `ALTER`/`CREATE TABLE`-Vorgehen standardmäßig keinen Postgres-Advisory-Lock, sodass ein Prozess beim konkurrierenden Anlegen der `alembic_version`-Tabelle einen `UniqueViolation` bekommen kann. Dieses Risiko war bereits als bekannte Lücke dokumentiert (`architecture/0002-testkonzept.md`, Abschnitt "Bekannte Lücken"), dort mit zwei Lösungsrichtungen skizziert: (a) Migration nur noch in einem Service ausführen, (b) Postgres-Advisory-Lock in `backend/alembic/env.py` ergänzen.

Konkret bei Daniel aufgetreten nach Löschen von Postgres-Container+Volume und Neu-Deploy über seine externe Dockhand-Instanz: Die Migrationskette lief nicht vollständig durch (inkl. der Auth-Seed-Migration `1574f8180817_seed_auth_users.py`), wodurch keine Seed-User angelegt wurden — Symptom war ein `401` beim Login trotz korrekt konfigurierter `AUTH_SEED_USER*`-Variablen.

Geprüfte Optionen:

1. **Migration nur in `backend`; `worker` wartet per `depends_on: condition: service_healthy` auf einen neuen Compose-Healthcheck auf dem bestehenden `/health`-Endpoint.** Deterministische Startreihenfolge, keine zwei konkurrierenden Migrationsläufe mehr möglich (`worker` führt gar keine Migration mehr aus).
2. **Postgres-Advisory-Lock in `backend/alembic/env.py`** (`pg_advisory_xact_lock` um `do_run_migrations`), beide Services behalten ihren eigenen `alembic upgrade head`-Aufruf, der zweite wartet einfach, bis der erste den Lock freigibt.
3. **Dedizierter `migrate`-One-Off-Service** (`profiles`, Precedent: ADR 0010, dortiger `seed`-Service), `backend`/`worker` hängen per `depends_on: condition: service_completed_successfully` daran.

Option 3 wurde verworfen: `service_completed_successfully` erfordert eine hinreichend aktuelle Docker-Compose-Version; ob Daniels produktiv genutztes externes Deploy-Tool "Dockhand" (siehe Spec 0009/ADR 0007) diese Condition unterstützt, ist nicht verifiziert, und ein Fehlschlag würde sich erst beim nächsten echten Deploy zeigen — also genau in der Situation, die diesen Bug überhaupt ausgelöst hat. Ein Risiko, das sich mit Option 1 vollständig vermeiden lässt, ohne einen neuen Service einzuführen.

## Entscheidung

Wir verwenden **Option 1**: `worker` verliert `alembic upgrade head &&` aus seinem `command`, Migrationen laufen fortan ausschließlich in `backend`. `backend` bekommt einen Compose-Healthcheck auf dem bereits bestehenden `/health`-Endpoint (`backend/src/photosort/main.py:56`). `worker` bekommt zusätzlich zu seinen bestehenden `depends_on`-Einträgen für `postgres`/`redis` (die es für seinen eigenen Betrieb — DB-Zugriff, Queue — weiterhin direkt braucht, unabhängig von `backend`) einen weiteren Eintrag `backend: condition: service_healthy`.

Konkret:

- `docker-compose.yml`, Service `backend`: neuer `healthcheck`-Block, `test: python`-basiert (kein `curl`/`wget` im `python:3.12-slim`-Basisimage vorhanden, kein Grund, dafür das Image aufzublähen — Python selbst reicht für einen einfachen HTTP-GET gegen `localhost:8000/health`).
- `docker-compose.yml`, Service `worker`: `command` wird zu `python -m arq photosort.worker.WorkerSettings` (kein `sh -c "... && ..."`-Wrapper mehr nötig, da nur noch ein Befehl); `depends_on` erhält zusätzlich `backend: condition: service_healthy`.
- Kein neuer Service, kein neues `networks:` (Konsistenz mit Spec 0010 unberührt — `backend`/`worker` deklarieren weiterhin kein eigenes `networks:`).
- `backend/alembic/env.py` bleibt unverändert — kein Advisory-Lock (siehe Begründung unten).

## Begründung

- **Macht die Race-Bedingung strukturell unmöglich statt sie nur zu entschärfen:** Mit nur noch einem Aufrufer von `alembic upgrade head` gibt es keine zwei konkurrierenden `CREATE TABLE`-Läufe mehr, unabhängig von Timing, Systemlast oder Neustartverhalten. Kein Lock nötig, um ein Problem zu vermeiden, das durch das Design gar nicht mehr auftreten kann — konsistent mit dem bereits in ADR 0010 etablierten Prinzip ("das Problem strukturell verschwinden lassen, statt es zu kaschieren").
- **Kein neues Kompatibilitätsrisiko:** `condition: service_healthy` ist ein seit Jahren etabliertes, breit unterstütztes Compose-Feature (im Gegensatz zu `service_completed_successfully`), exakt das gleiche Muster, das `docker-compose.yml` bereits für `postgres`/`redis` verwendet — keine neue, unverifizierte Anforderung an Dockhands Compose-Version.
- **Minimaler, klar lokalisierter Diff:** Eine Zeile `command`-Änderung in `worker`, ein `healthcheck`-Block in `backend`, ein zusätzlicher `depends_on`-Eintrag — kein neuer Service, keine neue Datei, keine Änderung an Anwendungscode.
- **Advisory-Lock (Option 2) bewusst nicht zusätzlich umgesetzt:** Er würde ein reales Problem lösen, das nach dieser Änderung nicht mehr existiert (`worker` ruft `alembic` gar nicht mehr auf) — ein Lock ohne zweiten konkurrierenden Aufrufer ist tote Absicherung gegen ein aktuell nicht vorhandenes Szenario. Er bliebe nur dann relevant, falls künftig **mehrere `backend`-Replicas** gleichzeitig hochskaliert würden (aktuell nirgends geplant oder dokumentiert) oder ein weiterer Service eigenständig `alembic upgrade head` ausführen würde. Sollte einer dieser Fälle eintreten, ist ein `pg_advisory_xact_lock` um `do_run_migrations` in `backend/alembic/env.py` die naheliegende Ergänzung — leichtgewichtig genug, um dann nachgezogen zu werden, ohne die jetzige Entscheidung zu revidieren.
- **Testbar mit vorhandenem CI-Muster:** Der bereits existierende `docker-compose-check`-Job (siehe `.github/workflows/ci.yml`, Funktionscheck zu Spec 0010) bringt bereits `postgres`/`redis` real hoch und prüft reale Docker-Eigenschaften statt nur `docker compose config`. Ein analoger Schritt kann `backend`+`worker` gegen eine frische, leere Datenbank hochfahren und verifizieren, dass beide ohne Neustart (`RestartCount == 0`) durchlaufen — ohne neue Test-Infrastruktur.

## Konsequenzen

- `docker-compose.yml`: `backend` bekommt `healthcheck` (Python-basiert, kein neues Paket im Image nötig); `worker`s `command` verliert `alembic upgrade head &&`, `depends_on` bekommt `backend: condition: service_healthy` zusätzlich zu `postgres`/`redis`.
- `worker` ist ab jetzt strukturell von `backend` abhängig, um zu starten (bisher nur indirekt über die gemeinsame DB-Migration) — bei einem `backend`-Ausfall startet `worker` nicht mehr eigenständig durch, sondern wartet auf dessen Healthcheck. Das ist beabsichtigt: `worker` auf einer Datenbank ohne garantiert vollständiges Schema laufen zu lassen wäre riskanter als diese neue, explizite Abhängigkeit.
- Kein neuer Service, kein neues `networks:`, keine Änderung an Anwendungscode oder Datenmodell.
- Die "Bekannte Lücke" in `architecture/0002-testkonzept.md` (Abschnitt "Bekannte Lücken") ist damit behoben und sollte vom `test-engineer`-Agenten entsprechend aktualisiert werden (Eintrag entfernen bzw. auf "gelöst, siehe ADR 0012" umstellen), inklusive des oben skizzierten CI-Funktionschecks.
- Falls künftig mehrere `backend`-Replicas eingeführt werden: dann greift diese Entscheidung nicht mehr vollständig, und ein Postgres-Advisory-Lock in `backend/alembic/env.py` (Option 2 oben) wird relevant — zu diesem Zeitpunkt per neuer ADR nachzuziehen, nicht durch stille Änderung dieser ADR.
