import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { UserEvent } from '@testing-library/user-event'
import type { ReactNode } from 'react'
import type { InitialEntry, Location, NavigateFunction } from 'react-router'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router'
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
  PersonOut,
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

/** `draft: null` lässt den Abruf so, wie der Fall ihn vorher eingerichtet hat (Laden, Fehler). */
function renderPage(
  draft: AlbumDraftOut | null,
  observer?: ObserverFactory,
  path = '/projects/1/album',
) {
  if (draft !== null) {
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draft)
  }
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[path]}>
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

  it('shows the empty state only for a run without events, the cloud consent text first', async () => {
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

  it('undo brings back a taken photo without a ranking row that striking took out of the draft', async () => {
    // Ohne Rangzeile verlässt ein gestrichenes Foto die Antwortmenge - das Rückgängig muss es
    // wieder einfügen, nicht nur einen vorhandenen Eintrag fortschreiben.
    const user = userEvent.setup()
    renderPage(
      {
        events: [EVENT_A],
        items: [photo(1, { ratings: own('album_worthy'), ranking: null }), photo(2)],
      },
      noObserver,
    )
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'rejected'))
    await user.click(await screen.findByRole('button', { name: 'Streichen: 1.jpg' }))
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Streichen: 1.jpg' })).toBeNull(),
    )
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'album_worthy'))

    await user.click(screen.getByRole('button', { name: 'Rückgängig' }))

    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toHaveFocus()
    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
  })

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

describe('AlbumDraftPage: Fehlerfall je Handgriff', () => {
  it('keeps both photos and the band open when the exchange is refused', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) })],
      total: 1,
    })
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(photosApi.exchangeDraftPhoto).mockRejectedValueOnce(
      new ApiError(409, 'Schon vergeben.'),
    )

    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    await user.click(await screen.findByRole('button', { name: 'Tauschen: 3.jpg' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Schon vergeben.')
    expect(screen.getByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tauschen: 3.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rückgängig' })).toBeNull()
  })

  it('shows the reason in the panel and adds nothing when adding is refused', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(5, { event: EVENT_B, ranking: ranking(false) })],
      total: 1,
    })
    renderPage({ events: [EVENT_A, EVENT_B], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockRejectedValueOnce(new ApiError(409, 'Nicht mehr da.'))

    await user.click(await screen.findByRole('button', { name: /^Foto hinzufügen: .*Lyon/ }))
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 5.jpg' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Nicht mehr da.')
    expect(screen.queryByRole('button', { name: 'Streichen: 5.jpg' })).toBeNull()
    expect(screen.getByText(DRAFT_EMPTY_EVENT_TEXT)).toBeInTheDocument()
  })

  it('keeps the struck photo in the struck row when re-adding is refused', async () => {
    const user = userEvent.setup()
    renderPage(
      { events: [EVENT_A], items: [photo(1, { ratings: own('rejected') }), photo(2)] },
      noObserver,
    )
    vi.mocked(ratingsApi.deleteRating).mockRejectedValueOnce(new ApiError(409, 'Gesperrt.'))

    await user.click(await screen.findByRole('button', { name: '1 gestrichen – anzeigen' }))
    await user.click(screen.getByRole('button', { name: 'Wieder aufnehmen: 1.jpg' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Gesperrt.')
    expect(screen.getByRole('button', { name: 'Wieder aufnehmen: 1.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Streichen: 1.jpg' })).toBeNull()
  })

  it('keeps the notice with the server reason instead of the button when undoing a strike fails', async () => {
    const user = userEvent.setup()
    renderPage({ events: [EVENT_A], items: [photo(1), photo(2)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'rejected'))
    await user.click(await screen.findByRole('button', { name: 'Streichen: 1.jpg' }))
    vi.mocked(ratingsApi.deleteRating).mockRejectedValueOnce(
      new ApiError(409, 'Inzwischen geändert.'),
    )

    await user.click(await screen.findByRole('button', { name: 'Rückgängig' }))

    expect(await screen.findByText('Inzwischen geändert.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rückgängig' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Streichen: 1.jpg' })).toBeNull()
  })
})

describe('AlbumDraftPage: Fokus-Sonderfälle', () => {
  it('moves the focus to the previous tile when the last tile of an event is struck', async () => {
    const user = userEvent.setup()
    renderPage({ events: [EVENT_A], items: [photo(1), photo(2)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(2, 'rejected'))

    await user.click(await screen.findByRole('button', { name: 'Streichen: 2.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Streichen: 1.jpg' })).toHaveFocus(),
    )
  })

  it.each([
    [
      'Schließen',
      async (user: UserEvent) => {
        await user.click(screen.getByRole('button', { name: 'Schließen' }))
      },
    ],
    [
      'Esc',
      async (user: UserEvent) => {
        await user.keyboard('{Escape}')
      },
    ],
  ])('focuses the band heading on opening and returns to the trigger via %s', async (_, close) => {
    const user = userEvent.setup()
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    const trigger = await screen.findByRole('button', { name: 'Alternativen: 1.jpg' })

    await user.click(trigger)
    expect(
      await screen.findByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' }),
    ).toHaveFocus()
    await close(user)

    expect(trigger).toHaveFocus()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('moves the focus along the panel after adding, and to its heading once it is empty', async () => {
    const user = userEvent.setup()
    const candidates = [
      photo(5, { event: EVENT_B, ranking: ranking(false) }),
      photo(6, { event: EVENT_B, ranking: ranking(false) }),
    ]
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({ items: candidates, total: 2 })
    renderPage({ events: [EVENT_A, EVENT_B], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating)
      .mockResolvedValueOnce(written(5, 'album_worthy'))
      .mockResolvedValueOnce(written(6, 'album_worthy'))

    const trigger = await screen.findByRole('button', { name: /^Foto hinzufügen: .*Lyon/ })
    await user.click(trigger)
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 5.jpg' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Hinzufügen: 6.jpg' })).toHaveFocus(),
    )

    await user.click(screen.getByRole('button', { name: 'Hinzufügen: 6.jpg' }))
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 4, name: /^Foto zu .*Lyon.* hinzufügen$/ }),
      ).toHaveFocus(),
    )

    await user.click(screen.getByRole('button', { name: 'Schließen' }))
    expect(trigger).toHaveFocus()
  })

  it('moves the focus to the next struck tile after re-adding', async () => {
    const user = userEvent.setup()
    renderPage(
      {
        events: [EVENT_A],
        items: [
          photo(1, { ratings: own('rejected') }),
          photo(2, { ratings: own('rejected') }),
          photo(3),
        ],
      },
      noObserver,
    )
    vi.mocked(ratingsApi.deleteRating).mockResolvedValueOnce(written(1, null))

    await user.click(await screen.findByRole('button', { name: '2 gestrichen – anzeigen' }))
    await user.click(screen.getByRole('button', { name: 'Wieder aufnehmen: 1.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Wieder aufnehmen: 2.jpg' })).toHaveFocus(),
    )
    expect(document.activeElement).not.toBe(document.body)
  })
})

describe('AlbumDraftPage: Personenfilter', () => {
  const anna: PersonOut = { id: 1, name: 'Anna', reference_count: 2 }
  const ben: PersonOut = { id: 2, name: 'Ben', reference_count: 2 }
  const withAnna = photo(1, { persons: [{ person_id: 1, origin: 'recognized', face: null }] })
  const nobody = photo(2)
  const struckNobody = photo(4, { ratings: own('rejected') })
  const withBen = photo(3, {
    event: EVENT_B,
    taken_at: '2026-07-21T10:03:00',
    persons: [{ person_id: 2, origin: 'corrected', face: null }],
  })
  const draft: AlbumDraftOut = {
    events: [EVENT_A, EVENT_B],
    items: [withAnna, nobody, struckNobody, withBen],
  }

  beforeEach(() => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([anna, ben])
  })

  it('counts the whole draft in the head and keeps every section standing', async () => {
    renderPage(draft, noObserver, '/projects/1/album?person=1')

    expect(await screen.findByText('1 von 3 Fotos des Entwurfs sichtbar.')).toHaveAttribute(
      'role',
      'status',
    )
    expect(
      screen.getByText('3 im Album · Richtwert etwa 3 · 0 aufgenommen · 1 gestrichen'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Streichen: 2.jpg' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Streichen: 3.jpg' })).toBeNull()
    // Beide Eventabschnitte bleiben stehen - auch der, in dem der Filter alles verbirgt.
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(2)
    expect(screen.getByRole('button', { name: /^Foto hinzufügen: .*Lyon/ })).toBeInTheDocument()
  })

  it('filters neither the struck row nor the add panel nor the band', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(5, { ranking: ranking(false) })],
      total: 1,
    })
    renderPage(draft, noObserver, '/projects/1/album?person=1')

    await user.click(await screen.findByRole('button', { name: '1 gestrichen – anzeigen' }))
    expect(screen.getByRole('button', { name: 'Wieder aufnehmen: 4.jpg' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Alternativen: 1.jpg' }))
    expect(await screen.findByRole('button', { name: 'Tauschen: 5.jpg' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Foto hinzufügen: .*Paris/ }))
    expect(await screen.findByRole('button', { name: 'Hinzufügen: 5.jpg' })).toBeInTheDocument()
  })

  it('focuses the heading and says so when the exchanged photo is hidden by the filter', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(5, { ranking: ranking(false) })],
      total: 1,
    })
    renderPage(draft, noObserver, '/projects/1/album?person=1')
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(5, 'album_worthy'),
      struck: written(1, 'rejected'),
    })

    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    await user.click(await screen.findByRole('button', { name: 'Tauschen: 5.jpg' }))

    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveFocus())
    expect(
      screen.getByText('Das eingetauschte Foto ist durch den Filter ausgeblendet.'),
    ).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('button', { name: 'Streichen: 5.jpg' })).toBeNull()
  })

  it('neither writes nor reloads the draft when the filter changes', async () => {
    const user = userEvent.setup()
    renderPage(draft, noObserver)
    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })

    await user.click(await screen.findByRole('button', { name: 'Anna' }))
    await user.click(screen.getByRole('button', { name: 'Beide: Anna und Ben' }))
    await user.click(screen.getByRole('button', { name: 'Alle' }))

    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
    expect(personsApi.setPhotoPerson).not.toHaveBeenCalled()
  })
})

describe('AlbumDraftPage: Zustände und Fremdtext', () => {
  it('shows a skeleton grid while loading', () => {
    vi.mocked(photosApi.getAlbumDraft).mockReturnValue(new Promise(() => {}))
    renderPage(null, noObserver)

    expect(screen.getByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
  })

  it('shows an error alert whose retry triggers exactly one new request', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.getAlbumDraft).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    renderPage(null, noObserver)

    expect(await screen.findByText('Serverfehler')).toBeInTheDocument()
    const before = vi.mocked(photosApi.getAlbumDraft).mock.calls.length
    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

    await waitFor(() =>
      expect(vi.mocked(photosApi.getAlbumDraft).mock.calls.length).toBe(before + 1),
    )
  })

  it('strikes one photo while the decision on another is still running', async () => {
    // Die Sperre gilt je Foto: ein zweiter Druck auf ein ANDERES Foto verpufft nicht.
    const user = userEvent.setup()
    renderPage({ events: [EVENT_A], items: [photo(1), photo(2)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockImplementation((photoId) =>
      photoId === 1 ? new Promise(() => {}) : Promise.resolve(written(photoId, 'rejected')),
    )

    await user.click(await screen.findByRole('button', { name: 'Streichen: 1.jpg' }))
    await user.click(screen.getByRole('button', { name: 'Streichen: 2.jpg' }))

    await waitFor(() => expect(ratingsApi.setRating).toHaveBeenCalledWith(2, 'rejected'))
  })

  it('drops a motif from the event line as soon as its last carrier is struck', async () => {
    const user = userEvent.setup()
    const assessed = {
      source: 'cloud' as const,
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2026-07-21T09:00:00',
    }
    const motifsWith = (present: string[]) =>
      MOTIF_SET.items.map((item) => ({
        key: item.key,
        strength: 0.5,
        correction: null,
        present: present.includes(item.key),
      }))
    renderPage(
      {
        events: [EVENT_A],
        items: [
          photo(1, { motif_assessment: assessed, motifs: motifsWith(['menschen']) }),
          photo(2, { motif_assessment: assessed, motifs: motifsWith(['tiere']) }),
        ],
      },
      noObserver,
    )
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(2, 'rejected'))
    await screen.findByText('Menschen, Tiere')

    await user.click(screen.getByRole('button', { name: 'Streichen: 2.jpg' }))

    expect(await screen.findByText('Menschen')).toBeInTheDocument()
    expect(screen.queryByText('Menschen, Tiere')).toBeNull()
  })

  /*
   * Spec 0434 S8 / Spec 0514 S1: `place_name` und `landmark_name` sind freier Fremdtext und
   * erscheinen ausschließlich als React-Textknoten. Der Nachweis gehört an die Rendering-Stelle.
   */
  const hostile = '<img src=x onerror="window.__pwned = true">'

  it('renders a hostile landmark and place name as ONE text node, never as markup', async () => {
    renderPage(
      {
        events: [
          {
            ...EVENT_A,
            place: { kind: 'landmark', landmark_name: hostile, lat: null, lon: null },
            place_name: hostile,
          },
        ],
        items: [photo(1)],
      },
      noObserver,
    )

    const heading = await screen.findByRole('heading', { level: 3 })
    expect(heading.textContent).toBe(`${hostile}, ${hostile} (10:00–11:00 Uhr)`)
    expect(heading.childNodes).toHaveLength(1)
    expect(heading.childNodes[0]?.nodeType).toBe(Node.TEXT_NODE)
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
  })

  it('renders a hostile person name in the filter group as plain text', async () => {
    vi.mocked(personsApi.listPersons).mockResolvedValue([
      { id: 1, name: hostile, reference_count: 2 },
      { id: 2, name: 'Ben', reference_count: 2 },
    ])
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)

    const group = await screen.findByRole('group', { name: 'Personen' })
    expect(within(group).getByRole('button', { name: hostile })).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
  })
})

/*
 * specs/features/0531-kuratierung-grossansicht.md - die Großansicht in der Seite, unverändert seit
 * Spec 0558. Vor der Seite liegt eine Stub-Route als Verlaufssonde: Jeder Fall endet mit einem
 * Zurück, das dort ankommen muss - so fällt ein verwaister oder überzähliger Verlaufseintrag auf.
 * Geöffnet wird über `fireEvent.click`, das (wie Safari) den Button NICHT fokussiert.
 */
describe('AlbumDraftPage: Großansicht', () => {
  const probe: { location?: Location; navigate?: NavigateFunction } = {}

  function Probe() {
    probe.location = useLocation()
    probe.navigate = useNavigate()
    return null
  }

  function renderWithHistory(
    draft: AlbumDraftOut | null,
    entry: InitialEntry = '/projects/1/album',
  ) {
    if (draft !== null) {
      vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draft)
    }
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/stub', entry]} initialIndex={1}>
          <Probe />
          <Routes>
            <Route path="/stub" element={<p>Stub</p>} />
            <Route
              path="/projects/:projectId/album"
              element={<AlbumDraftPage createPositionObserver={noObserver} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    return queryClient
  }

  function back(): void {
    act(() => {
      void probe.navigate!(-1)
    })
  }

  function writeCalls(): number {
    return (
      vi.mocked(ratingsApi.setRating).mock.calls.length +
      vi.mocked(ratingsApi.deleteRating).mock.calls.length +
      vi.mocked(ratingsApi.setFavorite).mock.calls.length +
      vi.mocked(photosApi.exchangeDraftPhoto).mock.calls.length +
      vi.mocked(photosApi.undoDraftExchange).mock.calls.length +
      vi.mocked(photosApi.setMotifCorrection).mock.calls.length +
      vi.mocked(photosApi.deleteMotifCorrection).mock.calls.length
    )
  }

  const twoPhotos: AlbumDraftOut = {
    events: [EVENT_A],
    items: [photo(1, { relative_path: 'reise/a.jpg' }), photo(2, { relative_path: 'reise/b.jpg' })],
  }

  const closeWays: [string, () => void][] = [
    ['Schließen', () => fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))],
    ['Escape', () => fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })],
    [
      'Klick neben das Bild',
      () => {
        const stage = screen.getByTestId('lightbox-stage')
        fireEvent.pointerDown(stage)
        fireEvent.click(stage)
      },
    ],
    ['Browser-Zurück', back],
  ]

  it.each(closeWays)(
    'opens exactly the clicked photo and closes via %s back to the same place',
    async (_, closeLightbox) => {
      renderWithHistory(twoPhotos)
      const trigger = await screen.findByRole('button', { name: 'Großansicht: reise/b.jpg' })

      fireEvent.click(trigger)

      expect(screen.getByRole('dialog', { name: 'b.jpg' })).toBeInTheDocument()
      expect(probe.location).toMatchObject({
        pathname: '/projects/1/album',
        state: { grossansicht: 2 },
      })

      closeLightbox()

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(trigger).toHaveFocus()
      expect(trigger.isConnected).toBe(true)
      expect(screen.getByRole('button', { name: 'Streichen: reise/b.jpg' })).toBeInTheDocument()
      expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
      expect(writeCalls()).toBe(0)
      expect(probe.location).toMatchObject({ pathname: '/projects/1/album', state: null })
      back()
      expect(probe.location?.pathname).toBe('/stub')
    },
  )

  it('starts with collapsed details on every opening', async () => {
    renderWithHistory(twoPhotos)

    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/a.jpg' }))
    fireEvent.click(screen.getByRole('button', { name: 'Details' }))
    fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Großansicht: reise/b.jpg' }))

    expect(screen.getByRole('button', { name: 'Details' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('reopens the photo after a reload once the draft has loaded', async () => {
    let resolveDraft: (draft: AlbumDraftOut) => void = () => {}
    vi.mocked(photosApi.getAlbumDraft).mockReturnValue(
      new Promise((resolve) => {
        resolveDraft = resolve
      }),
    )
    renderWithHistory(null, { pathname: '/projects/1/album', state: { grossansicht: 2 } })

    await screen.findByRole('status', { name: 'Fotos werden geladen…' })
    expect(probe.location?.state).toEqual({ grossansicht: 2 })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await act(async () => {
      resolveDraft(twoPhotos)
    })

    expect(await screen.findByRole('dialog', { name: 'b.jpg' })).toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.getByRole('button', { name: 'Großansicht: reise/b.jpg' })).toHaveFocus()
    expect(probe.location?.state).toBeNull()
    back()
    expect(probe.location?.pathname).toBe('/stub')
  })

  it('shows nothing and clears the entry when the reloaded photo is not in the draft', async () => {
    renderWithHistory(twoPhotos, { pathname: '/projects/1/album', state: { grossansicht: 99 } })

    await screen.findByRole('button', { name: 'Großansicht: reise/a.jpg' })

    await waitFor(() => expect(probe.location?.state).toBeNull())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(photosApi.fetchPhotoImageBlobUrl).not.toHaveBeenCalledWith(99, 'display')
    back()
    expect(probe.location?.pathname).toBe('/stub')
  })

  it('closes without a leftover entry and focuses the heading when the photo disappears', async () => {
    const queryClient = renderWithHistory(twoPhotos)
    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/b.jpg' }))
    expect(screen.getByRole('dialog', { name: 'b.jpg' })).toBeInTheDocument()

    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue({
      events: [EVENT_A],
      items: [photo(1, { relative_path: 'reise/a.jpg' })],
    })
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ['photos', 1] })
    })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: 'Album-Entwurf' })).toHaveFocus(),
    )
    expect(probe.location?.state).toBeNull()
    back()
    expect(probe.location?.pathname).toBe('/stub')
  })

  it('has no link in the large view', async () => {
    renderWithHistory(twoPhotos)

    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/a.jpg' }))

    expect(within(screen.getByRole('dialog')).queryAllByRole('link')).toEqual([])
  })
})
