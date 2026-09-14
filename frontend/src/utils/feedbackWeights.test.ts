import { describe, expect, it } from 'vitest'

import type { FeedbackDiagnosisOut } from '../api/types'
import { formatDelta, formatWeight, weightRows } from './feedbackWeights'

function diagnosis(): FeedbackDiagnosisOut {
  return {
    correction_count: 4,
    motif_errors: [],
    exchanges: [],
    criteria: [
      { criterion_key: 'sharpness', display_name: 'Schärfe', case_count: 3, agreement: 0.5 },
      { criterion_key: 'exposure', display_name: 'Belichtung', case_count: 0, agreement: 0 },
    ],
    weights: {
      current: [
        { criterion_key: 'sharpness', weight: 1 },
        { criterion_key: 'exposure', weight: 1 },
      ],
      proposed: [
        { criterion_key: 'sharpness', weight: 1.15, delta: 0.15 },
        { criterion_key: 'exposure', weight: 1, delta: 0 },
      ],
      based_on_event_id: 12,
      current_set_id: null,
      can_revert: false,
    },
  }
}

describe('formatWeight', () => {
  it('zeigt zwei Nachkommastellen im deutschen Zahlenformat', () => {
    expect(formatWeight(1)).toBe('1,00')
    expect(formatWeight(1.234)).toBe('1,23')
  })
})

describe('formatDelta', () => {
  it('trägt ein Vorzeichen, sobald die ANGEZEIGTE Abweichung nicht null ist', () => {
    expect(formatDelta(0.15)).toBe('+0,15')
    expect(formatDelta(-0.15)).toBe('−0,15')
  })

  it('zeigt die exakte Null ohne Vorzeichen', () => {
    // Ein „+0,00" behauptete eine Bewegung nach oben, die es nicht gibt.
    expect(formatDelta(0)).toBe('0,00')
  })

  it('zeigt auch eine auf null gerundete Abweichung ohne Vorzeichen', () => {
    // Die Regel hängt an der ANGEZEIGTEN Zahl, nicht am Rohwert: „−0,00" wäre ein Vorzeichen zu
    // einer Null, und ein Gleitkommarest von 1e-17 ist keine Abwertung.
    expect(formatDelta(-0.000000001)).toBe('0,00')
    expect(formatDelta(0.0000000001)).toBe('0,00')
  })

  it('rundet erst und setzt das Vorzeichen danach', () => {
    expect(formatDelta(0.004)).toBe('0,00')
    expect(formatDelta(0.006)).toBe('+0,01')
  })
})

describe('weightRows', () => {
  it('verbindet geltendes Gewicht, Vorschlag und Fallzahl je Kriterium', () => {
    // EIN Zeilenobjekt je Kriterium: Die Tabelle stellt drei Listen derselben Antwort
    // nebeneinander, und ein Join im JSX ginge bei jeder Zelle neu über alle drei.
    expect(weightRows(diagnosis())).toEqual([
      {
        criterionKey: 'sharpness',
        displayName: 'Schärfe',
        current: 1,
        proposed: 1.15,
        delta: 0.15,
        caseCount: 3,
      },
      {
        criterionKey: 'exposure',
        displayName: 'Belichtung',
        current: 1,
        proposed: 1,
        delta: 0,
        caseCount: 0,
      },
    ])
  })

  it('behält die Reihenfolge der geltenden Gewichte', () => {
    // Die Serverreihenfolge ist der Startwertsatz und auf jeder Antwort dieselbe. Nach Abweichung
    // sortiert sprängen die Zeilen nach jeder Korrektur, und die Tabelle wäre nicht mehr
    // wiederzuerkennen.
    const payload = diagnosis()
    payload.criteria.reverse()
    payload.weights.proposed.reverse()

    expect(weightRows(payload).map((row) => row.criterionKey)).toEqual(['sharpness', 'exposure'])
  })

  it('lässt ein Kriterium ohne Vorschlag oder ohne Bilanz nicht aus der Tabelle fallen', () => {
    // Beide Listen kommen aus demselben Schlüsselsatz; eine fehlende Zeile wäre ein Serverfehler.
    // Die Tabelle zeigt das Kriterium trotzdem - mit dem geltenden Gewicht und ohne Vorschlag ist
    // sie immer noch eine wahre Aussage, eine verschwundene Zeile wäre keine.
    const payload = diagnosis()
    payload.weights.proposed = []
    payload.criteria = []

    expect(weightRows(payload)).toEqual([
      {
        criterionKey: 'sharpness',
        displayName: 'sharpness',
        current: 1,
        proposed: null,
        delta: null,
        caseCount: 0,
      },
      {
        criterionKey: 'exposure',
        displayName: 'exposure',
        current: 1,
        proposed: null,
        delta: null,
        caseCount: 0,
      },
    ])
  })
})
