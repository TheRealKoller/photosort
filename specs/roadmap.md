# Roadmap

Lebendes Dokument, gepflegt vom `requirements-engineer`-Agenten. Enthält die Priorisierung und den Status-Überblick der Features — die eigentliche fachliche Wahrheit steht in den einzelnen Spec-Dateien unter `specs/features/`, hier nur Reihenfolge/Einordnung darüber. Kein Lifecycle wie bei Specs, wird laufend aktualisiert.

## Priorisierung

### Jetzt

- ~~**Auth-Implementierung**~~ — [`specs/features/0006-auth.md`](./features/0006-auth.md) (Status: **Implemented**, [PR #1](https://github.com/TheRealKoller/photosort/pull/1), 2026-07-21). Login/JWT gemäß [`decisions/0003-auth-model.md`](./decisions/0003-auth-model.md) und [`decisions/0005-auth-implementation.md`](./decisions/0005-auth-implementation.md) (Argon2, PyJWT, Bearer+localStorage, Rate-Limiting via `slowapi`) umgesetzt, inkl. React Router + TanStack Query als erster sichtbarer Oberfläche des Projekts. War Prerequisite für Spec 0002 und Spec 0005 — beide sind jetzt entsperrt.
- ~~**Minimales Projekt-Frontend**~~ — [`specs/features/0005-minimal-project-frontend.md`](./features/0005-minimal-project-frontend.md) (Status: **Implemented**, [PR #2](https://github.com/TheRealKoller/photosort/pull/2), 2026-07-22). Projektliste, Projekt-Anlage-Formular mit Ordner-Browser, Projekt-Detailseite mit Scan-Trigger/-Polling umgesetzt, inkl. der beiden Backend-Härtungen (CORS-Allowlist, Path-Traversal-Fix in `opencloud/client.py::_join`). War Prerequisite für Spec 0002 — jetzt entsperrt.
- **Manuelle Kategorisierung** — [`specs/features/0002-manual-categorization.md`](./features/0002-manual-categorization.md) (Status: Accepted, geschärft im idea-sharpener-Gespräch vom 2026-07-19). Direkt anschließend an die Backend-Grundlage aus Spec 0001; ohne diese Kategorisierungs-Oberfläche gibt es für Daniel und seine Frau noch keinen nutzbaren Workflow. Beide Prerequisite-Specs (Auth → Minimales Projekt-Frontend) sind jetzt implementiert — 0002 ist entsperrt und laut Roadmap-Reihenfolge das nächste Ticket für `developer`.

### Als Nächstes

- **Automatische Vorauswahl** — [`specs/features/0003-automatic-best-photo-selection.md`](./features/0003-automatic-best-photo-selection.md) (Status: Proposed). Baut auf dem `Rating`-Modell aus Spec 0002 auf (Vorschläge dürfen manuelle Bewertungen nie überschreiben) — ergibt erst nach 0002 Sinn.

### Später

- **Export nach OpenCloud** — [`specs/features/0004-opencloud-export.md`](./features/0004-opencloud-export.md) (Status: Proposed). Setzt eine belastbare Menge an Bewertungen aus Spec 0002 voraus; die dort verschobene Frage zur Konfliktbehandlung unterschiedlicher Nutzer-Bewertungen wird hier final geklärt.

### Ideenspeicher

- (aktuell leer)

## Status auf einen Blick

| Spec | Titel | Status |
|---|---|---|
| [0001](./features/0001-opencloud-project-connection.md) | OpenCloud-Projekt-Anbindung | Implemented (Backend) — Frontend-Oberfläche und API-Authentifizierung noch offen, siehe Abhängigkeiten unten |
| [0002](./features/0002-manual-categorization.md) | Manuelle Kategorisierung | Accepted |
| [0003](./features/0003-automatic-best-photo-selection.md) | Automatische Vorauswahl | Proposed |
| [0004](./features/0004-opencloud-export.md) | Export nach OpenCloud | Proposed |
| [0005](./features/0005-minimal-project-frontend.md) | Minimales Projekt-Frontend | Implemented ([PR #2](https://github.com/TheRealKoller/photosort/pull/2)) |
| [0006](./features/0006-auth.md) | Auth-Implementierung | Implemented ([PR #1](https://github.com/TheRealKoller/photosort/pull/1)) |

## Bekannte Abhängigkeiten

- **0001 → 0006 (Auth-Implementierung, Implemented) → 0005 (Minimales Projekt-Frontend, Implemented) → 0002:** Spec 0001 deckt nur das Backend ab (kein Frontend, kein Auth). Ursprünglich als zwei parallele Prerequisites zu 0002 eingeordnet; seit der Stakeholder-Entscheidung vom 2026-07-20 war die Reihenfolge **sequenziell**: Spec 0005 setzte eine bereits umgesetzte Auth-Spec (0006) voraus (Login-Screen, geschützte Routen, Token-Handling sind Teil der Auth-Spec, nicht des Frontend-Grundgerüsts). Spec 0006 ist mit [PR #1](https://github.com/TheRealKoller/photosort/pull/1) umgesetzt, Spec 0005 mit [PR #2](https://github.com/TheRealKoller/photosort/pull/2) (Projektliste/-anlage/-detail, CORS-Allowlist, Path-Traversal-Fix) — beide Prerequisites sind jetzt erfüllt, Spec 0002 ist entsperrt und ist laut Stakeholder das nächste Ticket.
- **0002 → 0003:** Spec 0003 nutzt dasselbe `Rating`-Datenmodell wie 0002 und muss dessen `source`-Unterscheidung (`manual` vs. `auto`) respektieren — sollte nach 0002 umgesetzt werden.
- **0002 → 0004:** Spec 0004 exportiert Fotos anhand der Bewertungen aus 0002 und klärt dort die von 0002 übernommene offene Frage zur Konfliktbehandlung unterschiedlicher Bewertungen beider Nutzer — kann erst nach 0002 sinnvoll abgeschlossen werden.
