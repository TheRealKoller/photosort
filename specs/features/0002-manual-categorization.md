# 0002 - Manuelle Kategorisierung

**Status:** Proposed
**Erstellt:** 2026-07-19
**Bezug:** Ausgangsgespräch Projekt-Setup

## Ziel

Daniel und seine Frau können die Fotos eines Projekts in einer Oberfläche durchsehen und jeweils als **Favorit**, **Album-würdig** oder **Verwerfen** einstufen — schnell genug, um mehrere tausend Fotos in überschaubarer Zeit durchzugehen.

## User Story

Als Nutzer möchte ich Fotos eines Projekts schnell nacheinander durchklicken und mit einem der drei Zustände markieren, damit am Ende eine kuratierte Auswahl entsteht.

## Akzeptanzkriterien

- [ ] Grid- und/oder Einzelbild-Ansicht (z.B. Tastatur-/Swipe-Navigation) für zügiges Durchsortieren.
- [ ] Drei-Zustands-Bewertung pro Foto und Nutzer: `favorite`, `album_worthy`, `rejected` (unbewertet als Ausgangszustand).
- [ ] Bewertungen sind pro Nutzer getrennt gespeichert (Daniel und seine Frau sehen/setzen ihre eigenen Bewertungen).
- [ ] Es gibt eine Ansicht, die beide Bewertungen nebeneinander zeigt (z.B. für Fotos, bei denen sich beide einig oder uneinig sind).
- [ ] Filter-/Sortiermöglichkeiten (z.B. nur unbewertete, nur Favoriten, nach Datum).
- [ ] Bedienbar als PWA auch auf Mobilgeräten (Touch-Bedienung beim Durchsortieren).

## Datenmodell-Bezug

Neu: `Rating` (photo_id, user_id, status, updated_at). Siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Offene Fragen

- Wie wird mit unterschiedlichen Bewertungen beider Nutzer für dasselbe Foto beim Export umgegangen (z.B. nur "beide stimmen überein" exportieren, oder manuelle Konfliktauflösung)?
- Soll es eine Kommentar-/Notiz-Funktion pro Foto geben (z.B. "unscharf, aber schöner Moment")?
- Tastatur-Shortcuts gewünscht (z.B. 1/2/3 für die drei Zustände)?

## Out of Scope

Automatische Vorauswahl (Spec 0003), Export (Spec 0004).
