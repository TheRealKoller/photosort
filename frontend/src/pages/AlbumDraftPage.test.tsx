import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as motifsApi from '../api/motifs'
import * as personsApi from '../api/persons'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import type {
  AlbumDraftOut,
  EventOut,
  PhotoOut,
  ProjectOut,
  RankingOut,
  RatingStatus,
  RatingWriteOut,
} from '../api/types'
import { setToken } from '../auth/token'
import { DRAFT_EMPTY_EVENT_TEXT } from '../components/DraftEventSection'
import type { ObserverFactory } from '../hooks/useDraftPosition'
import { MOTIF_SET } from '../test/motifSetFixture'
import { AlbumDraftPage, DRAFT_CLOUD_CONSENT_TEXT, DRAFT_EMPTY_TEXT } from './AlbumDraftPage'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/motifs')
vi.mock('../api/persons')

const USER_ID = 7

function projectOut(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: '/CostaRica',
    created_at: '2026-07-01T10:00:00',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: false,
    cloud_vision_detection_enabled: true,
    cloud_vision_consent_at: '2026-07-01T10:00:00',
    selection_target: 3,
    effective_selection_target: 3,
    photo_count: 0,
    taken_at_earliest: null,
    taken_at_latest: null,
    ...overrides,
  }
}

function makeToken(username: string): string {
  return `${btoa('{}')}.${btoa(JSON.stringify({ sub: String(USER_ID), username }))}.sig`
}

const EVENT_A: EventOut = {
  id: 1,
  position: 1,
  started_at: '2026-07-20T10:00:00',
  ended_at: '2026-07-20T11:00:00',
  place: null,
  place_name: 'Paris',
}
const EVENT_B: EventOut = {
  ...EVENT_A,
  id: 2,
  position: 2,
  place_name: 'Lyon',
  started_at: '2026-07-21T10:00:00',
  ended_at: '2026-07-21T11:00:00',
}

function ranking(proposed: boolean): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
    proposed,
    partition_size: 3,
    curation_position: null,
  }
}

function photo(id: number, overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id,
    relative_path: `${id}.jpg`,
    taken_at: `2026-07-20T10:0${id}:00`,
    taken_at_original: `2026-07-20T10:0${id}:00`,
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: ranking(true),
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons: [],
    motif_assessment: null,
    motifs: [],
    album_suitability: null,
    event: EVENT_A,
    ...overrides,
  }
}

function own(status: RatingStatus) {
  return [{ user_id: USER_ID, username: 'daniel', status, favorite: false }]
}

function written(photoId: number, status: RatingStatus | null): RatingWriteOut {
  return { photo_id: photoId, user_id: USER_ID, status, favorite: false, updated_at: null }
}

function renderPage(draft: AlbumDraftOut, observer?: ObserverFactory) {
  vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draft)
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={['/projects/1/album']}>
      <Routes>
        <Route
          path="/projects/:projectId/album"
          element={<AlbumDraftPage createPositionObserver={observer} />}
        />
        <Route path="/projects/:projectId/selection" element={<p>Endauswahl-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

const noObserver: ObserverFactory = () => ({ observe: () => {}, disconnect: () => {} })

beforeEach(() => {
  vi.resetAllMocks()
  window.localStorage.clear()
  setToken(makeToken('daniel'))
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
  vi.mocked(projectsApi.getProject).mockResolvedValue(projectOut())
  vi.mocked(personsApi.listPersons).mockResolvedValue([])
  vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({ items: [], total: 0 })
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }))
})

describe('AlbumDraftPage: Kopf und Abschluss', () => {
  it('names days, events, counts and closes with one primary link to the final selection', async () => {
    renderPage(
      {
        events: [EVENT_A, EVENT_B],
        items: [
          photo(1),
          photo(2, { ratings: own('album_worthy'), ranking: ranking(false) }),
          photo(3, { ratings: own('rejected') }),
        ],
      },
      noObserver,
    )

    expect(await screen.findByText('2 Tage · 2 Events')).toBeInTheDocument()
    expect(screen.getByText(/^Tag \d von 2 · Event \d von 2$/)).toBeInTheDocument()
    expect(
      screen.getByText('2 im Album · Richtwert etwa 3 · 1 aufgenommen · 1 gestrichen'),
    ).toBeInTheDocument()
    expect(screen.getByText('2 Fotos im Album, Richtwert etwa 3.')).toBeInTheDocument()
    expect(screen.getByText('Deine Eingriffe: 1 aufgenommen, 1 gestrichen.')).toBeInTheDocument()
    const links = screen.getAllByRole('link', { name: 'Zur Endauswahl' })
    expect(links).toHaveLength(2)
    for (const link of links) {
      expect(link).toHaveAttribute('href', '/projects/1/selection')
    }
    // Das leere Event steht als Abschnitt mit Hinzufügen-Feld da.
    expect(screen.getByText(DRAFT_EMPTY_EVENT_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Foto hinzufügen: .*Lyon/ })).toBeInTheDocument()
  })

  it('follows the section the observer reports', async () => {
    let report: () => void = () => {}
    const observer: ObserverFactory = (callback) => {
      report = callback
      return { observe: () => {}, disconnect: () => {} }
    }
    const { container } = renderPage({ events: [EVENT_A, EVENT_B], items: [photo(1)] }, observer)
    await screen.findByText(/^Tag \d von 2 · Event \d von 2$/)
    const sections = [...container.querySelectorAll<HTMLElement>('[data-draft-position]')]
    const place = (secondTop: number) => {
      for (const section of sections) {
        const top = section.dataset.draftPosition === '2' ? secondTop : -500
        section.getBoundingClientRect = () => ({ top }) as DOMRect
      }
      act(() => report())
    }

    place(900)
    expect(await screen.findByText('Tag 1 von 2 · Event 1 von 2')).toBeInTheDocument()
    place(0)
    expect(await screen.findByText('Tag 2 von 2 · Event 2 von 2')).toBeInTheDocument()
  })

  it('shows the empty state only for a run without events, with cloud consent taking precedence', async () => {
    const first = renderPage({ events: [], items: [] }, noObserver)
    expect(await screen.findByText(DRAFT_EMPTY_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(/So funktioniert|Hier steht der Vorschlag/)).toBeNull()
    first.unmount()

    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ cloud_vision_detection_enabled: false }),
    )
    renderPage({ events: [], items: [] }, noObserver)
    expect(await screen.findByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
  })
})

describe('AlbumDraftPage: Streichen und Rückgängig', () => {
  it.each([
    { previous: null, undoCall: 'delete' },
    { previous: 'album_worthy' as const, undoCall: 'put' },
  ])(
    'strikes without reload and restores the state before ($previous)',
    async ({ previous, undoCall }) => {
      const user = userEvent.setup()
      const first = photo(1, previous === null ? {} : { ratings: own(previous) })
      renderPage({ events: [EVENT_A], items: [first, photo(2)] }, noObserver)
      vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'rejected'))

      await user.click(await screen.findByRole('button', { name: 'Streichen: 1.jpg' }))

      // Die Kachel verschwindet, der Fokus geht auf die nachfolgende, der Hinweis erscheint.
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Streichen: 1.jpg' })).toBeNull(),
      )
      expect(screen.getByRole('button', { name: 'Streichen: 2.jpg' })).toHaveFocus()
      expect(screen.getByRole('status', { name: '' })).toBeDefined()
      expect(screen.getByRole('button', { name: '1 gestrichen – anzeigen' })).toBeInTheDocument()

      if (undoCall === 'delete') {
        vi.mocked(ratingsApi.deleteRating).mockResolvedValueOnce(written(1, null))
      } else {
        vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'album_worthy'))
      }
      await user.click(screen.getByRole('button', { name: 'Rückgängig' }))

      expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toHaveFocus()
      if (undoCall === 'delete') {
        expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
      } else {
        expect(ratingsApi.setRating).toHaveBeenLastCalledWith(1, 'album_worthy')
      }
      expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
    },
  )

  it('undo restores "Aufgenommen", re-adding from the struck row returns to "Vorschlag"', async () => {
    const user = userEvent.setup()
    renderPage(
      { events: [EVENT_A], items: [photo(1, { ratings: own('album_worthy') })] },
      noObserver,
    )
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'rejected'))
    await user.click(await screen.findByRole('button', { name: 'Streichen: 1.jpg' }))
    // Ohne Nachbarn geht der Fokus auf die Gestrichen-Zeile.
    const toggle = await screen.findByRole('button', { name: '1 gestrichen – anzeigen' })
    expect(toggle).toHaveFocus()

    await user.click(toggle)
    vi.mocked(ratingsApi.deleteRating).mockResolvedValueOnce(written(1, null))
    await user.click(screen.getByRole('button', { name: 'Wieder aufnehmen: 1.jpg' }))

    // Vorgeschlagen: die eigene Entscheidung wird entfernt, das Foto ist wieder „Vorschlag".
    expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
    const decide = await screen.findByRole('button', { name: 'Streichen: 1.jpg' })
    expect(decide).toHaveFocus()
    expect(screen.getByLabelText('Vorschlag')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /gestrichen –/ })).toBeNull()
  })

  it('shows the server reason at the tile and keeps the focus on the trigger when striking fails', async () => {
    const user = userEvent.setup()
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockRejectedValueOnce(new ApiError(409, 'Gerade verändert.'))

    const button = await screen.findByRole('button', { name: 'Streichen: 1.jpg' })
    await user.click(button)

    expect(await screen.findByRole('alert')).toHaveTextContent('Gerade verändert.')
    expect(screen.getByRole('button', { name: 'Streichen: 1.jpg' })).toHaveFocus()
  })
})

describe('AlbumDraftPage: Tauschen und Hinzufügen', () => {
  it('exchanges from the band, hides the replaced photo and undoes the exchange in one call', async () => {
    const user = userEvent.setup()
    const candidate = photo(3, { ranking: ranking(false) })
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({ items: [candidate], total: 1 })
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(3, 'album_worthy'),
      struck: written(1, 'rejected'),
    })

    const trigger = await screen.findByRole('button', { name: 'Alternativen: 1.jpg' })
    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await user.click(await screen.findByRole('button', { name: 'Tauschen: 3.jpg' }))

    expect(photosApi.exchangeDraftPhoto).toHaveBeenCalledWith(1, 3, 1)
    expect(await screen.findByRole('button', { name: 'Streichen: 3.jpg' })).toHaveFocus()
    expect(screen.queryByRole('button', { name: 'Streichen: 1.jpg' })).toBeNull()
    expect(screen.getByText('Getauscht')).toBeInTheDocument()

    vi.mocked(photosApi.undoDraftExchange).mockResolvedValueOnce({
      photo: written(3, null),
      replaced: written(1, null),
    })
    await user.click(screen.getByRole('button', { name: 'Rückgängig' }))

    expect(photosApi.undoDraftExchange).toHaveBeenCalledWith(1, {
      photo_id: 3,
      replaced_photo_id: 1,
      photo_previous_status: null,
      replaced_previous_status: null,
    })
    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toHaveFocus()
    expect(screen.queryByRole('button', { name: 'Streichen: 3.jpg' })).toBeNull()
  })

  it('keeps the notice with the server reason when undoing an exchange is refused', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) })],
      total: 1,
    })
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(3, 'album_worthy'),
      struck: written(1, 'rejected'),
    })
    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    await user.click(await screen.findByRole('button', { name: 'Tauschen: 3.jpg' }))
    vi.mocked(photosApi.undoDraftExchange).mockRejectedValueOnce(
      new ApiError(409, 'Nicht mehr möglich.'),
    )

    await user.click(await screen.findByRole('button', { name: 'Rückgängig' }))

    expect(await screen.findByText('Nicht mehr möglich.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: 3.jpg' })).toBeInTheDocument()
  })

  it('adds a struck proposed photo as "Aufgenommen" in an empty event, beyond the target, without asking', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ effective_selection_target: 0 }),
    )
    const struck = photo(4, { event: EVENT_B, ratings: own('rejected') })
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({ items: [struck], total: 1 })
    renderPage({ events: [EVENT_A, EVENT_B], items: [photo(1), struck] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'album_worthy'))

    await user.click(await screen.findByRole('button', { name: /^Foto hinzufügen: .*Lyon/ }))
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 4.jpg' }))

    expect(ratingsApi.setRating).toHaveBeenCalledWith(4, 'album_worthy')
    const tile = (await screen.findByRole('button', { name: 'Streichen: 4.jpg' })).closest('li')!
    expect(within(tile).getByLabelText('Aufgenommen')).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_EMPTY_EVENT_TEXT)).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
