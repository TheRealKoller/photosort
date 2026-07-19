# 0001 - OpenCloud-Projekt-Anbindung

**Status:** Accepted
**Erstellt:** 2026-07-19
**Akzeptiert:** 2026-07-19
**Bezug:** Ausgangsgespräch Projekt-Setup

## Ziel

Nutzer können in PhotoSort ein "Projekt" (z.B. "Costa Rica") anlegen und diesem einen Ordner auf der OpenCloud-Instanz zuordnen. Das ist die Grundlage für alle weiteren Features (manuelle Kategorisierung, automatische Auswahl, Export).

## User Story

Als Nutzer möchte ich ein neues Projekt anlegen und einen OpenCloud-Ordner damit verknüpfen, damit die darin enthaltenen Fotos in PhotoSort verwaltet werden können.

## Akzeptanzkriterien

- [ ] Die OpenCloud-Zugangsdaten (Server-URL + App-Token) werden als Umgebungsvariablen (`OPENCLOUD_BASE_URL`, `OPENCLOUD_APP_TOKEN`) konfiguriert — kein Credential-UI, keine Speicherung in der Datenbank.
- [ ] Nutzer kann per Ordner-Browser (WebDAV `PROPFIND` gegen `dav/spaces/{id}/{path}`) genau einen Ordner auf der konfigurierten OpenCloud-Instanz auswählen.
- [ ] Nutzer kann ein Projekt mit Namen (z.B. "Costa Rica") anlegen, dem der ausgewählte Ordner zugeordnet ist.
- [ ] PhotoSort listet beim Anlegen eines Projekts alle Bilddateien (JPEG, PNG, HEIC) aus dem verknüpften Ordner **und allen Unterordnern rekursiv** und speichert deren Metadaten (Pfad, ETag, Aufnahmedatum aus EXIF) in der Datenbank.
- [ ] Andere Dateitypen (Video, RAW, etc.) werden beim Scan ignoriert (nicht verarbeitet, nicht gelöscht) und in der Scan-Zusammenfassung als "übersprungen" gezählt.
- [ ] Ein manueller "Aktualisieren"-Button auf der Projektseite stößt einen erneuten Scan des Ordners an und gleicht neue/gelöschte Dateien ab (Abgleich über ETag/Pfad-Vergleich).
- [ ] Verbindungsfehler (falsches Token, Ordner nicht erreichbar) werden dem Nutzer verständlich angezeigt.

## Datenmodell-Bezug

Neu: `Project`, `Photo` (Ingest-Teil). Kein eigenes `OpenCloudConnection`-Datenbankmodell — die Verbindung ist eine global konfigurierte, für beide Nutzer gemeinsame Instanz-Einstellung (siehe Entscheidungen unten). Siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Entscheidungen (2026-07-19, im Stakeholder-Dialog geklärt)

- **Eine gemeinsame OpenCloud-Verbindung** für beide Nutzer (kein `OpenCloudConnection`-Modell pro User) — beide greifen auf dieselbe Instanz zu.
- **Token-Speicherung:** ausschließlich als Umgebungsvariable (`OPENCLOUD_APP_TOKEN`), analog zu `OPENCLOUD_BASE_URL`. Keine Verschlüsselung in der DB nötig, da nicht dort gespeichert.
- **Unterordner:** werden automatisch rekursiv einbezogen, keine explizite Auswahl nötig.
- **Dateitypen:** initial nur JPEG/PNG/HEIC. RAW- und Video-Unterstützung ist explizit spätere Erweiterung (eigene Spec).
- **Re-Sync:** manueller "Aktualisieren"-Button statt automatischem Abgleich beim Öffnen (Performance bei tausenden Dateien, Einfachheit).

## Out of Scope

Manuelle Kategorisierung, automatische Auswahl, Export — jeweils eigene Specs. RAW-/Video-Unterstützung, mehrere Ordner pro Projekt, mehrere OpenCloud-Instanzen.
