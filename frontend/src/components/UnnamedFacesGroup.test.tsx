import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import type { FaceAssignmentOut, PersonOut, UnnamedFacesPageOut } from '../api/types'
import { usePersonsQuery } from '../hooks/usePersons'
import { useUnnamedFaces } from '../hooks/useUnnamedFaces'
import type { UnnamedFaces } from '../hooks/useUnnamedFaces'
import { UnnamedFacesGroup } from './UnnamedFacesGroup'

vi.mock('../api/persons')

const ANNA: PersonOut = { id: 7, name: 'Anna' } as PersonOut
const BEN: PersonOut = { id: 8, name: 'Ben' } as PersonOut
// Ein erzeugtes, einfarbiges Stück JPEG-Anfang ohne Gesicht (S11) - base64 genügt hier.
const CROP = btoa('\xff\xd8\xff\xe0einfarbig')

interface Call {
  afterId: number
  maxPhotos: number | undefined
  resolve: (page: UnnamedFacesPageOut) => void
  reject: (error: unknown) => void
}

let calls: Call[] = []
let created = 0

function page(
  faces: [number, number][],
  next: number | null,
  done: number,
  total: number,
  notReady: number[] = [],
  crop = CROP,
): UnnamedFacesPageOut {
  return {
    faces: faces.map(([photoId, index]) => ({
      photo_id: photoId,
      face_index: index,
      crop_jpeg: crop,
    })),
    not_ready_photo_ids: notReady,
    next_after_id: next,
    photos_done: done,
    photos_total: total,
  }
}

function assigned(person: PersonOut, learned = true): FaceAssignmentOut {
  return { person, learned, photo_persons: [] } as unknown as FaceAssignmentOut
}

async function settle() {
  for (let round = 0; round < 3; round += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }
}

async function answer(afterId: number, result: UnnamedFacesPageOut | Error, maxPhotos?: number) {
  await waitFor(() =>
    expect(calls.some((c) => c.afterId === afterId && c.maxPhotos === maxPhotos)).toBe(true),
  )
  const call = calls.find((c) => c.afterId === afterId && c.maxPhotos === maxPhotos)!
  calls = calls.filter((entry) => entry !== call)
  if (result instanceof Error) {
    call.reject(result)
  } else {
    call.resolve(result)
  }
  await settle()
}

let exposed: UnnamedFaces | null = null

function Harness() {
  const unnamed = useUnnamedFaces(3)
  const persons = usePersonsQuery()
  const headingRef = useRef<HTMLHeadingElement>(null)
  exposed = unnamed
  return (
    <UnnamedFacesGroup
      projectId={3}
      persons={persons.data ?? []}
      unnamed={unnamed}
      headingId="ohne-namen"
      headingRef={headingRef}
    />
  )
}

async function renderGroup(persons: PersonOut[] = [ANNA, BEN]) {
  vi.mocked(personsApi.listPersons).mockResolvedValue(persons)
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <Harness />
    </QueryClientProvider>,
  )
  await settle()
  return { ...view, queryClient }
}

/** Gruppe mit einer vollständig geladenen Seite. */
async function loaded(
  faces: [number, number][] = [
    [3, 0],
    [5, 0],
    [8, 0],
  ],
  persons: PersonOut[] = [ANNA, BEN],
) {
  const view = await renderGroup(persons)
  await answer(0, page(faces, null, 10, 10))
  return view
}

function cards(): HTMLElement[] {
  return within(screen.getByRole('region', { name: 'Ohne Namen' }))
    .getAllByRole('listitem')
    .filter((item) => !item.hasAttribute('aria-hidden'))
}

function progressLine(): HTMLElement {
  return screen.getByText(/^(Gesichter werden gesucht|Suche |Das Projekt hat)/)
}

beforeEach(() => {
  calls = []
  created = 0
  exposed = null
  Object.assign(URL, {
    createObjectURL: vi.fn(() => `blob:crop-${++created}`),
    revokeObjectURL: vi.fn(),
  })
  vi.mocked(personsApi.listUnnamedFaces).mockReset()
  vi.mocked(personsApi.addReference).mockReset()
  vi.mocked(personsApi.createPerson).mockReset()
  vi.mocked(personsApi.listUnnamedFaces).mockImplementation(
    (_projectId, afterId, maxPhotos) =>
      new Promise((resolve, reject) => {
        calls.push({ afterId, maxPhotos, resolve, reject })
      }),
  )
})

describe('UnnamedFacesGroup - Statusleiste', () => {
  it('führt den Fortschritt durch die Zustände, ohne die Fortschrittszeile live zu schalten', async () => {
    await renderGroup()

    expect(progressLine()).toHaveTextContent('Gesichter werden gesucht…')
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('value')
    expect(progressLine().closest('[role="status"], [aria-live]')).toBeNull()

    await answer(0, page([[3, 0]], 10, 10, 30))
    expect(progressLine()).toHaveTextContent(
      'Gesichter werden gesucht – 10 von 30 Fotos durchgesehen.',
    )
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('value', '10')
    expect(bar).toHaveAttribute('max', '30')
    expect(bar).toHaveAccessibleName(progressLine().textContent ?? '')

    await answer(10, new ApiError(500, 'Der Dienst ist gerade nicht erreichbar.'))
    expect(progressLine()).toHaveTextContent('Suche unterbrochen – 10 von 30 Fotos durchgesehen.')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Der Dienst ist gerade nicht erreichbar.')
    // Bereits gefundene Gesichter bleiben stehen und zuordenbar.
    expect(cards()).toHaveLength(1)

    await userEvent.setup().click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    await answer(10, page([], null, 30, 30))
    expect(progressLine()).toHaveTextContent('Suche abgeschlossen: 30 Fotos durchgesehen.')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('nennt den Abschluss eines Projekts mit einem Foto im Singular', async () => {
    await renderGroup()
    await answer(0, page([], null, 1, 1))

    expect(progressLine()).toHaveTextContent('Suche abgeschlossen: 1 Foto durchgesehen.')
    expect(screen.getByText('Kein Gesicht ohne Namen.')).toBeInTheDocument()
  })

  it('meldet eine Unterbrechung vor der ersten Seite ohne Fotozahlen und setzt bei 0 fort', async () => {
    const user = userEvent.setup()
    await renderGroup()
    await answer(0, new Error('netz'))

    expect(progressLine()).toHaveTextContent(/^Suche unterbrochen\.$/)
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Suche nach Gesichtern ist unterbrochen.',
    )

    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    await answer(0, page([], null, 2, 2))
    expect(progressLine()).toHaveTextContent('Suche abgeschlossen: 2 Fotos durchgesehen.')
  })

  it('meldet ein Projekt ohne Fotos', async () => {
    await renderGroup()
    await answer(0, page([], null, 0, 0))

    expect(progressLine()).toHaveTextContent('Das Projekt hat noch keine Fotos.')
  })

  it('zählt nicht bereite Fotos eindeutig, schon während der Suche und danach', async () => {
    await renderGroup()
    await answer(0, page([], 10, 10, 20, [9]))

    expect(
      screen.getByText(
        '1 Foto nicht bereit – noch ohne Vorschau oder nicht lesbar. Gesichter darauf fehlen hier.',
      ),
    ).toBeInTheDocument()

    await answer(10, page([], null, 20, 20, [9, 12]))

    expect(
      screen.getByText(
        '2 Fotos nicht bereit – noch ohne Vorschau oder nicht lesbar. Gesichter darauf fehlen hier.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Kein Gesicht ohne Namen.')).toBeInTheDocument()
  })

  it('zeigt je gescheiterter Einzelabfrage einen Alert, mit oder ohne Dateinamen', async () => {
    const user = userEvent.setup()
    await loaded()

    act(() => exposed!.refreshPhoto(3, 'a.jpg'))
    await answer(2, new ApiError(500, 'weg'), 1)
    act(() => exposed!.refreshPhoto(5, null))
    await answer(4, new ApiError(500, 'weg'), 1)

    const alerts = screen.getAllByRole('alert')
    expect(alerts.map((alert) => alert.textContent)).toEqual([
      expect.stringContaining('Das Gesicht auf a.jpg konnte nicht wieder aufgenommen werden.'),
      expect.stringContaining('Die Gesichter eines Fotos konnten nicht neu gesucht werden.'),
    ])

    await user.click(within(alerts[0]).getByRole('button', { name: 'Erneut versuchen' }))
    await answer(2, page([[3, 0]], 3, 1, 10), 1)

    expect(screen.getAllByRole('alert')).toHaveLength(1)
  })
})

describe('UnnamedFacesGroup - Liste', () => {
  it('zeigt Gesichter flach in der Reihenfolge der Antwort, ohne Gruppierung je Foto', async () => {
    await loaded([
      [3, 0],
      [5, 0],
      [5, 1],
    ])

    const items = cards()
    expect(items).toHaveLength(3)
    // Zwei Gesichter desselben Fotos: zwei Karten, deren gemeinsamer Container die ganze Liste ist.
    expect(items[1].parentElement).toBe(items[0].parentElement)
    expect(items[2].parentElement).toBe(items[0].parentElement)
    for (const item of items) {
      expect(within(item).getByRole('img', { name: 'Gesicht ohne Namen' })).toBeInTheDocument()
    }
  })

  it('stellt die Namen auf jeder Karte gleich, in der Reihenfolge der Personenliste', async () => {
    await loaded()

    for (const item of cards()) {
      const buttons = within(item).getAllByRole('button')
      expect(buttons.map((button) => button.getAttribute('aria-label'))).toEqual([
        'Zuordnen: Anna',
        'Zuordnen: Ben',
      ])
      expect(buttons.map((button) => button.textContent)).toEqual(['Anna', 'Ben'])
      expect(buttons[0].className).toBe(buttons[1].className)
      for (const button of buttons) {
        expect(button).not.toHaveAttribute('aria-pressed')
      }
    }
    expect(document.activeElement).toBe(document.body)
  })

  it('zeigt außerhalb der Fortschritts- und "nicht bereit"-Zeile keine Ziffer', async () => {
    const user = userEvent.setup()
    await renderGroup()
    await answer(
      0,
      page(
        [
          [3, 0],
          [5, 0],
        ],
        10,
        10,
        30,
        [4],
      ),
    )
    vi.mocked(personsApi.addReference).mockResolvedValue(assigned(ANNA, false))
    await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' }))
    await settle()

    const region = screen.getByRole('region', { name: 'Ohne Namen' })
    const counted = [progressLine(), screen.getByText(/nicht bereit/)]
    const walker = document.createTreeWalker(region, NodeFilter.SHOW_TEXT)
    const outside: string[] = []
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      if (!counted.some((line) => line.contains(node))) {
        outside.push(node.textContent ?? '')
      }
    }
    // Gegenprobe: Die beiden Zeilen tragen tatsächlich Fotozahlen.
    expect(counted.map((line) => line.textContent).join('')).toMatch(/\d/)
    expect(outside.join(' ')).toContain('Als Anna benannt')
    expect(outside.join(' ')).not.toMatch(/\d/)
  })

  it('lässt einen nicht darstellbaren Ausschnitt als Fläche stehen, Zuordnen bleibt möglich', async () => {
    const user = userEvent.setup()
    await renderGroup()
    await answer(0, page([[3, 0]], null, 1, 1, [], '%%% kein base64 %%%'))
    vi.mocked(personsApi.addReference).mockResolvedValue(assigned(ANNA))

    expect(screen.getByRole('img', { name: 'Ausschnitt nicht verfügbar' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zuordnen: Anna' }))

    expect(personsApi.addReference).toHaveBeenCalledWith(ANNA.id, 3, 0)
  })
})

describe('UnnamedFacesGroup - Zuordnen', () => {
  it('ordnet mit einem Druck zu, nimmt die Karte heraus und fragt die Auflistung nicht neu an', async () => {
    const user = userEvent.setup()
    await loaded()
    vi.mocked(personsApi.addReference).mockResolvedValue(assigned(ANNA))
    const requests = vi.mocked(personsApi.listUnnamedFaces).mock.calls.length
    const url = within(cards()[1]).getByRole('img').getAttribute('src')

    await user.click(within(cards()[1]).getByRole('button', { name: 'Zuordnen: Anna' }))

    expect(personsApi.addReference).toHaveBeenCalledExactlyOnceWith(ANNA.id, 5, 0)
    await waitFor(() => expect(cards()).toHaveLength(2))
    expect(screen.getByRole('status')).toHaveTextContent('Gesicht als Anna gezeigt.')
    expect(vi.mocked(personsApi.listUnnamedFaces).mock.calls).toHaveLength(requests)
    // Die Blob-URL der gegangenen Karte ist genau einmal freigegeben.
    expect(
      vi.mocked(URL.revokeObjectURL).mock.calls.filter(([value]) => value === url),
    ).toHaveLength(1)
    // Fokus auf die nachrückende Karte an derselben Stelle.
    expect(within(cards()[1]).getByRole('button', { name: 'Zuordnen: Anna' })).toHaveFocus()
  })

  it('nennt an der Obergrenze den Satz, dass nur benannt und nicht gelernt wurde', async () => {
    const user = userEvent.setup()
    await loaded()
    vi.mocked(personsApi.addReference).mockResolvedValue(assigned(BEN, false))

    await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Ben' }))

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'Als Ben benannt, aber nicht gelernt: Für Ben sind schon genug Gesichter gezeigt.',
      ),
    )
    expect(cards()).toHaveLength(2)
  })

  it('setzt den Fokus auf die vorige Karte, sonst auf die Überschrift', async () => {
    const user = userEvent.setup()
    await loaded([
      [3, 0],
      [5, 0],
    ])
    vi.mocked(personsApi.addReference).mockResolvedValue(assigned(ANNA))

    await user.click(within(cards()[1]).getByRole('button', { name: 'Zuordnen: Anna' }))
    await waitFor(() =>
      expect(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' })).toHaveFocus(),
    )

    await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 2, name: 'Ohne Namen' })).toHaveFocus(),
    )
  })

  it('lässt eine zweite Karte bedienen, während die erste noch speichert', async () => {
    const user = userEvent.setup()
    await loaded()
    const resolvers: ((value: FaceAssignmentOut) => void)[] = []
    vi.mocked(personsApi.addReference).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvers.push(resolve)
        }),
    )

    await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' }))
    expect(within(cards()[0]).getByRole('button', { name: 'Wird gespeichert…' })).toBeDisabled()
    expect(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Ben' })).toBeDisabled()
    const second = within(cards()[1]).getByRole('button', { name: 'Zuordnen: Ben' })
    expect(second).toBeEnabled()
    await user.click(second)

    await act(async () => resolvers[1](assigned(BEN)))
    await act(async () => resolvers[0](assigned(ANNA)))

    await waitFor(() => expect(cards()).toHaveLength(1))
    expect(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' })).toBeInTheDocument()
  })

  it('hält die übrigen Karten als dieselben Knoten über Entfernen, Nachladen und Einzelabfrage', async () => {
    const user = userEvent.setup()
    await renderGroup()
    await answer(
      0,
      page(
        [
          [3, 0],
          [5, 0],
          [8, 0],
        ],
        10,
        10,
        20,
      ),
    )
    const [first, , third] = cards()
    vi.mocked(personsApi.addReference).mockResolvedValue(assigned(ANNA))

    await user.click(within(cards()[1]).getByRole('button', { name: 'Zuordnen: Anna' }))
    await waitFor(() => expect(cards()).toHaveLength(2))
    await answer(10, page([[12, 0]], null, 20, 20))

    expect(cards()[0]).toBe(first)
    expect(cards()[1]).toBe(third)

    act(() => exposed!.refreshPhoto(8, null))
    await answer(7, page([[8, 0]], 8, 3, 20), 1)
    expect(cards()[0]).toBe(first)
    expect(cards()[1]).toBe(third)
  })
})

describe('UnnamedFacesGroup - Neue Person', () => {
  it('bietet "Neue Person…" nur bei weniger als zwei Personen an', async () => {
    await loaded(undefined, [ANNA, BEN])

    expect(screen.queryByRole('button', { name: 'Neue Person…' })).not.toBeInTheDocument()
  })

  it('öffnet höchstens ein Formular und gibt den Fokus bei Abbrechen und Esc zurück', async () => {
    const user = userEvent.setup()
    await loaded(undefined, [ANNA])

    const firstTrigger = within(cards()[0]).getByRole('button', { name: 'Neue Person…' })
    expect(firstTrigger).toHaveAttribute('aria-expanded', 'false')
    await user.click(firstTrigger)
    expect(screen.getByLabelText('Name der neuen Person')).toHaveFocus()
    await user.type(screen.getByLabelText('Name der neuen Person'), 'Carla')

    await user.click(within(cards()[1]).getByRole('button', { name: 'Neue Person…' }))
    expect(screen.getAllByLabelText('Name der neuen Person')).toHaveLength(1)
    expect(within(cards()[1]).getByLabelText('Name der neuen Person')).toHaveValue('')

    await user.keyboard('{Escape}')
    expect(screen.queryByLabelText('Name der neuen Person')).not.toBeInTheDocument()
    expect(within(cards()[1]).getByRole('button', { name: 'Neue Person…' })).toHaveFocus()

    await user.click(within(cards()[0]).getByRole('button', { name: 'Neue Person…' }))
    await user.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(within(cards()[0]).getByRole('button', { name: 'Neue Person…' })).toHaveFocus()
  })

  it('sperrt "Festlegen" bei leerem Namen und sendet mit Enter ab', async () => {
    const user = userEvent.setup()
    await loaded(undefined, [ANNA])
    vi.mocked(personsApi.createPerson).mockResolvedValue(assigned(BEN))

    await user.click(within(cards()[0]).getByRole('button', { name: 'Neue Person…' }))
    const field = screen.getByLabelText('Name der neuen Person')
    await user.type(field, '   ')
    expect(screen.getByRole('button', { name: 'Festlegen' })).toBeDisabled()

    await user.clear(field)
    await user.type(field, ' Ben ')
    expect(screen.getByRole('button', { name: 'Festlegen' })).toBeEnabled()
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    await user.keyboard('{Enter}')

    expect(personsApi.createPerson).toHaveBeenCalledExactlyOnceWith('Ben', 3, 0)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ben ist festgelegt.'))
    // Die Personenliste lädt neu: Bei zwei Personen entfällt "Neue Person…" auf allen Karten.
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Neue Person…' })).not.toBeInTheDocument(),
    )
    for (const item of cards()) {
      expect(within(item).getByRole('button', { name: 'Zuordnen: Ben' })).toBeInTheDocument()
    }
  })
})

describe('UnnamedFacesGroup - Ablehnungen', () => {
  it.each([PERSON_REFUSALS_TEXT('faceAlreadyOnPhoto'), PERSON_REFUSALS_TEXT('faceOfOtherPerson')])(
    'lässt die Karte stehen und zeigt "%s" ohne Namen',
    async (detail) => {
      const user = userEvent.setup()
      await loaded()
      vi.mocked(personsApi.addReference).mockRejectedValue(new ApiError(409, detail))

      await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' }))

      const alert = await within(cards()[0]).findByRole('alert')
      expect(alert).toHaveTextContent(detail)
      expect(alert.textContent).not.toMatch(/Anna|Ben/)
      expect(cards()).toHaveLength(3)
    },
  )

  it('schließt bei "zwei Personen" das Formular und lädt die Personenliste neu', async () => {
    const user = userEvent.setup()
    const { queryClient } = await loaded(undefined, [ANNA])
    vi.mocked(personsApi.createPerson).mockRejectedValue(
      new ApiError(409, personsApi.PERSON_REFUSALS.limitReached),
    )
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

    await user.click(within(cards()[0]).getByRole('button', { name: 'Neue Person…' }))
    await user.type(screen.getByLabelText('Name der neuen Person'), 'Carla{Enter}')

    expect(await within(cards()[0]).findByRole('alert')).toHaveTextContent(
      personsApi.PERSON_REFUSALS.limitReached,
    )
    expect(screen.queryByLabelText('Name der neuen Person')).not.toBeInTheDocument()
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['persons'] })
  })

  it.each([
    [409, 'Eine Person mit diesem Namen gibt es schon.'],
    [422, 'Der Name ist zu lang.'],
  ])('markiert bei %i das Feld und behält die Eingabe', async (status, detail) => {
    const user = userEvent.setup()
    await loaded(undefined, [ANNA])
    vi.mocked(personsApi.createPerson).mockRejectedValue(new ApiError(status, detail))

    await user.click(within(cards()[0]).getByRole('button', { name: 'Neue Person…' }))
    const field = screen.getByLabelText('Name der neuen Person')
    await user.type(field, 'Anna{Enter}')

    await within(cards()[0]).findByRole('alert')
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveAccessibleDescription(expect.stringContaining(detail))
    expect(field).toHaveValue('Anna')
  })

  it('lädt bei 404 die Personenliste neu', async () => {
    const user = userEvent.setup()
    const { queryClient } = await loaded()
    vi.mocked(personsApi.addReference).mockRejectedValue(
      new ApiError(404, 'Person nicht gefunden.'),
    )
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

    await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Ben' }))

    expect(await within(cards()[0]).findByRole('alert')).toHaveTextContent('Person nicht gefunden.')
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['persons'] })
  })

  it('sucht bei "kein Gesicht mehr" die Gesichter des Fotos neu und meldet es in der Leiste', async () => {
    const user = userEvent.setup()
    await loaded()
    vi.mocked(personsApi.addReference).mockRejectedValue(
      new ApiError(409, personsApi.PERSON_REFUSALS.faceNotFound),
    )

    await user.click(within(cards()[1]).getByRole('button', { name: 'Zuordnen: Anna' }))

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden.',
      ),
    )
    expect(within(cards()[1]).getByRole('button', { name: 'Zuordnen: Anna' })).toHaveFocus()
    await answer(
      4,
      page(
        [
          [5, 0],
          [5, 1],
        ],
        5,
        2,
        10,
      ),
      1,
    )
    expect(cards()).toHaveLength(4)
  })

  it('nennt sonstige Fehler allgemein', async () => {
    const user = userEvent.setup()
    await loaded()
    vi.mocked(personsApi.addReference).mockRejectedValue(new Error('netz'))

    await user.click(within(cards()[0]).getByRole('button', { name: 'Zuordnen: Anna' }))

    expect(await within(cards()[0]).findByRole('alert')).toHaveTextContent(
      'Das Gesicht konnte nicht gespeichert werden.',
    )
  })
})

function PERSON_REFUSALS_TEXT(name: 'faceAlreadyOnPhoto' | 'faceOfOtherPerson'): string {
  return {
    faceAlreadyOnPhoto: 'Diese Person hat auf diesem Foto schon ein Gesicht.',
    faceOfOtherPerson: 'Dieses Gesicht gehört auf diesem Foto schon der anderen Person.',
  }[name]
}
