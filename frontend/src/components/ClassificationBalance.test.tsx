import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CloudPhaseSummaryOut, CriterionScoringRunSummary } from '../api/types'
import { ClassificationBalance } from './ClassificationBalance'

/**
 * specs/features/0348-klassifizierungs-transparenz.md, Abschnitt "Nach dem Lauf: Bilanz des
 * Durchlaufs". Komponententest ohne Provider und ohne Router.
 */

function cloudPhase(overrides: Partial<CloudPhaseSummaryOut> = {}): CloudPhaseSummaryOut {
  return {
    purpose: 'remote_category',
    photos_total: 8,
    photos_processed: 8,
    failed_calls: 1,
    responses_used: 7,
    input_tokens: 21_400,
    output_tokens: 1_820,
    cost_usd: 0.9,
    model: 'claude-haiku-4-5',
    provider: 'anthropic',
    ...overrides,
  }
}

const LANDMARK_PHASE = cloudPhase({
  purpose: 'landmark',
  photos_total: 4,
  photos_processed: 4,
  failed_calls: 0,
  responses_used: 4,
  input_tokens: 6_200,
  output_tokens: 540,
  cost_usd: 0.33,
})

function run(overrides: Partial<CriterionScoringRunSummary> = {}): CriterionScoringRunSummary {
  return {
    status: 'success',
    started_at: '2026-09-09T10:00:00Z',
    finished_at: '2026-09-09T10:20:00Z',
    photos_total: 20,
    photos_processed: 20,
    error_message: null,
    phase: null,
    cloud_requested: true,
    cloud_error_message: null,
    cloud_phases: [cloudPhase(), LANDMARK_PHASE],
    estimated_cost_usd: 2.5,
    cloud_cost_total_usd: 1.23,
    ...overrides,
  }
}

function block(): HTMLElement {
  return screen.getByTestId('classification-balance')
}

describe('ClassificationBalance (A): Cloud-Teilschritte vorhanden', () => {
  it('nennt je Teilschritt gesendete Fotos, verwertete Antworten und Fehlschläge', () => {
    render(<ClassificationBalance run={run()} />)

    const remote = screen.getByTestId('classification-balance-phase-remote_category')
    expect(remote).toHaveTextContent('8 Fotos gesendet')
    expect(remote).toHaveTextContent('7 Antworten verwertet')
    expect(remote).toHaveTextContent(/1 fehlgeschlagen/i)
  })

  it('nennt tatsächliche Kosten und Modell je Teilschritt', () => {
    render(<ClassificationBalance run={run()} />)

    const remote = screen.getByTestId('classification-balance-phase-remote_category')
    expect(remote).toHaveTextContent('0,90 USD')
    expect(remote).toHaveTextContent('claude-haiku-4-5')
  })

  it('nennt den abgerechneten Tokenverbrauch als Grundlage des Betrags', () => {
    render(<ClassificationBalance run={run()} />)

    const remote = screen.getByTestId('classification-balance-phase-remote_category')
    expect(remote).toHaveTextContent('21.400')
    expect(remote).toHaveTextContent('1.820')
  })

  it('nennt den Preis je Bild NICHT — er ist die Grundlage der Schätzung, nicht der Abrechnung', () => {
    render(<ClassificationBalance run={run()} />)

    expect(block().textContent).not.toMatch(/je bild|pro bild/i)
  })

  it('zeigt die Gesamtkosten und ordnet sie gegen die Schätzung ein', () => {
    render(<ClassificationBalance run={run()} />)

    expect(block()).toHaveTextContent('1,23 USD')
    expect(block()).toHaveTextContent(/vor dem start geschätzt/i)
    expect(block()).toHaveTextContent('2,50 USD')
  })

  it('erfindet ohne eingefrorene Schätzung keine Vergleichszeile', () => {
    render(<ClassificationBalance run={run({ estimated_cost_usd: null })} />)

    expect(block().textContent).not.toMatch(/vor dem start geschätzt/i)
  })

  it('zeigt die Bilanz auch für einen fehlgeschlagenen Lauf — das Geld war ausgegeben', () => {
    render(<ClassificationBalance run={run({ status: 'failed', error_message: 'Abbruch' })} />)

    expect(block()).toHaveTextContent('1,23 USD')
  })

  it('führt genau eine Kopfzeile und keine Historie', () => {
    render(<ClassificationBalance run={run()} />)

    expect(screen.getAllByRole('heading')).toHaveLength(1)
    expect(screen.getAllByTestId(/classification-balance-phase-/)).toHaveLength(2)
  })
})

describe('ClassificationBalance (A): kein hinterlegter Preis', () => {
  const unpriced = run({
    cloud_phases: [cloudPhase({ cost_usd: null, model: 'ein-nie-bepreistes-modell' })],
    cloud_cost_total_usd: null,
  })

  it('sagt "kein Preis hinterlegt" statt eines Betrags und "unvollständig" statt einer Summe', () => {
    render(<ClassificationBalance run={unpriced} />)

    expect(block()).toHaveTextContent(/kein preis hinterlegt/i)
    expect(block()).toHaveTextContent(/unvollständig/i)
  })

  it('zeigt nirgends einen stillen Nullbetrag', () => {
    render(<ClassificationBalance run={unpriced} />)

    // Ein stilles "0,00 USD" wäre die gefährlichste aller Anzeigen - es tarnte einen
    // kostenpflichtigen Lauf als kostenlos.
    expect(block().textContent).not.toMatch(/0,00 USD/)
  })
})

describe('ClassificationBalance (B): ohne Cloud-Nutzung', () => {
  const localRun = run({ cloud_requested: false, cloud_phases: [], cloud_cost_total_usd: null })

  it('erklärt den Durchlauf in einem Satz', () => {
    render(<ClassificationBalance run={localRun} />)

    expect(block()).toHaveTextContent(/ohne cloud-anreicherung durchgeführt/i)
    expect(block()).toHaveTextContent(/keine fotos an einen anbieter gesendet/i)
  })

  it('zeigt weder Nullwerte noch leere Felder noch Fehler-Styling', () => {
    render(<ClassificationBalance run={localRun} />)

    expect(block().textContent).not.toMatch(/USD/)
    expect(screen.queryByTestId(/classification-balance-phase-/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('ClassificationBalance (C): Cloud angefragt, keine Bilanz erfasst', () => {
  const withoutBalance = run({
    cloud_requested: true,
    cloud_phases: [],
    cloud_cost_total_usd: null,
    estimated_cost_usd: null,
  })

  it('sagt das ehrlich, statt Zahlen zu erfinden', () => {
    render(<ClassificationBalance run={withoutBalance} />)

    expect(block()).toHaveTextContent(/keine cloud-bilanz erfasst/i)
    expect(block().textContent).not.toMatch(/USD/)
  })

  it('verwechselt den Fall nicht mit "ohne Cloud-Nutzung"', () => {
    render(<ClassificationBalance run={withoutBalance} />)

    expect(block().textContent).not.toMatch(/ohne cloud-anreicherung durchgeführt/i)
  })
})
