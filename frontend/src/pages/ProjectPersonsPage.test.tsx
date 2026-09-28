import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as motifsApi from '../api/motifs'
import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import type { PersonOut, PhotoListOut, PhotoOut, UnnamedFacesPageOut } from '../api/types'
import { PERSONS_QUERY_KEY } from '../hooks/usePersons'
import { MOTIF_SET } from '../test/motifSetFixture'
import { ProjectPersonsPage } from './ProjectPersonsPage'

vi.mock('../api/persons')
vi.mock('../api/photos')
vi.mock('../api/motifs')

const ANNA = { id: 7, name: 'Anna' } as PersonOut
const BEN = { id: 8, name: 'Ben' } as PersonOut
const CROP = btoa('\xff\xd8\xff\xe0einfarbig')

function photo(id: number, personIds: number[]): PhotoOut {
  return {
    id,
    relative_path: `reise/p${id}.jpg`,
    taken_at: '2024-07-20T10:00:00',
    taken_at_original: '2024-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    aspect_ratio: 1.5,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons: personIds.map((personId) => ({
      person_id: personId,
      origin: 'recognized',
      face: null,
    })),
    event: null,
    motif_assessment: null,
    motifs: [],
    album_suitability: null,
  } as unknown as PhotoOut
}
/** Je Person die Fotos, die ihren Namen tragen - der Stub filtert wie die Personeneinschränkung. */
function photosFor(byPerson: Record<number, PhotoOut[]>) {
  vi.mocked(photosApi.listPhotos).mockImplementation(async (_projectId, params = {}) => {
    const items = byPerson[params.personIds?.[0] ?? -1] ?? []
    return { items, total: items.length } as unknown as PhotoListOut
  })
}

function unnamedPage(faces: [number, number][]): UnnamedFacesPageOut {
  return {
    faces: faces.map(([photoId, index]) => ({
      photo_id: photoId,
      face_index: index,
      crop_jpeg: CROP,
    })),
    not_ready_photo_ids: [],
    next_after_id: null,
    photos_done: 5,
    photos_total: 5,
  }
}

let location: { pathname: string; hash: string } | null = null

function LocationProbe() {
  const current = useLocation()
  location = current
  return null
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects/3/persons']}>
        <Routes>
          <Route path="/projects/:projectId/persons" element={<ProjectPersonsPage />} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { queryClient }
}

function groupHeadings(): string[] {
  return screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent ?? '')
}

beforeEach(() => {
  location = null
  Object.assign(URL, {
    createObjectURL: vi.fn(() => 'blob:crop'),
    revokeObjectURL: vi.fn(),
  })
  vi.mocked(personsApi.listPersons).mockReset()
  vi.mocked(personsApi.listUnnamedFaces).mockReset()
  vi.mocked(personsApi.listUnnamedFaces).mockResolvedValue(unnamedPage([]))
  vi.mocked(photosApi.listPhotos).mockReset()
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReturnValue(new Promise(() => {}))
  vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
})

describe('ProjectPersonsPage - Zustände', () => {
  it('zeigt Platzhalter, solange die Personen laden', () => {
    vi.mocked(personsApi.listPersons).mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Personen' })).toBeInTheDocument()
    expect(screen.getByText('Personen werden geladen…')).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument()
  })

  it('zeigt beim Ladefehler der Personen nur den Alert mit "Erneut versuchen"', async () => {
    const user = userEvent.setup()
    vi.mocked(personsApi.listPersons)
      .mockRejectedValueOnce(new Error('netz'))
      .mockResolvedValueOnce([ANNA])
    photosFor({ [ANNA.id]: [] })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Personen konnten nicht geladen werden.',
    )
    expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByRole('heading', { level: 2, name: 'Anna' })).toBeInTheDocument()
  })

  it('zeigt ohne festgelegte Person nur "Ohne Namen" und keine Sprungleiste', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([])
    renderPage()

    expect(
      await screen.findByText(
        'Noch keine Person festgelegt. Wähle bei einem Gesicht unter „Ohne Namen“ „Neue Person…“, um sie festzulegen.',
      ),
    ).toBeInTheDocument()
    expect(groupHeadings()).toEqual(['Ohne Namen'])
    expect(screen.queryByRole('navigation', { name: 'Gruppen' })).not.toBeInTheDocument()
  })

  it('meldet ein unbekanntes Projekt', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    photosFor({})
    vi.mocked(personsApi.listUnnamedFaces).mockRejectedValue(
      new ApiError(404, 'Projekt nicht gefunden.'),
    )
    renderPage()

    expect(await screen.findByText('Projekt nicht gefunden.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument()
  })
})

describe('ProjectPersonsPage - Gruppen', () => {
  it('stellt die Personen in der Reihenfolge der Liste und "Ohne Namen" zuletzt', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([BEN, ANNA])
    photosFor({ [ANNA.id]: [photo(1, [ANNA.id])], [BEN.id]: [photo(2, [BEN.id])] })
    renderPage()

    await screen.findByText('p1.jpg')
    expect(groupHeadings()).toEqual(['Ben', 'Anna', 'Ohne Namen'])
    const jumps = within(screen.getByRole('navigation', { name: 'Gruppen' })).getAllByRole('link')
    expect(jumps.map((link) => link.textContent)).toEqual(['Ben', 'Anna', 'Ohne Namen'])
  })

  it('rendert die Personengruppen, ohne auf die Gesichtssuche zu warten', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    photosFor({ [ANNA.id]: [photo(1, [ANNA.id])] })
    vi.mocked(personsApi.listUnnamedFaces).mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(await screen.findByText('p1.jpg')).toBeInTheDocument()
    expect(screen.getByText('Gesichter werden gesucht…')).toBeInTheDocument()
  })

  it('setzt mit der Sprungleiste den Fokus auf die Überschrift, ohne die Adresse zu ändern', async () => {
    const user = userEvent.setup()
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    photosFor({ [ANNA.id]: [] })
    renderPage()

    const nav = await screen.findByRole('navigation', { name: 'Gruppen' })
    await user.click(within(nav).getByRole('link', { name: 'Ohne Namen' }))

    expect(screen.getByRole('heading', { level: 2, name: 'Ohne Namen' })).toHaveFocus()
    expect(location).toMatchObject({ pathname: '/projects/3/persons', hash: '' })
  })

  it('lässt eine entfernte Person nach dem Neuladen überall verschwinden', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    photosFor({ [ANNA.id]: [], [BEN.id]: [] })
    vi.mocked(personsApi.listUnnamedFaces).mockResolvedValue(unnamedPage([[4, 0]]))
    const { queryClient } = renderPage()
    await screen.findByRole('button', { name: 'Zuordnen: Ben' })

    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA])
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
    })

    await waitFor(() => expect(groupHeadings()).toEqual(['Anna', 'Ohne Namen']))
    const nav = screen.getByRole('navigation', { name: 'Gruppen' })
    expect(within(nav).queryByRole('link', { name: 'Ben' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Zuordnen: Ben' })).not.toBeInTheDocument()
  })

  it('rendert einen Namen mit Markup an jeder Stelle als Text', async () => {
    const user = userEvent.setup()
    const tricky = { id: 9, name: '<b>Eva</b>' } as PersonOut
    vi.mocked(personsApi.listPersons).mockResolvedValue([tricky])
    photosFor({ [tricky.id]: [] })
    vi.mocked(personsApi.listUnnamedFaces).mockResolvedValue(
      unnamedPage([
        [4, 0],
        [5, 0],
      ]),
    )
    vi.mocked(personsApi.addReference).mockResolvedValue({
      person: tricky,
      learned: true,
      photo_persons: [],
    } as never)
    renderPage()

    expect(await screen.findByRole('heading', { level: 2, name: '<b>Eva</b>' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Gruppen' })
    expect(within(nav).getByRole('link', { name: '<b>Eva</b>' })).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Zuordnen: <b>Eva</b>' })[0])

    expect(await screen.findByText('Gesicht als <b>Eva</b> gezeigt.')).toBeInTheDocument()
    expect(document.querySelector('b')).toBeNull()
  })
})

describe('ProjectPersonsPage - Großansicht', () => {
  it('öffnet aus der zweiten Gruppe und gibt den Fokus an den Auslöser dieser Gruppe zurück', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    const both = photo(1, [ANNA.id, BEN.id])
    photosFor({ [ANNA.id]: [both], [BEN.id]: [both, photo(2, [BEN.id])] })
    renderPage()
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: 'Großansicht: reise/p1.jpg' })).toHaveLength(2),
    )

    const second = screen.getAllByRole('button', { name: 'Großansicht: reise/p1.jpg' })[1]
    fireEvent.click(second)

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getAllByText('p1.jpg').length).toBeGreaterThan(0)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Schließen' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(second).toHaveFocus())
  })

  it('öffnet auch ein Foto, das nur in der zweiten Gruppe steht', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([ANNA, BEN])
    photosFor({ [ANNA.id]: [photo(1, [ANNA.id])], [BEN.id]: [photo(2, [BEN.id])] })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/p2.jpg' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getAllByText('p2.jpg').length).toBeGreaterThan(0)
  })
})
