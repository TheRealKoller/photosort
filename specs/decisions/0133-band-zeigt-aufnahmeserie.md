# 0133 - Das Alternativen-Band zeigt die Aufnahmeserie, vom Server geschnitten

**Status:** Accepted
**Datum:** 2026-10-05
**Bezug:** Spec [`features/0578-alternativen-serie-und-hinzufuegen.md`](../features/0578-alternativen-serie-und-hinzufuegen.md)

**Löst ab (teilweise):**

- [`0132`](./0132-alternativen-zeitlich-geordnet-mit-bezugsposition.md), Punkt 3 — das
  Bandfenster `nearest=N` mit `clamp(reference_index − ⌊N/2⌋, …)`. Punkte 1, 2 und 4 (ein
  Schlüssel im Backend, `reference_index` als Antwortfeld, eigene Antwortform) gelten unverändert.

## Entscheidung

1. **Die Serie entsteht im Backend, in derselben Reihe.** Der Query-Parameter `nearest` entfällt;
   an seine Stelle tritt `series: bool` (nur mit `photo_id`, sonst `422`). Grundlage ist die nach
   ADR 0132 Punkt 1 geordnete Kandidatenreihe mit dem Bezugsbild an `reference_index`. Die Serie
   ist der zusammenhängende Abschnitt `[a, b)` dieser Reihe, der vom Bezugsbild aus nach beiden
   Seiten wächst, solange der Abstand zweier benachbarter `taken_at` (das Bezugsbild als erster
   Nachbar) höchstens `SERIES_GAP` beträgt; die erste größere Lücke beendet die Seite. Fotos des
   Entwurfs überbrücken keine Lücke — sie sind nicht in der Reihe.
2. **Das Fenster ist immer zusammenhängend**, damit `offset` und `reference_index` die Marke
   unverändert tragen. Es wächst vom Bezugsbild aus um jeweils den Nachbarn, dessen `taken_at`
   dem Bezugsbild näher liegt (Gleichstand: der frühere):
   - Serie mit `BAND_MIN ≤ b − a ≤ BAND_MAX_SERIES`: genau die Serie.
   - Längere Serie: innerhalb von `[a, b)` bis `BAND_MAX_SERIES`.
   - Kürzere Serie: über `[a, b)` hinaus im ganzen Event bis `BAND_MIN` (oder bis alles drin ist).
3. **Neues Antwortfeld `series_rest: int`** — die Zahl der Serienbilder außerhalb des Fensters,
   sonst `0`; ohne `series` immer `0`. Wie `total` aus derselben Kandidatenabfrage, ohne eigene
   Zähl- oder Positionsabfrage.
4. **Die Konstanten leben an einer Stelle**, `selection.py`: `SERIES_GAP = timedelta(minutes=2)`,
   `BAND_MIN = 4`, `BAND_MAX_SERIES = 12`. Das Frontend kennt keine davon; seine Platzhalterzahl ist
   eine Darstellungsgröße. `BAND_MAX_SERIES` bleibt unter dem `limit`-Deckel (200) und deckelt die
   Hydratation des Bandes.

## Konsequenzen

- Das Frontend schneidet, zählt und rechnet keine Zeit; eine clientseitige Serienbildung bräuchte
  die volle Reihe samt `taken_at` und wäre eine zweite Wahrheit neben dem Server.
- Die Schwelle ist nicht einstellbar; eine Änderung ist eine Codeänderung an einer Konstante.
