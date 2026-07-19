# 0001 - OpenCloud-Projekt-Anbindung

**Status:** Implemented (Backend)
**Erstellt:** 2026-07-19
**Akzeptiert:** 2026-07-19
**Implementiert:** 2026-07-19 (Commit "feat: implement OpenCloud project connection backend (spec 0001)")
**Bezug:** Ausgangsgespräch Projekt-Setup

**Scope-Hinweis:** Implementiert ist die Backend-API (WebDAV/Graph-API-Client, Datenmodell, Scan-Worker, REST-Endpunkte). Die Frontend-Oberfläche (Ordner-Browser-UI, Projekt-Anlage-Formular) sowie Authentifizierung der Endpunkte sind eigene, noch offene Erweiterungen — siehe "Out of Scope".

## Ziel

Nutzer können in PhotoSort ein "Projekt" (z.B. "Costa Rica") anlegen und diesem einen Ordner auf der OpenCloud-Instanz zuordnen. Das ist die Grundlage für alle weiteren Features (manuelle Kategorisierung, automatische Auswahl, Export).

## User Story

Als Nutzer möchte ich ein neues Projekt anlegen und einen OpenCloud-Ordner damit verknüpfen, damit die darin enthaltenen Fotos in PhotoSort verwaltet werden können.

## Akzeptanzkriterien

- [x] Die OpenCloud-Zugangsdaten (Server-URL, Username, App-Token) werden als Umgebungsvariablen (`OPENCLOUD_BASE_URL`, `OPENCLOUD_USERNAME`, `OPENCLOUD_APP_TOKEN`, `OPENCLOUD_DRIVE_NAME`) konfiguriert — kein Credential-UI, keine Speicherung in der Datenbank. (`backend/src/photosort/config.py`)
- [x] Ordner sind per `GET /opencloud/browse?path=` (WebDAV `PROPFIND` gegen die von der Graph-API gelieferte `webDavUrl` des konfigurierten Space) auflistbar. *(Backend-Endpunkt; Browser-UI selbst ist Frontend-Scope, noch offen.)*
- [x] `POST /projects` legt ein Projekt mit Namen und genau einem OpenCloud-Ordner an; der Ordner wird vor dem Anlegen per PROPFIND validiert. (`backend/src/photosort/api/projects.py`)
- [x] Der Scan-Worker (`scan_project`, ausgelöst über `POST /projects/{id}/scan`) listet alle Bilddateien (JPEG, PNG, HEIC/HEIF) aus dem verknüpften Ordner **und allen Unterordnern rekursiv** und speichert Pfad, ETag, Aufnahmedatum (EXIF für JPEG, sonst WebDAV-Änderungsdatum) in der Datenbank. (`backend/src/photosort/worker.py`)
- [x] Andere Dateitypen werden beim Scan ignoriert und in der `ScanRun`-Zusammenfassung (`files_skipped`) gezählt.
- [x] `POST /projects/{id}/scan` stößt einen erneuten Scan an; Diff-Logik über ETag/Pfad erkennt neue, geänderte und entfernte Dateien (`photos_added`/`photos_updated`/`photos_removed`).
- [x] Verbindungsfehler (ungültiges Token, nicht erreichbarer Server, Ordner nicht gefunden) werden als `OpenCloudError` gefangen und über die API als `400` mit verständlicher Fehlermeldung ausgegeben statt als roher 500er — inklusive Netzwerkfehlern (verifiziert per Docker-Compose-Smoketest).

## Datenmodell-Bezug

Neu: `Project`, `Photo` (Ingest-Teil). Kein eigenes `OpenCloudConnection`-Datenbankmodell — die Verbindung ist eine global konfigurierte, für beide Nutzer gemeinsame Instanz-Einstellung (siehe Entscheidungen unten). Siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Entscheidungen (2026-07-19, im Stakeholder-Dialog geklärt)

- **Eine gemeinsame OpenCloud-Verbindung** für beide Nutzer (kein `OpenCloudConnection`-Modell pro User) — beide greifen auf dieselbe Instanz zu.
- **Token-Speicherung:** ausschließlich als Umgebungsvariable (`OPENCLOUD_APP_TOKEN`), analog zu `OPENCLOUD_BASE_URL`. Keine Verschlüsselung in der DB nötig, da nicht dort gespeichert.
- **Unterordner:** werden automatisch rekursiv einbezogen, keine explizite Auswahl nötig.
- **Dateitypen:** initial nur JPEG/PNG/HEIC. RAW- und Video-Unterstützung ist explizit spätere Erweiterung (eigene Spec).
- **Re-Sync:** manueller "Aktualisieren"-Button statt automatischem Abgleich beim Öffnen (Performance bei tausenden Dateien, Einfachheit).

## Out of Scope

Manuelle Kategorisierung, automatische Auswahl, Export — jeweils eigene Specs. RAW-/Video-Unterstützung, mehrere Ordner pro Projekt, mehrere OpenCloud-Instanzen. **Frontend-Oberfläche** (Ordner-Browser-UI, Projekt-Anlage-Formular) und **Authentifizierung der API-Endpunkte** sind in dieser Implementierung noch nicht enthalten — eigene, nachfolgende Erweiterungen.
