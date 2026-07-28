# Roadmap

Lebendes Dokument, gepflegt vom `requirements-engineer`-Agenten. Enthält die Priorisierung und den Status-Überblick der Features — die eigentliche fachliche Wahrheit steht in den einzelnen Spec-Dateien unter `specs/features/`, hier nur Reihenfolge/Einordnung darüber. Kein Lifecycle wie bei Specs, wird laufend aktualisiert.

## Priorisierung

### Jetzt

- ~~**Auth-Implementierung**~~ — [`specs/features/0006-auth.md`](./features/0006-auth.md) (Status: **Implemented**, [PR #1](https://github.com/TheRealKoller/photosort/pull/1), 2026-07-21). Login/JWT gemäß [`decisions/0003-auth-model.md`](./decisions/0003-auth-model.md) und [`decisions/0005-auth-implementation.md`](./decisions/0005-auth-implementation.md) (Argon2, PyJWT, Bearer+localStorage, Rate-Limiting via `slowapi`) umgesetzt, inkl. React Router + TanStack Query als erster sichtbarer Oberfläche des Projekts. War Prerequisite für Spec 0002 und Spec 0005 — beide sind jetzt entsperrt.
- ~~**Minimales Projekt-Frontend**~~ — [`specs/features/0005-minimal-project-frontend.md`](./features/0005-minimal-project-frontend.md) (Status: **Implemented**, [PR #2](https://github.com/TheRealKoller/photosort/pull/2), 2026-07-22). Projektliste, Projekt-Anlage-Formular mit Ordner-Browser, Projekt-Detailseite mit Scan-Trigger/-Polling umgesetzt, inkl. der beiden Backend-Härtungen (CORS-Allowlist, Path-Traversal-Fix in `opencloud/client.py::_join`). War Prerequisite für Spec 0002 — jetzt entsperrt.
- ~~**Manuelle Kategorisierung**~~ — [`specs/features/0002-manual-categorization.md`](./features/0002-manual-categorization.md) (Status: **Implemented**, [PR #3](https://github.com/TheRealKoller/photosort/pull/3), 2026-07-27). Grid-/Einzelbild-/Vergleichsansicht, `Rating`-Modell, Thumbnail-Erzeugung im Worker umgesetzt — erster nutzbarer Kern-Workflow für Daniel und seine Frau. War Prerequisite für Spec 0003 und Spec 0004 — beide sind jetzt entsperrt.
- ~~**Automatische Vorauswahl (Phase A: lokale Heuristiken)**~~ — [`specs/features/0003-automatic-best-photo-selection.md`](./features/0003-automatic-best-photo-selection.md) (Status: **Implemented**, [PR #6](https://github.com/TheRealKoller/photosort/pull/6), 2026-07-28). Lokale Heuristiken (Schärfe, Belichtung, Duplikat-/Burst-Erkennung, lokaler Qualitäts-Score, Zeit-Clustering) umgesetzt, Vorschläge strukturell getrennt vom `Rating`-Modell aus Spec 0002 (`PhotoScore`/`ScoringRun`, ADR [`decisions/0006-local-scoring-datamodel.md`](./decisions/0006-local-scoring-datamodel.md)) — `Rating` bleibt unangetastet, ein Vorschlag wird erst durch aktive Bestätigung über den bestehenden `PUT /photos/{id}/rating`-Endpunkt verbindlich. War Prerequisite für Phase B (Cloud-Feinbewertung) — siehe "Ideenspeicher" unten, jetzt entsperrt (noch keine eigene Spec-Nummer).

### Als Nächstes

Aktuell keine akzeptierte Spec ohne offene Blocker in dieser Kategorie — Spec 0004 (siehe "Später") ist bereits entsperrt und der naheliegende nächste Kandidat für eine Schärfung.

### Später

- **Export nach OpenCloud** — [`specs/features/0004-opencloud-export.md`](./features/0004-opencloud-export.md) (Status: Proposed). Setzt eine belastbare Menge an Bewertungen aus Spec 0002 voraus; die dort verschobene Frage zur Konfliktbehandlung unterschiedlicher Nutzer-Bewertungen wird hier final geklärt.

### Ideenspeicher

- **Automatische Vorauswahl — Phase B (Cloud-Feinbewertung)**: aus Spec 0003 ausgegliedert (2026-07-27), noch keine eigene Spec-Nummer. Optionale, per Konfiguration abschaltbare Fein-Bewertung (Komposition/Ästhetik) der Top-Kandidaten pro Cluster via Vision-LLM-API (z.B. Anthropic), siehe [`decisions/0002-hybrid-ai-scoring.md`](./decisions/0002-hybrid-ai-scoring.md). Spec 0003 (Phase A) ist jetzt implementiert und liefert das Clustering (`cluster_key`) und die Perceptual-Hashes (`phash`), auf denen Phase B aufbauen kann — jetzt entsperrt, bereit für eine eigene Schärfungs-Session. Bereits mit Daniel vorentschiedene Punkte, die beim späteren Schärfen nicht neu verhandelt werden müssen: Kostenschätzung/-anzeige vor Start von Phase B — ja; Top-Kandidaten pro Cluster — vom Nutzer einstellbar; Clustering-Basis — Zeitfenster + visuelle Ähnlichkeit (Wiederverwendung des Perceptual-Hash aus der Duplikat-Erkennung von Phase A). **Bekannte, akzeptierte Lücke aus der Phase-A-Implementierung:** Wird die `display`-Cache-Datei eines bereits gescorten Fotos zwischen zwei Läufen unlesbar, bleibt dessen alte `PhotoScore`-Zeile (inkl. `phash`/`cluster_key`) unverändert stehen statt invalidiert zu werden (siehe `decisions/0006-local-scoring-datamodel.md`, Abschnitt "Konsequenzen") — für Phase B ggf. erneut bewerten.

## Status auf einen Blick

| Spec | Titel | Status |
|---|---|---|
| [0001](./features/0001-opencloud-project-connection.md) | OpenCloud-Projekt-Anbindung | Implemented (Backend) — Frontend-Oberfläche und API-Authentifizierung noch offen, siehe Abhängigkeiten unten |
| [0002](./features/0002-manual-categorization.md) | Manuelle Kategorisierung | Implemented ([PR #3](https://github.com/TheRealKoller/photosort/pull/3)) |
| [0003](./features/0003-automatic-best-photo-selection.md) | Automatische Vorauswahl (Phase A) | Implemented ([PR #6](https://github.com/TheRealKoller/photosort/pull/6)) |
| [0004](./features/0004-opencloud-export.md) | Export nach OpenCloud | Proposed |
| [0005](./features/0005-minimal-project-frontend.md) | Minimales Projekt-Frontend | Implemented ([PR #2](https://github.com/TheRealKoller/photosort/pull/2)) |
| [0006](./features/0006-auth.md) | Auth-Implementierung | Implemented ([PR #1](https://github.com/TheRealKoller/photosort/pull/1)) |

## Bekannte Abhängigkeiten

- ~~**0001 → 0006 (Auth-Implementierung, Implemented) → 0005 (Minimales Projekt-Frontend, Implemented) → 0002**~~ — alle vier Specs sind jetzt implementiert (0006: [PR #1](https://github.com/TheRealKoller/photosort/pull/1), 0005: [PR #2](https://github.com/TheRealKoller/photosort/pull/2), 0002: [PR #3](https://github.com/TheRealKoller/photosort/pull/3)). Kette vollständig abgeschlossen, hier nur noch der Vollständigkeit halber referenziert.
- ~~**0002 (Implemented) → 0003 (Implemented):**~~ Spec 0003 durfte das produktive `Rating`-Modell aus 0002 nicht verändern — Vorschläge landen laut ADR 0006 in eigenen Tabellen (`PhotoScore`/`ScoringRun`), `Rating` blieb unangetastet, ein Vorschlag wird erst über den bestehenden `PUT /photos/{id}/rating`-Endpunkt zu einer echten Bewertung. Beide Specs sind jetzt implementiert ([PR #3](https://github.com/TheRealKoller/photosort/pull/3), [PR #6](https://github.com/TheRealKoller/photosort/pull/6)).
- **0002 (Implemented) → 0004:** Spec 0004 exportiert Fotos anhand der Bewertungen aus 0002 und klärt dort die von 0002 übernommene offene Frage zur Konfliktbehandlung unterschiedlicher Bewertungen beider Nutzer — 0002 ist jetzt umgesetzt, Spec 0004 ist entsperrt.
- **0003 (Phase A, Implemented) → Phase B (Ideenspeicher, noch keine Spec):** Phase B baut auf dem Perceptual-Hash-/Cluster-Ergebnis aus Phase A auf (Wiederverwendung, keine Neuimplementierung) — Phase A ist jetzt implementiert und im Alltag nutzbar, Phase B ist damit entsperrt und bereit für eine eigene Schärfungs-Session.
