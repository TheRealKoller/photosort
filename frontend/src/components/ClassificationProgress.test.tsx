import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CloudPhaseSummaryOut, CriterionScoringRunSummary } from '../api/types'
import { ClassificationProgress } from './ClassificationProgress'

/**
 * specs/features/0348-klassifizierungs-transparenz.md, Abschnitt "Während des Laufs: sichtbare
 * Teilschritte mit konkreten Werten". Komponententest ohne Provider und ohne Router.
 *
 * Übernimmt den Block `describe('Teilschritt-Fortschritt')` aus ClassificationSection.test.tsx -
 * dort bleibt nur noch der Wiring-Nachweis.
 */

function cloudPhase(overrides: Partial<CloudPhaseSummaryOut> = {}): CloudPhaseSummaryOut {
  return {
    purpose: 'remote_category',
    photos_total: 8,
    photos_processed: 3,
    failed_calls: 0,
    responses_used: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    model: 'claude-haiku-4-5',
    provider: 'anthropic',
    ...overrides,
  }
}

function run(overrides: Partial<CriterionScoringRunSummary> = {}): CriterionScoringRunSummary {
  return {
    status: 'running',
    started_at: '2026-09-09T10:00:00Z',
    finished_at: null,
    photos_total: 10,
    photos_processed: 4,
    error_message: null,
    phase: 'criteria',
    cloud_requested: true,
    cloud_error_message: null,
    cloud_phases: [cloudPhase()],
    estimated_cost_usd: null,
    cloud_cost_total_usd: null,
    ...overrides,
  }
}

function stepRow(id: string): HTMLElement {
  return screen.getByTestId(`classification-step-${id}`)
}

describe('ClassificationProgress: die Teilschrittliste', () => {
  it('zeigt vier Zeilen in fester Reihenfolge bei angeforderter Cloud-Nutzung', () => {
    render(<ClassificationProgress run={run()} />)

    const items = screen.getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('data-step-id'))).toEqual([
      'remote_categories',
      'criteria',
      'landmark',
      'ranking',
    ])
  })

  it('zeigt ohne Cloud-Nutzung nur die beiden lokalen Teilschritte', () => {
    render(<ClassificationProgress run={run({ cloud_requested: false, cloud_phases: [] })} />)

    const items = screen.getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('data-step-id'))).toEqual(['criteria', 'ranking'])
  })

  it('benennt die Sehenswürdigkeits-Erkennung als eigenen Teilschritt', () => {
    render(<ClassificationProgress run={run()} />)

    expect(screen.getByText('Sehenswürdigkeits-Erkennung')).toBeInTheDocument()
  })

  it('gibt dem Rangfolge-Schritt keinen Fortschrittsbalken und keinen x/y-Wert', () => {
    render(
      <ClassificationProgress
        run={run({
          phase: 'ranking',
          cloud_phases: [cloudPhase(), cloudPhase({ purpose: 'landmark', photos_total: 6 })],
        })}
      />,
    )

    // Drei Balken im Cloud-Lauf: remote_categories, criteria, landmark - nicht ranking.
    expect(screen.queryAllByRole('progressbar')).toHaveLength(3)
    expect(stepRow('ranking').textContent).not.toMatch(/\d+\/\d+/)
  })
})

describe('ClassificationProgress: Zustände als Text', () => {
  it.each([
    ['remote_categories', 'erledigt'],
    ['criteria', 'läuft'],
    ['landmark', 'ausstehend'],
  ])('schreibt den Zustand von "%s" als Text aus (%s)', (id, expected) => {
    render(<ClassificationProgress run={run({ phase: 'criteria' })} />)

    expect(stepRow(id)).toHaveTextContent(expected)
  })

  it('schreibt "übersprungen" aus, wenn ein angeforderter Cloud-Schritt keine Spur hinterließ', () => {
    render(
      <ClassificationProgress run={run({ status: 'success', phase: null, cloud_phases: [] })} />,
    )

    expect(stepRow('landmark')).toHaveTextContent('übersprungen')
  })

  it('trägt den Zustand zusätzlich als data-Attribut, nicht allein über Farbe', () => {
    render(<ClassificationProgress run={run({ phase: 'criteria' })} />)

    expect(stepRow('criteria')).toHaveAttribute('data-step-state', 'running')
    expect(stepRow('landmark')).toHaveAttribute('data-step-state', 'pending')
  })
})

describe('ClassificationProgress: der laufende Cloud-Teilschritt', () => {
  const duringRemote = run({
    phase: 'remote_categories',
    cloud_phases: [cloudPhase({ photos_processed: 12, failed_calls: 2 })],
  })

  it('nennt abgesetzte Aufrufe, Anbieter und Modell', () => {
    render(<ClassificationProgress run={duringRemote} />)

    const row = stepRow('remote_categories')
    expect(row).toHaveTextContent(/aufrufe abgesetzt: 12/i)
    expect(row).toHaveTextContent(/anthropic/i)
    expect(row).toHaveTextContent('claude-haiku-4-5')
  })

  it('macht fehlgeschlagene Einzelaufrufe schon WÄHREND des Laufs sichtbar', () => {
    render(<ClassificationProgress run={duringRemote} />)

    // Eigenes Akzeptanzkriterium: nicht erst nach Abschluss des Laufs.
    expect(duringRemote.status).toBe('running')
    expect(stepRow('remote_categories')).toHaveTextContent(/fehlgeschlagen: 2/i)
  })

  it('zeigt bei unbekanntem Anbieter nur die Modell-ID, ohne Konfigurationshinweis', () => {
    render(
      <ClassificationProgress
        run={run({
          phase: 'remote_categories',
          cloud_phases: [cloudPhase({ model: 'ein-entferntes-modell', provider: null })],
        })}
      />,
    )

    const row = stepRow('remote_categories')
    expect(row).toHaveTextContent('ein-entferntes-modell')
    expect(row.textContent).not.toMatch(/null|undefined/)
    expect(row.textContent).not.toMatch(/anbieter prüfen|LANDMARK_PROVIDER|nicht gesetzt/i)
  })
})

describe('ClassificationProgress: eigene Fortschrittsquellen je Teilschritt', () => {
  it('bewegt beim Nachladen nur die Zeile, deren Zähler sich geändert hat', () => {
    const before = run({
      phase: 'landmark',
      photos_total: 10,
      photos_processed: 10,
      cloud_phases: [cloudPhase({ purpose: 'landmark', photos_total: 6, photos_processed: 1 })],
    })
    const { rerender } = render(<ClassificationProgress run={before} />)
    const criteriaBefore = stepRow('criteria').textContent

    rerender(
      <ClassificationProgress
        run={{
          ...before,
          cloud_phases: [cloudPhase({ purpose: 'landmark', photos_total: 6, photos_processed: 4 })],
        }}
      />,
    )

    expect(stepRow('landmark')).toHaveTextContent('4/6')
    // Die Gegenprobe ist der eigentliche Nachweis: die Quellen sind nicht geteilt.
    expect(stepRow('criteria').textContent).toBe(criteriaBefore)
  })

  it('zeigt einen unbestimmten Balken statt eines ungültigen max=0 direkt nach dem Auslösen', () => {
    render(
      <ClassificationProgress
        run={run({
          cloud_requested: false,
          cloud_phases: [],
          photos_total: 0,
          photos_processed: 0,
        })}
      />,
    )

    const bar = screen.getByRole('progressbar') as HTMLProgressElement
    expect(bar.hasAttribute('value')).toBe(false)
    expect(bar.hasAttribute('max')).toBe(false)
  })

  it('behauptet bei unbekanntem Zähler keine 0, sondern zeigt den unbestimmten Balken', () => {
    // `null` heisst "nicht erfasst". Ein `?? 0` behauptete hier "es ist noch nichts passiert" -
    // eine Aussage, die niemand getroffen hat, und dieselbe Fehlerart wie ein stilles
    // "0,00 USD" beim Betrag.
    render(
      <ClassificationProgress
        run={run({
          cloud_requested: false,
          cloud_phases: [],
          photos_total: 8,
          photos_processed: null as unknown as number,
        })}
      />,
    )

    const bar = screen.getAllByRole('progressbar')[0] as HTMLProgressElement
    expect(bar.hasAttribute('value')).toBe(false)
    expect(stepRow('criteria').textContent).not.toMatch(/0\/8/)
  })

  it('kündigt den Fortschritt höflich an', () => {
    render(<ClassificationProgress run={run()} />)

    expect(screen.getByRole('list')).toHaveAttribute('aria-live', 'polite')
  })
})
