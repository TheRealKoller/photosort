import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { DuplicateDecision, PhotoOut } from '../api/types'
import { DuplicatePhotoTile } from './DuplicatePhotoTile'

vi.mock('./PhotoImage', () => ({
  PhotoImage: ({ alt, className }: { alt: string; className?: string }) => (
    <img alt={alt} className={className} />
  ),
}))

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'Reise/serie-01.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    ...overrides,
  }
}

function renderTile(
  overrides: {
    decision?: DuplicateDecision | null
    enlarged?: boolean
    deciding?: boolean
    onToggle?: () => void
    onDecide?: (decision: DuplicateDecision) => void
  } = {},
) {
  const onToggle = overrides.onToggle ?? vi.fn()
  const onDecide = overrides.onDecide ?? vi.fn()
  render(
    <ul>
      <DuplicatePhotoTile
        photo={photo()}
        decision={overrides.decision ?? null}
        enlarged={overrides.enlarged ?? false}
        deciding={overrides.deciding ?? false}
        onToggle={onToggle}
        onDecide={onDecide}
      />
    </ul>,
  )
  return { onToggle, onDecide }
}

function tile(): HTMLElement {
  return screen.getByRole('listitem')
}

/* ------------------------------------------------------------------------------------------
 * AK6 - Zustand ohne Farbwahrnehmung
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - die drei Zustaende', () => {
  const ZUSTAENDE: { decision: DuplicateDecision | null; wert: string }[] = [
    { decision: null, wert: 'undecided' },
    { decision: 'keep', wert: 'keep' },
    { decision: 'discard', wert: 'discard' },
  ]

  it('traegt je Zustand einen eigenen Wert, Text und Symbol - paarweise verschieden', () => {
    // AK6: In Graustufen liegen die Umrissfarben dicht beieinander; die Aussage haengt deshalb an
    // drei unabhaengigen Traegern. Geprueft als PAARWEISE Verschiedenheit ueber alle drei
    // Zustaende hinweg, nicht je Zustand einzeln - drei Faelle mit demselben Symbol bestuenden
    // sonst jeder fuer sich.
    const gesehen = ZUSTAENDE.map(({ decision }) => {
      const { unmount } = render(
        <ul>
          <DuplicatePhotoTile
            photo={photo()}
            decision={decision}
            enlarged={false}
            deciding={false}
            onToggle={vi.fn()}
            onDecide={vi.fn()}
          />
        </ul>,
      )
      const kennzeichen = screen.getByTestId('duplicate-state')
      const ergebnis = {
        wert: screen.getByRole('listitem').dataset.duplicateDecision,
        text: kennzeichen.textContent,
        icon: kennzeichen.querySelector('[data-icon]')?.getAttribute('data-icon'),
      }
      unmount()
      return ergebnis
    })

    expect(gesehen.map((eintrag) => eintrag.wert)).toEqual(['undecided', 'keep', 'discard'])
    for (const schluessel of ['text', 'icon'] as const) {
      const werte = gesehen.map((eintrag) => eintrag[schluessel])
      expect(werte.every((wert) => wert !== undefined && wert !== null && wert !== '')).toBe(true)
      expect(new Set(werte).size).toBe(ZUSTAENDE.length)
    }
  })

  it('daempft die Bildflaeche NUR bei Ausschuss und NUR in der Uebersicht', () => {
    // Die vergroesserte Aufnahme bleibt unverfaelscht, weil sie beurteilt werden soll.
    const { unmount } = render(
      <ul>
        <DuplicatePhotoTile
          photo={photo()}
          decision="discard"
          enlarged={false}
          deciding={false}
          onToggle={vi.fn()}
          onDecide={vi.fn()}
        />
      </ul>,
    )
    expect(screen.getByTestId('duplicate-image').dataset.dimmed).toBe('true')
    unmount()

    render(
      <ul>
        <DuplicatePhotoTile
          photo={photo()}
          decision="discard"
          enlarged
          deciding={false}
          onToggle={vi.fn()}
          onDecide={vi.fn()}
        />
      </ul>,
    )
    expect(screen.getByTestId('duplicate-image').dataset.dimmed).toBe('false')
  })

  it('setzt data-dimmed auf "false" statt es wegzulassen', () => {
    // Ein fehlendes Attribut waere von "nicht gedaempft" nicht zu unterscheiden, und der
    // Pruefstack kann den berechneten Deckkraftwert nicht gegen eine Absicht halten.
    renderTile({ decision: 'keep' })

    expect(screen.getByTestId('duplicate-image').dataset.dimmed).toBe('false')
  })

  it('haelt die Daempfung an der Bildflaeche, nie am Kachelkoerper', () => {
    // ADR 0055 Abweichung 7: Ein `opacity-40` am Koerper drueckte Kennzeichen und Dateinamen
    // wieder unter die Kontrastschwelle.
    renderTile({ decision: 'discard' })

    expect(screen.getByTestId('duplicate-image').className).toContain('opacity-40')
    expect(tile().className).not.toContain('opacity-')
  })

  it('zeigt den Zustandsrahmen auch in der Vergroesserung', () => {
    // AK8: Das vergroesserte Bild wird ungedaempft gezeigt, traegt aber unveraendert seinen
    // Zustand - sonst verloere man beim Beurteilen genau die Angabe, die man gerade setzt.
    renderTile({ decision: 'discard', enlarged: true })

    expect(tile().dataset.duplicateDecision).toBe('discard')
  })
})

/* ------------------------------------------------------------------------------------------
 * AK7 - Vergroessern und Verkleinern
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - vergroessern', () => {
  it('ist ein natives button und nennt die Aktion im zugaenglichen Namen', async () => {
    const { onToggle } = renderTile()
    const knopf = screen.getByRole('button', { name: /vergrößern/i })

    expect(knopf.tagName).toBe('BUTTON')
    expect(knopf.getAttribute('type')).toBe('button')
    await userEvent.click(knopf)

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('nennt in der Vergroesserung die Gegenaktion', () => {
    renderTile({ enlarged: true })

    expect(screen.getByRole('button', { name: /verkleinern/i })).toBeTruthy()
  })

  it('nennt den Dateinamen in JEDEM zugaenglichen Namen der Kachel', () => {
    // Mehrere Kacheln im selben Raster waeren per Tastatur und Screenreader sonst nicht
    // auseinanderzuhalten - "Behalten" allein sagt nicht, welches Bild gemeint ist.
    renderTile()

    const namen = screen
      .getAllByRole('button')
      .map((knopf) => knopf.getAttribute('aria-label') ?? '')

    expect(namen).toHaveLength(3)
    expect(namen.every((name) => name.includes('serie-01.jpg'))).toBe(true)
    expect(new Set(namen).size).toBe(3)
  })

  it('wirkt mit Enter und Leertaste, ohne eigenen Tastatur-Handler', async () => {
    // AK7: Zugesichert ist, dass kein eigenes `onKeyDown` das native Element ersetzt - die
    // Tastaturbedienbarkeit kommt vom `<button>` selbst.
    const { onToggle } = renderTile()
    const knopf = screen.getByRole('button', { name: /vergrößern/i })

    knopf.focus()
    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')

    expect(onToggle).toHaveBeenCalledTimes(2)
  })
})

/* ------------------------------------------------------------------------------------------
 * AK4 - Einzelentscheidung
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - die Wahlzeile', () => {
  it('bietet beide Richtungen und meldet die gedrueckte', async () => {
    const { onDecide } = renderTile()

    await userEvent.click(screen.getByRole('button', { name: /^Behalten:/ }))
    await userEvent.click(screen.getByRole('button', { name: /^Ausschuss:/ }))

    expect(onDecide).toHaveBeenNthCalledWith(1, 'keep')
    expect(onDecide).toHaveBeenNthCalledWith(2, 'discard')
    expect(onDecide).toHaveBeenCalledTimes(2)
  })

  it('weist den geltenden Wert ueber aria-pressed aus', () => {
    renderTile({ decision: 'keep' })

    expect(screen.getByRole('button', { name: /^Behalten:/ }).getAttribute('aria-pressed')).toBe(
      'true',
    )
    expect(screen.getByRole('button', { name: /^Ausschuss:/ }).getAttribute('aria-pressed')).toBe(
      'false',
    )
  })

  it('bietet KEINE Ruecknahme nach "noch nicht entschieden"', () => {
    // AK4/ADR 0104: Der Zustand ist ein Anfangszustand, kein Ziel. Genau zwei Waehlbare, und die
    // Zaehlung ist die Zusage - ein dritter Knopf faellt hier auf.
    renderTile({ decision: 'keep' })

    expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(1)
    expect(screen.getAllByRole('button', { pressed: true })).toHaveLength(1)
  })

  it('sperrt die Wahlzeile waehrend der eigenen laufenden Entscheidung', async () => {
    const { onDecide } = renderTile({ deciding: true })

    await userEvent.click(screen.getByRole('button', { name: /^Behalten:/ }))

    expect(onDecide).not.toHaveBeenCalled()
  })

  it('laesst die Entscheidung auch in der Vergroesserung zu', async () => {
    // AK8: Eine Entscheidung in der Vergroesserung aendert den Zustand, hebt die Vergroesserung
    // nicht auf und blaettert nicht weiter.
    const { onDecide, onToggle } = renderTile({ enlarged: true })

    await userEvent.click(screen.getByRole('button', { name: /^Ausschuss:/ }))

    expect(onDecide).toHaveBeenCalledWith('discard')
    expect(onToggle).not.toHaveBeenCalled()
  })
})
