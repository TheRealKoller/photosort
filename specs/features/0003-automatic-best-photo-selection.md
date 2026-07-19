# 0003 - Automatische Auswahl der besten Fotos

**Status:** Proposed
**Erstellt:** 2026-07-19
**Bezug:** Ausgangsgespräch Projekt-Setup, [`decisions/0002-hybrid-ai-scoring.md`](../decisions/0002-hybrid-ai-scoring.md)

## Ziel

PhotoSort schlägt automatisch die besten Fotos eines Projekts für ein Album vor, basierend auf dem in ADR 0002 beschriebenen hybriden Scoring (lokale Heuristiken + optionale Cloud-Bewertung).

## User Story

Als Nutzer möchte ich per Knopfdruck eine automatische Vorauswahl der besten Fotos eines Projekts erhalten, damit ich nicht alle tausend Fotos manuell durchsehen muss, sondern nur noch die Vorschläge prüfen muss.

## Akzeptanzkriterien

- [ ] Nutzer kann für ein Projekt "Beste Fotos automatisch vorschlagen" anstoßen (asynchroner Hintergrund-Job).
- [ ] Phase A (lokal) läuft immer: Schärfe-, Belichtungs- und Duplikat-/Burst-Erkennung; klar unbrauchbare Fotos (starke Unschärfe, Duplikate, geschlossene Augen) werden automatisch aussortiert bzw. niedrig gewichtet.
- [ ] Verbleibende Fotos erhalten einen lokalen Qualitäts-Score und werden nach Zeit-/Motiv-Clustern gruppiert.
- [ ] Phase B (Cloud) ist optional zuschaltbar/deaktivierbar (globale Einstellung) und wird nur auf die Top-Kandidaten pro Cluster angewendet.
- [ ] Ergebnis erscheint als **Vorschlag** (nicht als verbindliche Bewertung) im selben Rating-Modell wie die manuelle Kategorisierung — der Nutzer bestätigt oder korrigiert.
- [ ] Automatische Vorschläge überschreiben nie bereits vorhandene manuelle Bewertungen desselben Nutzers.
- [ ] Fortschritt des Hintergrund-Jobs ist in der UI sichtbar (läuft über tausende Fotos, kann dauern).

## Datenmodell-Bezug

Neu: `PhotoScore` (sharpness, exposure, duplicate_of, local_quality_score, cloud_aesthetic_score, computed_at). Vorschläge nutzen `Rating` mit einem Kennzeichen `source=auto` vs. `source=manual` (Detail offen, siehe unten).

## Offene Fragen

- Konkrete Gewichtung/Schwellenwerte der lokalen Heuristiken (z.B. ab welcher Laplace-Varianz gilt ein Foto als "zu unscharf")?
- Wie werden automatische Vorschläge von manuellen Bewertungen im Datenmodell unterschieden (eigenes Feld `source`, oder komplett getrennte Tabelle `Suggestion`)?
- Wie groß sollen "Top-Kandidaten pro Cluster" für Phase B sein (z.B. Top 3 pro Zeit-Cluster)?
- Soll es eine Kostenanzeige/-schätzung geben, bevor Phase B ausgelöst wird?
- Clustering-Kriterium für "Zeit-/Motiv-Cluster": reine Zeitfenster (z.B. Aufnahmen < 2 Minuten auseinander) oder zusätzlich visuelle Ähnlichkeit?

## Out of Scope

Manuelle Kategorisierungs-UI (Spec 0002), Export (Spec 0004).
