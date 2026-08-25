# 0034 - Strukturiertes Logging für Cloud-Vision-Fehler (erste Logging-Einführung im Projekt)

**Status:** Accepted
**Datum:** 2026-08-24
**Bezug:** [`inbox/0039-logging-fuer-remote-kategorie-calls-fehlt.md`](../inbox/0039-logging-fuer-remote-kategorie-calls-fehlt.md) (Ursprung), künftige Feature-Spec 0056, [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) (Punkt 3: best-effort/`continue`-Verhalten der Landmark-Phase, hier unverändert), [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Punkt 5: dasselbe best-effort-Verhalten für die Remote-Kategorie-Klassifizierung), `cloud_vision.py` (`raise_for_vision_api_status`/`*_response_to_json`, bereits bestehendes Sicherheits-Muss-Kriterium "Fehlermeldungen betten nie Base64-Bilddaten/API-Key ein").

## Kontext

Im gesamten Backend (`backend/src/photosort/`) existiert aktuell **kein einziges** `logging`/`print`. Zwei Stellen verschlucken pro Foto fehlgeschlagene Cloud-Vision-Aufrufe bewusst best-effort mit `except`/`continue` (dokumentierte, unveränderte Design-Entscheidung, ADR 0025 Punkt 3 bzw. ADR 0032 Punkt 5): `worker.py::run_criterion_scoring` (Landmark-Phase, `_detect_landmark_for_photo`) und `worker.py::run_remote_category_classification` (`_classify_photo_for_remote_category`). Nach einem Lauf ist nicht mehr feststellbar, ob/warum ein Foto übersprungen wurde — `docker compose logs` zeigt dazu nichts, obwohl beide Backend-Prozesse (`uvicorn`/`python -m arq`, siehe `docker-compose.yml`) bereits vollständig über stdout/stderr geloggt und von `docker compose logs` eingesammelt werden.

Da dies die **erste** Logging-Einführung im Projekt ist, legt diese ADR nicht nur die konkrete Umsetzung für die beiden genannten Stellen fest, sondern eine projektweite, wiederverwendbare Konvention für jedes künftige Feature, das Logging braucht.

## Entscheidung

### 1. Python-Standardbibliothek `logging`, keine externe Dependency

Kein `structlog` oder vergleichbares Paket. Es existiert keine Log-Aggregation/-Suche-Infrastruktur (kein ELK/Loki/o.ä.) — einziger Konsument ist `docker compose logs` für einen Einzelbetreiber (Daniel). Strukturiertes JSON-Logging wäre Mehraufwand ohne erkennbaren Nutzen für diesen Betriebskontext; Minimalismus-Prinzip (ADR 0006), konsistent mit der wiederholt im Projekt getroffenen "keine neue Abhängigkeit ohne echten Bedarf"-Linie (z.B. ADR 0025 Punkt 1 zum `httpx`-statt-SDK-Ansatz).

### 2. Logger-Pattern: `logging.getLogger(__name__)` pro Modul, zentrale Einmal-Konfiguration über neues Modul `logging_config.py`

- Jedes Modul, das loggen will, holt sich seinen eigenen Logger über das idiomatische Standard-Pattern `logger = logging.getLogger(__name__)` (Modul-Konstante direkt nach den Imports) — kein Logger-Objekt wird durchgereicht/injiziert. Für die konkrete Spec 0056 betrifft das nur `worker.py` (beide `except`-Blöcke liegen dort, nicht in `landmark.py`/`remote_classification.py`/`cloud_vision.py` — die Exception-Objekte kommen dort bereits fertig aus `asyncio.gather(..., return_exceptions=True)` zurück, `worker.py` hat als einzige Stelle sowohl die Exception als auch den Foto-Kontext).
- Neues, eigenständiges, sehr kleines Modul `backend/src/photosort/logging_config.py` mit genau einer Funktion `configure_logging() -> None` (`logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`). Eigenes Modul statt Anhängsel an `config.py` (das nur die pydantic-`Settings` führt, keine Prozess-Bootstrap-Logik) — konsistent mit dem im Projekt etablierten Prinzip, eine neue, isolierte Zuständigkeit in ein eigenes kleines Modul zu legen (`aesthetics.py`, `landmark.py`, `horizon.py`).
- **Aufruf an beiden Prozess-Einstiegspunkten, nicht nur beim Worker:** `main.py::create_app()` ruft `configure_logging()` (API-Prozess, `uvicorn`), `worker.py::WorkerSettings` bekommt einen `on_startup`-Hook, der `configure_logging()` ruft (Worker-Prozess, `python -m arq`, erste Nutzung von arqs `on_startup`-Mechanismus im Projekt, analog zur ersten Nutzung von arqs Cron-Mechanismus in ADR 0019). Beide Prozesse bekommen dieselbe Konfiguration, obwohl nur der Worker sie für Spec 0056 tatsächlich braucht — bewusst, damit ein künftiges Feature mit API-seitigem Logging-Bedarf nicht erneut eine Konfigurationsentscheidung treffen muss. Ohne einen expliziten `basicConfig`-Aufruf würde Python zwar über den "Handler of last resort" ohnehin auf stderr ausgeben, aber ohne Zeitstempel/Level/Modulname — für die Fehlersuche zu mager.

### 3. Log-Level: `WARNING`, nicht `ERROR`

Der Skip eines einzelnen Fotos ist eine **erwartete, dokumentierte** Verhaltensweise (best-effort, ADR 0025/0032) — der Lauf selbst schließt weiterhin mit `status=success` ab, kein Job-Fehlschlag. `ERROR` ist im Projekt bereits an die tatsächliche `FAILED`-Semantik eines Laufs gebunden (`_fail_run`, Watchdog ADR 0019) — würde `ERROR` für einen einzelnen, für sich genommen harmlosen Foto-Skip verwendet, verwischt das die Unterscheidung zwischen "ein Lauf ist wirklich fehlgeschlagen" und "ein Lauf lief durch, ein Foto wurde übersprungen". `WARNING` passt semantisch (Python-Konvention: "etwas Unerwartetes, Software funktioniert weiterhin wie vorgesehen") und bleibt bei `docker compose logs` ohne zusätzliches Level-Flag sichtbar (Default-Threshold `WARNING` aus Punkt 2).

### 4. Format: einfacher Text über stdout, kein JSON

`docker compose logs` sammelt stdout/stderr beider Prozesse bereits vollständig ein und zeigt sie chronologisch an — ein Format-String mit Zeitstempel/Level/Loggername/Message (siehe Punkt 2) reicht für das manuelle Durchsuchen durch einen einzelnen Betreiber. Kein strukturiertes JSON (keine Log-Pipeline, die es parsen würde, siehe Punkt 1).

### 5. Inhalt/Leitplanke: kein Rohtext von API-Antworten, kein Traceback, nur Fehlergrund + Foto-Kontext

- Geloggt wird ausschließlich: `type(exc).__name__`, `str(exc)` (die bereits an der Exception-Konstruktionsstelle sanitierte Meldung — `cloud_vision.py::raise_for_vision_api_status` liefert nur Statuscode+Reason-Phrase, `anthropic_response_to_json`/`mistral_response_to_json` liefern nur eine generische Meldung ohne Rohtext, bestehendes Sicherheits-Muss-Kriterium aus ADR 0025/0031/0032 — **wird durch diese ADR nicht verändert, nur wiederverwendet**), plus `photo.id`/`photo.relative_path` als Foto-Kontext.
- **Explizit verboten:** rohe HTTP-Response-Bodies/-Header direkt aus dem `except`-Block heraus loggen (nur über die bereits sanitierte Exception-Message gehen, nie erneut auf `response.text`/`response.json()`/`response.headers` zugreifen), Bild-Bytes/Base64-Daten, API-Keys/Settings-Werte.
- Kein `exc_info=True`/voller Traceback — eine Zeile pro fehlgeschlagenem Foto reicht für den beschriebenen Zweck (Fehlergrund + Kontext, kein Debugging-Traceback für eine erwartete, best-effort behandelte Bedingung) und hält das Log-Volumen bei vielen übersprungenen Fotos überschaubar.
- **Offener Punkt für `security-engineer`s Detailprüfung (nicht hier final entschieden):** Ob `str(exc)` bei einem von `httpx.HTTPError` gewrappten Netzwerkfehler (`LandmarkApiError(f"... nicht erreichbar: {exc}")`, `landmark.py`) in Ausnahmefällen URL-Query-Parameter oder ähnliches enthalten könnte, die nicht für ein Log gedacht sind — die bisherige Praxis im Projekt geht davon aus, dass httpx-Transportfehler keine Header/Secrets in ihrer String-Repräsentation führen, das ist aber nicht ADR-seitig verifiziert.

### 6. Beide Call-Sites gleich behandelt, keine neue Settings-Option

`_detect_landmark_for_photo`- und `_classify_photo_for_remote_category`-Fehlschläge werden identisch geloggt (gleiche Message-Struktur, unterschiedlicher Phasenname im Text zur Unterscheidung). Level ist fest `WARNING`, kein neues env-überschreibbares Settings-Feld dafür — Log-Level-Konfigurierbarkeit ist kein hier vorliegender Bedarf, YAGNI, analog zu anderen im Projekt bewusst als Modul-Konstante (nicht Settings-Feld) geführten rein technischen Werten (z.B. `VISION_REQUEST_TIMEOUT_SECONDS`).

## Begründung

- Löst das konkrete Sichtbarkeitsproblem (Inbox 0039) minimal-invasiv, ohne das bestehende, bewusst unveränderte best-effort/`continue`-Verhalten anzutasten.
- Etabliert eine einzige, wiederverwendbare Logging-Konvention für das gesamte Projekt statt einer feature-lokalen Ad-hoc-Lösung, die bei der nächsten Logging-Anforderung erneut entschieden werden müsste.
- Wiederverwendet ein bereits bestehendes Sicherheits-Muss-Kriterium (sanitierte Fehlermeldungen in `cloud_vision.py`) statt eine parallele, neue Sanitisierungslogik einzuführen.

## Konsequenzen

- **Neue Backend-Abhängigkeit:** keine.
- **Neues Modul:** `backend/src/photosort/logging_config.py` (`configure_logging()`).
- **Neue Aufrufstellen:** `main.py::create_app()` (Anfang der Funktion), `worker.py::WorkerSettings.on_startup`.
- **Kein neues Settings-Feld, keine Migration, kein neuer Endpunkt, kein Datenmodell-Bezug.**
- **`docs/architecture.md`** (Owner `architect`) bekommt nach Umsetzung einen kurzen Eintrag zur neuen, projektweiten Logging-Konvention (erster Präzedenzfall) — nachgezogen im selben PR wie die Implementierung, nicht durch diese ADR selbst.
- Ein künftiges Feature, das ebenfalls loggen will, folgt demselben Pattern (`logging.getLogger(__name__)` im jeweiligen Modul, `configure_logging()` bleibt unverändert einmalig) — kein erneuter ADR-Bedarf für die reine Anwendung dieser Konvention, nur bei einer tatsächlichen Änderung der Konvention selbst (z.B. Wechsel auf strukturiertes Logging, falls später eine Aggregations-Infrastruktur entsteht).
