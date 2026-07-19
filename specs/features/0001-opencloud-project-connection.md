# 0001 - OpenCloud-Projekt-Anbindung

**Status:** Proposed
**Erstellt:** 2026-07-19
**Bezug:** Ausgangsgespräch Projekt-Setup

## Ziel

Nutzer können in PhotoSort ein "Projekt" (z.B. "Costa Rica") anlegen und diesem einen oder mehrere Ordner auf ihrer OpenCloud-Instanz zuordnen. Das ist die Grundlage für alle weiteren Features (manuelle Kategorisierung, automatische Auswahl, Export).

## User Story

Als Nutzer möchte ich ein neues Projekt anlegen und einen OpenCloud-Ordner damit verknüpfen, damit die darin enthaltenen Fotos in PhotoSort verwaltet werden können.

## Akzeptanzkriterien

- [ ] Nutzer kann OpenCloud-Zugangsdaten (Server-URL + App-Token) einmalig hinterlegen.
- [ ] Nutzer kann per Ordner-Browser (WebDAV `PROPFIND`) einen oder mehrere Ordner auf der verbundenen OpenCloud-Instanz auswählen.
- [ ] Nutzer kann ein Projekt mit Namen (z.B. "Costa Rica") anlegen, dem die ausgewählten Ordner zugeordnet sind.
- [ ] PhotoSort listet beim Öffnen eines Projekts alle Bilddateien aus den verknüpften Ordnern (inkl. Unterordnern) und speichert deren Metadaten (Pfad, ETag, Aufnahmedatum aus EXIF) in der Datenbank.
- [ ] Verbindungsfehler (falsches Token, Ordner nicht erreichbar) werden dem Nutzer verständlich angezeigt.

## Datenmodell-Bezug

Neu: `OpenCloudConnection`, `Project`, `Photo` (Ingest-Teil). Siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Offene Fragen

- Wie wird das App-Token verschlüsselt gespeichert (z.B. Fernet mit Secret aus `.env`)? Reicht das für den Homeserver-Kontext oder wird mehr benötigt?
- Ein OpenCloudConnection pro User oder eine gemeinsame Verbindung für beide Nutzer (da beide vermutlich denselben OpenCloud-Account/dieselbe Instanz nutzen)?
- Sollen Unterordner automatisch rekursiv einbezogen werden, oder wählt der Nutzer explizit?
- Wie wird mit Nicht-Bild-Dateien (Videos, RAW-Formate) im Ordner umgegangen — ignorieren, separat kennzeichnen?
- Erkennung neuer/gelöschter Dateien bei erneutem Öffnen eines Projekts: automatischer Re-Sync oder manueller "Aktualisieren"-Button?

## Out of Scope

Manuelle Kategorisierung, automatische Auswahl, Export — jeweils eigene Specs.
