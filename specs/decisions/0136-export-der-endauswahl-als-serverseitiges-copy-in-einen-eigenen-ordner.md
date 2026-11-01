# 0136 - Export der Endauswahl: serverseitiges WebDAV COPY in einen eigenen Zielordner

**Status:** Accepted
**Datum:** 2026-11-01
**Bezug:** Issue [#263](https://github.com/TheRealKoller/photosort/issues/263), Spec
[`0431`](../features/0431-endauswahl-gemeinsam.md) und ADR
[`0099`](./0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md) (Konsequenz „Der Export
findet hier seine Menge"), ADR
[`0009`](./0009-local-opencloud-demo-stack.md) (Upload/Export blieb diesem Issue vorbehalten)

## Kontext

Die Endauswahl (Spec 0431, ADR 0099) ist die Menge, die als Album gilt — aber sie führt bisher
nirgendwohin. Der Export soll sie als neuen Ordner auf der gemeinsamen OpenCloud-Instanz
bereitstellen. PhotoSort ist gegenüber OpenCloud heute **ausschließlich lesend**; der Export ist
der **erste Schreibpfad** dorthin. Quelle und Ziel teilen dieselbe Instanz: Die Fotos liegen unter
`Project.opencloud_drive_id` + `Project.opencloud_path`, der Export landet ebenfalls dort.

## Entscheidung

### 1. Übertragung per serverseitigem WebDAV `COPY`, nicht per Re-Upload

Jedes Foto wird per `COPY` (RFC 4918) mit `Destination`-Header serverseitig kopiert; es fließt
kein Byte durch PhotoSort. Quelle und Ziel teilen die Instanz, deshalb ist `COPY` dem Re-Upload
(Download + `PUT`) strikt überlegen: keine doppelte Netzlast, keine großen Originale (HEIC/RAW) im
Speicher/auf der Platte, bytegenaue Kopie („unverändert im Original"), Quelle unangetastet
(„kein Verschieben/Löschen"), und je Foto genau ein isolierter `COPY`-Request, dessen Scheitern
den Lauf nicht abbricht.

`OpenCloudClient` erhält zwei Methoden: `copy(webdav_url, source_path, dest_url)` und
`mkcol(webdav_url, path)`. `mkcol` toleriert `405` (Ordner existiert) für den Wurzelordner; der
Lauf-Ordner ist eindeutig benannt und kollidiert nie. Kein `PUT`-Upload, kein `MOVE`.

### 2. Das Ziel ist ein eigener Ordner außerhalb des Scan-Wurzelpfads

Exporte landen in einem festen Wurzelordner `PhotoSort-Export` auf **derselben** Instanz — über
die WebDAV-URL des `Project.opencloud_drive_id` — je Lauf in einem Unterordner
`<bereinigter Projektname> <YYYY-MM-DD HH-MM-SS.ffffff>` (UTC, Mikrosekunden). Der
Sub-Sekunden-Anteil garantiert die Eindeutigkeit strukturell: Der Zeitstempel wird beim Anlegen des
Laufs im Worker genommen, und der Worker verarbeitet Aufträge nacheinander — zwei Läufe können nicht
in derselben Mikrosekunde beginnen, ein „erneuter Export" erzeugt also immer einen weiteren neuen
Ordner. Der Wurzelordner liegt damit **nicht** unter `Project.opencloud_path`: der Scan läuft nur
über `opencloud_path` und importiert Exporte deshalb nie erneut. Frühere Exporte werden weder
überschrieben noch verändert.

**Der Zielordner bildet die Quell-Unterordnerstruktur ab:** Das Ziel eines Fotos unter dem
Lauf-Ordner ist `relative_path` selbst (Dateinamen 1:1 erhalten, nicht auf den Basename abgeflacht).
Je Unterordner von `relative_path` entsteht ein `MKCOL`, dedupliziert und 405-tolerant wie der
Wurzelordner. Basename-Kollisionen sind durch `uq_photo_project_path` (`relative_path` ist je
Projekt eindeutig) strukturell ausgeschlossen.

Der Projektname wird beim Bau des Ordnernamens bereinigt (Steuerzeichen sowie `/` und `\` entfernt,
`..`-Segmente ausgeschlossen); `_join`'s bestehende `..`-Ablehnung ist die Rückfallebene. Der
Wurzelordnername ist eine Modulkonstante, kein Env-Parameter.

### 3. Nachvollziehbarkeit über einen Lauf und einen Mengen-Schnappschuss

Neue Tabelle `export_runs` (Muster `ScanRun`/`ScoringRun`): `project_id`, `status`
(`running`/`success`/`failed`), `started_at`, `finished_at`, `target_path`, `photo_count`,
`exported_count`, `failed_count`, `error_message`. **Kein `user_id`** — das Ergebnis gehört dem
Projekt, wie bei `FinalSelectionDecision` (ADR 0099 Punkt 3).

Die Endauswahl ist abgeleitet und bleibt danach änderbar; „nachvollziehbar, welche Auswahl wohin
exportiert wurde" verlangt deshalb einen **Schnappschuss der exportierten Menge**. Kindtabelle
`export_photos` (Muster `CriterionScoringRun.rankings`): je Foto eine Zeile mit `photo_id`
(nullable), `relative_path` (eingefroren, zugleich Zielpfad unter dem Lauf-Ordner — der Zielordner
spiegelt die Quellstruktur, Punkt 2) und `error` (nullable). Dieselbe Tabelle trägt die Fehler je
Foto: Ein fehlgeschlagenes `COPY` schreibt die Fehlermeldung in die Zeile, der
Lauf läuft weiter und endet trotz Teilfehlern `success`. Nur ein fataler Fehler (Zielordner nicht
anlegbar, OpenCloud nicht erreichbar) endet `failed`.

### 4. Die Menge ist die abgeleitete Endauswahl, an genau einer Stelle

Exportiert wird ausschließlich `selection_state(...).included == true` (ADR 0099 Punkt 1) — nie
Favoriten, nie Einzelentwürfe, nie die additive Antwortmenge des Lesepfads. Die Ableitung wird aus
`api/photos.py::album_selection` in ein geteiltes, DB-gestütztes Modul `final_selection.py`
extrahiert, das die reine Regel `album_selection.selection_state` nutzt und die inkludierte Menge
zurückgibt. Lesepfad und Export-Worker rufen dieselbe Stelle — eine zweite Ableitung lieferte still
eine andere, plausibel aussehende Menge (Auflage S9 der Spec 0431).

### 5. Verarbeitung im Worker

Der Export läuft als arq-Job (`export_project`, `max_tries=1`, Muster `scan_project`): Auslösen →
202 → der Worker leitet die Menge ab, legt `ExportRun` und Schnappschuss an, erzeugt den Ordner
und `COPY` je Foto. Vorher liefert `GET /projects/{id}/export-preview` die Anzahl aus derselben
Ableitung; danach trägt `ProjectOut.last_export_run` (Muster `last_scan`) Zustand, Anzahl und
`target_path`, ein Detailendpunkt die Fehler je Foto.

## Konsequenzen

- **Erster Schreibpfad auf OpenCloud**, begrenzt auf genau einen Wurzelordner: Jede Schreiboperation
  der Anwendung liegt unter `PhotoSort-Export`, nichts anderes wird je angefasst.
- **`project_deletion.py`** nimmt `export_runs` und `export_photos` auf; der Vollständigkeitswächter
  gegen `Base.metadata` fängt ein Vergessen.
- **`docs/architecture.md`** bekommt die neuen Tabellen, die Endpunkte und den Worker-Job im
  betroffenen Pull Request.
- **Kein neuer Env-Parameter, kein neues Infrastruktur-Baustück.**
