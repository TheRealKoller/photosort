# 0263 - Export nach OpenCloud

**Status:** Accepted
**Erstellt:** 2026-11-01
**Bezug:** [Issue #263](https://github.com/TheRealKoller/photosort/issues/263)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Vier Abschnitte tragen ihn, jeder aus einem
eigenen Grund: „Architektur / Umsetzung" führt die betroffenen Dateien je Arbeitspaket auf, weil
der `developer` sie ohne eigene Planung abarbeitet; „Security" führt die Auflagen einzeln abhakbar
samt Angriffsmodell, weil der Export der erste Schreibpfad auf OpenCloud ist; „Teststrategie"
benennt die Zusicherungen, die ohne eigenen Testfall still brechen — ein falsch abgeleiteter
Zielordner oder eine still abgeflachte Dateistruktur wirft keine Ausnahme, sie liefert ein
plausibel aussehendes Ergebnis; „UI/UX" legt die drei Zustände des Auslösers fest, für die es im
Bestand kein Vorbild gibt.

## Ziel

Beide Nutzer eines Projekts haben gemeinsam die Endauswahl des Projekts entschieden — die Menge der
Fotos, die ins Fotoalbum gehören (Spec [`0431`](./0431-endauswahl-gemeinsam.md)). Bisher führt
diese Auswahl nirgendwohin: Es gibt keinen Weg, sie zurück auf die eigene OpenCloud-Instanz zu
bringen, um daraus ein Fotoalbum zu erstellen und drucken zu lassen. Der Export schließt die Lücke:
Mit einem Auslöser wird die Endauswahl als neuer Ordner auf OpenCloud bereitgestellt.

## User Story

Als einer der beiden Nutzer eines Projekts möchte ich die gemeinsam entschiedene Endauswahl mit
einem Auslöser als neuen Ordner auf unserer OpenCloud-Instanz bereitstellen, damit wir daraus ein
Fotoalbum erstellen und drucken können.

## Akzeptanzkriterien

- [ ] Der Export nimmt ausschließlich die Endauswahl des Projekts (die gemeinsam entschiedene Album-Menge), nicht einzelne Favoriten und nicht einzelne Nutzer-Entwürfe.
- [ ] Ein Export erzeugt genau einen neuen, eindeutig benannten Zielordner (aus Projektname und Zeitpunkt). Ein erneuter Export erzeugt einen weiteren neuen Ordner; frühere Exporte werden weder überschrieben noch verändert.
- [ ] Vor dem Auslösen sieht der Nutzer, wie viele Fotos die Auswahl umfasst; nach Abschluss erhält er eine Bestätigung mit Anzahl und Zielpfad.
- [ ] Schlägt das Übertragen einzelner Fotos fehl, bricht der Gesamtexport nicht ab; die betroffenen Fotos werden gesammelt gemeldet.
- [ ] Beide Nutzer können den Export auslösen; das Ergebnis gehört dem Projekt, nicht dem auslösenden Nutzer.
- [ ] Die Fotos werden unverändert im Original exportiert — keine Druckaufbereitung, kein Layout, keine Skalierung.
- [ ] Der Export verändert die Quelle nicht (kein Verschieben oder Löschen der Originale) und ist jederzeit wiederholbar.
- [ ] Nach einem Export ist nachvollziehbar, wann welche Auswahl wohin exportiert wurde.

## Datenmodell-Bezug

Neu: `ExportRun` (Tabelle `export_runs`, Muster `ScanRun`/`ScoringRun`) und die Kindtabelle
`export_photos` (Muster `CriterionScoringRun.rankings`) als Mengen-Schnappschuss; Enum
`ExportRunStatus` (`running`/`success`/`failed`). **Kein `user_id`** an `ExportRun` — das Ergebnis
gehört dem Projekt, wie bei `FinalSelectionDecision`. Details und Spaltenliste in ADR
[`0136`](../decisions/0136-export-der-endauswahl-als-serverseitiges-copy-in-einen-eigenen-ordner.md)
und [`docs/architecture.md`](../../docs/architecture.md).

Unverändert: `Project` (`opencloud_drive_id`, `opencloud_path`), `Photo` (`relative_path`, `etag`),
`FinalSelectionDecision`. Keine neue Spalte an bestehenden Tabellen.

## Architektur / Umsetzung

Die Entscheidungen sind als ADR
[`0136`](../decisions/0136-export-der-endauswahl-als-serverseitiges-copy-in-einen-eigenen-ordner.md)
festgehalten und dort begründet. Sie löst keine bestehende ADR ab — sie setzt auf ADR
[`0099`](../decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md) (die
Endauswahl als Menge) auf. Kein Kopfzeilen-Nachtrag an einer bestehenden ADR.

### Gewählter Ansatz

Der Export ist ein **Hintergrund-Job im Worker** (Muster `scan_project`), kein synchroner Request:
Ordneranlage plus ein `COPY` je Foto ist nicht die Sache eines HTTP-Aufrufs, und die
Akzeptanzkriterien „Fehler je Foto gesammelt melden" und „nachvollziehbar, wann welche Auswahl
wohin exportiert wurde" verlangen einen Lauf mit eindeutigem Endzustand und einer Bestätigung
danach. Die drei Antworten der Story entstehen so: Anzahl **vorher** (Preview, synchron), 202 +
Polling **während**, Bestätigung (Anzahl + Zielpfad + Fehlerliste) **danach**.

- **Übertragung: serverseitiges WebDAV `COPY`, kein Re-Upload.** Quelle und Ziel teilen dieselbe
  OpenCloud-Instanz; `COPY` spart Bandbreite (kein Byte durch PhotoSort), ist bytegenau
  („unverändert im Original"), fasst die Quelle nicht an („kein Verschieben/Löschen") und isoliert
  Einzelfehler je `COPY`-Request. Re-Upload (Download + `PUT`) wäre bei geteilter Instanz strikt
  schlechter und läge große Originale (HEIC/RAW) in Speicher/auf Platte.
- **Ziel: ein eigener Ordner außerhalb des Scan-Wurzelpfads, der die Quell-Unterordnerstruktur
  abbildet.** Fester Wurzelordner `PhotoSort-Export` auf derselben Instanz (über die WebDAV-URL des
  `Project.opencloud_drive_id`), je Lauf ein Unterordner
  `<bereinigter Projektname> <YYYY-MM-DD HH-MM-SS.ffffff>` (UTC, Mikrosekunden). Das Ziel eines
  Fotos ist `Lauf-Ordner/relative_path` — Dateinamen 1:1 erhalten, nicht auf den Basename
  abgeflacht; je Unterordner von `relative_path` entsteht ein `MKCOL`. Der Wurzelordner liegt
  **nicht** unter `Project.opencloud_path` — der Scan läuft nur über `opencloud_path` und würde die
  Exporte sonst beim nächsten Lauf als neue Fotos importieren. Der Sub-Sekunden-Anteil macht jeden
  Lauf eindeutig und wiederholbar: zwei Läufe können nicht in derselben Mikrosekunde beginnen
  (Zeitstempel beim Anlegen des Laufs im nacheinander arbeitenden Worker), ein „erneuter Export"
  erzeugt also immer einen weiteren neuen Ordner.
- **Menge: die abgeleitete Endauswahl** (`selection_state(...).included == true`), nicht Favoriten,
  nicht Einzelentwürfe, nicht die additive Antwortmenge des Lesepfads.
- **Nachvollziehbarkeit: `ExportRun` + Mengen-Schnappschuss** (Kindtabelle `export_photos`).

### Datenfluss

1. `GET /projects/{project_id}/export-preview` — leitet die Endauswahl ab und liefert
   `{photo_count}` (dieselbe Ableitung wie der Export selbst).
2. `POST /projects/{project_id}/export` — enqueued `export_project(project_id)`, antwortet 202
   (Muster `trigger_scan`).
3. Worker `export_project`: Menge ableiten → `ExportRun` (running) + Schnappschuss anlegen →
   `resolve_drive` → `MKCOL` Wurzel **und je Unterordner von `relative_path`** (beides dedupliziert,
   405-tolerant) → je Foto `COPY` von `source` nach `Lauf-Ordner/relative_path` in fester
   Reihenfolge; Einzelfehler in die Schnappschusszeile schreiben und weiterlaufen → Lauf `success`
   (auch mit Teilfehlern) bzw. `failed` (fatal, z. B. Zielordner nicht anlegbar).
4. `ProjectOut.last_export_run` (Muster `last_scan`) liefert den Polling-Zustand samt Anzahl und
   `target_path`; `GET /projects/{project_id}/exports/{run_id}` die Fehler je Foto.

### Neue/geänderte Dateien

- `backend/src/photosort/opencloud/client.py` — `copy(webdav_url, source_path, dest_url)` (WebDAV
  `COPY` mit `Destination`-Header) und `mkcol(webdav_url, path)` (`MKCOL`, 405-tolerant; für Wurzel-
  und Unterordner). Nur das — kein `PUT`-Upload, kein `MOVE`.
- `backend/src/photosort/final_selection.py` (neu, DB-gestützt) — extrahiert die Ableitung der
  Endauswahl aus `api/photos.py::album_selection` und nutzt die reine Regel
  `album_selection.selection_state`. Importiert **nichts** aus `api/` (dieselbe Regel wie
  `client.py` gegenüber `worker.py`). Genau eine Stelle für „die Menge, die der Export nimmt".
- `backend/src/photosort/api/photos.py` — refaktoriert auf `final_selection.py`; die bestehende
  Antwortmenge von `GET …/album-selection` bleibt unverändert.
- `backend/src/photosort/api/export.py` (neu) — Router `export.router` mit router-weitem
  Auth-Torwächter (`dependencies=[Depends(get_current_user)]`, Muster `album_decisions.router`: der
  Auslöser kennt keinen Nutzerbezug): `export-preview`, `POST export` (202), `GET exports/{run_id}`.
  Registrierung ausschließlich in `main.py`.
- `backend/src/photosort/models.py` — `ExportRun`, `ExportPhoto` (Kindtabelle), `ExportRunStatus`.
- `backend/src/photosort/worker.py` — `export_project` + `run_export`; Eintrag in
  `WorkerSettings.functions` mit `arq_func(export_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1)`
  („ein Trigger → genau ein Lauf").
- `backend/src/photosort/project_deletion.py` — nimmt `export_runs`/`export_photos` auf.
- Migration (`backend/alembic/versions/`), `ProjectOut.last_export_run` (`api/projects.py`),
  `docs/architecture.md`.

### Namentlich geklärte Punkte

- **`COPY` vs. Re-Upload:** `COPY` (ADR 0136 Punkt 1).
- **Ableitung der Menge:** Wiederverwendung der Spec-0431-Logik über das extrahierte
  `final_selection.py`; die reine Regel `selection_state` bleibt unverändert und die einzige.
- **Zielordner-Namensschema:** `PhotoSort-Export/<bereinigter Projektname> <YYYY-MM-DD HH-MM-SS.ffffff>`
  (UTC, Mikrosekunden für strukturelle Eindeutigkeit). Innerhalb des Lauf-Ordners
  `target = relative_path` (Quell-Unterordnerstruktur wird abgebildet, je Unterordner ein
  dedupliziertes, 405-tolerantes `MKCOL`); Basename-Kollisionen sind durch `uq_photo_project_path`
  strukturell ausgeschlossen.
- **Datenmodell:** `ExportRun` (Muster Run) + `export_photos`-Schnappschuss (`relative_path`
  eingefroren, zugleich Zielpfad); **kein `user_id`**.
- **Endpunkte:** `GET …/export-preview` (Anzahl vorher), `POST …/export` (202, Auslösen),
  `GET …/exports/{run_id}` (Ergebnis danach, inkl. Fehlerliste); dazu `ProjectOut.last_export_run`.
- **Synchron vs. Worker:** Worker (arq), Muster `scan_project`.
- **Wo landet es:** auf derselben Instanz über die WebDAV-URL von `opencloud_drive_id`, im
  Wurzelordner `PhotoSort-Export` — nie unter `opencloud_path`.

## UI/UX

**Sichtbare Oberfläche: ja.** Der Export ist ein ausgelöster Hintergrund-Job mit drei Antworten an
derselben Stelle: Anzahl vorher, Laufzustand währenddessen, Bestätigung danach.

**Ort.** Die Endauswahl-Ansicht (`AlbumSelectionPage`, Route `/projects/{projectId}/selection`,
Navigationseintrag „Endauswahl"), und dort ausschließlich die **Ergebnissicht** (Schalter
„Endauswahl“). Grund: Der Export nimmt die ganze Endauswahl — dieselbe Menge, die die Ergebnissicht
zeigt. In der Arbeitssicht („Unterschiede“) stünde ein „exportiere N Fotos“-Auslöser neben einer
gefilterten Teilmenge und wäre missverständlich. Ein kompakter, **nicht haftender** Exportbereich
steht deshalb zwischen dem Sicht-Umschalter und der Foto-Liste, sichtbar nur in der Ergebnissicht.
Kein haftender Balken: die Seite ist foto-zentriert, der Export eine gelegentliche Abschlussaktion —
ein dauerhaft haftender Bereich wäre Dauerlärm.

**Ablauf** (drei Zustände an derselben Stelle, kein Dialog, kein Zwischenschritt):

1. **Vorher — Anzahl.** Der Bereich zeigt dauerhaft die Anzahl der Endauswahl-Fotos („N Fotos"),
   geladen über `GET /projects/{projectId}/export-preview` (server-autoritativ — exakt die Menge,
   die der Export gleich nimmt) und bei jeder Änderung der Endauswahl (Herausnehmen/Zurücknehmen in
   dieser Ansicht) nachgezogen. Daneben der primäre Auslöser „Nach OpenCloud exportieren“.
2. **Auslösen → läuft.** Nach `POST /projects/{projectId}/export` (202) bleibt der Auslöser
   **deaktiviert, nicht ausgeblendet**, und trägt den Inline-Spinner (Busy-Button-Muster); die
   Statuszeile daneben/darunter zeigt „Export läuft …“ mit `aria-live="polite"` und dem
   indeterminierten Fortschritt (`ui/progress.tsx`). Der Laufzustand folgt dem Polling über
   `ProjectOut.last_export_run` (Muster `last_scan`); die Trigger-Bestätigung überbrückt das Fenster
   zwischen 202 und erstem bestätigendem Poll (Muster `useTriggerConfirmation`).
3. **Danach — Bestätigung.** Nach Abschluss ersetzt eine Bestätigung den Laufzustand: Anzahl,
   Zielpfad (vollständiger Unterordner, `font-mono`, als regulärer Textknoten) und Zeitpunkt. Bei
   Teilfehlern zusätzlich eine Warn-Meldung (Alert, Ton `info`) mit der gesammelten Liste der nicht
   übertragenen Fotos (Dateinamen). Daneben der nachrangige Auslöser „Erneut exportieren“
   (RerunBlock-Muster) mit dauerhaft sichtbarem Erklärsatz, dass ein neuer Lauf einen weiteren,
   eigenen Ordner anlegt und den vorherigen unverändert lässt. Die Bestätigung bleibt nach dem
   Neuladen sichtbar (letzter Lauf aus `last_export_run` plus Laufdetail) — das erfüllt
   „nachvollziehbar, wann welche Auswahl wohin“: Zeitpunkt und Anzahl aus dem Lauf, Ziel aus dem
   Pfad.

**Zustände:**

- **Leere Endauswahl (0 Fotos):** Auslöser deaktiviert mit dauerhaft sichtbarem Grund („Die
  Endauswahl ist leer — es gibt nichts zu exportieren"), nicht ausgeblendet (Muster „nicht
  verfügbare Aktion / Vorbedingung").
- **Laufender Export:** Busy-Button + Statuszeile + indeterminierter Fortschritt; Doppel-Auslösen
  gesperrt.
- **Fehler beim Auslösen:** inline Alert (Fehler, `x-circle`) mit „Erneut versuchen", Server-`detail`
  wörtlich.
- **Lauf fehlgeschlagen:** inline Alert (Fehler) mit „Erneut versuchen"; der Auslöser wird wieder
  aktiv — kein RerunBlock nach einem Fehlschlag (die einzige Wiederholung ist die Hauptaktion,
  Muster „Erneut-Auslöser").
- **Teilfehler (Erfolg mit einzelnen Fehlschlägen):** Erfolgs-Bestätigung + Warn-Alert mit der
  gesammelten Liste; kein Abbruch, kein anderer Gesamtzustand.

**Bezug zum Design-System.** Kein neues Muster und keine Ergänzung von
`specs/architecture/0004-design-system.md` nötig — alles besteht aus vorhandenen Bausteinen:
Busy-Button (`ui/button.tsx`), Statuszeile + indeterminierter Fortschritt (`ui/progress.tsx`,
`aria-live`), Alert (Erfolg/Warnung/Fehler, `ui/alert.tsx`), RerunBlock, „nicht verfügbare Aktion"
für die leere Auswahl, Status-Punkt (`StatusDot`, nur dekorativ, nie als Textfarbe). **Kein neues
Symbol:** der Auslöser trägt nur Beschriftung wie die bestehenden Lauf-Auslöser (Scan,
Klassifizierung); der Symbolsatz bleibt unangetastet. **Kein Bestätigungsdialog:** der Export ist
nicht destruktiv (die Quelle bleibt unverändert) und jederzeit wiederholbar — nach der Regel
„Bestätigungsdialoge nur für destruktive, schwer rückgängig zu machende Aktionen" genügt die
sichtbare Anzahl als Schutz.

## Security

**Einschätzung: relevant.** Der Export ist der **erste Schreibpfad des Produkts auf OpenCloud**
(MKCOL + serverseitiges `COPY`, ADR 0136) — bislang ist PhotoSort gegenüber OpenCloud ausschließlich
lesend. Neu sind zwei Schreib-/Lese-Endpunkte, freie Texte (`Project.name`,
`Photo.relative_path`-Basenames) als Pfadbestandteile eines HTTP-Headers und der erste Fall, in dem
ein gestohlenes JWT den Backend zu Schreibzugriffen auf OpenCloud veranlassen kann.

### Auth-Vollständigkeit der neuen Endpunkte (Muss)

`POST /projects/{id}/export`, `GET /projects/{id}/export-preview` und der Fehler-Detailendpunkt
liegen in einem eigenen Router `api/export.py` mit Pfaden unter `/projects/{id}/…`.
`projects.router` (Präfix `/projects`) deckt sie **nicht** ab — der Vollständigkeitstest iteriert
Router, nicht Pfade (Präzedenzfall `project_overview.router`).

- Der Router hängt router-weit an `dependencies=[Depends(get_current_user)]`
  (Muster `album_decisions.router`).
- `export.router` wird in `tests/test_auth_guard.py::_protected_router_operations()` eingetragen.
- Der Auslöser nimmt **kein** `current_user` entgegen (Ergebnis gehört dem Projekt, `export_runs`
  ohne `user_id`) — seine Authentifizierung ist an der Signatur unsichtbar. Deshalb zusätzlich ein
  pfadbenannter 401-Test in `test_api_export.py` (dreifache Sicherung, Muster
  Endauswahl/Diagnose/Duplikate).

### WebDAV-`Destination`-Header-Injection und Pfad-Traversal (Muss)

Der Zielordnername entsteht aus `Project.name` (Freitext) + Zeitstempel; der Ziel-Dateiname aus dem
Basename von `Photo.relative_path` (Fremdtext aus dem OpenCloud-Scan). Beides fließt in WebDAV-URLs
bzw. den `Destination`-Header von `COPY`.

- **Jede URL-/Pfadbildung läuft über `opencloud/client.py::_join`** (quotet jedes Segment via
  `quote()`, lehnt `..`-Segmente ab). Der `Destination`-Header wird ausschließlich aus
  `_join(webdav_url, dest_path)` gebaut, nie durch manuelle String-Konkatenation mit rohen Namen —
  sonst wären CRLF-Header-Injection oder ein `..`-Ausbruch aus `PhotoSort-Export` möglich.
- **Sanitisierung des Ordnernamens vor `_join`** (ADR 0136, hier als Muss wiederholt): Steuerzeichen
  (C0/C1) sowie `/` und `\` entfernen, `..`-Segmente ausschließen, Länge begrenzen; Zeitstempel in
  dateisystem-/WebDAV-sicherer Form ohne `:`. `_join`'s `..`-Ablehnung ist die Rückfallebene, nicht
  der alleinige Schutz.
- **Basenames** (Ziel-Dateinamen) durchlaufen dieselbe `_join`-Quotierung; ein Foto, dessen Name die
  Regeln verletzt, scheitert als **Einzelfehler** und landet in `export_photos.error` — nie bricht
  es den Lauf ab, nie überschreibt es ein Ziel (`COPY` + strukturelle Kollisionsfreiheit, kein
  `MOVE`/`PUT`).
- **Fehlermeldungen** von `copy`/`mkcol` geben weiterhin nur Statuscode/Reason-Phrase aus, nie
  Auth-Header/Token (bestehendes `_raise_for_status`-Muster, gilt für die neuen Methoden
  unverändert).

### Rechte/Scope des App-Tokens

`OPENCLOUD_APP_TOKEN` ist ein kontoweites OpenCloud-App-Token; OpenCloud kennt keine feinere
(je-Space/je-Methode) Tokenstufe. Das Feature verengt den Token-Umfang nicht und kann ihn nicht
verengen — es nutzt die vorbestehende Schreibfähigkeit erstmals. Die Grenze wird **im Code**
durchgesetzt: jede Schreiboperation liegt unter dem festen Wurzelordner `PhotoSort-Export`
(Modulkonstante, kein Env-Parameter), Pfadbildung nur über `_join`. Ein geleaktes Token hat bereits
heute kontoweiten Zugriff (unverändert). Neu ist allein: ein gestohlenes **JWT** veranlasst den
Backend (der das Token hält) zu Schreibzugriffen — siehe Restrisiko.

### Idempotenz/Replay des Auslösers

Replay ist gewollt (jeder Export → neuer eindeutiger Ordner; kein Idempotenz-/Deduplizierungszwang,
Akzeptanzkriterium). Sicherheitlich relevant ist nur die Ressourcenwirkung: ein gestohlenes JWT
kann Exporte wiederholt auslösen und OpenCloud-Speicher mit Kopien füllen. Begrenzend: Schreibziele
liegen ausschließlich unter `PhotoSort-Export`, kein Überschreiben/Löschen fremder Daten, keine neue
Vertraulichkeitsgrenze (Quelle und Ziel im selben OpenCloud-Account; Daten verlassen die Instanz
nicht). Als akzeptiertes Restrisiko geführt, konsistent mit den bestehenden „gestohlenes
JWT"-Eskalationen.

### Sichtbarkeit zwischen den beiden Nutzern

`export_runs`/`export_photos` ohne `user_id`; Historie projekt-skopiert, für beide Nutzer lesbar;
kein Owner-Check — konsistent mit „kein Innentäter-Modell" und dem
`GET /projects/{id}/photos`-Präzedenzfall. Keine neue Sichtbarkeitsasymmetrie: Zielpfad und
Fehlerliste (Dateinamen) sind über die Fotoliste ohnehin für beide sichtbar.

### SSRF / Frontend

- **SSRF:** `webdav_url` stammt ausschließlich aus serverseitiger Konfiguration/DB
  (`opencloud_drive_id`), nie aus Nutzereingabe; Ziel-Host = Quell-Host. Kein SSRF-Zuwachs.
- **XSS:** Zielpfad als `font-mono`-Textknoten, Fehlerliste als Alert — ausschließlich
  React-Textknoten, kein `dangerouslySetInnerHTML`, keine Fremdwerte in Attributen.
- **CSRF:** entfällt nach ADR 0005 (Bearer-Header, kein Cookie).

### Ergänzung des Sicherheitskonzepts (im selben PR)

- Ankerliste: Zeile „Auth-Torwächter als Router-Dependency" um `export` ergänzen.
- WebDAV-Client-Abschnitt: erste **schreibende** Operationen (MKCOL/COPY) — Ziel auf
  `PhotoSort-Export` begrenzt, Pfadbildung nur über `_join`.
- „Bewusst akzeptierte Restrisiken": gestohlenes JWT → OpenCloud-Schreibzugriff (Speicherfüllung,
  kein Datenverlust, keine neue Vertraulichkeitsgrenze).

## Teststrategie

Der Export ist der **erste Schreibpfad auf OpenCloud** und folgt den bestehenden Mustern; gemockt
wird ausschließlich an der Außenschnittstelle (`FakeOpenCloudClient`, um `copy`/`mkcol` erweitert
und **aufzeichnend**: welche Schreiboperation mit welchem Zielpfad abgesetzt wurde — das erste Mal,
dass Tests prüfen, *was wohin* geschrieben wird, nicht nur *was* gelesen). Kein Test erreicht ein
Netz (bestehende Socket-Sperre).

- **Unit:** reine Funktionen — Projektnamen-Bereinigung, `copy`/`mkcol` im `OpenCloudClient` gegen
  `httpx.MockTransport` (`Destination`-Header, `OpenCloudError` bei Fehlstatus, 405-Toleranz des
  `mkcol`); die Endauswahl-Regel selbst bleibt in `test_album_selection.py`.
- **Integration (Schwerpunkt):** `run_export` gegen echte In-Memory-SQLite +
  Recording-`FakeOpenCloudClient` (Muster `run_project_scan`). Fälle: Erfolgslauf (genau `n`
  `COPY` mit Ziel `Lauf-Ordner/relative_path`, kein Download/Upload/Move, Quelle unangetastet),
  zwei gleichnamige Basenamen in verschiedenen Unterordnern landen kollisionsfrei und je
  Unterordner wird genau ein `MKCOL` gesetzt, Einzelfehler (Lauf `success`, `failed_count`/
  Fehlerzeilen korrekt), fatal (`MKCOL`/`resolve_drive` → `failed`), leerer Auswahl (kein Lauf),
  zwei Läufe → zwei Ordner, deterministische Reihenfolge, Schnappschuss-überlebt-Quelländerung.
  `final_selection` liefert exakt die `included`-Menge und ist mit dem API-Lesepfad **geteilt**.
- **API:** `GET /projects/{id}/export-preview` (Anzahl = Worker-Menge), `POST /projects/{id}/export`
  → 202 + `FakeEnqueuer.calls == [("export_project", (project_id,))]` (Muster `trigger_scan`),
  `ProjectOut.last_export_run`, `GET /projects/{id}/exports/{run_id}`. **Beide** Nutzer (zweiter
  Token) triggern und lesen dieselben Läufe; `export_runs` ohne `user_id`.
- **Migration/Modell:** `test_migration_export.py` (Spaltenmenge exakt ohne `user_id`,
  `export_photos.photo_id` nullable, `error` nullable, `down`-Weg); `test_models.py` (Foto-Löschung
  → `photo_id NULL`, Schnappschuss bleibt); `test_project_deletion.py`
  (Vollständigkeits-/Reihenfolge-Wächter fängt `export_runs`/`export_photos` automatisch über
  `Base.metadata`).
- **Auth:** `export.router` in `_protected_router_operations()` (Registerstelle) **plus** eigener
  pfadbenannter 401-Fall, da der Router kein `current_user` entgegennimmt (Muster
  `album_decisions`/`feedback`).
- **Frontend (vitest):** `AlbumSelectionPage` — Anzahl, Auslösen, Busy/Polling, Bestätigung (Anzahl
  + Zielpfad), Warn-Alert mit Fehlerliste bei Teilfehlern; leerer Auswahl (Auslöser deaktiviert mit
  Grund), Lauf fehlgeschlagen.
- **Bewusst nicht automatisiert:** echter OpenCloud-`COPY`/`MKCOL` gegen die reale Instanz
  (ungepinntes Rolling-Image) und Byte-Gleichheit Original↔Kopie — bleibt manueller Smoke-Test vor
  Merge (wie heute der Worker-Smoke-Test); die Socket-Sperre bleibt unangetastet.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) bekommt im selben PR eine neue Sektion
„Export der Endauswahl (erster Schreibpfad auf OpenCloud, Spec 0263)" mit drei neuen Mustern:
aufzeichnender Fake für Schreiboperationen, `mkcol`-405-Toleranz als Client-Verhalten,
„Schnappschuss überlebt Quelländerung".

## Entscheidungen

- **Alle vier Agenten konsultiert, keine Skip-Entscheidung** (Schritte 1–3 des spec-writer-Ablaufs):
  `architect` (Architektur + ADR 0136), `ux-ui-designer` (sichtbare Oberfläche), `test-engineer`
  (Teststrategie), `security-engineer` (sicherheitsrelevant).
- **Produktentscheidung (von Daniel getroffen):** Namenskollision im Zielordner wird durch Abbilden
  der Quell-Unterordnerstruktur aufgelöst (`target = relative_path`), nicht durch Abflachen oder
  Umbenennen. Festgehalten in ADR 0136 Punkt 2.

## Out of Scope

Layout-/Druckvorbereitung eines physischen Fotobuchs — der Export stellt nur die Auswahl als Ordner
bereit. Upload per `PUT`/`MOVE` im Produktivcode (der `OpenCloudClient` bekommt ausschließlich
`copy` und `mkcol`). Automatisierte CI-Tests gegen einen echten OpenCloud-Server (bleibt manueller
Smoke-Test, wie Spec 0009). Auswahl einzelner Fotos für den Export (es wird immer die ganze
Endauswahl exportiert).
