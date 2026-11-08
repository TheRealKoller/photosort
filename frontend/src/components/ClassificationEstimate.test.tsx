import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ClassificationEstimateOut } from '../api/types'
import { ClassificationEstimate } from './ClassificationEstimate'

/**
 * Spec 0383: die Vorschau zeigt JEDEN nicht-`null` Anteil als Zeile mit Tätigkeit, Menge, Betrag
 * und Grundlage. `null` ist „findet nicht statt" - als Satz, nie als Zeile mit `0`. Der frühere
 * Satz „Beide Cloud-Anteile werden mit demselben Preis je Bild gerechnet" ist entfallen; er wäre
 * falsch, sobald die Tätigkeiten verschiedene Modelle tragen.
 */

function estimate(overrides: Partial<ClassificationEstimateOut> = {}): ClassificationEstimateOut {
  return {
    mode: 'project',
    candidate_count: 40,
    categorization: {
      kind: 'cloud',
      provider: 'mistral',
      model: 'ministral-3b-2512',
      price_per_image_usd: 0.000305,
      candidate_count: 30,
      estimated_cost_usd: 0.9,
    },
    landmark: {
      kind: 'cloud',
      provider: 'anthropic',
      model: 'claude-haiku-4-5',
      price_per_image_usd: 0.0052,
      candidate_count: 10,
      estimated_cost_usd: 0.33,
    },
    estimated_cost_usd: 1.23,
    ...overrides,
  }
}

function block(): HTMLElement {
  return screen.getByTestId('classification-estimate')
}

describe('ClassificationEstimate: je Anteil eine Zeile', () => {
  it('weist beide Cloud-Anteile mit Tätigkeit, Fotoanzahl und Betrag aus', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(screen.getByText('Kategorisierung')).toBeInTheDocument()
    expect(screen.getByText('Sehenswürdigkeits-Erkennung')).toBeInTheDocument()
    expect(block()).toHaveTextContent('30 Fotos')
    expect(block()).toHaveTextContent('10 Fotos')
    expect(block()).toHaveTextContent('0,90 USD')
    expect(block()).toHaveTextContent('0,33 USD')
  })

  it('nennt die Gesamtsumme in der Formatierung der Bilanz', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(screen.getByText('Gesamtsumme')).toBeInTheDocument()
    expect(block()).toHaveTextContent('1,23 USD')
  })

  it('nennt je Anteil Anbieter, Modell und Preis je Bild als Grundlage', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(block()).toHaveTextContent(/Mistral, ministral-3b-2512/)
    expect(block()).toHaveTextContent(/Anthropic, claude-haiku-4-5/)
    expect(block()).toHaveTextContent('0,0052 USD je Bild')
  })

  it('verwendet nirgends die alte Dollar-Darstellung', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(block()).not.toHaveTextContent('$')
  })
})

describe('ClassificationEstimate: der Eye-Anteil', () => {
  it('nennt Eye kostenfrei und die Grundlage "auf diesem Server"', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({
          mode: 'project',
          categorization: {
            kind: 'eye',
            provider: null,
            model: null,
            price_per_image_usd: 0,
            candidate_count: 12,
            estimated_cost_usd: 0,
          },
          landmark: null,
          candidate_count: 12,
          estimated_cost_usd: 0,
        })}
      />,
    )

    expect(block()).toHaveTextContent('kostenfrei')
    expect(block()).toHaveTextContent('Eye, auf diesem Server')
    expect(block()).not.toHaveTextContent('0,00 USD')
  })
})

describe('ClassificationEstimate: was nicht stattfindet', () => {
  it('sagt beim Fehlen des Landmark-Anteils, dass er nicht stattfindet', () => {
    render(<ClassificationEstimate estimate={estimate({ landmark: null })} />)

    expect(screen.queryByTestId('classification-estimate-part-landmark')).not.toBeInTheDocument()
    expect(block()).toHaveTextContent(
      'Die Sehenswürdigkeits-Erkennung findet in diesem Durchlauf nicht statt.',
    )
  })

  it('sagt beim lokalen Weg EINE Zeile statt einer Tabelle aus Nullen', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({
          mode: 'local',
          categorization: null,
          landmark: null,
          candidate_count: 0,
          estimated_cost_usd: 0,
        })}
      />,
    )

    expect(block()).toHaveTextContent('Dieser Durchlauf ist kostenfrei.')
    expect(
      screen.queryByTestId('classification-estimate-part-categorization'),
    ).not.toBeInTheDocument()
  })

  it('behauptet bei einem unbekannten Preis kein "kostenfrei"', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({
          categorization: {
            kind: 'cloud',
            provider: 'mistral',
            model: 'ministral-3b-2512',
            price_per_image_usd: null,
            candidate_count: 30,
            estimated_cost_usd: null,
          },
          landmark: null,
          estimated_cost_usd: null,
        })}
      />,
    )

    expect(screen.getByTestId('classification-estimate-part-categorization')).toHaveTextContent(
      'kein Preis hinterlegt',
    )
    expect(block()).toHaveTextContent('Preis unbekannt')
  })
})

describe('ClassificationEstimate: die Menge kann unbekannt sein', () => {
  /** Vor dem ersten erfolgreichen Durchlauf gibt es keine gespeicherten Kriterien-Werte - die API
   * liefert dann `candidate_count: null` und `estimated_cost_usd: null`. Die Zeile darf daraus
   * weder "0 Fotos" noch "kostenfrei" machen. */
  const unknownLandmark = {
    kind: 'cloud' as const,
    provider: 'anthropic',
    model: 'claude-haiku-4-5',
    price_per_image_usd: 0.0052,
    candidate_count: null,
    estimated_cost_usd: null,
  }

  it('laesst die Mengenangabe weg statt " Fotos" zu schreiben', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({ landmark: unknownLandmark, estimated_cost_usd: 0.9 })}
      />,
    )

    const zeile = screen.getByTestId('classification-estimate-part-landmark')
    expect(zeile).not.toHaveTextContent('Fotos')
    expect(zeile).not.toHaveTextContent('null')
  })

  it('nennt den Grund und behauptet trotzdem Kosten', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({ landmark: unknownLandmark, estimated_cost_usd: 0.9 })}
      />,
    )

    const zeile = screen.getByTestId('classification-estimate-part-landmark')
    expect(zeile).toHaveTextContent('Menge noch unbekannt')
    expect(zeile).toHaveTextContent('verursacht trotzdem Kosten')
    // Der bekannte Preis des Modells bleibt sichtbar - unbekannt ist die Menge, nicht der Preis.
    expect(zeile).toHaveTextContent('Anthropic, claude-haiku-4-5 · 0,0052 USD je Bild')
  })

  it('beschriftet die Summe als Untergrenze und sagt das darunter', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({ landmark: unknownLandmark, estimated_cost_usd: 0.9 })}
      />,
    )

    expect(screen.getByText('Mindestens')).toBeInTheDocument()
    expect(screen.queryByText('Gesamtsumme')).not.toBeInTheDocument()
    expect(block()).toHaveTextContent(
      'Ein Anteil ist noch unbekannt — der tatsächliche Betrag liegt höher.',
    )
    expect(block()).toHaveTextContent('0,90 USD')
  })

  it('behauptet "bereits klassifiziert" nur, wenn alles bekannt und nichts offen ist', () => {
    const { unmount } = render(
      <ClassificationEstimate
        estimate={estimate({
          categorization: {
            kind: 'cloud',
            provider: 'mistral',
            model: 'ministral-3b-2512',
            price_per_image_usd: 0.000305,
            candidate_count: 0,
            estimated_cost_usd: 0,
          },
          landmark: unknownLandmark,
          candidate_count: 0,
          estimated_cost_usd: null,
        })}
      />,
    )

    expect(block()).not.toHaveTextContent('Alle Fotos bereits klassifiziert')
    expect(screen.getByText('Mindestens')).toBeInTheDocument()

    unmount()

    render(
      <ClassificationEstimate
        estimate={estimate({
          categorization: {
            kind: 'cloud',
            provider: 'mistral',
            model: 'ministral-3b-2512',
            price_per_image_usd: 0.000305,
            candidate_count: 0,
            estimated_cost_usd: 0,
          },
          landmark: { ...unknownLandmark, candidate_count: 0, estimated_cost_usd: 0 },
          candidate_count: 0,
          estimated_cost_usd: 0,
        })}
      />,
    )

    expect(block()).toHaveTextContent(
      'Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten.',
    )
  })
})
