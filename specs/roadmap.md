# Roadmap

Lebendes Dokument, gepflegt vom `requirements-engineer`-Agenten. Enthält die Priorisierung und den Status-Überblick der Features — die eigentliche fachliche Wahrheit steht in den einzelnen Spec-Dateien unter `specs/features/`, hier nur Reihenfolge/Einordnung darüber. Kein Lifecycle wie bei Specs, wird laufend aktualisiert.

## Priorisierung

### Jetzt

- **Auth-Implementierung** (noch keine Spec-Datei — beim Schärfen von Spec 0002 am 2026-07-19 als fehlendes Prerequisite entdeckt). Login/JWT gemäß [`decisions/0003-auth-model.md`](./decisions/0003-auth-model.md), bisher nur als ADR entschieden, nicht umgesetzt. Muss vor Spec 0002 stehen, da deren Endpunkte `get_current_user` voraussetzen.
- **Minimales Projekt-Frontend** (noch keine Spec-Datei — ebenfalls beim Schärfen von Spec 0002 entdeckt). Projekt-Anlage, Ordner-Browser-UI, Routing-/API-Client-Grundgerüst — Spec 0001 deckt nur das Backend ab. Muss vor Spec 0002 stehen, da deren Views auf diesem Grundgerüst aufbauen.
- **Manuelle Kategorisierung** — [`specs/features/0002-manual-categorization.md`](./features/0002-manual-categorization.md) (Status: Accepted, geschärft im idea-sharpener-Gespräch vom 2026-07-19). Direkt anschließend an die Backend-Grundlage aus Spec 0001; ohne diese Kategorisierungs-Oberfläche gibt es für Daniel und seine Frau noch keinen nutzbaren Workflow. Braucht die beiden oben genannten, noch ungeschärften Prerequisite-Specs, bevor `developer` sie umsetzen kann.

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

## Bekannte Abhängigkeiten

- **0001 → Auth-Implementierung / Minimales Projekt-Frontend → 0002:** Spec 0001 deckt nur das Backend ab (kein Frontend, kein Auth). Spec 0002 setzt beides voraus (auth-pflichtige Endpunkte, Routing-/API-Grundgerüst) — beide Prerequisite-Specs müssen geschärft und akzeptiert sein, bevor `developer` Spec 0002 umsetzen kann, siehe deren Abschnitt "Architektur / Umsetzung".
- **0002 → 0003:** Spec 0003 nutzt dasselbe `Rating`-Datenmodell wie 0002 und muss dessen `source`-Unterscheidung (`manual` vs. `auto`) respektieren — sollte nach 0002 umgesetzt werden.
- **0002 → 0004:** Spec 0004 exportiert Fotos anhand der Bewertungen aus 0002 und klärt dort die von 0002 übernommene offene Frage zur Konfliktbehandlung unterschiedlicher Bewertungen beider Nutzer — kann erst nach 0002 sinnvoll abgeschlossen werden.
