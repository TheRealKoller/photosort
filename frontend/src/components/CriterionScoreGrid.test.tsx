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

    const quality = screen.getByRole('group', { name: 'Bildqualität' })
    const content = screen.getByRole('group', { name: 'Bildinhalt' })

    expect(within(quality).getByText('Schärfe')).toBeInTheDocument()
    expect(within(quality).getByText('80%')).toBeInTheDocument()
    expect(within(content).getByText('Menschen erkannt')).toBeInTheDocument()
    expect(within(content).getByText('60%')).toBeInTheDocument()
  })

  /* Die Aufteilung folgt der geteilten Funktion, nie einer hier gepflegten Schlüsselliste. */
  it('ordnet einen Wert ohne Präsenz-Schwelle der Bildqualität zu', () => {
    render(<CriterionScoreGrid criterionScores={[QUALITY]} />)

    const quality = screen.getByRole('group', { name: 'Bildqualität' })
    expect(within(quality).getByText('Schärfe')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Bildinhalt' })).toBeNull()
  })

  /* Der Rang gehört fachlich zum Bildinhalt und erscheint auch ohne ein einziges
     Inhalts-Kriterium, sobald eine Rangzeile MIT Rang vorliegt. */
  it('zeigt den Rang im Bildinhalt-Block', () => {
    render(
      <CriterionScoreGrid
        criterionScores={[QUALITY]}
        ranking={{
          event_id: 1,
          rank_score: 0.8,
          rank_position: 2,
          proposed: true,
          partition_size: 5,
          curation_position: null,
        }}
      />,
    )

    const content = screen.getByRole('group', { name: 'Bildinhalt' })
    expect(within(content).getByText('Rang')).toBeInTheDocument()
    expect(within(content).getByText('Rang 2 von 5')).toBeInTheDocument()
  })

  /* Auf `!== null` geprüft, nie auf Falsyness: "Rang — von 12" wäre eine Rangaussage über ein
     Foto ohne Rang. */
  it('lässt die Rangzeile ohne Rangposition weg', () => {
    render(
      <CriterionScoreGrid
        criterionScores={[CONTENT]}
        ranking={{
          event_id: 1,
          rank_score: 0.8,
          rank_position: null,
          proposed: false,
          partition_size: 5,
          curation_position: null,
        }}
      />,
    )

    expect(screen.queryByText('Rang')).toBeNull()
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

    expect(screen.queryByRole('group', { name: 'Bildqualität' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Bildinhalt' })).toBeInTheDocument()
  })

  it('rendert bei komplett leerer Eingabe gar nichts', () => {
    const { container } = render(<CriterionScoreGrid criterionScores={[]} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('rendert ohne Kriterien, aber mit Rang, nur den Bildinhalt-Block', () => {
    render(
      <CriterionScoreGrid
        criterionScores={[]}
        ranking={{
          event_id: 1,
          rank_score: 0.8,
          rank_position: 3,
          proposed: true,
          partition_size: 9,
          curation_position: null,
        }}
      />,
    )

    expect(screen.queryByRole('group', { name: 'Bildqualität' })).toBeNull()
    expect(
      within(screen.getByRole('group', { name: 'Bildinhalt' })).getByText('Rang 3 von 9'),
    ).toBeInTheDocument()
  })

  it('behandelt ein fehlendes Ranking wie keines', () => {
    render(<CriterionScoreGrid criterionScores={[QUALITY]} />)

    expect(screen.queryByText('Rang')).toBeNull()
  })
})
