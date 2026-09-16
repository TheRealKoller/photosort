import type { MotifKey } from '../api/types'
import type { IconName } from '../components/ui/icon'

/**
 * Motivschluessel -> Symbolname des Board-Satzes (ADR 0113 Punkt 3).
 *
 * Die Zuordnung lebt im FRONTEND, nicht als Feld an `MotifOut`: Ein Symbolname ist eine
 * Eigenschaft des ausgelieferten Symbolsatzes, dessen Bestand das Backend nicht kennt. Die Zusage
 * "kein Motivschluessel wird im Frontend in Text uebersetzt" bleibt unberuehrt - Anzeigename,
 * Definition und Abgrenzung kommen weiterhin ausschliesslich vom Server.
 *
 * ALS `Map`, NICHT ALS OBJEKT-LOOKUP - dieselbe Begruendung wie in `utils/motifLabels.ts`: Ein
 * Schluessel wie `"toString"` traefe in einem Objektliteral `Object.prototype` und lieferte eine
 * Funktion statt eines Symbolnamens.
 */
const ICON_BY_MOTIF = new Map<string, IconName>([
  ['menschen', 'user-round'],
  ['landschaft', 'mountain-snow'],
  ['bauwerk_sehenswuerdigkeit', 'landmark'],
  ['stadt_strasse', 'building-2'],
  ['tiere', 'paw-print'],
  ['essen_trinken', 'utensils'],
  ['aktivitaet', 'footprints'],
  ['detail_stimmung', 'sparkles'],
])

/** Neutrales Ersatzsymbol: Ein Altwert aus der Laufhistorie zerreisst die Reihe nicht (AK5). */
const FALLBACK_ICON: IconName = 'tag'

export function motifIconName(motifKey: MotifKey): IconName {
  return ICON_BY_MOTIF.get(motifKey) ?? FALLBACK_ICON
}
