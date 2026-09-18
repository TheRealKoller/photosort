import type { CriterionScoreOut } from '../api/types'

/**
 * Teilt die Kriterienwerte eines Fotos in Qualität (ohne Präsenz-Schwelle) und Bildinhalt (mit).
 *
 * Die Zuordnung folgt AUSSCHLIESSLICH dem Registry-Flag `has_presence_threshold` aus der
 * API-Antwort; hier wird bewusst KEINE Schlüsselliste gepflegt, sonst liefen Backend-Registry und
 * Frontend beim nächsten neuen Kriterium auseinander.
 *
 * ORDNUNGSERHALTEND (zweimal `filter`, kein Sortieren): Die Reihenfolge innerhalb eines Blocks
 * bleibt die vom Backend gelieferte Registry-Reihenfolge.
 *
 * EINE Quelle für beide Darstellungen — das kompakte Kachel-Popover
 * (`components/CriterionDetailsList.tsx`) und das Nachschlagraster der Detailseite
 * (`components/CriterionScoreGrid.tsx`). Zwei getrennte Aufteilungen schnitten Qualität und
 * Bildinhalt verschieden, und die Abweichung fiele in keinem Komponententest auf. Der strukturelle
 * Wächter `photoDetail.structure.test.ts` bindet den Feldnamen deshalb auf genau zwei
 * Produktivquellen: `api/types.ts` und diese Datei.
 */
export function partitionByPresenceThreshold(criterionScores: CriterionScoreOut[]): {
  quality: CriterionScoreOut[]
  content: CriterionScoreOut[]
} {
  return {
    quality: criterionScores.filter((score) => !score.has_presence_threshold),
    content: criterionScores.filter((score) => score.has_presence_threshold),
  }
}
