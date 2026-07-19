# 0002 - Hybrides KI-Scoring für die Fotoauswahl

**Status:** Accepted
**Datum:** 2026-07-19

## Kontext

Die automatische Auswahl der "besten" Fotos soll auf einem CPU-only-Homeserver laufen, bei Sammlungen von mehreren tausend Fotos pro Projekt. Reine Cloud-KI-Bewertung aller Fotos wäre teuer und schickt private Familienfotos an einen externen Dienst; reine lokale Heuristik allein liefert ggf. weniger nuancierte Ästhetik-Bewertungen.

## Entscheidung

Zweiphasiges, hybrides Scoring:

- **Phase A (lokal, immer aktiv, CPU-only):** Schärfe (Varianz des Laplace-Filters), Belichtung (Histogramm-Analyse auf Über-/Unterbelichtung), Duplikat-/Burst-Erkennung (perceptual hashing, Clustering nach Zeitstempel + Hash-Distanz), optional Augen-/Gesichtserkennung (z.B. mediapipe) zum Aussortieren von Fotos mit geschlossenen Augen. Ergebnis: harte Ausschlüsse (unscharf, Duplikat, Augen zu) + lokaler Qualitäts-Score für die verbleibenden Fotos.
- **Phase B (optional, on-demand, Cloud):** Für die Top-Kandidaten pro Zeit-/Motiv-Cluster kann eine Vision-fähige LLM-API (z.B. Anthropic) zur Fein-Bewertung (Komposition, Ästhetik) herangezogen werden. Wird explizit vom Nutzer ausgelöst (Button "Beste Fotos automatisch vorschlagen"), ist per Konfiguration global abschaltbar.

Automatische Vorschläge landen als Vorschlag im selben Bewertungsmodell wie manuelle Ratings, überschreiben aber nie bestehende manuelle Bewertungen.

## Begründung

- Phase A ist kostenlos, datenschutzfreundlich und schnell genug für CPU-only-Batches über tausende Fotos.
- Phase B wird gezielt nur auf eine kleine Vorauswahl angewendet — begrenzt Kosten und Datenversand auf ein Minimum, bleibt aber optional nutzbar für bessere Ergebnisse.

## Konsequenzen

- Gewichtung/Schwellenwerte der lokalen Heuristiken müssen in einer eigenen Feature-Spec konkretisiert werden (siehe [`features/0003-automatic-best-photo-selection.md`](../features/0003-automatic-best-photo-selection.md)).
- Phase B erfordert einen konfigurierbaren API-Key (z.B. `ANTHROPIC_API_KEY`) und darf nie Voraussetzung für die Kernfunktion sein.
