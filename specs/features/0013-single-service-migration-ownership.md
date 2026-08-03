# 0013 - Alembic-Migrationen ausschließlich in `backend` ausführen

**Status:** Implemented ([PR #16](https://github.com/TheRealKoller/photosort/pull/16))
**Erstellt:** 2026-08-03
**Akzeptiert:** 2026-08-03
**Bezug:** Live im Chat mit Daniel entdeckt (2026-08-03), ausgelöst durch einen produktiven Deploy-Fehler über seine Dockhand-Instanz: nach Löschen von `postgres`-Container+Volume und Neu-Deploy schlug der Login mit `401 Unauthorized` fehl; Postgres-Logs zeigten `duplicate key value violates unique constraint "pg_type_typname_nsp_index"` beim Anlegen von `alembic_version`. Das zugrunde liegende Problem war bereits als bekannte Lücke in `specs/architecture/0002-testkonzept.md:85` dokumentiert (entdeckt als Nebenbefund beim Smoke-Test zu Spec 0010), aber noch nicht als eigene Spec/Fix umgesetzt. Idea-Sharpening-Gespräch mit Daniel im Chat, 2026-08-03.

## Ziel

`backend` und `worker` führen in `docker-compose.yml` bisher beide unabhängig `alembic upgrade head && ...` in ihrem Start-`command` aus und hängen per `depends_on` nur an `postgres`/`redis` (`service_healthy`), nicht aneinander. Gegen eine frisch angelegte, leere Datenbank (Erst-Deploy oder Volume-Reset) starten beide Container ihre Migration praktisch gleichzeitig; da Alembic standardmäßig keinen Postgres-Advisory-Lock nimmt, kollidieren beide beim Anlegen von `alembic_version`. Ziel ist, diese Race strukturell unmöglich zu machen, damit jeder Neu-Deploy gegen eine leere Datenbank zuverlässig mit vollständig durchgelaufener Migrationskette (inkl. Auth-Seed-Migration) endet.

## User Story

Als Betreiber von PhotoSort (Daniel) möchte ich, dass beim Start von `backend` und `worker` gegen eine leere Datenbank die Alembic-Migrationen zuverlässig genau einmal und vollständig durchlaufen, damit ein frischer Deploy nicht durch eine Race Condition zwischen beiden Containern in einem inkonsistenten Schema-Zustand landet (fehlende Auth-Seed-User, 401 beim Login).

## Akzeptanzkriterien

- [ ] **Statischer Konfigurations-Check (CI, `docker-compose-check`-Job):** `docker compose config` zeigt für `worker` ein `command` ohne die Zeichenkette `alembic`; für `backend` weiterhin `alembic upgrade head && uvicorn ...`.
- [ ] **Funktionaler Compose-Smoke-Test gegen frische, leere DB (CI, neuer Schritt im `docker-compose-check`-Job):** frisches `postgres_data`-Volume, `docker compose up -d --build`, warten bis `backend` `healthy` ist (mit Timeout). Dann:
  - `docker compose logs backend` enthält die Alembic-Ausgabe für Revision `1574f8180817` genau einmal; `docker compose logs worker` enthält keine Alembic-Ausgabe.
  - `alembic_version`-Tabelle enthält genau eine Zeile mit dem aktuellen `head` (per `alembic heads` ermittelt, nicht hartkodiert).
  - `RestartCount` beider Container ist `0`.
  - `POST /auth/login` mit den im Testlauf gesetzten `AUTH_SEED_USER1_*`-Credentials liefert `200` + Token.
  - Der Fehler `duplicate key value violates unique constraint "pg_type_typname_nsp_index"` taucht in keinem der beiden Container-Logs auf.
- [ ] **Idempotenz bei Neustart gegen bereits migrierte DB:** `docker compose restart backend` gegen eine bereits vollständig migrierte DB läuft fehlerfrei durch, ohne Seed-User zu duplizieren (bereits durch bestehenden Unit-Test der Seed-Migration abgedeckt, hier nur explizit als AC nachgezogen).
- [ ] **Demo-Overlay-Kompatibilität:** `docker compose -f docker-compose.yml -f docker-compose.demo.yml config -q` bleibt gültig (bestehender CI-Schritt, `docker-compose.demo.yml` definiert `backend`/`worker` nicht neu).
- [ ] Normalbetrieb gegen eine bereits migrierte, bestehende Datenbank bleibt unverändert (kein spürbarer zusätzlicher Overhead, kein Verhaltensunterschied bei einem Neustart ohne ausstehende Migrationen).

**Bewusst nicht automatisiert getestet:** Der Fall "`backend` wird nie `healthy`" (z.B. Migration schlägt dauerhaft fehl) lässt `worker` laut `depends_on: condition: service_healthy` unbegrenzt warten bzw. lässt `docker compose up` mit "dependency failed to start" abbrechen — beabsichtigtes Verhalten, aber kein automatisierter CI-Test dafür (ein Test, der bewusst auf einen nie erfüllten Health-Check wartet, riskiert einen hängenden CI-Job). Stattdessen einmaliger manueller Smoke-Test-Nachweis bei der Umsetzung.

**Nicht Scope dieser Spec:** mehrere `backend`-Replicas (`--scale backend=2`) — würde einen Advisory-Lock nötig machen, siehe ADR 0012, "Nachzieh-Option".

## Datenmodell-Bezug

Keines. Reine Deploy-/Startreihenfolge-Änderung, kein neues oder geändertes Datenmodell.

## Architektur / Umsetzung

**Ansatz:** Migrationen laufen künftig ausschließlich im `backend`-Service. `worker` führt `alembic upgrade head` nicht mehr selbst aus, sondern wartet über einen neuen Compose-Healthcheck auf `backend`, bevor er startet. Siehe [`decisions/0012-single-service-migration-ownership.md`](../decisions/0012-single-service-migration-ownership.md) für die vollständige Begründung und die verworfenen Alternativen (dedizierter `migrate`-Service, Postgres-Advisory-Lock).

**Betroffene Dateien — ausschließlich `docker-compose.yml`:**

- Service `backend`: neuer `healthcheck`-Block gegen den bestehenden `/health`-Endpoint (`backend/src/photosort/main.py:56`), python-basiert (kein `curl`/`wget` im `python:3.12-slim`-Image):
  ```yaml
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]
    interval: 5s
    timeout: 5s
    retries: 10
    start_period: 10s
  ```
  (`start_period` neu gegenüber dem `postgres`/`redis`-Muster, da `backend` vor dem ersten erfolgreichen Check erst die Migration durchlaufen muss.)
- Service `worker`: `command` verliert `alembic upgrade head &&` — wird zu `command: ["python", "-m", "arq", "photosort.worker.WorkerSettings"]` (kein `sh -c`-Wrapper mehr nötig). `depends_on` bekommt zusätzlich zu den bestehenden `postgres`/`redis`-Einträgen (bleiben unverändert, `worker` braucht sie weiterhin direkt) einen dritten Eintrag `backend: condition: service_healthy`.
- `backend/alembic/env.py` und `backend/Dockerfile`: keine Änderung (kein Advisory-Lock, kein zusätzliches Paket nötig — `python` ist im Image bereits vorhanden).

**ADR:** [`decisions/0012-single-service-migration-ownership.md`](../decisions/0012-single-service-migration-ownership.md) — Migration nur in `backend`, kein dedizierter `migrate`-Service (vermeidet ungetestete Abhängigkeit von `depends_on: condition: service_completed_successfully`, dessen Unterstützung durch Daniels Dockhand-Instanz nicht verifiziert ist), kein zusätzlicher Advisory-Lock (würde ein Problem absichern, das nach dieser Änderung strukturell nicht mehr existiert).

**Nicht betroffen:** `specs/architecture/0001-overview.md` und `README.md` — keine strukturelle Architektur-/Datenmodelländerung, nur Start-Reihenfolge-Robustheit.

## UI/UX

Nicht relevant. Reine Backend-/Infrastruktur-Änderung (`docker-compose.yml`), keine Frontend-Dateien betroffen.

## Security

Nicht sicherheitsrelevant: reine Deploy-/Startreihenfolge-Änderung (Migration nur noch im `backend`-Service, `worker` wartet per Compose-Healthcheck), keine neue Eingabe von außen, keine Auth-/Berechtigungsänderung. `/health` bleibt unverändert exponiert und informationslos (statische `{"status": "ok"}`-Antwort, keine `get_current_user`-Dependency) — die neue Nutzung als Healthcheck-Ziel ist ein containerinterner Aufruf, kein neuer externer Zugriffspfad. Der Wechsel von `sh -c "..."` auf Exec-Form (`["python", "-m", "arq", ...]`) bei `worker` ist eine marginale Verbesserung (eine Shell-Zwischenschicht weniger), kein neues Risiko — es gab vorher ohnehin keine Nutzereingabe im Kommando. Eine unvollständig durchgelaufene Migration (der bisherige Fehlerzustand) ist ein reines Verfügbarkeitsproblem (kompletter Login-Ausfall für legitime Nutzer), kein Auth-Bypass. Details siehe security-engineer-Konsultation, 2026-08-03.

## Teststrategie

- **Test First (Infrastruktur-Ebene, kein klassischer Unit-Test):** Vor der Compose-Änderung muss ein neuer funktionaler CI-Schritt die aktuell noch reproduzierbare Race gegen frische DB zuverlässig als rot erkennen — sonst ist nicht belegt, dass der Test sie überhaupt findet.
- Zwei dauerhafte neue Prüfungen im bestehenden `docker-compose-check`-CI-Job (kein Wegwerf-Test): (1) statischer Config-Check "`worker`-Command enthält kein `alembic`" als schneller Regressionsschutz, (2) funktionaler Smoke-Test gegen frisches Volume mit Log-/`RestartCount`-/Login-Assertions (siehe Akzeptanzkriterien). Kein Retry-Loop nötig, da die Race durch ADR 0012 strukturell (nicht nur statistisch) eliminiert wird — `worker` ruft `alembic` nach der Änderung gar nicht mehr auf.
- Manueller Smoke-Test bei der Umsetzung (Muster aus `architecture/0002-testkonzept.md`): `docker compose down -v` (Volume löschen, wie bei Daniels ursprünglichem Repro), `docker compose up --build`, verifizieren, dass Login mit den Seed-Usern sofort funktioniert, ohne manuellen Neustart eines Containers. Zusätzlich einmalig verifizieren: `backend` absichtlich nicht healthy werden lassen (z.B. `SECRET_KEY` auf ungültigen Platzhalter), beobachten dass `worker` nicht hochkommt statt auf ungesichertem Schema zu laufen.
- `specs/architecture/0002-testkonzept.md`: Eintrag "Bekannte Lücken" (Zeile 85) auf "gelöst, siehe ADR 0012" aktualisieren; Abschnitt "Backend"/E2E-Ebene um den neuen permanenten CI-Schritt ergänzen (zweiter Fall eines funktionalen, nicht nur Syntax-Compose-Checks nach dem Netzwerk-Check aus Spec 0010 — lohnt sich, das Muster "funktionaler Compose-Check in CI" dort explizit als wiederverwendbares Vorgehen zu benennen). Wird vom `test-engineer` nach Umsetzung/Review des Feature-Branches gepflegt, nicht bereits jetzt beim Spec-Sharpening.

## Offene Fragen

- Soll dieser Bugfix vor, nach oder parallel zum bestehenden `webDavUrl`-Bug bearbeitet werden (beide aktuell unter "Jetzt" in `specs/roadmap.md`)? Blockiert nicht die Umsetzung dieser Spec selbst, nur die Bearbeitungsreihenfolge.

## Out of Scope

- Mehrere `backend`-Replicas / horizontale Skalierung — würde einen Advisory-Lock nötig machen (siehe ADR 0012, dort als künftige Nachzieh-Option benannt), aktuell nirgends geplant.
- Automatisierter CI-Test für den Fall "`backend` wird nie healthy" — Risiko eines hängenden CI-Jobs überwiegt den Testwert, bleibt manueller Smoke-Test.
- Ein dedizierter `migrate`-One-Off-Compose-Service — bewusst verworfene Alternative, siehe ADR 0012.

## Entscheidungen

- Migration nur noch in `backend`, `worker` wartet per Healthcheck-Gate statt eigener Migration — kein dedizierter `migrate`-Service, kein Advisory-Lock (architect-Konsultation, 2026-08-03, siehe ADR 0012).
- Healthcheck-Timing-Werte (`interval: 5s, timeout: 5s, retries: 10, start_period: 10s`) analog zum bestehenden `postgres`/`redis`-Muster, mit zusätzlichem `start_period` für die Migrationsdauer (test-engineer-Konsultation, 2026-08-03).
- Kein automatisierter Test für "`backend` nie healthy" — Abwägung Testwert gegen Risiko eines hängenden CI-Jobs, stattdessen manueller Smoke-Test (test-engineer-Konsultation, 2026-08-03).
- Kein Retry-Loop im funktionalen CI-Test nötig, da die Race strukturell (nicht nur statistisch) eliminiert wird (test-engineer-Konsultation, 2026-08-03).
- Nicht sicherheitsrelevant, kein Update von `specs/architecture/0003-securitykonzept.md` nötig (security-engineer-Konsultation, 2026-08-03).
- Relative Priorität gegenüber dem bereits offenen `webDavUrl`-Bug in `specs/roadmap.md`: beide unter "Jetzt" eingeordnet (requirements-engineer-Konsultation, 2026-08-03). Die genaue Bearbeitungsreihenfolge zwischen beiden ist eine offene Rückfrage an Daniel, siehe Abschnitt "Offene Fragen".
