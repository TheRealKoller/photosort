import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { DuplicateDecision, PhotoOut } from '../api/types'
import {
  DUPLICATE_IMMUTABLE_TEXT,
  DUPLICATE_ZUSTAENDE,
  DuplicatePhotoTile,
} from './DuplicatePhotoTile'

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
    persons: [],
    ...overrides,
  }
}

interface TileOverrides {
  effectiveDecision?: DuplicateDecision
  keepPossible?: boolean
  sharpness?: number | null
  exposure?: number | null
  bestSharpness?: boolean
  bestExposure?: boolean
  deciding?: boolean
  onOpen?: () => void
  onDecide?: (decision: DuplicateDecision) => void
}

function tileElement(overrides: TileOverrides = {}) {
  return (
    <DuplicatePhotoTile
      photo={photo()}
      effectiveDecision={overrides.effectiveDecision ?? 'keep'}
      keepPossible={overrides.keepPossible ?? true}
      sharpness={overrides.sharpness === undefined ? 412.7 : overrides.sharpness}
      exposure={overrides.exposure === undefined ? 0.125 : overrides.exposure}
      bestSharpness={overrides.bestSharpness ?? false}
      bestExposure={overrides.bestExposure ?? false}
      deciding={overrides.deciding ?? false}
      onOpen={overrides.onOpen ?? vi.fn()}
      onDecide={overrides.onDecide ?? vi.fn()}
    />
  )
}

function renderTile(overrides: TileOverrides = {}) {
  const onOpen = overrides.onOpen ?? vi.fn()
  const onDecide = overrides.onDecide ?? vi.fn()
  render(<ul>{tileElement({ ...overrides, onOpen, onDecide })}</ul>)
  return { onOpen, onDecide }
}

function tile(): HTMLElement {
  return screen.getByRole('listitem')
}

/** Der Wert eines Messwerts in der Bewertungszeile, gefunden ueber seinen Begriff. */
function metricValue(begriff: string): HTMLElement | null {
  const term = within(tile()).queryByText(begriff, { selector: 'dt' })
  return term?.nextElementSibling instanceof HTMLElement ? term.nextElementSibling : null
}

/* ------------------------------------------------------------------------------------------
 * Zustand ohne Farbwahrnehmung, und es gibt nur zwei
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - die zwei Zustaende', () => {
  const ZUSTAENDE: DuplicateDecision[] = ['keep', 'discard']

  it('traegt je Zustand einen eigenen Wert, Text und Symbol - paarweise verschieden', () => {
    // Die dreifache Codierung ist die Zusage, nicht die Farbe: In Graustufen liegen die
    // Umrissfarben dicht beieinander. Geprueft als PAARWEISE Verschiedenheit ueber beide
    // Zustaende hinweg, nicht je Zustand einzeln.
    const gesehen = ZUSTAENDE.map((effectiveDecision) => {
      const { unmount } = render(<ul>{tileElement({ effectiveDecision })}</ul>)
      const kennzeichen = screen.getByTestId('duplicate-state')
      const ergebnis = {
        wert: screen.getByRole('listitem').dataset.duplicateDecision,
        text: kennzeichen.textContent,
        icon: kennzeichen.querySelector('[data-icon]')?.getAttribute('data-icon'),
      }
      unmount()
      return ergebnis
    })

    expect(gesehen.map((eintrag) => eintrag.wert)).toEqual(['keep', 'discard'])
    for (const schluessel of ['text', 'icon'] as const) {
      const werte = gesehen.map((eintrag) => eintrag[schluessel])
      expect(werte.every((wert) => wert !== undefined && wert !== null && wert !== '')).toBe(true)
      expect(new Set(werte).size).toBe(ZUSTAENDE.length)
    }
  })

  it('kennt keinen Wert ausserhalb von keep/discard', () => {
    // Die Schluesselmenge als GLEICHHEIT: Ein wieder eingefuehrtes "noch offen" faellt hier auf,
    // auch wenn es nirgends gerendert wird.
    expect(Object.keys(DUPLICATE_ZUSTAENDE).sort()).toEqual(['discard', 'keep'])
  })

  it('traegt in keinem Zustand ein data-dimmed', () => {
    // A6: Jede Aufnahme steht in voller Helligkeit - hier liegen aehnliche Aufnahmen nebeneinander,
    // und ihr Helligkeitsunterschied SOLL beurteilt werden. Ueber den GANZEN Kachelbaum.
    for (const effectiveDecision of ['keep', 'discard'] as const) {
      const { unmount } = render(<ul>{tileElement({ effectiveDecision })}</ul>)

      expect(tile().hasAttribute('data-dimmed')).toBe(false)
      expect(tile().querySelectorAll('[data-dimmed]')).toHaveLength(0)
      unmount()
    }
  })

  it('reserviert die Hoehe der Bildflaeche, bevor das Bild da ist', () => {
    // Die Bildflaeche laedt ueber einen authentifizierten Abruf und trifft erst nach dem ersten
    // Rendern ein; ohne reservierte Hoehe spraenge das Raster beim Eintreffen.
    renderTile()

    expect(screen.getByTestId('duplicate-image').className).toContain('aspect-square')
  })
})

/* ------------------------------------------------------------------------------------------
 * A4 - alles gleichzeitig sichtbar
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - Aufbau', () => {
  it.each([
    ['mit Wahlzeile', true],
    ['ohne Wahlzeile', false],
  ])('zeigt alle fuenf Teile ohne Aufklappen (%s)', (_fall, keepPossible) => {
    renderTile({ effectiveDecision: 'discard', keepPossible })

    expect(screen.getByRole('button', { name: 'Reise/serie-01.jpg vergrößern' })).toBeTruthy()
    expect(within(tile()).getByText('serie-01.jpg')).toBeTruthy()
    expect(screen.getByTestId('duplicate-state')).toHaveTextContent(
      DUPLICATE_ZUSTAENDE.discard.text,
    )
    expect(metricValue('Schärfe')).not.toBeNull()
    if (keepPossible) {
      expect(screen.getByRole('group', { name: /Wahl/ })).toBeTruthy()
    } else {
      expect(screen.getByText(DUPLICATE_IMMUTABLE_TEXT)).toBeTruthy()
    }
    expect(tile().querySelectorAll('[aria-expanded]')).toHaveLength(0)
    expect(tile().querySelectorAll('details:not([open])')).toHaveLength(0)
  })
})

/* ------------------------------------------------------------------------------------------
 * A7 - die Bewertungszeile
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - die Bewertungszeile', () => {
  it('nennt Schaerfe und Belichtung in der Formatierung der Ansicht', () => {
    renderTile({ sharpness: 412.7, exposure: 0.125 })

    expect(metricValue('Schärfe')).toHaveTextContent(/^413$/)
    expect(metricValue('Belichtung')).toHaveTextContent(/^12,5 % ohne Zeichnung$/)
  })

  it('nennt eine fehlende Schaerfe als "nicht gemessen"', () => {
    renderTile({ sharpness: null })

    expect(metricValue('Schärfe')).toHaveTextContent('nicht gemessen')
  })

  it('laesst die Belichtungszeile weg, wenn der Wert fehlt', () => {
    renderTile({ exposure: null })

    expect(metricValue('Belichtung')).toBeNull()
    expect(metricValue('Schärfe')).not.toBeNull()
  })

  it('zeigt 0 als Wert und nicht als Abwesenheit', () => {
    renderTile({ sharpness: 0, exposure: 0 })

    expect(metricValue('Schärfe')).toHaveTextContent(/^0$/)
    expect(metricValue('Belichtung')).toHaveTextContent(/^0 % ohne Zeichnung$/)
  })

  it('traegt die Auszeichnung als Wort neben dem Wert', () => {
    renderTile({ bestSharpness: true, bestExposure: true })

    expect(metricValue('Schärfe')).toHaveTextContent('413 — schärfste')
    expect(metricValue('Belichtung')).toHaveTextContent('12,5 % ohne Zeichnung — beste Belichtung')
  })

  it('aendert mit der Auszeichnung weder Zustand, Rahmen noch Bedienelemente', () => {
    // Die Auszeichnung ist nur ein Wort. Sie steht widerspruchsfrei auf einer Ausschuss-Aufnahme,
    // waehrend eine andere "Behalten" traegt.
    const ohne = render(<ul>{tileElement({ effectiveDecision: 'discard' })}</ul>)
    const vorher = {
      zustand: tile().dataset.duplicateDecision,
      rahmen: tile().className,
      knoepfe: screen.getAllByRole('button').map((knopf) => knopf.getAttribute('aria-pressed')),
    }
    ohne.unmount()

    render(
      <ul>
        {tileElement({ effectiveDecision: 'discard', bestSharpness: true, bestExposure: true })}
      </ul>,
    )

    expect({
      zustand: tile().dataset.duplicateDecision,
      rahmen: tile().className,
      knoepfe: screen.getAllByRole('button').map((knopf) => knopf.getAttribute('aria-pressed')),
    }).toEqual(vorher)
  })
})

/* ------------------------------------------------------------------------------------------
 * A8 - was sich nicht aendern laesst, sagt das
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - das unveraenderliche Mitglied', () => {
  it.each([
    ['mit Wahl', true, 3],
    ['ohne Wahl', false, 1],
  ])('zaehlt die Bedienelemente der Karte (%s)', (_fall, keepPossible, anzahl) => {
    // Ueber die ANZAHL der Bedienelemente, nie ueber `queryByRole(name)`: Eine Abfrage nach dem
    // Namen ist gegen ein umbenanntes Label blind. Ohne Wahl bleibt genau die Bildflaeche - auch
    // "Ausschuss" fehlt, und keine Schaltflaeche ist bloss gesperrt.
    renderTile({ effectiveDecision: 'discard', keepPossible })

    const knoepfe = screen.getAllByRole('button')
    expect(knoepfe).toHaveLength(anzahl)
    expect(knoepfe.filter((knopf) => knopf.hasAttribute('disabled'))).toHaveLength(0)
    expect(screen.queryByText(DUPLICATE_IMMUTABLE_TEXT) !== null).toBe(!keepPossible)
  })
})

/* ------------------------------------------------------------------------------------------
 * A11 - die Bildflaeche oeffnet die Grossansicht
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - vergroessern', () => {
  it('ist ein natives button und nennt die Aktion im zugaenglichen Namen', async () => {
    const { onOpen } = renderTile()
    const knopf = screen.getByRole('button', { name: /vergrößern/i })

    expect(knopf.tagName).toBe('BUTTON')
    expect(knopf.getAttribute('type')).toBe('button')
    await userEvent.click(knopf)

    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['mit Wahlzeile', true, 3],
    ['ohne Wahlzeile', false, 1],
  ])(
    'nennt den Dateinamen in JEDEM zugaenglichen Namen der Kachel (%s)',
    (_fall, keepPossible, anzahl) => {
      // Mehrere Kacheln im selben Raster waeren per Tastatur und Screenreader sonst nicht
      // auseinanderzuhalten - "Behalten" allein sagt nicht, welches Bild gemeint ist.
      renderTile({ effectiveDecision: 'discard', keepPossible })

      const namen = screen
        .getAllByRole('button')
        .map((knopf) => knopf.getAttribute('aria-label') ?? '')

      expect(namen).toHaveLength(anzahl)
      expect(namen.every((name) => name.includes('serie-01.jpg'))).toBe(true)
      expect(new Set(namen).size).toBe(anzahl)
    },
  )

  it('wirkt mit Enter und Leertaste, ohne eigenen Tastatur-Handler', async () => {
    const { onOpen } = renderTile()
    const knopf = screen.getByRole('button', { name: /vergrößern/i })

    knopf.focus()
    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')

    expect(onOpen).toHaveBeenCalledTimes(2)
  })
})

/* ------------------------------------------------------------------------------------------
 * A5 - die Wahlzeile
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

  it('weist den geltenden Wert ueber aria-pressed und sein Symbol aus', () => {
    // `aria-pressed` folgt `effectiveDecision`. Die gedrueckte Schaltflaeche traegt zusaetzlich
    // ihr Zustandssymbol - so traegt die Form den Zustand, nicht nur die Farbe.
    renderTile({ effectiveDecision: 'keep' })

    const behalten = screen.getByRole('button', { name: /^Behalten:/ })
    const ausschuss = screen.getByRole('button', { name: /^Ausschuss:/ })
    expect(behalten.getAttribute('aria-pressed')).toBe('true')
    expect(ausschuss.getAttribute('aria-pressed')).toBe('false')
    expect(behalten.querySelector('[data-icon]')?.getAttribute('data-icon')).toBe(
      DUPLICATE_ZUSTAENDE.keep.icon,
    )
    expect(ausschuss.querySelector('[data-icon]')).toBeNull()
  })

  it('bietet GENAU ZWEI Wahlschaltflaechen, genau eine gedrueckt', () => {
    renderTile({ effectiveDecision: 'keep' })

    expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(1)
    expect(screen.getAllByRole('button', { pressed: true })).toHaveLength(1)
  })

  it('sperrt die Wahlzeile waehrend der eigenen laufenden Entscheidung', async () => {
    const { onDecide } = renderTile({ deciding: true })

    await userEvent.click(screen.getByRole('button', { name: /^Behalten:/ }))

    expect(onDecide).not.toHaveBeenCalled()
  })
})
