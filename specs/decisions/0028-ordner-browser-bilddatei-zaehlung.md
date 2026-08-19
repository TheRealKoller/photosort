# 0028 - Ordner-Browser: begrenzte, parallele Bilddatei-Zählung pro Unterordner

**Status:** Accepted
**Datum:** 2026-08-19
**Bezug:** `specs/inbox/0006-dateianzahl-beim-ordner-heraussuchen.md` (Idee, nach Aufnahme in die
zugehörige Feature-Spec zu löschen); künftige Feature-Spec vermutlich `specs/features/0050-...md`.
Baut auf dem bestehenden BFS-Traversierungsmuster (`opencloud/client.py::OpenCloudClient.walk`,
Zyklenschutz seit ADR [`decisions/0019-job-lauf-heartbeat-watchdog.md`](./0019-job-lauf-heartbeat-watchdog.md))
sowie dem bestehenden `GET /opencloud/browse`-Endpunkt (`api/opencloud.py`,
`specs/features/0005-minimal-project-frontend.md`) auf. Zur begrenzt-parallelen HTTP-seitigen
Ausführung vergleichbar mit, aber bewusst **kein** Wiederverwendungsfall von
[`decisions/0020-scan-enumeration-und-parallele-verarbeitung.md`](./0020-scan-enumeration-und-parallele-verarbeitung.md) —
siehe Begründung Punkt 4.

## Kontext

Mit Daniel bereits geklärt (siehe Übergabe an den `architect`-Agenten): Jeder im `FolderBrowser`
gelistete Unterordner soll seine eigene, rekursive Bilddatei-Anzahl zeigen, bevor man
hineinklickt — eager (automatisch für alle gelisteten Unterordner, nicht erst bei Klick), aber mit
harter Obergrenze (z.B. 500, dann "500+"), um die Traversierungstiefe/-dauer pro Unterordner zu
begrenzen. Eine naive Umsetzung (vollständiger `client.walk()` pro Unterordner ohne Abbruch) würde
bei tief verschachtelten Kamera-Exports beliebig lange laufen und den Ordner-Browser dabei
blockieren.

Zwei bereits bestehende, aber für sich genommen nicht ausreichende Bausteine:

- `OpenCloudClient.walk()` ist ein `AsyncIterator`, der lazy PROPFIND-Anfragen (`Depth: 1`) pro
  Ebene stellt — es traversiert nicht "auf einmal", sondern liefert Einträge on demand, solange der
  Konsument iteriert.
- `worker.py` kennt bereits ein Muster für begrenzte Parallelität (`_process_scan_block`, ADR
  0020) — dieses Muster ist aber an einen Job-Kontext gebunden (lange laufender Hintergrund-Job,
  `AsyncSession`-Schreibzugriffe, Crash-Sicherheits-Commits pro Block). Der Ordner-Browser läuft
  dagegen synchron im HTTP-Request/Response-Zyklus eines interaktiven UI-Aufrufs, schreibt nichts in
  die DB und muss innerhalb einer für den Browser akzeptablen Zeit antworten.

## Entscheidung

### 1. Wiederverwendung von `OpenCloudClient.walk()` mit frühem Abbruch statt neuem Zählmechanismus

Kein neuer, dedizierter Traversierungscode. `walk()` ist eine `async def ... yield`-Generatorfunktion
— sie pausiert exakt an jedem `yield`, bis die konsumierende Seite den nächsten Eintrag anfordert.
Bricht der Konsument die `async for`-Schleife ab (z.B. weil die Zähl-Obergrenze erreicht ist), stellt
`walk()` ab diesem Punkt keine weiteren PROPFIND-Anfragen mehr — kein "einmal den ganzen Baum
durchlaufen und danach kappen", sondern echter Early-Exit direkt auf Netzwerkebene. Der bestehende
Zyklenschutz (`visited`-Set) gilt dabei unverändert mit. Die Zählfunktion selbst ist ein kleiner,
neuer, endpoint-lokaler Helfer in `api/opencloud.py` (nicht in `OpenCloudClient` selbst — Zählen mit
Obergrenze ist Endpunkt-spezifische Geschäftslogik, kein generisches WebDAV-Client-Verhalten; `client.py`
bleibt bewusst ein reiner, dünner Transport-Layer, analog zur bestehenden Trennung
"`worker.py`-Phasenlogik nutzt `client.walk()`, ohne dass `client.py` selbst etwas über Scan-Phasen
weiß").

### 2. Neuer Batch-Endpunkt `GET /opencloud/folder-counts`, keine Einzel-Requests pro Unterordner

Statt vom Frontend aus einen separaten Request pro gelistetem Unterordner abzusetzen, bekommt jedes
`/opencloud/browse`-Listing genau einen begleitenden Request auf einen neuen Endpunkt
`GET /opencloud/folder-counts?path=<gleicher Pfad wie beim Listing>`. Der Endpunkt listet selbst
(identisch zu `browse_folder`) die direkten Unterordner des übergebenen Pfads und zählt dann für
jeden gefundenen Unterordner parallel, begrenzt durch eine neue Konfigurationsgröße
`settings.opencloud_folder_count_concurrency` (env-überschreibbar, Default 4 — dieselbe
Überlastschutz-Begründung wie `scan_download_concurrency`, ADR 0020 Punkt 5: der
Einzelnutzer-Homeserver-OpenCloud soll nicht mit vielen gleichzeitigen Zähl-Traversierungen
geflutet werden, auch wenn ein Ordner z.B. 30 Unterordner enthält). Diese eine Server-seitige
Bündelung ist der eigentliche Grund für einen Batch- statt Einzel-Endpunkt: sie macht die
Gesamt-Parallelität über *alle* Unterordner-Zählungen eines Listings hinweg serverseitig
kontrollierbar; N unkoordinierte, gleichzeitig vom Browser abgefeuerte Einzel-Requests entzögen sich
dieser Steuerung vollständig. Response-Signatur bewusst symmetrisch zu `browse_folder`
(`path`-Query-Parameter, keine Liste von Pfaden im Query-String) — ein neues `FolderCount`-Schema
(`path: str`, `count: int`, `at_limit: bool`, `error: bool`) pro Unterordner.

Der bestehende `GET /opencloud/browse`-Endpunkt selbst bleibt unverändert (kein neues Feld, keine
zusätzliche Traversierung) — die Listing-Antwort wird durch die Zählung nicht verzögert, da beide
Requests unabhängig sind.

### 3. Bildendungs-Filter: `worker.py::_IMAGE_EXTENSIONS` wird nach `opencloud/client.py` verschoben

`api/opencloud.py` darf `worker.py` nicht importieren — `worker.py` zieht über
`classification.py`/`aesthetics.py` die schweren `mediapipe`-/`tensorflow`-Abhängigkeiten nach sich
(derselbe Grund, aus dem `classification.py` von `scoring.py` getrennt gehalten wird, siehe
[`decisions/0015-lokale-kategorie-klassifikation.md`](./0015-lokale-kategorie-klassifikation.md)),
das darf nicht in den Import-Pfad des API-Prozesses (Request-Handling) einsickern. Die bisher private
Modul-Konstante `_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}` zieht daher als
öffentliche Konstante `IMAGE_EXTENSIONS` nach `opencloud/client.py` um — der bereits heute gemeinsame,
leichte Baustein, den sowohl `worker.py` als auch (neu) `api/opencloud.py` ohnehin importieren.
`worker.py` importiert die Konstante künftig von dort, statt sie lokal zu duplizieren — ein einziger
Ort für "was zählt als Bild", keine zwei potenziell auseinanderlaufenden Listen.

### 4. Fehlerbehandlung: `asyncio.gather(..., return_exceptions=True)` über alle Unterordner-Zählungen eines Requests, kein Block-Muster

Anders als in ADR 0020 (Scan-Job) gibt es hier **keine** `AsyncSession`-Nebenläufigkeitsgrenze und
keinen Crash-Sicherheits-Commit-Bedarf — der Endpunkt schreibt nichts in die Datenbank, ein
fehlgeschlagener Request bedeutet lediglich "diese HTTP-Antwort war unvollständig", nicht "ein
Job-Lauf muss sauber resumable bleiben". Deshalb kein Blockgrößen-Muster wie in `_process_scan_block`,
sondern ein einziger `asyncio.gather(..., return_exceptions=True)` über alle Unterordner-Zählungen
des Requests, mit einem `asyncio.Semaphore(settings.opencloud_folder_count_concurrency)` um jede
einzelne Zählung (statt fester Blöcke — hier keine Commit-Grenze, an der sich eine Blockgröße
orientieren müsste). Schlägt eine einzelne Unterordner-Zählung fehl (z.B. `OpenCloudError` durch
Timeout), wird das als `FolderCount(path=..., count=0, at_limit=False, error=True)` in die Antwort
aufgenommen statt die gesamte Batch-Antwort mit einer `HTTPException` scheitern zu lassen — die
übrigen Zähler und die Listing-/Navigationsfunktion des `FolderBrowser` bleiben davon unberührt. Nur
ein Scheitern des vorgelagerten Listings selbst (Auflisten der direkten Unterordner, analog
`browse_folder`) liefert weiterhin einen echten `400`, da dann gar keine Zählbasis existiert.

### 5. Obergrenze `FOLDER_COUNT_LIMIT = 500` als reine Modul-Konstante, keine Settings-Größe

Anders als die Concurrency (echter Betriebsparameter, Überlastschutz) ist die Zähl-Obergrenze ein
reiner Anzeige-/UX-Wert ("500+" statt einer exakten großen Zahl) ohne betriebliche
Tuning-Notwendigkeit — analog zur bestehenden Unterscheidung "Betriebsparameter → `Settings`-Feld,
reiner Kalibrierungswert → Modul-Konstante" aus ADR 0020 Punkt 5 (dort `scan_download_concurrency`
vs. `SCAN_COMMIT_BATCH_SIZE`). Eine einzelne Zählung bricht ab, sobald `FOLDER_COUNT_LIMIT`
erreichte Bilddateien gezählt wurden, unabhängig davon, wie viele weitere Dateien/Ordner darunter
noch existieren.

### 6. Caching: keine neue Strategie, identisches Muster wie `useOpenCloudBrowseQuery`

Der neue Frontend-Hook (`useOpenCloudFolderCountsQuery(path)`) übernimmt exakt das bestehende Muster
— eigener React-Query-Key pro Pfad, `staleTime: Infinity`. Der `FolderBrowser` ist ohnehin nur für
die Dauer eines einzelnen Projekt-Anlage-Dialogs gemountet, der React-Query-Cache lebt nur innerhalb
der Browser-Tab-Session; dieselbe bereits akzeptierte Inkonsistenz-Toleranz ("Ordnerinhalt kann sich
zwischen zwei Projektanlagen ändern, wird aber innerhalb einer Session nicht automatisch
neu-validiert") gilt für Namen und Zähler gleichermaßen. Eine abweichende TTL nur für die Zähler wäre
eine unbegründete Inkonsistenz zwischen zwei Werten, die ohnehin gemeinsam angezeigt werden.

## Begründung

- Löst das eigentliche Performance-Problem (unbegrenzte Traversierungstiefe/-dauer) strukturell
  durch Wiederverwendung der bestehenden lazy-Generator-Semantik von `walk()`, statt einen zweiten,
  parallelen Traversierungsmechanismus einzuführen — minimale neue Fläche.
- Der Batch-Endpunkt ist die einzige Stelle, an der die Gesamt-Nebenläufigkeit über potenziell viele
  Unterordner hinweg serverseitig begrenzt werden kann; das rechtfertigt die zusätzliche
  API-Fläche gegenüber dem naheliegenderen "ein Request pro Unterordner".
- Die Verschiebung von `IMAGE_EXTENSIONS` ist keine kosmetische Aufräumaktion, sondern eine echte
  Abhängigkeitsgrenze: `api/opencloud.py` (Request-Pfad) darf strukturell nicht von `worker.py`
  (zieht `mediapipe`/`tensorflow` nach sich) abhängen.
- Bewusst **kein** Wiederverwendungsfall des Block-Musters aus ADR 0020: unterschiedlicher Kontext
  (keine DB-Schreibzugriffe, kein Resume-Bedarf) rechtfertigt ein einfacheres
  Semaphore-plus-`gather`-Muster statt der dortigen Blockgrößen-/Commit-Logik — ein
  Copy-Paste des Job-Musters hierher wäre unnötig komplex gewesen.

## Konsequenzen

- Neues `Settings`-Feld `opencloud_folder_count_concurrency` (`config.py`, `Field(default=4, ge=1)`,
  analog `scan_download_concurrency`).
- Keine Migration, kein neues DB-Modell — die Zählung ist rein transient, nicht persistiert.
- `docs/architecture.md` (Owner: `architect`) wird nach Umsetzung um den neuen Endpunkt, die
  verschobene `IMAGE_EXTENSIONS`-Konstante und die neue Settings-Größe ergänzt.
- Test-Engineer-relevant (nicht Teil dieser ADR, aber direkte Konsequenz): ein Regressionstest, der
  belegt, dass `walk()` bei einem Abbruch nach Erreichen der Obergrenze tatsächlich keine weiteren
  PROPFIND-Anfragen mehr stellt (z.B. über einen Fake-Transport mit Anfrage-Zähler) — schützt exakt
  die in Entscheidung 1 beschriebene Early-Exit-Eigenschaft, die sonst bei einer künftigen Änderung
  an `walk()` unbemerkt regredieren könnte. Ebenso ein Test für den `error: true`-Fall eines
  einzelnen Unterordners (fehlschlagende Zählung darf die übrigen Zähler/die Listing-Antwort nicht
  beeinträchtigen).
