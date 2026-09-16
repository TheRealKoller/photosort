import { render, screen } from '@testing-library/react'
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
    ...overrides,
  }
}

interface TileOverrides {
  effectiveDecision?: DuplicateDecision
  keepPossible?: boolean
  enlarged?: boolean
  deciding?: boolean
  onToggle?: () => void
  onDecide?: (decision: DuplicateDecision) => void
}

function tileElement(overrides: TileOverrides = {}) {
  return (
    <DuplicatePhotoTile
      photo={photo()}
      effectiveDecision={overrides.effectiveDecision ?? 'keep'}
      keepPossible={overrides.keepPossible ?? true}
      enlarged={overrides.enlarged ?? false}
      deciding={overrides.deciding ?? false}
      onToggle={overrides.onToggle ?? vi.fn()}
      onDecide={overrides.onDecide ?? vi.fn()}
    />
  )
}

function renderTile(overrides: TileOverrides = {}) {
  const onToggle = overrides.onToggle ?? vi.fn()
  const onDecide = overrides.onDecide ?? vi.fn()
  render(<ul>{tileElement({ ...overrides, onToggle, onDecide })}</ul>)
  return { onToggle, onDecide }
}

function tile(): HTMLElement {
  return screen.getByRole('listitem')
}

/* ------------------------------------------------------------------------------------------
 * AK1/AK2 - Zustand ohne Farbwahrnehmung, und es gibt nur noch zwei
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - die zwei Zustaende', () => {
  const ZUSTAENDE: DuplicateDecision[] = ['keep', 'discard']

  it('traegt je Zustand einen eigenen Wert, Text und Symbol - paarweise verschieden', () => {
    // Die dreifache Codierung ist die Zusage, nicht die Farbe: In Graustufen liegen die
    // Umrissfarben dicht beieinander. Geprueft als PAARWEISE Verschiedenheit ueber beide
    // Zustaende hinweg, nicht je Zustand einzeln.
    //
    // ZWEI, NICHT DREI (AK2, hebt AK6 der Spec 0374 auf): "Noch offen" gibt es nicht mehr - die
    // Ansicht zeigt das Ueberlebens-Praedikat, und das kennt keinen dritten Wert.
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

  it('traegt in keinem Zustand und in keiner Darstellung ein data-dimmed', () => {
    // AK1 (Spec 0498): Jede Aufnahme wird in voller Helligkeit gezeigt - genau hier liegen
    // mehrere aehnliche Aufnahmen nebeneinander, und ihr Helligkeitsunterschied SOLL beurteilt
    // werden. `data-dimmed` hatte genau einen Zweck (einen berechneten Deckkraftwert gegen eine
    // Absicht zu halten) und sagt ohne Daempfung nichts mehr.
    //
    // Ueber den GANZEN Kachelbaum, nicht nur ueber die Bildflaeche: Ein stehengebliebenes
    // Attribut an einem beliebigen Kind bliebe sonst unbemerkt.
    for (const effectiveDecision of ['keep', 'discard'] as const) {
      for (const enlarged of [false, true]) {
        const { unmount } = render(<ul>{tileElement({ effectiveDecision, enlarged })}</ul>)

        expect(tile().hasAttribute('data-dimmed')).toBe(false)
        expect(tile().querySelectorAll('[data-dimmed]')).toHaveLength(0)
        unmount()
      }
    }
  })

  it('reserviert die Hoehe der Bildflaeche in BEIDEN Zustaenden, bevor das Bild da ist', () => {
    // Die Bildflaeche laedt ueber einen authentifizierten Abruf und trifft immer erst nach dem
    // ersten Rendern ein. Ohne reservierte Hoehe waere die vergroesserte Kachel bis dahin flach
    // und wuechse danach um die volle Bildhoehe - alles darunter rutschte aus dem Sichtbereich,
    // nachdem bereits gescrollt wurde.
    //
    // Geprueft als Anwesenheit einer FESTEN Hoehe, nicht als Abwesenheit von `max-h-96`: Ein
    // dritter Zustand ohne reservierte Hoehe faellt hier ebenfalls auf.
    for (const [enlarged, erwartet] of [
      [false, 'aspect-square'],
      [true, 'h-96'],
    ] as const) {
      const { unmount } = render(<ul>{tileElement({ enlarged })}</ul>)
      const flaeche = screen.getByTestId('duplicate-image')

      expect(flaeche.className).toContain(erwartet)
      expect(flaeche.className).not.toContain('max-h-')
      unmount()
    }
  })

  it('zeigt Zustandsrahmen, Symbol und Wort auch in der Vergroesserung', () => {
    // AK4 (Spec 0498): Seit die Bildflaeche in voller Helligkeit steht, tragen den Zustand
    // ausschliesslich der zustandsabhaengige Rahmen und das Zustandsfeld aus Symbol UND Wort -
    // beide auch in der Vergroesserung, sonst verloere man beim Beurteilen genau die Angabe, die
    // man gerade setzt.
    renderTile({ effectiveDecision: 'discard', enlarged: true })

    expect(tile().dataset.duplicateDecision).toBe('discard')
    const kennzeichen = screen.getByTestId('duplicate-state')
    expect(kennzeichen).toHaveTextContent(DUPLICATE_ZUSTAENDE.discard.text)
    expect(kennzeichen.querySelector('[data-icon]')).not.toBeNull()
  })
})

/* ------------------------------------------------------------------------------------------
 * AK3 - was sich nicht aendern laesst, sagt das
 * ---------------------------------------------------------------------------------------- */

describe('DuplicatePhotoTile - das unveraenderliche Mitglied', () => {
  it('rendert GAR KEINE Wahlschaltflaechen, wenn keine Wahl wirkt', async () => {
    // Ueber die ANZAHL der Bedienelemente, nie ueber `queryByRole(name)`: Eine Abfrage nach dem
    // Namen ist gegen ein umbenanntes Label blind und bestuende dann auch, wenn die Schaltflaeche
    // sehr wohl da waere. Uebrig bleibt genau die Bildflaeche.
    //
    // AUCH "Ausschuss" FEHLT, nicht nur "behalten": Der waere ebenso wirkungslos - das Mitglied
    // steht bereits unveraenderlich dort.
    renderTile({ effectiveDecision: 'discard', keepPossible: false })

    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(screen.getByRole('button').getAttribute('aria-label')).toMatch(/vergrößern$/)
  })

  it('nennt stattdessen den Grund als sichtbaren Text', () => {
    renderTile({ effectiveDecision: 'discard', keepPossible: false })

    expect(screen.getByText(DUPLICATE_IMMUTABLE_TEXT)).toBeTruthy()
    expect(DUPLICATE_IMMUTABLE_TEXT).toMatch(/Bildqualität/i)
  })

  it('ist NICHT disabled - "nicht anwendbar" ist etwas anderes als "kurzzeitig gesperrt"', () => {
    // Gegenprobe zum Fall darueber: Im Regelfall stehen drei Bedienelemente, und der Grundtext
    // steht nicht da. Ohne sie bestuende der Fall oben auch gegen eine Kachel, die NIE eine Wahl
    // anbietet.
    renderTile({ effectiveDecision: 'discard', keepPossible: true })

    expect(screen.getAllByRole('button')).toHaveLength(3)
    expect(screen.queryByText(DUPLICATE_IMMUTABLE_TEXT)).toBeNull()
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

  it.each([
    ['mit Wahlzeile', true, 3],
    ['ohne Wahlzeile', false, 1],
  ])(
    'nennt den Dateinamen in JEDEM zugaenglichen Namen der Kachel (%s)',
    (_fall, keepPossible, anzahl) => {
      // Mehrere Kacheln im selben Raster waeren per Tastatur und Screenreader sonst nicht
      // auseinanderzuhalten - "Behalten" allein sagt nicht, welches Bild gemeint ist.
      //
      // Die ANZAHL haengt seit AK3 an der Datenlage: Beim unveraenderlichen Mitglied bleibt nur die
      // Bildflaeche. Beide Faelle stehen deshalb hier, statt eine feste Drei zu behaupten.
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
    // `aria-pressed` folgt `effectiveDecision`, nicht einer gespeicherten Entscheidungszeile: Die
    // Kachel weiss nicht, ob der Zustand vom System oder vom Nutzer stammt (AK2).
    renderTile({ effectiveDecision: 'keep' })

    expect(screen.getByRole('button', { name: /^Behalten:/ }).getAttribute('aria-pressed')).toBe(
      'true',
    )
    expect(screen.getByRole('button', { name: /^Ausschuss:/ }).getAttribute('aria-pressed')).toBe(
      'false',
    )
  })

  it('bietet GENAU ZWEI Wahlschaltflaechen, solange eine Wahl wirkt', () => {
    // Es gibt keine Ruecknahme nach "noch nicht entschieden" - jener Zustand existiert nicht mehr.
    // Die Zaehlung ist die Zusage: ein dritter Knopf faellt hier auf, und genau einer ist
    // gedrueckt.
    renderTile({ effectiveDecision: 'keep' })

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
