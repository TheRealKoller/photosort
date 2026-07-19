# Architektur-Übersicht

**Status:** Living Document (kein Lifecycle, wird laufend aktualisiert)
**Letzte Aktualisierung:** 2026-07-19

## Systemkontext

PhotoSort verwaltet keine eigenen Bilddateien dauerhaft — die Fotos bleiben auf einer externen **OpenCloud**-Instanz. PhotoSort speichert Metadaten, Bewertungen und einen lokalen Verarbeitungs-Cache (Thumbnails).

```
┌─────────────┐      WebDAV (App-Token)      ┌──────────────┐
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
- **Backend** (`backend/`): FastAPI. REST-API für Projekte, Fotos, Bewertungen; Auth (JWT); Anbindung an OpenCloud via WebDAV; stößt Hintergrund-Jobs im Worker an.
- **Worker** (`backend/`, eigener Container-Prozess): `arq`-basierte Jobs für Foto-Ingest (Listing, Download, Thumbnail-Erzeugung), lokale Heuristik-Berechnung und optionale Cloud-KI-Bewertung. Siehe [`decisions/0002-hybrid-ai-scoring.md`](../decisions/0002-hybrid-ai-scoring.md).
- **Postgres**: Metadaten (Projekte, Fotos, Bewertungen, Nutzer), keine Bilddaten.
- **Redis**: Job-Queue für den Worker.
- **Lokaler Cache**: Docker-Volume für Thumbnails/Zwischenergebnisse, kein Ersatz für OpenCloud als Quelle der Wahrheit.

## Datenmodell (Skizze, wird pro Feature-Spec verfeinert)

- **User**: Account (Daniel, Ehefrau), getrennt authentifiziert.
- **Project**: z.B. "Costa Rica"; referenziert einen oder mehrere OpenCloud-Ordner.
- **OpenCloudConnection**: Basis-URL + App-Token-Referenz (verschlüsselt gespeichert), pro User oder pro Instanz — Details offen, siehe [`features/0001-opencloud-project-connection.md`](../features/0001-opencloud-project-connection.md).
- **Photo**: gehört zu einem Project, referenziert Pfad/ETag auf OpenCloud, EXIF-Metadaten, Thumbnail-Cache-Pfad.
- **PhotoScore**: Ergebnis der lokalen Heuristiken (Schärfe, Belichtung, Duplikat-Cluster) und optional der Cloud-Bewertung.
- **Rating**: Bewertung eines Photos durch einen User (`favorite` / `album_worthy` / `rejected`), pro User getrennt gespeichert.

## Bewusste Annahmen (können per ADR/Spec revidiert werden)

- Kein eingebauter Reverse Proxy/TLS in `docker-compose.yml` — das Homeserver-Setup von Daniel übernimmt das.
- CPU-only-Betrieb: alle lokalen KI-Heuristiken müssen ohne GPU praktikabel laufen.
- Cloud-KI-Aufrufe (Phase B des Scorings) sind immer optional/on-demand, nie Voraussetzung für die Kernfunktion.
