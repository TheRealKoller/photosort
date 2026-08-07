# 0023 - Scan-Zuverlässigkeit: hängender Job + eingefrorener Live-Zähler

**Status:** Implemented — alle Akzeptanzkriterien (Terminierungs-Fix und Batch-Größen-Fix) umgesetzt in [PR #43](https://github.com/TheRealKoller/photosort/pull/43)
**Erstellt:** 2026-08-07
**Bezug:** Bug-Report von Daniel selbst (interaktive Session, 2026-08-07), direkt im Gespräch diagnostiziert, unmittelbar nach Merge von [Spec 0022](./0022-scan-live-fortschrittszaehler.md) (PR #40). Ursprünglich als reiner Batch-Größen-Bug vermutet; Nachfrage bei Daniel ergab, dass das eigentliche, schon länger beobachtete Problem schwerwiegender ist (siehe "Ziel"). Zwei technische Konsultationen (`architect`) haben den vollständigen Fix erarbeitet.

## Ziel

Diese Spec behebt zwei zusammenhängende, beide in `worker.py::run_project_scan` liegende Probleme, die zusammen dazu führen, dass ein Scan-Vorgang für den Nutzer wie "hängengeblieben" wirkt:

1. **Kritisch — Job bleibt für immer auf "running" hängen:** `run_project_scan` fängt in seinem Fehlerbehandlungs-Block ausschließlich `OpenCloudError` ab; jede andere Exception (insbesondere aus dem bisher ungeschützten WebDAV-XML-Parsing in `opencloud/webdav_xml.py::parse_multistatus`, das bei einer kaputten/unerwarteten Server-Antwort eine rohe `ParseError`/`ValueError` werfen kann) läuft ungefangen durch — auch der Job-Einstiegspunkt `scan_project` hat kein eigenes Sicherheitsnetz. Der `ScanRun`-Datenbankeintrag bleibt dadurch dauerhaft auf `status="running"` stehen, es existiert kein Watchdog/Retry-Mechanismus, der das je korrigiert — auch ein Container-Neustart ändert nichts an dem bereits geschriebenen, hängenden Eintrag. Das erklärt Daniels beobachtetes Symptom: "Job schien nie zu enden... selbst nach einem Neustart war der Job unverändert."
2. **Kosmetisch — Live-Zähler (Spec 0022) bleibt bei kleinen Scans eingefroren:** Der periodische Zwischen-Commit von `scan_run.files_found` committet nur bei exakten Vielfachen von `SCAN_COMMIT_BATCH_SIZE` (=25). Bei einem Scan mit weniger als 25 Dateien (typisch für eine Familienfoto-Ergänzung) wird diese Bedingung im gesamten Lauf nie erfüllt — der Zähler bleibt bei "0 Dateien verarbeitet" eingefroren und springt erst am Ende abrupt auf den finalen Wert.

Beide Fixes ändern dieselbe Funktion und werden im selben PR umgesetzt.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass ein Scan-Vorgang zuverlässig entweder erfolgreich abschließt oder mit einer erkennbaren Fehlermeldung fehlschlägt — nie unbegrenzt im Zustand "läuft" hängen bleibt — und dass der Live-Zähler dabei unabhängig von der Scan-Größe tatsächlich sichtbar mitwächst, damit ich verlässlich einschätzen kann, ob der Scan aktiv arbeitet oder tatsächlich ein Problem vorliegt.

## Akzeptanzkriterien

**Terminierungs-Fix (kritisch):**

- [x] `run_project_scan` fängt jede Exception ab (`except Exception`, nicht mehr nur `OpenCloudError`) und setzt `scan_run.status = FAILED` mit `error_message = str(exc)`, `finished_at` gesetzt, zuverlässig in jedem Fall — analog zum bereits bestehenden, identischen Muster in `run_project_scoring` (Zeile ~381, seit Spec 0003).
- [x] `asyncio.CancelledError` (kein `Exception`-Subtyp seit Python 3.8, sondern `BaseException`) wird von der breiteren `except Exception`-Klausel weiterhin **nicht** abgefangen — ein geplanter Worker-Shutdown markiert einen Lauf nicht fälschlich als `failed`.
- [x] `opencloud/client.py::list_folder` fängt `ElementTree.ParseError`/`ValueError`/`TypeError` beim Aufruf von `parse_multistatus` ab und übersetzt sie in eine `OpenCloudError` mit verständlicher deutscher Fehlermeldung — konsistent mit dem bestehenden Muster in `_drive_from_graph_api_item` (gleiche Datei), das dieselbe Art von Fehlerklassen bereits für die Graph-API-Antworten übersetzt.
- [x] Neuer Test, der eine unerwartete, nicht-`OpenCloudError`-Exception mitten im Scan-Loop simuliert (z.B. ein Fake-`walk()`, der nach einigen Einträgen einen generischen `RuntimeError` wirft) und nachweist: `scan_run.status == FAILED`, `error_message` enthält die Exception-Nachricht, kein unbegrenztes Hängen.
- [x] Neuer Test in `test_opencloud_client.py`: `list_folder` gegen eine Response mit kaputtem XML-Body wirft `OpenCloudError` (nicht die rohe `ParseError`).
- [x] Bestehender Regressionstest `test_scan_run_marked_failed_on_opencloud_error` bleibt unverändert grün.

**Batch-Größen-Fix (kosmetisch, Spec 0022 nachgebessert):**

- [x] `SCAN_COMMIT_BATCH_SIZE` wird von `25` auf `1` geändert — jede verarbeitete/übersprungene Datei löst einen Zwischen-Commit von `scan_run.files_found` aus, unabhängig von der Gesamtzahl der Dateien im Scan.
- [x] Ein Scan mit z.B. 3 Dateien zeigt während der Laufzeit sichtbar wachsende Zwischenstände (1, 2, 3), nicht nur einen Sprung von 0 auf 3 am Ende.
- [x] Bestehendes Verhalten bei großen Scans (≥25 Dateien) bleibt funktional unverändert (Zähler wächst weiterhin monoton).
- [x] Bestehende Tests, die `SCAN_COMMIT_BATCH_SIZE` per Monkeypatch auf `1`/`2` setzen, bleiben unverändert grün.
- [x] Neuer Test ohne Monkeypatch auf den (jetzt korrekten) Produktivwert zeigt einen Zwischen-Commit vor dem finalen Commit bei einem kleinen Scan.

## Datenmodell-Bezug

Nicht betroffen — reine Fehlerbehandlungs- und Konstanten-Änderung, kein Schema-, API- oder Frontend-Typ-Delta.

## Architektur / Umsetzung

**Bezug:** Behebt eine Inkonsistenz zwischen zwei Zwillingsfunktionen im selben Modul — `run_project_scoring` hat das benötigte Sicherheitsnetz (`except Exception`) bereits seit Spec 0003, `run_project_scan` bisher nicht. Kein neues Muster, reine Angleichung (architect-Konsultation, 2026-08-07).

**Betroffene Dateien:**

- **`backend/src/photosort/opencloud/client.py`** (`list_folder`, nach dem bestehenden `_raise_for_status(...)`-Aufruf): `parse_multistatus`-Aufruf in `try/except (ElementTree.ParseError, ValueError, TypeError)` einbetten, Exception in `OpenCloudError` übersetzen. `ElementTree.ParseError` deckt kaputtes XML ab, `ValueError` sowohl nicht-numerischen `content-length` als auch unparsbares Datum in `_parse_last_modified` (ab Python 3.10 garantiert `ValueError`, Projekt auf `>=3.12` gepinnt), `TypeError` defensiv ergänzt. Vorbild: `_drive_from_graph_api_item` in derselben Datei. `webdav_xml.py` selbst bleibt unverändert (kein neuer Import/keine Kopplung dort, würde einen Zirkelimport erzeugen).
- **`backend/src/photosort/worker.py`** (`run_project_scan`): `except OpenCloudError as exc:` → `except Exception as exc:`, Körper unverändert (ein einzelner Handler reicht, da `OpenCloudError ⊂ Exception`). Erklärender Kommentar zum `CancelledError`-Verhalten und zum Bugfix-Charakter der Änderung ergänzen, analog zum bereits bestehenden Handler in `run_project_scoring`.
- **`backend/src/photosort/worker.py`** (`SCAN_COMMIT_BATCH_SIZE`): `25` → `1`. Begründender Kommentar: anders als `SCORE_COMMIT_BATCH_SIZE` (CPU-only, schnelle Verarbeitung, Batching reduziert spürbaren Commit-Overhead sinnvoll) ist `run_project_scan` netzwerkgebunden (EXIF-Range-Read + Thumbnail-Generierung pro Datei über OpenCloud-WebDAV) — ein zusätzlicher DB-Commit pro Datei fällt gegenüber der Netzwerklatenz nicht messbar ins Gewicht.
- **`backend/tests/test_worker_scan_project.py`**: neue Tests für beide Fixes (siehe Akzeptanzkriterien/Teststrategie).
- **`backend/tests/test_opencloud_client.py`**: neuer Test für `list_folder` gegen kaputtes XML.
- **`specs/architecture/0003-securitykonzept.md`** (Owner: `security-engineer`, im Review dieses Feature-Branches nachzuziehen): zwei Korrekturen — (a) neuer Abschnitt "Job-Lauf-Terminierung (projektweites Robustheitsprinzip)", analog zum bestehenden "Lokale Bildverarbeitung"-Prinzip, das nach dem zweiten unabhängigen Auftreten (jetzt: `run_project_scoring` UND `run_project_scan`) als projektweiter Grundsatz verankert wird: *jede* `ScanRun`/`ScoringRun`-Verarbeitung muss in einem äußeren, breiten `except Exception`-Handler enden, der den Lauf zuverlässig auf `failed` setzt; `asyncio.CancelledError` bleibt davon unberührt. (b) Korrektur der bestehenden, nachweislich falschen Aussage in Zeile 98 ("Umgang mit malformed XML ... bereits abgedeckt (Stand Spec 0001)") auf den jetzt tatsächlich gefixten Stand.

**Nicht Teil dieses Fixes (bewusste Abgrenzung):** Ein Watchdog/Heartbeat-Mechanismus für Hänger *ohne* Exception (Prozess-Kill/OOM mitten im Lauf, Endlosschleife, Deadlock) wäre eine eigenständige, größere Funktionalität und bleibt außerhalb des Scopes dieses Bugfixes — dieser Fix behebt das hier tatsächlich beobachtete, Exception-basierte Hängenbleiben vollständig.

**Reihenfolge der Umsetzung (TDD):**

1. Terminierungs-Fix zuerst (kritischer): fehlschlagender Test für `list_folder` gegen kaputtes XML in `test_opencloud_client.py` → `try/except`-Übersetzung in `client.py` implementieren → grün.
2. Fehlschlagender Test in `test_worker_scan_project.py`: Fake-`walk()` wirft generischen `RuntimeError` mitten im Loop → `except Exception` in `worker.py::run_project_scan` implementieren → grün.
3. Bestehenden Regressionstest `test_scan_run_marked_failed_on_opencloud_error` prüfen (muss weiterhin grün sein, `OpenCloudError` ist jetzt Teilmenge des breiteren Handlers).
4. Batch-Größen-Fix: fehlschlagender Test ohne Monkeypatch auf Produktivwert → `SCAN_COMMIT_BATCH_SIZE = 1` setzen → grün.
5. `specs/architecture/0003-securitykonzept.md` im Review nachziehen (security-engineer).
6. Vollständige Test-/Lint-/Typecheck-Läufe vor PR.

**Keine ADR nötig:** reine Korrektur einer Inkonsistenz zwischen zwei bereits bestehenden, strukturell identischen Funktionen — kein neues Muster, keine neue Technologie (architect-Konsultation, 2026-08-07, bestätigt).

## UI/UX

Keine Änderung an der Darstellung selbst — die UI/UX-Entscheidungen aus Spec 0022 (Text, kein Balken, kein eigenes `aria-live`) bleiben unverändert. Mittelbare Verbesserung: ein zuvor unsichtbar hängender Scan zeigt nach diesem Fix zuverlässig entweder Fortschritt oder die bereits bestehende Fehleranzeige (`Alert` mit "Erneut versuchen", Spec 0017) — kein neuer UI-Zustand nötig, nur ein bisher unerreichbarer bestehender Zustand (`failed`) wird jetzt tatsächlich erreicht.

## Security

**Sicherheitsrelevant: ja** — anders als Spec 0022 (reine Konstanten-/Anzeige-Änderung) betrifft dieser Fix die Robustheit der Verarbeitung von Daten, die von einer externen Quelle (OpenCloud-WebDAV-Server) stammen.

- **Kein neues Datenleck, keine neue Eingabe von außen:** Die WebDAV-Antwort wird bereits heute vollständig geparst und verarbeitet — dieser Fix ändert nur, dass eine *unerwartete* Antwortstruktur jetzt sauber als Fehler behandelt wird, statt den gesamten Job in einem unbestimmten Zustand hängen zu lassen. Keine neue Angriffsfläche.
- **Verfügbarkeit/Robustheit ist der eigentliche Zweck dieses Fixes:** Ein dauerhaft hängender `ScanRun` ist zwar kein klassisches Sicherheitsleck, aber ein Robustheitsdefekt gegen eine (nicht zwingend böswillige) externe Quelle mit unerwartetem Verhalten — konsistent mit dem bereits etablierten Grundsatz "externe Antworten sind potenziell fehlerhaft, nie vertrauenswürdig strukturiert" (Sicherheitskonzept, Vertrauensgrenzen-Abschnitt).
- **`except Exception` als breiter Fangblock:** bewusst so gewählt (nicht auf bekannte Exception-Klassen beschränkt), da nur so *jede* künftige, heute noch unbekannte Fehlerquelle den Lauf sauber terminiert statt erneut unbegrenzt hängen zu bleiben — exakt dasselbe, bereits akzeptierte Muster wie bei `generate_variants`/`extract_taken_at` (Best-effort bei potenziell außergewöhnlichen, aber nicht böswilligen Daten), hier auf Lauf-Ebene statt Einzelfoto-Ebene angewendet. `asyncio.CancelledError` bleibt als `BaseException` unberührt, ein geplanter Shutdown wird nicht fälschlich als Fehler gewertet.
- **`specs/architecture/0003-securitykonzept.md` wird ergänzt** (siehe Architektur-Abschnitt oben): neuer projektweiter Grundsatz "Job-Lauf-Terminierung" sowie Korrektur einer bestehenden, nachweislich falschen Aussage zum WebDAV-XML-Parsing.

## Teststrategie

**Backend — `backend/tests/test_worker_scan_project.py`:**

- Neuer Test (Terminierung): Fake-`walk()`-Async-Generator liefert einige Einträge und wirft danach einen generischen `RuntimeError` (nicht `OpenCloudError`) — Nachweis, dass `scan_run.status == FAILED`, `error_message` die Exception-Nachricht enthält, und der Test nicht unbegrenzt hängt/timeoutet.
- Neuer Test (Batch-Größe): Scan mit z.B. 3 synthetischen Dateien, **kein** Monkeypatch auf `SCAN_COMMIT_BATCH_SIZE` (realer Produktivwert nach dem Fix) — Nachweis über einen Fake-Client, der zwischen `walk()`-Einträgen den DB-Zustand inspiziert, dass `scan_run.files_found` bereits vor dem finalen Commit wächst.
- Bestehender Test `test_scan_run_marked_failed_on_opencloud_error` unverändert als Regressionsschutz.

**Backend — `backend/tests/test_opencloud_client.py`:**

- Neuer Test: `list_folder` gegen eine Mock-Response mit syntaktisch kaputtem XML-Body (z.B. abgeschnittenes Tag) — erwartet `OpenCloudError`, nicht die rohe `ElementTree.ParseError`. Analog zum bestehenden Testmuster für `_drive_from_graph_api_item` (`KeyError`/`TypeError`/`AttributeError` → `OpenCloudError`).

Kein Update von `specs/architecture/0002-testkonzept.md` nötig — beide Testmuster (Fehler-Übersetzung an der Client-Grenze, Lauf-Ebenen-Terminierungs-Sicherheitsnetz) sind bereits an anderer Stelle im Projekt etabliert (siehe `_drive_from_graph_api_item`-Tests bzw. `run_project_scoring`-Tests), diese Spec wendet sie nur ein zweites Mal an.

## Entscheidungen

- **`except Exception` statt eng gefasster Exception-Liste in `run_project_scan`:** garantiert Terminierung auch bei künftigen, heute unbekannten Fehlerquellen — nicht nur den heute identifizierten (XML-Parsing). Angleichung an das bereits bestehende, identische Muster in `run_project_scoring` (architect-Konsultation, 2026-08-07).
- **Fehler-Übersetzung an der Client-Aufrufstelle (`client.py::list_folder`), nicht im reinen Parsing-Modul (`webdav_xml.py`):** vermeidet einen Zirkelimport (`webdav_xml.py` hat aktuell keine Projekt-Imports), folgt dem bereits etablierten Vorbild `_drive_from_graph_api_item` in derselben Datei (architect-Konsultation, 2026-08-07).
- **`asyncio.CancelledError` bleibt unberührt:** kein Sonderfall im Code nötig, da es seit Python 3.8 kein `Exception`-Subtyp mehr ist, sondern `BaseException` — rein dokumentierend im Kommentar festgehalten (architect-Konsultation, 2026-08-07).
- **`SCAN_COMMIT_BATCH_SIZE = 1` statt eines mittleren Werts:** garantiert sichtbaren Fortschritt bei jeder Scan-Größe, nicht nur oberhalb eines gewählten Schwellwerts — mit Daniel direkt besprochen, da der Commit-Overhead beim netzwerkgebundenen Scan-Job vernachlässigbar ist.
- **Kein Watchdog/Heartbeat für Exception-lose Hänger (Prozess-Kill, Deadlock):** bewusst außerhalb des Scopes — der hier tatsächlich beobachtete, Exception-basierte Fall wird vollständig behoben; ein Watchdog wäre eine eigenständige, größere Funktionalität ohne aktuellen Anlass (architect-Konsultation, 2026-08-07).
- **Beide Fixes (Terminierung + Batch-Größe) in einer Spec/einem PR gebündelt statt getrennt:** beide ändern dieselbe Funktion (`run_project_scan`), direkt mit Daniel abgestimmt.
- **Keine ADR:** reine Korrektur einer Inkonsistenz zwischen zwei bereits bestehenden, identisch intendierten Funktionen, kein neues Muster (architect-Konsultation, 2026-08-07).

## Offene Fragen

Keine.

## Out of Scope

- Watchdog/Heartbeat-Mechanismus für Hänger ohne Exception (Prozess-Kill/OOM, Endlosschleife, Deadlock) — eigene, spätere Spec bei Bedarf.
- Automatische Bereinigung/Erkennung bereits heute in der Produktivdatenbank hängender `ScanRun`-Einträge aus der Zeit vor diesem Fix — ein erneuter Scan-Trigger legt ohnehin einen neuen, aktuellen `ScanRun` an, der den alten hängenden Eintrag als "letzter Lauf" in der UI ersetzt; der alte Eintrag bleibt als harmlose Karteileiche in der DB stehen.
