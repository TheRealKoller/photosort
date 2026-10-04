# 0131 - Richtwert-Vorbelegung fest 150 statt ein Zehntel der Bilderzahl

**Status:** Accepted
**Datum:** 2026-10-04
**Bezug:** Spec `specs/features/0567-*.md`
**Löst ab (teilweise):** ADR
[`0097`](./0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md) —
ausschließlich die **Höhe der Vorbelegung** in Punkt 1 („ein Zehntel der Bilderzahl, aufgerundet
und mindestens 1, berechnet im Moment der Auswahl") samt der Folgerung, die Vorbelegung wachse mit
dem Bestand mit. Unverändert gelten: `projects.selection_target`, `NULL` heißt „nicht selbst
eingestellt", die Vorbelegung wird nie in die Spalte geschrieben, genau eine Ableitungsstelle
(`selection.py::effective_target`), beide Felder an `ProjectOut`, sowie die Punkte 2-7.

## Kontext

Die mitwachsende Vorbelegung liefert bei großen Beständen einen Vorschlag, den niemand bestellt
hat, und ändert ihn mit jedem Scan. Story 0567 verlangt einen festen Standard von 150 Bildern, der
mit dem Bestand nicht mitwächst, und eine erkennbare Unterscheidung „Standard" gegen „eigene
Angabe".

## Entscheidung

1. **Die Vorbelegung ist die Konstante `DEFAULT_TARGET = 150`** in `selection.py`; sie ersetzt
   `DEFAULT_TARGET_DIVISOR`. `effective_target(configured)` hängt nicht mehr von der Bilderzahl ab
   und verliert den Parameter `photo_count`; jede Aufrufstelle zieht mit.
2. **`NULL` bleibt der Ausdruck „Standard".** Keine Migration, kein Backfill: Wer heute nichts
   eingestellt hat, hat danach den Standard 150, wer etwas eingestellt hat, behält es. Eine
   eingeschriebene 150 wäre von einer Nutzereingabe nicht zu unterscheiden — derselbe Grund wie in
   ADR 0097.
3. **Die Umstellung rechnet nichts neu.** `selection_position` ist ein persistiertes
   Lauf-Artefakt (ADR 0097 Punkt 2) und bleibt bis zum nächsten Auslöser (erfolgreicher Lauf,
   Richtwert-Änderung, Versatz-Neuaufbau) stehen. In dieser Übergangszeit nennt
   `effective_selection_target` bei Projekten ohne Angabe bereits 150, während der Vorschlag noch
   nach dem alten Zehntel gebildet ist. Diese Abweichung wird bewusst nicht markiert: Ein
   Merker „nach welchem Richtwert gerechnet" wäre eine neue Spalte für einen einmaligen,
   selbstheilenden Zustand.

## Konsequenzen

- Keine Schemaänderung; die Migration `e7f8a9b0c1d2` bleibt mit ihrem historischen Docstring
  unverändert.
- `event_probe.py` behält `project_photos` als Messgröße der Auswertungsgrenze, der Richtwert
  rechnet darauf aber nicht mehr.
- Tests, die das Zehntel behaupten, werden ersetzt statt angepasst.
