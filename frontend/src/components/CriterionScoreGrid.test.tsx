import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CriterionScoreOut } from '../api/types'
import { CriterionScoreGrid } from './CriterionScoreGrid'

function score(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    has_presence_threshold: false,
    ...overrides,
  }
}

const QUALITY = score({ criterion_key: 'sharpness', display_name: 'Schärfe', value: 0.8 })
const CONTENT = score({
  criterion_key: 'content_people',
  display_name: 'Menschen erkannt',
  value: 0.6,
  has_presence_threshold: true,
})

describe('CriterionScoreGrid: der Regelfall', () => {
  it('zeigt beide Kopfzeilen und jeden Wert unter der richtigen', () => {
    render(<CriterionScoreGrid criterionScores={[QUALITY, CONTENT]} />)

    const quality = screen.getByRole('group', { name: 'Qualität — Einzelwerte' })
    const content = screen.getByRole('group', { name: 'Bildinhalt — Einzelwerte' })

    expect(within(quality).getByText('Schärfe')).toBeInTheDocument()
    expect(within(quality).getByText('80%')).toBeInTheDocument()
    expect(within(content).getByText('Menschen erkannt')).toBeInTheDocument()
    expect(within(content).getByText('60%')).toBeInTheDocument()
  })

  /* Die Aufteilung folgt der geteilten Funktion, nie einer hier gepflegten Schlüsselliste. */
  it('ordnet einen Wert ohne Präsenz-Schwelle der Bildqualität zu', () => {
    render(<CriterionScoreGrid criterionScores={[QUALITY]} />)

    const quality = screen.getByRole('group', { name: 'Qualität — Einzelwerte' })
    expect(within(quality).getByText('Schärfe')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Bildinhalt — Einzelwerte' })).toBeNull()
  })

  /* KEIN RANG (AK5): Er ist keiner der fünfzehn Einzelwerte, sondern Teil des Urteils und steht
     allein in `PhotoVerdict`. Die Zusage steht als ABWESENHEIT hier, nicht nur als Anwesenheit
     dort: Zwei Komponenten, die dieselbe Angabe rendern können, laufen früher oder später
     auseinander - und der Nutzer läse denselben Rang zweimal untereinander. */
  it('zeigt keinen Rang, auch nicht neben Bildinhalt-Werten', () => {
    render(<CriterionScoreGrid criterionScores={[QUALITY, CONTENT]} />)

    expect(screen.queryByText(/^Rang/)).toBeNull()
    expect(
      within(screen.getByRole('group', { name: 'Bildinhalt — Einzelwerte' })).queryByText(/^Rang/),
    ).toBeNull()
  })

  /* AK8/Teststrategie: KEINE Bedienhandlung führt zu einer Angabe - das Raster trägt weder
     Aufklappbares noch einen Auslöser. */
  it('trägt kein aufklappbares Element und keinen Auslöser', () => {
    const { container } = render(<CriterionScoreGrid criterionScores={[QUALITY, CONTENT]} />)

    expect(container.querySelector('details')).toBeNull()
    expect(container.querySelector('summary')).toBeNull()
    expect(container.querySelector('[aria-expanded]')).toBeNull()
    expect(container.querySelector('[aria-haspopup]')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  /* S3: Die Zeilen werden über ihren Registry-Schlüssel geschlüsselt. Sichtbar gemacht an zwei
     gleichnamigen Kriterien - beide erscheinen. */
  it('trägt zwei gleichnamige Kriterien nebeneinander', () => {
    render(
      <CriterionScoreGrid
        criterionScores={[
          score({ criterion_key: 'a', display_name: 'Gleich', value: 0.1 }),
          score({ criterion_key: 'b', display_name: 'Gleich', value: 0.9 }),
        ]}
      />,
    )

    expect(screen.getAllByText('Gleich')).toHaveLength(2)
  })
})

describe('CriterionScoreGrid: leer und fehlend', () => {
  /* Kein leerer Bereich: Ein Block ohne Inhalt wird komplett weggelassen - keine Kopfzeile, kein
     leeres `<dl>`. */
  it('lässt einen leeren Block ganz weg', () => {
    render(<CriterionScoreGrid criterionScores={[CONTENT]} />)

    expect(screen.queryByRole('group', { name: 'Qualität — Einzelwerte' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Bildinhalt — Einzelwerte' })).toBeInTheDocument()
  })

  it('rendert bei komplett leerer Eingabe gar nichts', () => {
    const { container } = render(<CriterionScoreGrid criterionScores={[]} />)

    expect(container).toBeEmptyDOMElement()
  })

  /* Der Bildinhalt-Block haengt jetzt AUSSCHLIESSLICH an eigenen Werten - seit der Rang
     entfallen ist, gibt es keine zweite Grundlage mehr, ihn zu zeigen. */
  it('rendert ohne Bildinhalt-Werte keinen Bildinhalt-Block', () => {
    render(<CriterionScoreGrid criterionScores={[QUALITY]} />)

    expect(screen.getByRole('group', { name: 'Qualität — Einzelwerte' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Bildinhalt — Einzelwerte' })).toBeNull()
  })
})
