import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { FineLabelOut, RankingOut } from '../api/types'
import { PhotoVerdict } from './PhotoVerdict'

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 2,
    proposed: true,
    partition_size: 5,
    curation_position: null,
    ...overrides,
  }
}

function fineLabel(overrides: Partial<FineLabelOut> = {}): FineLabelOut {
  return {
    canonical_key: 'urlaub',
    display_name: 'Urlaub',
    raw_label: 'Urlaub',
    provider: 'anthropic',
    ...overrides,
  }
}

const PWN_FLAG = '__pwned'

afterEach(() => {
  delete (window as unknown as Record<string, unknown>)[PWN_FLAG]
})

describe('PhotoVerdict: der Regelfall', () => {
  it('zeigt Stufe, Begründung, Rang und Feinlabel ohne jede Bedienhandlung', () => {
    render(
      <PhotoVerdict
        albumSuitability={{ level: 4, reason: 'Alle schauen in die Kamera.' }}
        ranking={ranking()}
        fineLabels={[fineLabel()]}
      />,
    )

    expect(screen.getByText('Stufe 4 von 5')).toBeInTheDocument()
    expect(screen.getByText('Alle schauen in die Kamera.')).toBeInTheDocument()
    /* Der Rang steht wie im Entwurf ohne das vorangestellte Wort - das trägt sein Label. */
    expect(screen.getByText('2 von 5')).toBeInTheDocument()
    expect(
      within(screen.getByRole('list', { name: 'Feinlabels' })).getByText('Urlaub'),
    ).toBeInTheDocument()
  })

  /* Die beiden Labels stehen im Entwurf über ihrem Wert. Sie sind der Grund, warum der Rang ohne
     das Wort „Rang" auskommt und die Begründung ohne einen Vorsatz gelesen werden kann. */
  it('beschriftet Albumtauglichkeit und Rang wie der Entwurf', () => {
    render(
      <PhotoVerdict
        albumSuitability={{ level: 4, reason: 'Alle schauen in die Kamera.' }}
        ranking={ranking()}
        fineLabels={[]}
      />,
    )

    expect(screen.getByText('Albumtauglichkeit')).toBeInTheDocument()
    expect(screen.getByText('Rang im Ereignis')).toBeInTheDocument()
  })

  /* Das Label des Rangs erscheint nur mit dem Rang - sonst beschriftete es nichts. */
  it('lässt das Rang-Label ohne Rangposition weg', () => {
    render(
      <PhotoVerdict
        albumSuitability={{ level: 4, reason: null }}
        ranking={ranking({ rank_position: null })}
        fineLabels={[]}
      />,
    )

    expect(screen.queryByText('Rang im Ereignis')).toBeNull()
  })

  /* AK5: Die Albumtauglichkeits-Zeile trägt einen eigenen Handle, damit der Browser-Prüfsatz ihre
     Schriftgröße messen kann, ohne sie über einen Text zu suchen. */
  it('trägt genau einen Handle an der Albumtauglichkeits-Zeile', () => {
    const { container } = render(
      <PhotoVerdict albumSuitability={{ level: 3, reason: null }} ranking={null} fineLabels={[]} />,
    )

    expect(container.querySelectorAll('[data-album-suitability-level]')).toHaveLength(1)
  })

  /* S4: Die Begründung bleibt als Aussage des MODELLS kenntlich, nicht als Aussage von PhotoSort.
     Bei Verletzung wird eine über Prompt-Injection erzeugte Zeile zur Systemaussage. */
  it('weist die Begründung erkennbar als Modellaussage aus', () => {
    render(
      <PhotoVerdict
        albumSuitability={{ level: 4, reason: 'Alle schauen in die Kamera.' }}
        ranking={null}
        fineLabels={[]}
      />,
    )

    const reason = screen.getByText('Alle schauen in die Kamera.')
    const carrier = reason.closest('[data-album-suitability-reason]')
    expect(carrier).not.toBeNull()
    /* Die Zuschreibung steht als SICHTBARER Textknoten IM SELBEN Absatz wie die Begründung -
       damit liest assistive Technik sie ohnehin mit, und Sehende sehen sie. Geprüft wird beides
       zusammen: dass sie da ist UND dass sie im Träger der Begründung steht. Stünde sie daneben,
       ließe sich die Begründung ohne Zuschreibung vorlesen. */
    expect(within(carrier as HTMLElement).getByText(/Begründung des Modells/i)).toBeInTheDocument()
    expect(carrier).toHaveTextContent(/Begründung des Modells.*Alle schauen in die Kamera\./)
  })

  /* S4: ungekürzt. Kappung findet an der Quelle statt, nie hier. */
  it('zeigt eine sehr lange Begründung ungekürzt', () => {
    const lang = 'Sehr ausführlich. '.repeat(40).trim()

    render(
      <PhotoVerdict albumSuitability={{ level: 2, reason: lang }} ranking={null} fineLabels={[]} />,
    )

    expect(screen.getByText(lang)).toBeInTheDocument()
  })

  it('trägt weder aufklappbares Element noch Auslöser', () => {
    const { container } = render(
      <PhotoVerdict
        albumSuitability={{ level: 4, reason: 'Gut.' }}
        ranking={ranking()}
        fineLabels={[fineLabel()]}
      />,
    )

    expect(container.querySelector('details')).toBeNull()
    expect(container.querySelector('summary')).toBeNull()
    expect(container.querySelector('[aria-expanded]')).toBeNull()
    expect(container.querySelector('[aria-haspopup]')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('PhotoVerdict: leer und fehlend', () => {
  /* `null` heißt „noch nicht bewertet" - dann trägt die Zeile den Satz statt einer Stufe, und es
     erscheint KEINE Begründungszeile. */
  it('trägt ohne Modellurteil den Satz statt einer Stufe', () => {
    const { container } = render(
      <PhotoVerdict albumSuitability={null} ranking={null} fineLabels={[]} />,
    )

    expect(screen.getByText('Noch nicht bewertet')).toBeInTheDocument()
    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('lässt die Begründungszeile ohne Begründung ersatzlos weg', () => {
    const { container } = render(
      <PhotoVerdict albumSuitability={{ level: 3, reason: null }} ranking={null} fineLabels={[]} />,
    )

    expect(screen.getByText('Stufe 3 von 5')).toBeInTheDocument()
    expect(container.querySelectorAll('[data-album-suitability-reason]')).toHaveLength(0)
  })

  it('lässt die Rangzeile ohne Rangposition weg', () => {
    render(
      <PhotoVerdict
        albumSuitability={null}
        ranking={ranking({ rank_position: null })}
        fineLabels={[]}
      />,
    )

    expect(screen.queryByText('2 von 5')).toBeNull()
  })

  it('rendert ohne Feinlabels keinen Platzhalter', () => {
    render(<PhotoVerdict albumSuitability={null} ranking={null} fineLabels={[]} />)

    expect(screen.queryByRole('list', { name: 'Feinlabels' })).toBeNull()
  })
})

describe('PhotoVerdict: Sicherheit (S1/S4/S5)', () => {
  /* S5 — DIESER TEST WANDERT MIT DER RENDERSTELLE. `album_suitability.reason` stammt aus einem
     Bild, das selbst Text enthalten kann; das Session-Token liegt in `localStorage`. Ein in
     `CriterionDetailsList.test.tsx` verbliebener Test bliebe grün, obwohl DIESE Komponente den
     Text rendert. */
  it('rendert eine feindlich belegte Begründung als reinen Textknoten', () => {
    const payload = '<img src=x onerror="window.__pwned = true">'

    render(
      <PhotoVerdict
        albumSuitability={{ level: 1, reason: payload }}
        ranking={null}
        fineLabels={[]}
      />,
    )

    expect(screen.getByText(payload)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>)[PWN_FLAG]).toBeUndefined()
  })

  it('macht aus einer javascript:-Begründung weder Link noch Bild', () => {
    const payload = 'javascript:alert(1)'

    const { container } = render(
      <PhotoVerdict
        albumSuitability={{ level: 1, reason: payload }}
        ranking={null}
        fineLabels={[]}
      />,
    )

    expect(screen.getByText(payload)).toBeInTheDocument()
    expect(container.querySelector('a')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })

  it('rendert einen feindlich belegten Feinlabel-Namen als reinen Textknoten', () => {
    const payload = '<img src=x onerror="window.__pwned = true">'

    render(
      <PhotoVerdict
        albumSuitability={null}
        ranking={null}
        fineLabels={[fineLabel({ display_name: payload })]}
      />,
    )

    expect(screen.getByText(payload)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>)[PWN_FLAG]).toBeUndefined()
  })

  /* Kein Fremdtext tritt als Attribut aus - weder in `style`, `href`, `src` noch in einem
     `url()`-Kontext. */
  it('lässt keinen Fremdtext in ein Attribut austreten', () => {
    const payload = '"><script>window.__pwned = true</script>'

    const { container } = render(
      <PhotoVerdict
        albumSuitability={{ level: 2, reason: payload }}
        ranking={null}
        fineLabels={[fineLabel({ display_name: payload, raw_label: payload })]}
      />,
    )

    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('[style]')).toBeNull()
    expect((window as unknown as Record<string, unknown>)[PWN_FLAG]).toBeUndefined()
  })
})
