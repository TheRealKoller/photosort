import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { FineLabelOut } from '../api/types'
import { FineLabelList } from './FineLabelList'

function fineLabel(overrides: Partial<FineLabelOut> = {}): FineLabelOut {
  return {
    canonical_key: 'urlaub',
    display_name: 'Urlaub',
    raw_label: 'Urlaub',
    provider: 'anthropic',
    ...overrides,
  }
}

/** Das Flag, das ein ausgefuehrtes Skript setzen wuerde - nach jedem Fall zurueckgesetzt, damit
 *  ein Treffer nicht in den naechsten Fall leckt. */
const PWN_FLAG = '__pwned'

afterEach(() => {
  delete (window as unknown as Record<string, unknown>)[PWN_FLAG]
})

describe('FineLabelList: der Regelfall', () => {
  it('zeigt jedes Feinlabel als Chip in einer beschrifteten Liste', () => {
    render(
      <FineLabelList
        fineLabels={[
          fineLabel({ canonical_key: 'urlaub', display_name: 'Urlaub' }),
          fineLabel({ canonical_key: 'strand', display_name: 'Strand' }),
        ]}
      />,
    )

    const list = screen.getByRole('list', { name: 'Feinlabels' })
    expect(within(list).getByText('Urlaub')).toBeInTheDocument()
    expect(within(list).getByText('Strand')).toBeInTheDocument()
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
  })

  /* Ohne Feinlabels wird KEIN Platzhalter gerendert - der Bereich entfaellt ersatzlos. */
  it('rendert ohne Feinlabels gar nichts', () => {
    const { container } = render(<FineLabelList fineLabels={[]} />)

    expect(screen.queryByRole('list', { name: 'Feinlabels' })).toBeNull()
    expect(container).toBeEmptyDOMElement()
  })

  /* S3: Der Schluessel kommt aus `canonical_key`, NIE aus dem Anzeigenamen. Zwei gleichnamige
     Labels sind der Normalfall; ein doppelter Schluessel brächte die Listenabgleichung von React
     durcheinander. Sichtbar gemacht an zwei Chips mit demselben Anzeigenamen: beide erscheinen. */
  it('trägt zwei gleichnamige Labels nebeneinander', () => {
    render(
      <FineLabelList
        fineLabels={[
          fineLabel({ canonical_key: 'strand-a', display_name: 'Strand' }),
          fineLabel({ canonical_key: 'strand-b', display_name: 'Strand' }),
        ]}
      />,
    )

    const list = screen.getByRole('list', { name: 'Feinlabels' })
    expect(within(list).getAllByText('Strand')).toHaveLength(2)
  })
})

describe('FineLabelList: Sicherheit (S1/S5)', () => {
  /* S5 — DIESER TEST WANDERT MIT DER RENDERSTELLE. Ein in `CriterionDetailsList.test.tsx`
     verbliebener Test bliebe grün, obwohl die Komponente den Text nicht mehr rendert; der Schutz
     bestünde dann nur noch nominell. `display_name` ist freier, extern erzeugter LLM-Text, und das
     Session-Token liegt in `localStorage`: ein eingeschleustes Skript liest es unmittelbar aus. */
  it('rendert einen feindlich belegten Anzeigenamen als reinen Textknoten', () => {
    const payload = '<img src=x onerror="window.__pwned = true">'

    render(<FineLabelList fineLabels={[fineLabel({ display_name: payload })]} />)

    expect(screen.getByText(payload)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>)[PWN_FLAG]).toBeUndefined()
  })

  it('macht aus einer javascript:-Nutzlast weder Link noch Bild', () => {
    const payload = 'javascript:alert(1)'

    const { container } = render(
      <FineLabelList fineLabels={[fineLabel({ display_name: payload })]} />,
    )

    expect(screen.getByText(payload)).toBeInTheDocument()
    expect(container.querySelector('a')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })

  /* Der Rohtext darf den Anzeigenamen nicht ueber ein `title`-Attribut umgehen. */
  it('lässt den Rohtext nicht als Attribut austreten', () => {
    const payload = '<img src=x onerror="window.__pwned = true">'

    const { container } = render(
      <FineLabelList fineLabels={[fineLabel({ display_name: 'Urlaub', raw_label: payload })]} />,
    )

    expect(container.innerHTML).not.toContain('onerror')
    expect((window as unknown as Record<string, unknown>)[PWN_FLAG]).toBeUndefined()
  })
})
