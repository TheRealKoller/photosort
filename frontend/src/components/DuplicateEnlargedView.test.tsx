import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { DuplicateDecision, DuplicateGroupItem, PhotoOut } from '../api/types'
import { DuplicateEnlargedView } from './DuplicateEnlargedView'
import { DUPLICATE_IMMUTABLE_TEXT, DUPLICATE_ZUSTAENDE } from './DuplicatePhotoTile'

vi.mock('./PhotoImage', () => ({
  PhotoImage: ({
    alt,
    className,
    variant,
  }: {
    alt: string
    className?: string
    variant: string
  }) => <img alt={alt} className={className} data-variant={variant} />,
}))

function photo(id: number): PhotoOut {
  return {
    id,
    relative_path: `Reise/serie-${id}.jpg`,
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
  }
}

function item(
  id: number,
  decision: DuplicateDecision = 'keep',
  keepPossible = true,
): DuplicateGroupItem {
  return {
    photo: photo(id),
    effective_decision: decision,
    keep_possible: keepPossible,
    sharpness: 100 + id,
    exposure: 0.1,
  }
}

const ITEMS = [item(1, 'keep'), item(2, 'discard'), item(3, 'discard')]

interface ViewOverrides {
  items?: DuplicateGroupItem[]
  currentId?: number
  onSelect?: (photoId: number) => void
  onClose?: () => void
  onDecide?: (photoId: number, decision: DuplicateDecision) => void
}

function renderView(overrides: ViewOverrides = {}) {
  const onSelect = overrides.onSelect ?? vi.fn()
  const onClose = overrides.onClose ?? vi.fn()
  const onDecide = overrides.onDecide ?? vi.fn()
  render(
    <DuplicateEnlargedView
      items={overrides.items ?? ITEMS}
      currentId={overrides.currentId ?? 2}
      bestSharpness={new Set()}
      bestExposure={new Set()}
      decidingIds={new Set()}
      onSelect={onSelect}
      onClose={onClose}
      onDecide={onDecide}
    />,
  )
  return { onSelect, onClose, onDecide }
}

/** Die Grossansicht mit echtem Zustand - fuer Faelle, in denen das Blaettern wirken muss. */
function Blaetterbar({ startId }: { startId: number }) {
  const [currentId, setCurrentId] = useState(startId)
  return (
    <DuplicateEnlargedView
      items={ITEMS}
      currentId={currentId}
      bestSharpness={new Set()}
      bestExposure={new Set()}
      decidingIds={new Set()}
      onSelect={setCurrentId}
      onClose={vi.fn()}
      onDecide={vi.fn()}
    />
  )
}

function sidebar(): HTMLElement {
  return screen.getByTestId('duplicate-sidebar')
}

describe('DuplicateEnlargedView - Aufbau', () => {
  it('nennt die Stelle in der Serie und fokussiert die Ueberschrift beim Oeffnen', () => {
    renderView({ currentId: 2 })

    const ueberschrift = screen.getByRole('heading', { level: 2, name: 'Aufnahme 2 von 3' })
    expect(document.activeElement).toBe(ueberschrift)
    expect(screen.getByRole('region', { name: 'Aufnahme 2 von 3' })).toBeTruthy()
  })

  it('zeigt das Bild in display-Qualitaet, eingepasst und unverfaelscht', () => {
    // A6/A11: keine Deckkraft, kein Filter, keine Ueberlagerung und kein Zustandsrahmen am Bild.
    renderView({ currentId: 2 })

    const buehne = screen.getByTestId('duplicate-stage')
    const bild = within(buehne).getByRole('img')
    expect(bild.getAttribute('data-variant')).toBe('display')
    expect(bild.className).toContain('object-contain')
    expect(buehne.querySelectorAll('[data-dimmed]')).toHaveLength(0)
    expect(buehne.children).toHaveLength(1)
    expect(buehne.className).not.toMatch(/border-(accent|danger)/)
  })

  it('zeigt in der Seitenspalte Dateiname, Zustand, Bewertung und Wahl', () => {
    renderView({ currentId: 2 })

    expect(within(sidebar()).getByText('Reise/serie-2.jpg')).toBeTruthy()
    expect(within(sidebar()).getByTestId('duplicate-state')).toHaveTextContent(
      DUPLICATE_ZUSTAENDE.discard.text,
    )
    expect(within(sidebar()).getByText('Schärfe', { selector: 'dt' })).toBeTruthy()
    expect(
      within(sidebar()).getByRole('button', { name: 'Ausschuss: Reise/serie-2.jpg' }),
    ).toHaveAttribute('aria-pressed', 'true')
  })

  it('traegt den Zustandsrahmen an der Seitenspalte', () => {
    renderView({ currentId: 1 })

    expect(sidebar().dataset.duplicateDecision).toBe('keep')
  })

  it.each([
    ['mit Wahl', true, 5],
    ['ohne Wahl', false, 3],
  ])('zaehlt die Bedienelemente der Seitenspalte (%s)', (_fall, keepPossible, anzahl) => {
    // A8 in der Seitenspalte: ohne Wahl gar keine Wahlschaltflaeche, auch keine gesperrte - uebrig
    // bleiben Vor, Zurueck und Schliessen. Das mittlere Mitglied, damit kein Rand sperrt.
    renderView({
      items: [item(1), item(2, 'discard', keepPossible), item(3)],
      currentId: 2,
    })

    const knoepfe = within(sidebar()).getAllByRole('button')
    expect(knoepfe).toHaveLength(anzahl)
    expect(knoepfe.filter((knopf) => knopf.hasAttribute('disabled'))).toHaveLength(0)
    expect(within(sidebar()).queryByText(DUPLICATE_IMMUTABLE_TEXT) !== null).toBe(!keepPossible)
  })

  it('fuehrt alle Mitglieder im Streifen, die aktuelle mit aria-current', () => {
    renderView({ currentId: 2 })

    const streifen = screen.getByRole('list', { name: 'Alle Aufnahmen der Gruppe' })
    const knoepfe = within(streifen).getAllByRole('button')
    expect(knoepfe.map((knopf) => knopf.getAttribute('aria-label'))).toEqual([
      'Aufnahme 1 von 3: Reise/serie-1.jpg, Behalten',
      'Aufnahme 2 von 3: Reise/serie-2.jpg, Ausschuss',
      'Aufnahme 3 von 3: Reise/serie-3.jpg, Ausschuss',
    ])
    expect(knoepfe.map((knopf) => knopf.getAttribute('aria-current'))).toEqual([null, 'true', null])
  })
})

describe('DuplicateEnlargedView - blaettern', () => {
  it('verschiebt mit Vor und Zurueck, ohne zu schliessen', async () => {
    const { onSelect, onClose } = renderView({ currentId: 2 })

    await userEvent.click(screen.getByRole('button', { name: 'Nächste Aufnahme' }))
    await userEvent.click(screen.getByRole('button', { name: 'Vorherige Aufnahme' }))

    expect(onSelect).toHaveBeenNthCalledWith(1, 3)
    expect(onSelect).toHaveBeenNthCalledWith(2, 1)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('blaettert auch mit den Pfeiltasten', async () => {
    const { onSelect } = renderView({ currentId: 2 })

    await userEvent.keyboard('{ArrowRight}')
    await userEvent.keyboard('{ArrowLeft}')

    expect(onSelect).toHaveBeenNthCalledWith(1, 3)
    expect(onSelect).toHaveBeenNthCalledWith(2, 1)
  })

  it.each([
    ['erste', 1, 'Vorherige Aufnahme', '{ArrowLeft}'],
    ['letzte', 3, 'Nächste Aufnahme', '{ArrowRight}'],
  ])('bleibt am %s Mitglied stehen - ohne Rundlauf', async (_fall, currentId, name, taste) => {
    const { onSelect } = renderView({ currentId })

    expect(screen.getByRole('button', { name })).toBeDisabled()
    await userEvent.keyboard(taste)

    expect(onSelect).not.toHaveBeenCalled()
  })

  it.each([
    ['Nächste Aufnahme', 2, 'Vorherige Aufnahme'],
    ['Vorherige Aufnahme', 2, 'Nächste Aufnahme'],
  ])(
    'gibt den Fokus von "%s" am Rand an die Gegenschaltflaeche ab',
    async (name, startId, gegen) => {
      render(<Blaetterbar startId={startId} />)

      await userEvent.click(screen.getByRole('button', { name }))

      expect(screen.getByRole('button', { name })).toBeDisabled()
      expect(document.activeElement).toBe(screen.getByRole('button', { name: gegen }))
    },
  )

  it('springt mit einem Klick im Streifen direkt', async () => {
    const { onSelect } = renderView({ currentId: 1 })

    await userEvent.click(
      screen.getByRole('button', { name: 'Aufnahme 3 von 3: Reise/serie-3.jpg, Ausschuss' }),
    )

    expect(onSelect).toHaveBeenCalledWith(3)
  })
})

describe('DuplicateEnlargedView - schliessen und entscheiden', () => {
  it('schliesst per Esc und per sichtbarer Schaltflaeche', async () => {
    const { onClose } = renderView()

    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('button', { name: 'Vergrößerung schließen' }))

    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('entscheidet in der Seitenspalte, ohne zu blaettern oder zu schliessen', async () => {
    const { onDecide, onSelect, onClose } = renderView({ currentId: 2 })

    await userEvent.click(screen.getByRole('button', { name: 'Behalten: Reise/serie-2.jpg' }))

    expect(onDecide).toHaveBeenCalledWith(2, 'keep')
    expect(onSelect).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})
