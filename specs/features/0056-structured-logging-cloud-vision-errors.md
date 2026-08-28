# 0056 - Strukturiertes Logging für Cloud-Vision-Fehler

**Status:** Implemented ([PR #247](https://github.com/TheRealKoller/photosort/pull/247))
**Erstellt:** 2026-08-24
**Bezug:** [`inbox/0039-logging-fuer-remote-kategorie-calls-fehlt.md`](../inbox/0039-logging-fuer-remote-kategorie-calls-fehlt.md) (Ursprung), [`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`](../decisions/0034-strukturiertes-logging-cloud-vision-fehler.md) (neue ADR dieser Spec), [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md) (Punkt 3: best-effort/`continue`-Verhalten der Landmark-Phase, unverändert), [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Punkt 5: identisches best-effort-Verhalten für die Remote-Kategorie-Klassifizierung), [`features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (dort im Betrieb aufgefallen)

## Ziel

Zwei Stellen in `worker.py` (Landmark-Erkennung, Remote-Kategorie-Klassifizierung) verschlucken pro Foto fehlgeschlagene Cloud-Vision-Aufrufe bewusst best-effort mit `except`/`continue`. Im gesamten Backend gibt es aktuell kein einziges `logging`/`print` — nach einem Lauf ist daher nicht mehr feststellbar, ob und warum ein einzelnes Foto übersprungen wurde (Cloud-Fehler wie 401/429, lokaler Lesefehler, Antwort-Parsing-Fehler). `docker compose logs` zeigt dazu nichts, obwohl beide Backend-Prozesse bereits vollständig über stdout/stderr eingesammelt werden. Diese Spec führt strukturiertes Logging für genau diese zwei Fehlerfälle ein — als Nebeneffekt zugleich die erste, projektweit wiederverwendbare Logging-Konvention.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich, dass fehlgeschlagene Cloud-Vision-Aufrufe (Landmark-Erkennung und Remote-Kategorie-Klassifizierung) automatisch mit ihrer Fehlerursache protokolliert werden, damit ich nach einem Lauf über `docker compose logs` nachvollziehen kann, warum einzelne Fotos übersprungen wurden, statt es raten zu müssen.

## Akzeptanzkriterien

- [ ] Ein fehlgeschlagener Pro-Foto-Aufruf in `_detect_landmark_for_photo` (Landmark-Phase, `worker.py::run_criterion_scoring`, ~Zeile 1254-1260) erzeugt genau einen Log-Eintrag auf Level `WARNING`, Logger `logging.getLogger(__name__)` (`photosort.worker`), **bevor** das bestehende `continue` greift.
- [ ] Ein fehlgeschlagener Pro-Foto-Aufruf in `_classify_photo_for_remote_category` (`worker.py::run_remote_category_classification`, ~Zeile 1460-1465) erzeugt ebenso genau einen `WARNING`-Eintrag am `continue`.
- [ ] Konsistentes Muster an beiden Stellen: dieselben Feldarten in derselben Struktur — `type(exc).__name__`, `str(exc)`, `photo.id`, `photo.relative_path`, ein Phasenbezeichner, der die beiden Stellen textuell unterscheidbar macht. Kein `exc_info=True`/voller Traceback.
- [ ] Nur Fehler werden geloggt — erfolgreiche Aufrufe und ein erfolgreich durchgelaufener Gesamtlauf erzeugen keinen Log-Eintrag. Bei N gleichzeitig verarbeiteten Fotos mit M Fehlschlägen entstehen exakt M `WARNING`-Records, nicht N.
- [ ] Das bestehende best-effort-Verhalten bleibt unverändert: `run.status == ScanStatus.SUCCESS`, keine Kriterien-/Detection-Zeile für das fehlgeschlagene Foto, alle anderen Kriterien/Fotos unberührt — nur die Sichtbarkeit des Fehlers ist neu.
- [ ] Ein `asyncio.CancelledError` (durchläuft die separate, vorgelagerte Propagations-Schleife) erzeugt **keinen** Log-Eintrag — ein Abbruch ist keine best-effort-Situation.
- [ ] Neues Modul `backend/src/photosort/logging_config.py` mit `configure_logging() -> None` (`logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`), aufgerufen in `main.py::create_app()` (API-Prozess) und einem neuen `WorkerSettings.on_startup`-Hook in `worker.py` (Worker-Prozess) — beide Prozesse bekommen dieselbe Konfiguration.
- [ ] Kein neues Settings-Feld für das Log-Level (fest `WARNING`), kein Datenmodell-Bezug, keine Migration.
- [ ] `docs/architecture.md` bekommt einen kurzen Eintrag zur neuen, projektweiten Logging-Konvention.
- [ ] `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md` sind bereits im Rahmen dieser Konsultation ergänzt (siehe unten).

## Datenmodell-Bezug

Nicht betroffen — kein neues Feld, keine neue Tabelle, keine Migration. Reine Verhaltens-/Sichtbarkeitsänderung.

## Architektur / Umsetzung

Siehe [`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`](../decisions/0034-strukturiertes-logging-cloud-vision-fehler.md) (Accepted, neue ADR — erste Logging-Einführung im Projekt) für die vollständige Begründung. Zusammenfassung:

- **Python-Standardbibliothek `logging`, keine neue Abhängigkeit** (kein `structlog`) — keine Log-Aggregation/-Suche-Infrastruktur im Projekt, einziger Konsument ist `docker compose logs` für Daniel als Einzelbetreiber.
- **Neues, kleines Modul `backend/src/photosort/logging_config.py`** mit genau `configure_logging() -> None` (`logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`) — eigenes Modul statt Anhängsel an `config.py`, konsistent mit dem Projektmuster kleiner, isolierter Module für eine neue Zuständigkeit. Aufgerufen an beiden Prozess-Einstiegspunkten: `main.py::create_app()` (Anfang der Funktion) und ein neuer `WorkerSettings.on_startup`-Hook in `worker.py` (erste Nutzung von arqs `on_startup`-Mechanismus im Projekt, analog zur ersten Cron-Nutzung, ADR 0019). Beide Prozesse bekommen dieselbe Konfiguration, obwohl nur der Worker sie für diese Spec tatsächlich braucht — bewusst, damit ein künftiges Feature mit API-seitigem Logging-Bedarf nicht erneut eine Konfigurationsentscheidung treffen muss.
- **Logger-Pattern:** `logger = logging.getLogger(__name__)` als Modul-Konstante in `worker.py` (direkt nach den Imports) — kein Logger-Objekt wird injiziert/durchgereicht. Nur `worker.py` braucht für dieses Feature einen Logger, nicht `landmark.py`/`remote_classification.py`/`cloud_vision.py` (die Exception-Objekte kommen dort bereits fertig aus `asyncio.gather(..., return_exceptions=True)` zurück; `worker.py` ist die einzige Stelle mit Zugriff auf sowohl die Exception als auch den Foto-Kontext).
- **Level `WARNING`, nicht `ERROR`:** der Skip ist erwartetes, dokumentiertes best-effort-Verhalten (ADR 0025 Punkt 3 / ADR 0032 Punkt 5), der Lauf schließt weiterhin mit `status=success`. `ERROR` bleibt reserviert für tatsächliche Lauf-Fehlschläge (`_fail_run`/Watchdog, ADR 0019).
- **Zwei neue, nahezu identische Logaufrufe** an den beiden bestehenden `except`/`continue`-Stellen in `worker.py` (Landmark-Phase ~1254-1260, Remote-Kategorie-Phase ~1460-1465): jeweils vor dem `continue` ein `logger.warning(...)` mit Phasenbezeichnung, `photo.id`, `photo.relative_path` (bzw. `photos_by_id[photo_id].relative_path`), `type(result).__name__`, `str(result)`.
- **Empfehlung (technische Detailentscheidung, `developer` kann davon abweichen):** ein einziger kleiner privater Helfer `_log_cloud_vision_failure(phase: str, photo_id: int, relative_path: str, exc: BaseException) -> None` in `worker.py`, von beiden Stellen aufgerufen — reduziert Duplikation. Kein Muss, da beide Stellen strukturell leicht unterschiedlich eingebettet sind.
- **Betroffene/neue Dateien:** neu `backend/src/photosort/logging_config.py`; geändert `backend/src/photosort/worker.py` (Logger-Konstante, zwei Logaufrufe, `WorkerSettings.on_startup`), `backend/src/photosort/main.py` (`configure_logging()`-Aufruf in `create_app()`).
- **Empfohlene Umsetzungsreihenfolge:** (1) `logging_config.py` + `configure_logging()`, (2) Verdrahtung in `main.py::create_app()` und `WorkerSettings.on_startup`, (3) die beiden Logaufrufe in `worker.py` (TDD über `caplog`, Ergänzung bestehender Fehlerfall-Tests statt neuer Testfunktionen), (4) `docs/architecture.md`-Ergänzung im selben PR.

## UI/UX

Nicht relevant (idea-sharpener, Schritt 7, strukturell begründet — kein AskUserQuestion nötig): reine Backend-Logging-Änderung ohne jede sichtbare Oberfläche, auch nicht mittelbar — keine neuen Daten werden irgendwo angezeigt, nur stdout-Logs für `docker compose logs`.

## Security

Sicherheitsrelevant, ja (`security-engineer`-Konsultation, 2026-08-24) — erste Logging-Einführung macht bisher nirgends sichtbare interne Fehlerdetails über `docker compose logs` neu sichtbar; direkt der Grundsatz "keine Secrets in Logs" und die im Sicherheitskonzept bereits als offen markierte Verifikation des `LandmarkApiError`/`RemoteCategoryClassificationApiError`-Fehlerpfads.

**Kernfrage geklärt (Code-verifiziert, nicht nur angenommen):** `raise_for_vision_api_status`/`anthropic_response_to_json`/`mistral_response_to_json` (`cloud_vision.py`) liefern bereits generische, statische Meldungen ohne eingebettete Nutzdaten. Der `httpx.HTTPError`-Pfad (`landmark.py`/`remote_classification.py`) wurde gegen `httpx`s eigene Fehlerkonstruktion verifiziert: die Exception-Message stammt ausschließlich vom unterliegenden Transportfehler (z.B. "Connection refused", DNS-Fehler, Timeout) — sie entsteht, bevor ein Request-Objekt existiert; URL und Header (inkl. API-Keys) werden nie in die Message interpoliert. Beide Ziel-URLs sind feste Konstanten ohne Query-Parameter. **Fazit:** Die Leitplanke (`type(exc).__name__` + `str(exc)` + Foto-Kontext, kein Traceback, kein direkter Zugriff auf `response.text`/`.json()`/`.headers`) ist für diesen Pfad ausreichend, keine zusätzliche Filterung zwingend nötig.

**Zusätzlich identifiziert, geringe Relevanz, kein Blocker:**
- Die `except`-Stellen in `worker.py` fangen via `isinstance(result, BaseException)` jede Exception ab, nicht nur die beiden API-Error-Klassen. `_detect_landmark_for_photo` liest vorab `path.read_bytes()` — fehlt der Cache-Eintrag, enthält `str(exc)` eines `FileNotFoundError`/`OSError` den vollen lokalen Dateisystempfad statt eines Cloud-Fehlertexts. Kein Secrets-Leck; für dieses private Einzelbetreiber-Projekt akzeptiert, kein Fix nötig.
- Theoretisches Log-Injection-Risiko über Steuerzeichen in `str(exc)` bei reinem Textformat ohne Escaping — praktisch irrelevant (einziger Log-Konsument ist Daniel selbst, kein automatisiertes Parsing, TLS-validierte feste Ziel-Hosts).
- Empfehlung (keine Pflicht): `str(exc)` beim Logging auf ~300 Zeichen kürzen als billige Absicherung gegen künftig ungewöhnlich lange Fehlertexte.

`specs/architecture/0003-securitykonzept.md` wird nach Umsetzung um die geschlossenen Verifikationsplatzhalter (Zeilen 213/223/232) und einen kurzen Logging-Bullet ergänzt (Aufgabe des `security-engineer` nach Merge).

## Teststrategie

`specs/architecture/0002-testkonzept.md` wurde bereits im Rahmen dieser Konsultation ergänzt (neue Sektion "Erstes `logging` im Projekt: `caplog`-Testmuster + `basicConfig`/pytest-Testbarkeitsfalle").

**Testebenen:**
- **Unit:** neue `test_logging_config.py` für `configure_logging()` — mit Reset von `logging.root.handlers` vor dem Aufruf (siehe Testbarkeits-Falle unten), Prüfung von Level und Format-String; zusätzlicher Fall für doppelten Aufruf (kein doppelter Handler).
- **Integration (Schwerpunkt), `caplog`:** `test_worker_criterion_scoring.py::test_failed_landmark_call_leaves_no_row_and_becomes_a_candidate_again_next_run` und `test_worker_remote_category_classification.py::test_best_effort_error_isolation_does_not_abort_the_run` werden um `caplog`-Assertions erweitert statt neuer Testfunktionen. Neuer Testfall für "mehrere gleichzeitig fehlschlagende Fotos im selben Nebenläufigkeits-Block" (Landmark-Phase hat dafür noch keine Fixture). Wiring von `create_app()`/`WorkerSettings.on_startup` per Spy/Identitätsvergleich geprüft, nicht über beobachtetes Logger-Verhalten.
- **E2E/Smoke:** keiner nötig — `docker compose logs`-Sichtbarkeit ist durch das Format aus ADR 0034 (Zeitstempel/Level/Modulname, stdout) strukturell gegeben.

**Relevante Edge Cases:**
1. Mehrere gleichzeitig fehlschlagende Fotos in einem Block — jede Message muss ihr eigenes `photo.id` referenzieren, keine Vertauschung durch die parallele `zip(..., strict=True)`-Zuordnung.
2. `CancelledError` — bestehende Tests ergänzt um `assert len(caplog.records) == 0` (strukturell bereits ausgeschlossen, da die Prüfung in einer eigenen, dem `continue`-Loop vorgelagerten Schleife läuft).
3. Leerer Kandidaten-Lauf — bestehende Tests ergänzt um dieselbe Null-Records-Assertion.
4. **Testbarkeits-Falle:** `logging.basicConfig()` ist ein No-op, sobald der Root-Logger bereits einen Handler hat — `pytest`s eigenes Logging-Plugin hängt unabhängig von `caplog` selbst einen Capture-Handler an den Root-Logger. Ein naiver Test von `configure_logging()` gegen den Root-Logger-Zustand wäre daher scheinbar grün, ohne dass `basicConfig()` tatsächlich etwas bewirkt hätte — deshalb Handler-Reset vor dem Test.

## Entscheidungen (2026-08-24, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Scope bewusst auf beide Cloud-Vision-Läufe erweitert:** Der Inbox-Rohtext beschrieb nur die Remote-Kategorie-Klassifizierung; die Code-Recherche fand ein identisches, stilles `except`/`continue`-Muster auch bei der Landmark-Erkennung. Daniel hat sich dafür entschieden, beide Stellen in derselben Spec mit demselben Muster zu lösen statt zweimal nachzuarbeiten.
- **Nur Fehler geloggt, keine Erfolgs-/Lauf-Zusammenfassung:** Daniel hat sich für die minimal-invasive Variante entschieden — deckt genau das im Rohtext beschriebene Problem (Diagnose eines Fehlschlags) ab, ohne zusätzliches Log-Volumen bei erfolgreichen Läufen.
- **Neue ADR statt Anhängsel an eine bestehende:** `architect` hat sich für eine eigenständige ADR (`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`) entschieden, da dies die erste, projektweite Logging-Konvention festlegt — nicht nur eine lokale Detailentscheidung der beiden betroffenen Stellen.
- **Level `WARNING` statt `ERROR`:** eigenständige technische Entscheidung von `architect` (kein Rückfrage-Charakter) — verhindert eine Verwischung der bestehenden Unterscheidung zwischen "Lauf tatsächlich fehlgeschlagen" (`_fail_run`/Watchdog) und "ein Foto wurde erwartungsgemäß übersprungen".
- **Beide Prozess-Einstiegspunkte (API + Worker) konfiguriert, obwohl nur der Worker es für diese Spec braucht:** eigenständige technische Entscheidung von `architect` — legt die Konvention für künftige Features gleich mit an, statt sie bei der nächsten Logging-Anforderung erneut zu treffen.
- **Kein Filtern/Kürzen von `str(exc)` als Muss-Kriterium:** `security-engineer` hat den ursprünglich offenen Verdachtspunkt (potenzielles Secret-Leck über gewrappte `httpx`-Fehler) durch Code-Verifikation ausgeräumt; eine Kürzung auf ~300 Zeichen ist nur als günstige Zusatzabsicherung empfohlen, nicht vorgeschrieben.

## Offene Fragen

Keine — alle im Sharpening-Gespräch aufgetretenen Unklarheiten wurden mit Daniel geklärt (siehe Abschnitt "Entscheidungen").

## Out of Scope

- Erfolgsprotokollierung (Anzahl bearbeiteter Fotos, Lauf-Zusammenfassungen).
- Änderung der best-effort-Strategie selbst (Retry, Abbruchverhalten) — nur die Sichtbarkeit des bestehenden Verhaltens ändert sich.
- Logging für andere Backend-Prozesse/-Läufe außerhalb der zwei genannten Cloud-Vision-Stellen (z.B. `run_project_scan`).
- Strukturiertes JSON-Logging oder eine externe Log-Aggregation — reines Textformat über stdout reicht für den aktuellen Betriebskontext (Einzelbetreiber, `docker compose logs`).
- Konfigurierbares Log-Level über eine Umgebungsvariable — fest auf `WARNING`, YAGNI.
