# Architektur-Übersicht

**Status:** Living Document (kein Lifecycle, wird laufend aktualisiert)
**Letzte Aktualisierung:** 2026-07-19 (OpenCloud-Anbindung gemäß [`features/0001`](../features/0001-opencloud-project-connection.md) konkretisiert)

## Systemkontext

PhotoSort verwaltet keine eigenen Bilddateien dauerhaft — die Fotos bleiben auf einer externen **OpenCloud**-Instanz. PhotoSort speichert Metadaten, Bewertungen und einen lokalen Verarbeitungs-Cache (Thumbnails).

```
┌─────────────┐   WebDAV (App-Token aus .env)  ┌──────────────┐
│  OpenCloud   │◄─────────────────────────────►│   Backend    │
│  (extern)    │      dav/spaces/{id}/{path}    │  (FastAPI)   │
└─────────────┘                                └──────┬───────┘
                                                        │
                        ┌───────────────┬───────────────┼───────────────┐
                        │               │               │               │
                  ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐         │
                  │ Postgres  │   │   Redis   │   │  Worker   │         │
                  │ (Metadaten)│  │ (Queue)   │   │  (arq)    │         │
                  └───────────┘   └───────────┘   └───────────┘         │
                                                                         │
                                                                  ┌──────▼───────┐
                                                                  │  Frontend    │
                                                                  │  (React PWA) │
                                                                  └──────────────┘
```

## Komponenten

- **Frontend** (`frontend/`): React + TypeScript + Vite, als PWA installierbar. Kommuniziert ausschließlich über die Backend-API (kein direkter OpenCloud-Zugriff vom Client aus, um App-Tokens nicht im Browser zu exponieren).
- **Backend** (`backend/`): FastAPI. REST-API für Projekte, Fotos, Bewertungen; Auth (JWT); Anbindung an OpenCloud via WebDAV; stößt Hintergrund-Jobs im Worker an. **Implementiert (Spec 0001):** `/opencloud/browse`, `/projects` (CRUD + Scan-Trigger), OpenCloud-Client (`opencloud/client.py`, `opencloud/webdav_xml.py`, `opencloud/exif.py`). **Noch offen:** Auth/JWT, Rating-/Bewertungs-Endpunkte (Spec 0002).
- **Worker** (`backend/`, eigener Container-Prozess): `arq`-basierte Jobs für Foto-Ingest (Listing, Download, Thumbnail-Erzeugung), lokale Heuristik-Berechnung und optionale Cloud-KI-Bewertung. Siehe [`decisions/0002-hybrid-ai-scoring.md`](../decisions/0002-hybrid-ai-scoring.md). **Implementiert (Spec 0001):** `scan_project`-Job (`worker.py`) für Foto-Ingest; Heuristik-/Cloud-Scoring folgt mit Spec 0003.
- **Postgres**: Metadaten (Projekte, Fotos, Bewertungen, Nutzer), keine Bilddaten.
- **Redis**: Job-Queue für den Worker.
- **Lokaler Cache**: Docker-Volume für Thumbnails/Zwischenergebnisse, kein Ersatz für OpenCloud als Quelle der Wahrheit.

## Datenmodell (Skizze, wird pro Feature-Spec verfeinert)

- **User**: Account (Daniel, Ehefrau), getrennt authentifiziert. *(Noch nicht implementiert — kommt mit Auth/Spec für Login.)*
- **Project** *(implementiert, `models.py`)*: z.B. "Costa Rica"; referenziert genau einen OpenCloud-Ordner (rekursiv inkl. Unterordner) über `opencloud_drive_id` + `opencloud_path`.
- **OpenCloud-Verbindung**: kein eigenes DB-Modell — eine einzige, instanzweite Verbindung, konfiguriert über `OPENCLOUD_BASE_URL`/`OPENCLOUD_USERNAME`/`OPENCLOUD_APP_TOKEN`/`OPENCLOUD_DRIVE_NAME` in `.env`. Details siehe [`features/0001-opencloud-project-connection.md`](../features/0001-opencloud-project-connection.md).
- **Photo** *(implementiert, `models.py`)*: gehört zu einem Project, referenziert `relative_path`/`etag` auf OpenCloud, `taken_at`/`last_modified`, `content_length`. Nur JPEG/PNG/HEIC (MVP).
- **ScanRun** *(implementiert, `models.py`)*: ein (Re-)Scan-Lauf eines Projekts — Status (`running`/`success`/`failed`), Zähler (`files_found`, `photos_added`, `photos_updated`, `photos_removed`, `files_skipped`), `error_message` bei Fehlern. Liefert die Zusammenfassung, die über `GET /projects/{id}` als `last_scan` ausgegeben wird.
- **PhotoScore** *(noch nicht implementiert, Spec 0003)*: Ergebnis der lokalen Heuristiken (Schärfe, Belichtung, Duplikat-Cluster) und optional der Cloud-Bewertung.
- **Rating** *(noch nicht implementiert, Spec 0002)*: Bewertung eines Photos durch einen User (`favorite` / `album_worthy` / `rejected`), pro User getrennt gespeichert.

## Bewusste Annahmen (können per ADR/Spec revidiert werden)

- Kein eingebauter Reverse Proxy/TLS in `docker-compose.yml` — das Homeserver-Setup von Daniel übernimmt das.
- CPU-only-Betrieb: alle lokalen KI-Heuristiken müssen ohne GPU praktikabel laufen.
- Cloud-KI-Aufrufe (Phase B des Scorings) sind immer optional/on-demand, nie Voraussetzung für die Kernfunktion.
