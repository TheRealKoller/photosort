import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ClassificationEstimateOut } from '../api/types'
import { ClassificationEstimate } from './ClassificationEstimate'

/**
 * specs/features/0348-klassifizierungs-transparenz.md, Abschnitt "Vor dem Start: aufgeschlüsselte
 * Schätzung". Komponententest ohne Provider und ohne Router - der Block bekommt die Schätzung als
 * Prop, er lädt sie nicht selbst.
 */

function estimate(overrides: Partial<ClassificationEstimateOut> = {}): ClassificationEstimateOut {
  return {
    candidate_count: 40,
    remote_categories: { candidate_count: 30, estimated_cost_usd: 0.9 },
    landmark: { candidate_count: 10, estimated_cost_usd: 0.33 },
    provider: 'anthropic',
    model: 'claude-haiku-4-5',
    price_per_image_usd: 0.0052,
    estimated_cost_usd: 1.23,
    ...overrides,
  }
}

function block(): HTMLElement {
  return screen.getByTestId('classification-estimate')
}

describe('ClassificationEstimate: die beiden Anteile', () => {
  it('weist beide Cloud-Anteile mit Name, Fotoanzahl und Betrag aus', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(screen.getByText('Kategorie-Vorschläge')).toBeInTheDocument()
    expect(screen.getByText('Sehenswürdigkeits-Erkennung')).toBeInTheDocument()
    expect(block()).toHaveTextContent('30 Fotos')
    expect(block()).toHaveTextContent('10 Fotos')
    expect(block()).toHaveTextContent('0,90 USD')
    expect(block()).toHaveTextContent('0,33 USD')
  })

  it('nennt die Gesamtsumme', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(screen.getByText('Gesamtsumme')).toBeInTheDocument()
    // Genau EIN Testfall nagelt das Format wörtlich fest - dieselbe Darstellung, in der später
    // die Bilanz ihre Ist-Kosten zeigt (sonst wäre der geforderte Vergleich optisch gebrochen).
    expect(block()).toHaveTextContent('1,23 USD')
  })

  it('nennt Anbieter und Modell, auf denen die Schätzung beruht', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(block()).toHaveTextContent(/anthropic/i)
    expect(block()).toHaveTextContent('claude-haiku-4-5')
  })

  it('verwendet nirgends mehr die alte Dollar-Darstellung', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    // Das lokale `$1.23`-Format ist entfallen: Schätzung und Bilanz müssen dieselbe
    // Währungsformatierung tragen, sonst ist "Ist gegen Schätzung einordenbar" optisch gebrochen.
    expect(block().textContent).not.toMatch(/\$/)
  })
})

describe('ClassificationEstimate: der unbekannte Landmark-Anteil', () => {
  const unknownLandmark = estimate({
    candidate_count: 30,
    landmark: { candidate_count: null, estimated_cost_usd: null },
    estimated_cost_usd: 0.9,
  })

  it('sagt ausdrücklich, dass der Anteil trotzdem Kosten verursacht', () => {
    render(<ClassificationEstimate estimate={unknownLandmark} />)

    expect(block()).toHaveTextContent(/menge noch unbekannt/i)
    // DER eigentliche Testfall: ohne diesen zweiten Satz liest sich die Leerstelle wie "fällt
    // nicht an" - genau die Fehlaussage, die die Story behebt.
    expect(block()).toHaveTextContent('Dieser Anteil verursacht trotzdem Kosten.')
  })

  it('zeigt für den unbekannten Anteil weder eine 0 noch einen Betrag', () => {
    render(<ClassificationEstimate estimate={unknownLandmark} />)

    const row = screen.getByTestId('classification-estimate-part-landmark')

    expect(row.textContent).not.toMatch(/\b0\b/)
    expect(row.textContent).not.toMatch(/USD/)
  })
})

describe('ClassificationEstimate: kein hinterlegter Preis', () => {
  const withoutPrice = estimate({
    remote_categories: { candidate_count: 30, estimated_cost_usd: null },
    landmark: { candidate_count: 10, estimated_cost_usd: null },
    price_per_image_usd: null,
    estimated_cost_usd: null,
  })

  it('benennt die Lücke, statt einen Betrag zu erfinden', () => {
    render(<ClassificationEstimate estimate={withoutPrice} />)

    expect(block()).toHaveTextContent(/kein preis hinterlegt/i)
    expect(block().textContent).not.toMatch(/0,00 USD/)
  })

  it('färbt den Fall nicht als Fehler ein', () => {
    render(<ClassificationEstimate estimate={withoutPrice} />)

    // Kein `Alert`: Alert ist im Projekt der Fehler-/Retry-Baustein, hier liegt kein Ladefehler
    // vor, sondern eine ehrliche Wissenslücke.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('behält die Fotoanzahlen sichtbar', () => {
    render(<ClassificationEstimate estimate={withoutPrice} />)

    expect(block()).toHaveTextContent('30 Fotos')
    expect(block()).toHaveTextContent('10 Fotos')
  })
})

describe('ClassificationEstimate: Schätzcharakter', () => {
  it('weist dauerhaft aus, dass es eine Schätzung und keine Abrechnung ist', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(block()).toHaveTextContent(/schätzung, keine abrechnung/i)
  })

  it('benennt die bewusste Grobheit, dass beide Anteile denselben Preis je Bild tragen', () => {
    render(<ClassificationEstimate estimate={estimate()} />)

    expect(block()).toHaveTextContent(/demselben preis je bild/i)
  })

  it('sagt bei leerem Kandidatenbestand, dass nichts mehr zu klassifizieren ist', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({
          candidate_count: 0,
          remote_categories: { candidate_count: 0, estimated_cost_usd: 0 },
          landmark: { candidate_count: 0, estimated_cost_usd: 0 },
          estimated_cost_usd: 0,
        })}
      />
    )

    expect(block()).toHaveTextContent(/alle fotos bereits klassifiziert/i)
  })

  it('behauptet nicht "alles klassifiziert", solange ein Anteil unbekannt ist', () => {
    render(
      <ClassificationEstimate
        estimate={estimate({
          candidate_count: 0,
          remote_categories: { candidate_count: 0, estimated_cost_usd: 0 },
          landmark: { candidate_count: null, estimated_cost_usd: null },
          estimated_cost_usd: 0,
        })}
      />
    )

    expect(block()).not.toHaveTextContent(/alle fotos bereits klassifiziert/i)
    expect(block()).toHaveTextContent(/menge noch unbekannt/i)
  })
})
