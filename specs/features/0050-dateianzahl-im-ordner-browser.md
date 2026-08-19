# 0050 - Dateianzahl pro Unterordner im OpenCloud-Ordner-Browser

**Status:** Accepted
**Erstellt:** 2026-08-19
**Bezug:** [`inbox/0006-dateianzahl-beim-ordner-heraussuchen.md`](../inbox/0006-dateianzahl-beim-ordner-heraussuchen.md) (Ursprung, nach Anlage dieser Spec gelöscht), ADR [`decisions/0028-ordner-browser-bilddatei-zaehlung.md`](../decisions/0028-ordner-browser-bilddatei-zaehlung.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-19.

## Ziel

Beim Anlegen eines neuen Projekts navigiert der Nutzer über den bestehenden `FolderBrowser` durch die OpenCloud-Ordnerstruktur, um den Quellordner auszuwählen (Spec 0001/0005). Der Browser listet aktuell nur Unterordnernamen, ohne jeden Hinweis darauf, wie viele Fotos tatsächlich enthalten sind — die Auswahl des richtigen Ordners ("ist das der Ordner mit den ganzen Fotos?") ist damit reines Rätselraten, bis man hineinklickt. Diese Spec zeigt pro gelistetem Unterordner eine rekursive Bilddatei-Anzahl an, damit die Entscheidung ohne Durchklicken möglich ist.

## User Story

Als Nutzer (Daniel oder seine Frau), der beim Anlegen eines neuen Projekts den OpenCloud-Quellordner auswählt, möchte ich für jeden gelisteten Unterordner sofort sehen, wie viele Fotos darin enthalten sind (auch in Unterordnern, z.B. bei nach Datum sortierten Kamera-Exports), damit ich den richtigen Ordner ohne mehrfaches Durchklicken finde.

## Akzeptanzkriterien

**Backend:**
- [ ] `IMAGE_EXTENSIONS`-Konstante zieht von `worker.py` (dort privat) nach `opencloud/client.py` um (dort öffentlich) — `worker.py` importiert von dort, keine zweite, potenziell abweichende Liste.
- [ ] Neues `Settings`-Feld `opencloud_folder_count_concurrency: int = Field(default=4, ge=1)` (env-überschreibbar).
- [ ] Neuer privater Helfer `_count_images_up_to_limit(client, webdav_url, path, limit)` in `api/opencloud.py`: konsumiert `client.walk()` (bestehende BFS-Traversierung mit Zyklenschutz), zählt nur Dateien mit Endung aus `IMAGE_EXTENSIONS`, bricht die Traversierung ab, sobald `limit` (`FOLDER_COUNT_LIMIT = 500`) erreicht ist, liefert `(count, at_limit)`.
- [ ] **Anfragezähler-Nachweis (Pflicht, nicht nur Ergebnisprüfung):** nach Erreichen des Limits werden keine weiteren PROPFIND-Requests mehr abgesetzt — ein reiner Ergebnistest würde eine künftige Regression an `walk()`s Lazy-Verhalten nicht erkennen.
- [ ] Neuer Endpunkt `GET /opencloud/folder-counts?path=<Pfad>`: listet dieselben direkten Unterordner wie `GET /opencloud/browse?path=<Pfad>`, zählt dann pro Unterordner parallel über `asyncio.gather(..., return_exceptions=True)` mit `asyncio.Semaphore(settings.opencloud_folder_count_concurrency)`. Response `list[FolderCountOut]` (`path`, `count`, `at_limit`, `error: bool`).
- [ ] Exakt 500 Bilddateien → `count=500, at_limit=True`; 499 → `count=499, at_limit=False`.
- [ ] Echter Leerordner → `count=0, at_limit=False`; Ordner mit ausschließlich Nicht-Bild-Dateien ebenfalls `count=0, at_limit=False` (separat getestet, unterschiedliche Ursache).
- [ ] Einzelner Unterordner-Zählfehler (z.B. Netzwerkfehler mitten in dessen Traversierung) liefert für diesen Eintrag `error=True, count=0, at_limit=False`; die Gesamtantwort bleibt `200`, alle übrigen Einträge sind unverändert korrekt.
- [ ] Schlägt dagegen das vorgelagerte Listing der direkten Unterordner selbst fehl, liefert der Endpunkt `400` (wie `browse_folder`) — keine leere/Teilantwort.
- [ ] Serverseitige Gesamt-Nebenläufigkeit aller Zählungen eines Requests ist durch `opencloud_folder_count_concurrency` begrenzt, unabhängig von der Anzahl gelisteter Unterordner (Test: mehr Unterordner als `concurrency` → `max_concurrent_walks <= concurrency`, nicht nur Endergebnis-Korrektheit).
- [ ] `GET /opencloud/browse` selbst ändert sich nicht (kein neues Feld, keine zusätzliche Traversierung, keine Verzögerung durch die neue Zählung).
- [ ] `FolderCountOut` enthält bewusst kein Freitext-/Meldungsfeld — `error: true` transportiert kein `str(exc)` an den Client.

**Frontend:**
- [ ] Neuer Hook `useOpenCloudFolderCountsQuery(path)` (Caching identisch zu `useOpenCloudBrowseQuery`: eigener Query-Key pro Pfad, `staleTime: Infinity`), löst automatisch parallel zum bestehenden Browse-Request desselben Pfads aus (eager, kein Klick nötig).
- [ ] `FolderBrowser.tsx` zeigt pro gelisteter Unterordner-Zeile einen von vier Zuständen, ohne die Liste oder Navigation zu blockieren: Lade-Icon (Anfrage aussteht), exakte Zahl (`count`, `at_limit=false`), `"500+"` (`at_limit=true`), Fehler-Symbol `"?"` (`error=true`).
- [ ] Layout: Name linksbündig (bestehend), Zahl/Icon rechtsbündig (neu), 12px Abstand (`gap-3`), keine Zeilenhöhenänderung.

## Datenmodell-Bezug

Keines — reine Laufzeit-Berechnung gegen OpenCloud, keine Persistierung, kein neues DB-Feld.

## Architektur / Umsetzung

Siehe [`decisions/0028-ordner-browser-bilddatei-zaehlung.md`](../decisions/0028-ordner-browser-bilddatei-zaehlung.md) (Accepted) für die vollständige Begründung. Zusammenfassung:

**Backend:**
- `opencloud/client.py`: `IMAGE_EXTENSIONS` (umgezogen von `worker.py`, unverändertes Wertset `{".jpg", ".jpeg", ".png", ".heic", ".heif"}`). Keine Änderung an `walk()`/`list_folder()` selbst — beide werden unverändert wiederverwendet; `walk()` ist als Async-Generator bereits von Natur aus früh-abbrechbar (kein `break` nötig innerhalb der Bibliothek, der Konsument steuert das).
- `config.py`: `opencloud_folder_count_concurrency: int = Field(default=4, ge=1)`, analog `scan_download_concurrency` (ADR 0020) — Überlastschutz für den Einzelnutzer-Homeserver-OpenCloud bei paralleler Zählung mehrerer Unterordner.
- `api/opencloud.py`: `FOLDER_COUNT_LIMIT = 500` (reiner Anzeigewert, kein Settings-Feld). `_count_images_up_to_limit()` konsumiert `client.walk()`, bricht die `async for`-Schleife beim Erreichen des Limits ab. Neuer Endpunkt `GET /opencloud/folder-counts` zählt parallel über `asyncio.gather(..., return_exceptions=True)` + `asyncio.Semaphore` — bewusst **kein** Block-Muster wie in ADR 0020 (kein DB-Session-/Resume-Bedarf hier). Der bestehende `GET /opencloud/browse`-Endpunkt bleibt unverändert.

**Frontend:**
- `api/opencloud.ts`: `fetchFolderCounts(path)`, analog `browseFolder`.
- Neuer Hook `useOpenCloudFolderCountsQuery(path)`, identisches Cache-Muster wie `useOpenCloudBrowseQuery`.
- `FolderBrowser.tsx`: löst den Counts-Request automatisch parallel zum bestehenden Browse-Request aus; die Ordnerliste rendert unverändert, sobald `browseFolder` zurück ist, die Dateianzahl wird pro Zeile nachgereicht.

**Reihenfolge der Umsetzung:**
1. `IMAGE_EXTENSIONS`-Umzug nach `opencloud/client.py` + `worker.py`-Importanpassung (reiner Refactor, isoliert testbar, keine Verhaltensänderung).
2. `config.py`: neues Settings-Feld.
3. `api/opencloud.py`: `_count_images_up_to_limit` (mit Anfragezähler-Test) und `GET /opencloud/folder-counts`.
4. Frontend: `fetchFolderCounts` → `useOpenCloudFolderCountsQuery` → `FolderBrowser.tsx`-Integration.

**Betroffene Dateien:** `backend/src/photosort/opencloud/client.py`, `backend/src/photosort/worker.py`, `backend/src/photosort/config.py`, `backend/src/photosort/api/opencloud.py`, `frontend/src/api/opencloud.ts`, `frontend/src/hooks/useOpenCloudBrowse.ts` (bzw. neue Datei daneben), `frontend/src/components/FolderBrowser.tsx`. Nach Umsetzung zusätzlich `docs/architecture.md` (Owner `architect`).

## UI/UX

Neues, im Design-System dokumentiertes Muster **"Eager-Zähler neben Listeneinträgen"** (`ux-ui-designer`-Konsultation, 2026-08-19; `specs/architecture/0004-design-system.md` bereits ergänzt). Jeder im `FolderBrowser` gelistete Unterordner zeigt rechts neben seinem Namen eine Bilddatei-Anzahl:

- **Ladephase:** kleines, rotierendes Lade-Icon (`Loader2`, `h-4 w-4 animate-spin`) rechts an Stelle der späteren Zahl — Liste wird sofort angezeigt, Zähler trudeln asynchron ein.
- **Erfolg:** die tatsächliche Zahl (z.B. "42"), oder `"500+"` bei erreichter Obergrenze (`at_limit=true`, optional `title="Mindestens 500 Bilder"`).
- **Erfolg, null Dateien:** "0" wird genauso wie jede andere Zahl gezeigt — nicht versteckt, damit eindeutig von "noch nicht geladen" unterscheidbar.
- **Fehler:** ein dezentes Fragezeichen "?" (nicht wie ein Warnbanner formatiert) mit optionalem `title="Zählung nicht verfügbar"` — blockiert weder andere Zähler noch die Navigation in den betroffenen Ordner.
- **Layout:** `flex justify-between`, 12px Abstand (`gap-3`) zwischen Name und Zahl, keine Zeilenhöhenänderung.
- **Caching:** identisch zu `useOpenCloudBrowseQuery` (`staleTime: Infinity` pro Pfad) — Inkonsistenz-Toleranz ("Ordnerinhalt kann sich zwischenzeitlich ändern") gilt für Namen wie für Zähler gleichermaßen, bereits akzeptiertes Verhalten des bestehenden Browsers.

## Security

Sicherheitsrelevant, aber ohne neue Angriffsflächen-Klasse (`security-engineer`-Konsultation, 2026-08-19):

- Neuer Endpunkt `GET /opencloud/folder-counts` hängt am selben router-weiten `dependencies=[Depends(get_current_user)]`-Torwächter wie `/opencloud/browse` (Muss-Kriterium, testseitig zu verifizieren: 401 ohne gültiges JWT).
- **Path-Traversal:** kein neues Risiko — `path` läuft über denselben, bereits gehärteten `_join()`-Baustein (`opencloud/client.py`), der jedes `..`-Segment vor der URL-Konstruktion zurückweist (bereits verifizierter, projektweiter Fix, deckt auch `walk()` ab).
- **DoS/Ressourcenverbrauch:** `asyncio.Semaphore(settings.opencloud_folder_count_concurrency)` (Default 4) plus harte Obergrenze `FOLDER_COUNT_LIMIT = 500` pro Unterordner-Traversierung begrenzen den Ressourcenverbrauch pro Request wirksam, analog zur bereits akzeptierten Begründung von `scan_download_concurrency` (ADR 0020). Kein zusätzliches Rate-Limiting auf den Endpunkt vorgesehen — bewusster Trade-off, konsistent mit der bestehenden, bewusst auf `POST /auth/login` beschränkten Rate-Limiting-Architektur (`rate_limit.py`) und dem Präzedenzfall "Kostenkontrolle als Angriffsfläche" (Sicherheitskonzept, Cloud-Vision-Abschnitt, Spec 0047): ein wiederholt abfeuernder authentifizierter Nutzer ist laut Bedrohungsmodell kein relevanter Angreifer (kein Innentäter-Modell zwischen den beiden Nutzern), und anders als bei Spec 0047 entstehen hier nicht einmal externe Kosten.
- **Informationsleck:** `FolderCountOut`-Antwortschema enthält bewusst kein Freitext-/Meldungsfeld — ein fehlgeschlagener Einzelzähler liefert kein `str(exc)` an den Client (Muss-Kriterium, im Review zu bestätigen).
- Kein neues Secret, keine neue externe Abhängigkeit, keine Änderung der Sichtbarkeit zwischen den beiden Nutzern.
- Keine Ergänzung des projektweiten Sicherheitskonzepts nötig — alle Aspekte sind Anwendungsfälle bereits dort verankerter Grundsätze.

## Teststrategie

Vollständig in `specs/architecture/0002-testkonzept.md` als neue Sektion **"Früh-Abbruch-Konsumierung eines lazy `AsyncIterator` + Semaphore-gebundener Batch-Endpunkt ohne Block-Muster (`/opencloud/folder-counts`)"** festgehalten (`test-engineer`-Konsultation, 2026-08-19). Kernpunkte:

- **Unit (Backend):** `_count_images_up_to_limit` gegen ein gemocktes `client.walk()` — reine Zähl-/Grenzfalllogik ohne Netzwerk.
- **Unit/Contract (Backend, `httpx.MockTransport`):** derselbe Helfer gegen einen echten `OpenCloudClient` mit Anfragezähler im Handler, analog `test_opencloud_client.py` — einziger Weg, den Early-Exit-Netzwerkeffekt tatsächlich zu beweisen.
- **Integration (Backend):** `GET /opencloud/folder-counts` End-to-End über `dependency_overrides[get_opencloud_client]`, `FakeClient` mit konfigurierbarem `walk()` pro Pfad und Aufrufzähler für Nebenläufigkeit — analog `test_api_opencloud_browse.py`/`max_concurrent_downloads`-Pattern aus `test_worker_scan_project.py`.
- **Frontend:** `useOpenCloudFolderCountsQuery` analog `useOpenCloudBrowse.test.tsx`; `FolderBrowser.tsx` für die vier Zeilenzustände inkl. gemischter Antwort (ein `error:true` neben normalen Zählungen).

**Relevante Edge Cases** (Details siehe Akzeptanzkriterien): Anfragezähler-Nachweis nach Limit-Erreichen; exakt 500 vs. 499 Bilddateien; Leerordner vs. reiner Nicht-Bild-Ordner; einzelner Unterordner-Fehler blockiert nicht die übrigen; Zyklenschutz von `walk()` bleibt unter der neuen Konsumierung wirksam (kein eigener `visited`-Zustand in `_count_images_up_to_limit`, im Review gegenzuprüfen); Nebenläufigkeits-Obergrenze real eingehalten bei mehr Unterordnern als `concurrency`; `IMAGE_EXTENSIONS`-Umzug ohne Auseinanderlaufen zwischen `worker.py` und `opencloud/client.py`.

**Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md`, neue Sektion (siehe oben) — erste bewusste Früh-Abbruch-Konsumierung einer bestehenden `walk()`-Generatorfunktion und erstes endpunkt-lokales `Semaphore`+`gather(return_exceptions=True)`-Muster ohne Block-/Commit-Semantik (Abgrenzung zu ADR 0020s `_process_scan_block`). Keine neue "Bekannte Lücken"-Eintrag nötig — vollständig automatisiert testbar, kein Kalibrierungs-/Modellrisiko.

## Entscheidungen (2026-08-19, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Anzeige-Ort (Rückfrage im Sharpening-Gespräch):** pro Unterordner in der Liste (nicht nur für den aktuell geöffneten Ordner) — man soll schon vor dem Hineinklicken sehen, wie viele Bilder in jedem gelisteten Unterordner sind.
- **Zähl-Umfang (Rückfrage im Sharpening-Gespräch):** nur Bilddateien, rekursiv inklusive aller Unterordner — relevant bei nach Datum sortierten Kamera-Exports mit tiefer Ordnerstruktur.
- **Feasibility-Fund (Schritt 4, Code-Recherche):** die gewählte Kombination (rekursiv **und** pro gelistetem Unterordner) hätte naiv umgesetzt mehrere vollständige Baum-Traversierungen pro Ordner-Listing bedeutet (`OpenCloudClient.walk()` ist BFS mit einer WebDAV-Anfrage pro Ebene, kein `Depth: infinity`). Auf Rückfrage hat Daniel sich bewusst für **eager mit Obergrenze** (500, "500+"-Anzeige) statt Scope-Reduktion (nur direkte Dateien) oder Lazy-Loading (nur on-demand) entschieden.
- **Devil's-Advocate-Ergebnis:** trotz einmaliger Nutzung pro Projektanlage hat Daniel bestätigt, dass die Unsicherheit beim Ordner-Picken ein echtes, den Aufwand rechtfertigendes Problem ist.
- **Technische Detailentscheidungen des `architect`-Agenten** (keine Rückfrage nötig, da innerhalb der bereits akzeptierten Richtung): Batch-Endpunkt statt N Einzel-Requests (einzige Möglichkeit, die Gesamt-Nebenläufigkeit serverseitig zu begrenzen); `IMAGE_EXTENSIONS`-Umzug nach `opencloud/client.py` (Abhängigkeitshygiene — `api/opencloud.py` darf `worker.py` mit seinen schweren `mediapipe`/`tensorflow`-Importen nicht in den API-Request-Pfad ziehen); `asyncio.gather`+`Semaphore` statt Block-Muster (kein DB-Session-/Resume-Bedarf hier).
- **Priorität — Niedrig** (nach Schärfung bestätigt, `requirements-engineer`-Vorschlag aus Schritt 2 übernommen): Quality-of-Life-Verbesserung ohne Blocker für Kern-Workflows, betrifft eine einmalige Aktion pro Projektanlage. **Kein Konflikt mit bereits Geplantem:** unabhängig von allen anderen offenen Specs, verdrängt nichts.
- **Korrektur während der Schärfung:** `requirements-engineer` hatte in Schritt 2 eigenmächtig die Tabellenstruktur der Inbox-Sektion in `specs/roadmap.md` umgebaut (neue Spalte "Priorität (Schärfung)") — das weicht vom etablierten Projekt-Muster ab (Inbox-Einträge werden erst in Schritt 9 vollständig entfernt, nicht vorab mit einer Prioritäts-Spalte versehen) und wurde vom Hauptagenten rückgängig gemacht, bevor mit Schritt 3 fortgefahren wurde.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- Anzeige der Dateianzahl außerhalb des Projekt-Anlage-Kontexts (z.B. an anderer Stelle im Frontend) — nur `FolderBrowser`/`ProjectCreatePage`.
- Zählung während des eigentlichen Scans (Spec 0036) — bleibt unverändert, keine Berührung der Worker-Enumerationsphase.
- Rate-Limiting auf den neuen Endpunkt — bewusst nicht vorgesehen (siehe Security-Abschnitt).
- Echtzeit-Aktualisierung der Zähler bei Änderungen auf OpenCloud zwischen Laden und Nutzung — Zählung ist "zum Zeitpunkt des Aufklappens aktuell", konsistent mit dem bestehenden Cache-Verhalten des Browsers.
- Anzeige weiterer Metadaten (Dateigröße, Änderungsdatum) — nur Bilddatei-Anzahl.
