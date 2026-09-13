import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import type { EventOut, PhotoListOut, PhotoOut, RankingOut } from '../api/types'
import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import {
  ALTERNATIVES_ERROR_TEXT,
  ALTERNATIVES_NONE_TEXT,
  DraftAlternativesDialog,
  PREVIOUSLY_IN_ALBUM_BADGE_TEXT,
} from './DraftAlternativesDialog'

vi.mock('../api/photos')

const USERNAME = 'daniel'

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 42,
    rank_score: 0.8,
    rank_position: 1,
    proposed: false,
    partition_size: 5,
    curation_position: null,
    ...overrides,
  }
}

function eventOut(overrides: Partial<EventOut> = {}): EventOut {
  return {
    id: 42,
    position: 3,
    started_at: '2026-07-20T10:00:00',
    ended_at: '2026-07-20T11:00:00',
    place: null,
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: ranking(),
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    event: eventOut(),
    ...overrides,
  }
}

function listOut(items: PhotoOut[], total = items.length): PhotoListOut {
  return { items, total }
}

function renderDialog(
  overrides: {
    photo?: PhotoOut
    open?: boolean
    onClose?: () => void
    onChoose?: (alternative: PhotoOut) => void
    exchanging?: boolean
  } = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <DraftAlternativesDialog
      projectId={1}
      photo={overrides.photo ?? photo()}
      username={USERNAME}
      open={overrides.open ?? true}
      onClose={overrides.onClose ?? (() => {})}
      onChoose={overrides.onChoose ?? (() => {})}
      exchanging={overrides.exchanging ?? false}
    />,
    { wrapper },
  )
}

describe('DraftAlternativesDialog', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  })

  it('does not ask for anything while it is closed', async () => {
    // Geladen wird ERST BEIM OEFFNEN - eine Abfrage je geöffnetem Bild, nie eine je Kachel.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(listOut([photo({ id: 2 })]))

    renderDialog({ open: false })

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(photosApi.listDraftAlternatives).not.toHaveBeenCalled()
  })

  it('asks for the alternatives of THIS photo in THIS event once opened', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(listOut([photo({ id: 2 })]))

    renderDialog({ photo: photo({ id: 9, event: eventOut({ id: 77 }) }) })

    await waitFor(() =>
      expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
        eventId: 77,
        photoId: 9,
        limit: expect.any(Number) as number,
        offset: 0,
      }),
    )
  })

  it('carries the event name as its title', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(listOut([]))

    renderDialog({
      photo: photo({
        event: eventOut({
          place: { kind: 'landmark', landmark_name: 'Eiffelturm', lat: 48.86, lon: 2.29 },
        }),
      }),
    })

    expect(await screen.findByRole('heading', { name: /Eiffelturm/ })).toBeInTheDocument()
  })

  it('keeps the ORDER OF THE ANSWER and does not sort again', async () => {
    // Die Reihenfolge hängt an den Motiven des Bezugsbildes und entsteht im Backend. Eine zweite
    // Sortierung hier wäre eine zweite Wahrheit - und sie fiele nicht auf, weil beide plausibel
    // aussähen.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      listOut([
        photo({ id: 5, relative_path: 'e.jpg' }),
        photo({ id: 2, relative_path: 'b.jpg' }),
        photo({ id: 9, relative_path: 'i.jpg' }),
      ]),
    )

    renderDialog()

    await screen.findByRole('button', { name: 'Austauschen gegen: e.jpg' })
    const names = screen
      .getAllByRole('button', { name: /Austauschen gegen:/ })
      .map((button) => button.getAttribute('aria-label'))
    expect(names).toEqual([
      'Austauschen gegen: e.jpg',
      'Austauschen gegen: b.jpg',
      'Austauschen gegen: i.jpg',
    ])
  })

  it('shows the quality of every alternative, missing values included', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      listOut([
        photo({ id: 2, relative_path: 'b.jpg', ranking: ranking({ rank_score: 0.8 }) }),
        photo({
          id: 3,
          relative_path: 'c.jpg',
          ranking: ranking({ rank_score: null, rank_position: null }),
        }),
      ]),
    )

    renderDialog()

    expect(await screen.findByText('Gut albumtauglich')).toBeInTheDocument()
    expect(screen.getByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeInTheDocument()
  })

  it('marks a struck photo as "zuvor im Album" - and nothing else', async () => {
    // Die Umkehrbarkeit ohne eigenen Rückgängig-Knopf: Das ausgetauschte Bild steht wieder hier
    // und ist als das erkennbar, was es war.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      listOut([
        photo({
          id: 2,
          relative_path: 'b.jpg',
          ratings: [{ user_id: 7, username: USERNAME, status: 'rejected', favorite: false }],
        }),
        photo({ id: 3, relative_path: 'c.jpg' }),
      ]),
    )

    renderDialog()

    await screen.findByRole('button', { name: 'Austauschen gegen: b.jpg' })
    expect(screen.getAllByText(PREVIOUSLY_IN_ALBUM_BADGE_TEXT)).toHaveLength(1)
  })

  it('reads the own decision over the username, never over any entry of ratings[]', async () => {
    // Auflage S6: Die Streichung des ANDEREN Nutzers ist nicht die eigene - sonst trüge ein Bild
    // „zuvor im Album", das nie im eigenen Album war.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      listOut([
        photo({
          id: 2,
          relative_path: 'b.jpg',
          ratings: [{ user_id: 8, username: 'someone-else', status: 'rejected', favorite: false }],
        }),
      ]),
    )

    renderDialog()

    await screen.findByRole('button', { name: 'Austauschen gegen: b.jpg' })
    expect(screen.queryByText(PREVIOUSLY_IN_ALBUM_BADGE_TEXT)).toBeNull()
  })

  it('hands the chosen alternative to its caller on the first press', async () => {
    const chosen = photo({ id: 2, relative_path: 'b.jpg' })
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(listOut([chosen]))
    const onChoose = vi.fn()
    const user = userEvent.setup()

    renderDialog({ onChoose })

    await user.click(await screen.findByRole('button', { name: 'Austauschen gegen: b.jpg' }))

    expect(onChoose).toHaveBeenCalledWith(chosen)
  })

  it('takes no second press while an exchange is running', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      listOut([photo({ id: 2, relative_path: 'b.jpg' })]),
    )
    const onChoose = vi.fn()
    const user = userEvent.setup()

    renderDialog({ onChoose, exchanging: true })

    await user.click(await screen.findByRole('button', { name: 'Austauschen gegen: b.jpg' }))

    expect(onChoose).not.toHaveBeenCalled()
  })

  it('says so when the event holds nothing else', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(listOut([]))

    renderDialog()

    expect(await screen.findByText(ALTERNATIVES_NONE_TEXT)).toBeInTheDocument()
  })

  it('shows the message of the server on a failure and retries exactly once', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockRejectedValue(new ApiError(500, 'Serverfehler.'))
    const user = userEvent.setup()

    renderDialog()

    expect(await screen.findByText('Serverfehler.')).toBeInTheDocument()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      listOut([photo({ id: 2, relative_path: 'b.jpg' })]),
    )

    await user.click(screen.getByRole('button', { name: /erneut/i }))

    expect(await screen.findByRole('button', { name: 'Austauschen gegen: b.jpg' })).toBeEnabled()
  })

  it('falls back to a generic message for a failure without a server text', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockRejectedValue(new Error('boom'))

    renderDialog()

    expect(await screen.findByText(ALTERNATIVES_ERROR_TEXT)).toBeInTheDocument()
  })

  it('shows a skeleton while loading, and no empty state', () => {
    // Der Leerzustand während des Ladens wäre eine Aussage über einen Stand, den es noch nicht
    // gibt - „keine Alternativen" und „noch nicht geladen" sind zwei Zustände.
    vi.mocked(photosApi.listDraftAlternatives).mockReturnValue(new Promise(() => {}))

    renderDialog()

    expect(screen.getByRole('status', { name: /Alternativen werden geladen/ })).toBeInTheDocument()
    expect(screen.queryByText(ALTERNATIVES_NONE_TEXT)).toBeNull()
  })

  it('loads the next page on demand and stops at the remaining count', async () => {
    vi.mocked(photosApi.listDraftAlternatives)
      .mockResolvedValueOnce(listOut([photo({ id: 2, relative_path: 'b.jpg' })], 2))
      .mockResolvedValueOnce(listOut([photo({ id: 3, relative_path: 'c.jpg' })], 2))
    const user = userEvent.setup()

    renderDialog()

    await user.click(await screen.findByRole('button', { name: /Weitere Alternativen/ }))

    expect(await screen.findByRole('button', { name: 'Austauschen gegen: c.jpg' })).toBeEnabled()
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Weitere Alternativen/ })).toBeNull(),
    )
  })

  it('asks for nothing when the photo carries no event', async () => {
    // Ohne Event ist kein Event adressiert; der Endpunkt verlangt beide Schlüssel. Die
    // Ausfallrichtung ist „nichts anbieten", nie eine Anfrage auf gut Glück.
    renderDialog({ photo: photo({ event: null }) })

    expect(await screen.findByText(ALTERNATIVES_NONE_TEXT)).toBeInTheDocument()
    expect(photosApi.listDraftAlternatives).not.toHaveBeenCalled()
  })
})
