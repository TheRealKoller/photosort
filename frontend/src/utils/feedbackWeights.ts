import type { FeedbackDiagnosisOut } from '../api/types'

/**
 * Die Aufbereitung der Gewichts-Vorschau. Reine Funktionen mit eigenen Unit-Tests - der Abschnitt
 * selbst enthält weder Formatierungs- noch Verbindungslogik.
 *
 * Deutsches Zahlenformat wie überall im Produkt (`utils/formatStats.ts`): Dezimalkomma, zwei
 * Nachkommastellen.
 */

const DECIMAL_TWO = new Intl.NumberFormat('de-DE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Die Nachkommastellen, auf die gerundet ANGEZEIGT wird. */
const DISPLAY_FACTOR = 100

/** Ein Gewicht, immer mit zwei Nachkommastellen - auch die glatte 1 steht als „1,00". */
export function formatWeight(weight: number): string {
  return DECIMAL_TWO.format(weight)
}

/**
 * Die Abweichung mit Vorzeichen - `+` oder `−` (Minuszeichen U+2212, nicht der Bindestrich).
 *
 * DAS VORZEICHEN HÄNGT AN DER ANGEZEIGTEN ZAHL, nicht am Rohwert: Gerundet wird zuerst, das
 * Vorzeichen kommt danach. Eine Abweichung von `-1e-17` ist keine Abwertung, und „−0,00" wäre ein
 * Vorzeichen zu einer Null. Eine Abweichung von exakt null steht ohne Vorzeichen da.
 *
 * Das Vorzeichen ist zugleich die Erfüllung von „keine Aussage allein über Farbe": Die Richtung
 * steht im Text.
 */
export function formatDelta(delta: number): string {
  const rounded = Math.round(delta * DISPLAY_FACTOR) / DISPLAY_FACTOR
  if (rounded === 0) {
    return DECIMAL_TWO.format(0)
  }
  return `${rounded > 0 ? '+' : '−'}${DECIMAL_TWO.format(Math.abs(rounded))}`
}

/** Eine Zeile der Vorschautabelle: alles, was ein Kriterium darin zeigt. */
export interface WeightRow {
  criterionKey: string
  displayName: string
  current: number
  /** `null` heißt „der Server hat zu diesem Kriterium keinen Vorschlag geliefert". */
  proposed: number | null
  delta: number | null
  /** Die Zahl der tatsächlich auswertbaren Paare - die ALLEINIGE Belastbarkeitsangabe. */
  caseCount: number
}

/**
 * Verbindet die drei Listen der Antwort je Kriterium zu einer Zeile.
 *
 * GEFÜHRT WIRD VON DEN GELTENDEN GEWICHTEN, und in genau ihrer Reihenfolge: Sie sind der
 * Startwertsatz des Servers und auf jeder Antwort dieselben. Nach Abweichung sortiert sprängen
 * die Zeilen nach jeder Korrektur, und die Tabelle wäre nicht wiederzuerkennen.
 *
 * Fehlt ein Kriterium in einer der beiden anderen Listen, fällt seine Zeile NICHT weg: Das Gewicht
 * gilt trotzdem, und eine verschwundene Zeile behauptete, es gäbe das Kriterium nicht.
 */
export function weightRows(diagnosis: FeedbackDiagnosisOut): WeightRow[] {
  const proposedByKey = new Map(
    diagnosis.weights.proposed.map((entry) => [entry.criterion_key, entry]),
  )
  const agreementByKey = new Map(diagnosis.criteria.map((entry) => [entry.criterion_key, entry]))

  return diagnosis.weights.current.map((entry) => {
    const proposed = proposedByKey.get(entry.criterion_key)
    const agreement = agreementByKey.get(entry.criterion_key)
    return {
      criterionKey: entry.criterion_key,
      displayName: agreement?.display_name ?? entry.criterion_key,
      current: entry.weight,
      proposed: proposed?.weight ?? null,
      delta: proposed?.delta ?? null,
      caseCount: agreement?.case_count ?? 0,
    }
  })
}
