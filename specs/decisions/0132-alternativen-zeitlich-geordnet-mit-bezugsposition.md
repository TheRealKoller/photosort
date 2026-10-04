# 0132 - Alternativen eines Austauschs zeitlich geordnet, Bezugsbild als Position in der Reihe

**Status:** Accepted
**Datum:** 2026-10-04
**Bezug:** Spec [`features/0569-ersatzvorschlaege-zeitlich.md`](../features/0569-ersatzvorschlaege-zeitlich.md)

**Löst ab (teilweise):**

- [`0098`](./0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md), Punkt 5 —
  ausschließlich die Sortierregel des Zweigs **mit** `photo_id` (Motivgruppe, dann Qualität) und
  der Satz „Zeitliche Nähe ist kein Sortierkriterium". Menge, Projekt-/Laufbindung, Seitenweise
  mit `total` als Restmenge und die Ablösung von `curation-candidates` gelten unverändert. Der
  Zweig **ohne** `photo_id` (Hinzufügen-Panel) bleibt nach Qualität geordnet.

## Kontext

Beim Austausch sucht man „das Bild davor oder danach", nicht das beste Bild mit demselben Motiv.
Die Story verlangt eine zeitliche Reihe, in der das zu ersetzende Bild an seiner Stelle sichtbar
ist, und ein Band der zeitlich nächsten Vorschläge. Das Bezugsbild gehört zum Entwurf und ist
deshalb nie in der Antwortmenge — seine Stelle muss trotzdem bestimmt werden.

## Entscheidung

1. **Ein Schlüssel, im Backend.** Bezugsbild und Kandidaten werden über `(Photo.taken_at,
   photo_id)` aufsteigend geordnet — `taken_at` ist die wirksame, um den Kamera-Versatz
   korrigierte Zeit (ADR 0090). Der Schlüssel ist eine Totalordnung und nutzerunabhängig; die
   Frontend-Reihenfolge bleibt die der Antwort.
2. **Die Stelle des Bezugsbildes ist ein Antwortfeld.** `reference_index` = Zahl der Kandidaten
   der vollen Restmenge, die nach demselben Schlüssel vor dem Bezugsbild stehen. Das Frontend
   rechnet keine Zeit nach; es setzt die Markierung an `reference_index − offset` der jeweiligen
   Seite. Eine clientseitige Einordnung über `taken_at` wäre eine zweite Sortierwahrheit.
3. **Das Band ist ein Fenster derselben Reihe, vom Server geschnitten.** Mit `nearest=N` wählt der
   Endpunkt `offset = clamp(reference_index − ⌊N/2⌋, 0, max(0, total − N))` und liefert diesen
   `offset` zurück. Das ergibt gleich viele Bilder davor und danach und füllt an einem Rand von
   der anderen Seite auf. Ein zweiter Abruf (erst Position, dann Fenster) entfällt.
4. **Eigene Antwortform** `DraftAlternativesOut` (`items`, `total`, `offset`, `reference_index`)
   statt Erweiterung von `PhotoListOut` — die Felder gibt es nur an diesem Endpunkt.

## Konsequenzen

- Motivabfrage entfällt für die Ordnung; Motive werden nur noch für die ausgelieferte Seite
  geladen.
- Die beobachtbare Reihenfolge verrät die Zeitposition des Bezugsbildes; es wird weiterhin
  ausschließlich über eine Rangzeile desselben Laufs und Events aufgelöst (unverändert S3).
- „Ohne Aufnahmezeitpunkt" kommt nicht vor: `Photo.taken_at` ist NOT NULL (Rückfall
  `last_modified`). Ein Bild mit Rückfallzeit ordnet sich nach dieser Zeit ein.
