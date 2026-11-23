/*
 * Entwurfsseite - Teil: Alternativenband, Fehlerfaelle und Fokus-Sonderfaelle (Spec 0651; gemeinsamer Unterbau in src/test/albumDraftPage.tsx).
 */
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { UserEvent } from '@testing-library/user-event'
import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { EventOut, RatingWriteOut } from '../api/types'
import { DRAFT_EMPTY_EVENT_TEXT } from '../components/DraftEventSection'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  EVENT_A,
  EVENT_B,
  ranking,
  photo,
  own,
  written,
  renderPage,
  noObserver,
  NO_POSITION,
  resetAlbumDraftMocks,
} from '../test/albumDraftPage'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/motifs')
vi.mock('../api/persons')

beforeEach(() => {
  resetAlbumDraftMocks()
})

describe('AlbumDraftPage: Hinzufügen und Tauschen aus dem Band', () => {
  const alternativesOf = (...ids: number[]) => ({
    items: ids.map((photoId) => photo(photoId, { ranking: ranking(false) })),
    total: ids.length,
    ...NO_POSITION,
  })

  async function openBand(user: UserEvent) {
    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    await screen.findByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' })
  }

  it('adds from the band with one PUT and keeps the band open, the reference untouched', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesOf(3, 4, 5))
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'album_worthy'))

    await openBand(user)
    expect(screen.getByText(/^1 im Album · Richtwert etwa 3/)).toBeInTheDocument()
    const calls = vi.mocked(photosApi.listDraftAlternatives).mock.calls.length
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 4.jpg' }))

    expect(ratingsApi.setRating).toHaveBeenCalledTimes(1)
    expect(ratingsApi.setRating).toHaveBeenCalledWith(4, 'album_worthy')
    const tile = (await screen.findByRole('button', { name: 'Streichen: 4.jpg' })).closest('li')!
    // 4 war nicht vorgeschlagen: Das Zeichen nennt das im Namen.
    expect(within(tile).getByLabelText('Aufgenommen, nicht vorgeschlagen')).toBeInTheDocument()
    expect(screen.getByText(/^2 im Album · Richtwert etwa 3 · 1 aufgenommen/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Hinzufügen: 4.jpg' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Hinzufügen: 3.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Hinzufügen: 5.jpg' })).toHaveFocus(),
    )
    expect(screen.queryByRole('button', { name: 'Rückgängig' })).toBeNull()
    // Kein Nachrücken: nichts wird nachgeladen.
    expect(vi.mocked(photosApi.listDraftAlternatives).mock.calls.length).toBe(calls)
  })

  it('moves the focus to the previous alternative, then to the band heading', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesOf(3, 4))
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating)
      .mockResolvedValueOnce(written(4, 'album_worthy'))
      .mockResolvedValueOnce(written(3, 'album_worthy'))

    await openBand(user)
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 4.jpg' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Hinzufügen: 3.jpg' })).toHaveFocus(),
    )
    await user.click(screen.getByRole('button', { name: 'Hinzufügen: 3.jpg' }))
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' }),
      ).toHaveFocus(),
    )
    // Liste leer: Leertext, Umschalter und „Schließen" bleiben.
    expect(screen.getByText('Keine weiteren Fotos in diesem Event.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Alle Fotos des Events' })).toBeInTheDocument()
  })

  it('adds a struck alternative as "Aufgenommen" and ends an open "Getauscht" notice', async () => {
    const user = userEvent.setup()
    const struck = photo(4, { ratings: own('rejected') })
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) }), struck],
      total: 2,
      ...NO_POSITION,
    })
    renderPage({ events: [EVENT_A], items: [photo(1), photo(2), struck] }, noObserver)
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(3, 'album_worthy'),
      struck: written(2, 'rejected'),
    })
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'album_worthy'))

    await user.click(await screen.findByRole('button', { name: 'Alternativen: 2.jpg' }))
    await user.click(await screen.findByRole('button', { name: 'Tauschen: 3.jpg' }))
    expect(await screen.findByText('Getauscht')).toBeInTheDocument()
    await openBand(user)
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 4.jpg' }))

    const tile = (await screen.findByRole('button', { name: 'Streichen: 4.jpg' })).closest('li')!
    expect(within(tile).getByLabelText('Aufgenommen')).toBeInTheDocument()
    expect(screen.queryByText('Getauscht')).toBeNull()
  })

  it('replaces the reference after two additions, and undo takes back only the exchange', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesOf(3, 4, 5))
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating)
      .mockResolvedValueOnce(written(3, 'album_worthy'))
      .mockResolvedValueOnce(written(4, 'album_worthy'))
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(5, 'album_worthy'),
      struck: written(1, 'rejected'),
    })

    await openBand(user)
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 3.jpg' }))
    await screen.findByRole('button', { name: 'Streichen: 3.jpg' })
    await user.click(screen.getByRole('button', { name: 'Hinzufügen: 4.jpg' }))
    await screen.findByRole('button', { name: 'Streichen: 4.jpg' })
    await user.click(screen.getByRole('button', { name: 'Tauschen: 5.jpg' }))

    expect(photosApi.exchangeDraftPhoto).toHaveBeenCalledWith(1, 5, 1)
    expect(await screen.findByText('Getauscht')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Streichen: 1.jpg' })).toBeNull()

    vi.mocked(photosApi.undoDraftExchange).mockResolvedValueOnce({
      photo: written(5, null),
      replaced: written(1, null),
    })
    await user.click(screen.getByRole('button', { name: 'Rückgängig' }))

    expect(photosApi.undoDraftExchange).toHaveBeenCalledWith(1, {
      photo_id: 5,
      replaced_photo_id: 1,
      photo_previous_status: null,
      replaced_previous_status: null,
    })
    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: 3.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Streichen: 4.jpg' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Streichen: 5.jpg' })).toBeNull()
  })

  it('adds and exchanges from the expanded row just like from the band', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockImplementation(async (_projectId, params) =>
      params.series === true ? alternativesOf(3) : alternativesOf(3, 4, 5),
    )
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'album_worthy'))
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(5, 'album_worthy'),
      struck: written(1, 'rejected'),
    })

    await openBand(user)
    const toggle = await screen.findByRole('button', { name: 'Alle Fotos des Events' })
    await user.click(toggle)
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 4.jpg' }))

    expect(ratingsApi.setRating).toHaveBeenCalledWith(4, 'album_worthy')
    await screen.findByRole('button', { name: 'Streichen: 4.jpg' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.queryByRole('button', { name: 'Hinzufügen: 4.jpg' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Tauschen: 5.jpg' }))
    expect(await screen.findByText('Getauscht')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Weniger anzeigen' })).toBeNull()
    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })

  /** Ein Server, dessen Restmenge nach jedem Hinzufügen tatsächlich schrumpft: Seiten werden
   * aus der AKTUELLEN Restmenge geschnitten, wie es der Endpunkt tut. */
  function shrinkingServer(ids: number[], event: EventOut) {
    const taken = new Set<number>()
    vi.mocked(photosApi.listDraftAlternatives).mockImplementation(async (_projectId, params) => {
      const rest = ids.filter((photoId) => !taken.has(photoId))
      const items =
        params.series === true
          ? rest.slice(0, 4)
          : rest.slice(params.offset ?? 0, (params.offset ?? 0) + (params.limit ?? 60))
      return {
        items: items.map((photoId) => photo(photoId, { event, ranking: ranking(false) })),
        total: rest.length,
        offset: params.series === true ? 0 : (params.offset ?? 0),
        reference_index: null,
        series_rest: 0,
      }
    })
    vi.mocked(ratingsApi.setRating).mockImplementation(async (photoId) => {
      taken.add(photoId)
      return written(photoId, 'album_worthy')
    })
  }

  function shownAddNames(): string[] {
    return screen
      .getAllByRole('button', { name: /^Hinzufügen: / })
      .map((button) => button.getAttribute('aria-label')!)
  }

  it('loses and doubles no photo when loading more after adding in the expanded row', async () => {
    const user = userEvent.setup()
    const ids = Array.from({ length: 62 }, (_, index) => 100 + index)
    shrinkingServer(ids, EVENT_A)
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)

    await openBand(user)
    await user.click(await screen.findByRole('button', { name: 'Alle Fotos des Events' }))
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 100.jpg' }))
    await screen.findByRole('button', { name: 'Streichen: 100.jpg' })
    await user.click(screen.getByRole('button', { name: 'Weitere Fotos' }))

    await screen.findByRole('button', { name: 'Hinzufügen: 161.jpg' })
    expect(shownAddNames()).toEqual(ids.slice(1).map((photoId) => `Hinzufügen: ${photoId}.jpg`))
    expect(screen.queryByRole('button', { name: 'Weitere Fotos' })).toBeNull()
  })

  it('loses and doubles no photo when loading more after adding in the add panel', async () => {
    const user = userEvent.setup()
    const ids = Array.from({ length: 10 }, (_, index) => 200 + index)
    shrinkingServer(ids, EVENT_B)
    renderPage({ events: [EVENT_A, EVENT_B], items: [photo(1)] }, noObserver)

    await user.click(await screen.findByRole('button', { name: /^Foto hinzufügen: .*Lyon/ }))
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 203.jpg' }))
    await screen.findByRole('button', { name: 'Streichen: 203.jpg' })
    await user.click(screen.getByRole('button', { name: 'Weitere Fotos' }))

    await screen.findByRole('button', { name: 'Hinzufügen: 209.jpg' })
    expect(shownAddNames()).toEqual(
      ids.filter((photoId) => photoId !== 203).map((photoId) => `Hinzufügen: ${photoId}.jpg`),
    )
    expect(screen.queryByRole('button', { name: 'Weitere Fotos' })).toBeNull()
  })

  it('keeps error, lock and focus per call when two additions overlap and the first fails', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesOf(3, 4, 5))
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    // `Promise.withResolvers` liegt jenseits der Bibliothek ES2023 dieses Projekts.
    let failFirst: (error: unknown) => void = () => {}
    let resolveSecond: (value: RatingWriteOut) => void = () => {}
    vi.mocked(ratingsApi.setRating)
      .mockReturnValueOnce(
        new Promise((_, reject) => {
          failFirst = reject
        }),
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSecond = resolve
        }),
      )

    await openBand(user)
    const addThree = await screen.findByRole('button', { name: 'Hinzufügen: 3.jpg' })
    await user.click(addThree)
    await user.click(screen.getByRole('button', { name: 'Hinzufügen: 4.jpg' }))
    await act(async () => {
      failFirst(new ApiError(409, 'Nicht mehr da.'))
      resolveSecond(written(4, 'album_worthy'))
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Nicht mehr da.')
    expect(await screen.findByRole('button', { name: 'Streichen: 4.jpg' })).toBeInTheDocument()
    await waitFor(() => expect(addThree).toBeEnabled())
    expect(screen.queryByRole('button', { name: 'Streichen: 3.jpg' })).toBeNull()
  })

  it('loads the band fresh once after closing and reopening', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesOf(3, 4))
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(3, 'album_worthy'))

    await openBand(user)
    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: 3.jpg' }))
    await screen.findByRole('button', { name: 'Streichen: 3.jpg' })
    const calls = vi.mocked(photosApi.listDraftAlternatives).mock.calls.length
    await user.click(screen.getByRole('button', { name: 'Schließen' }))
    await openBand(user)

    await waitFor(() =>
      expect(vi.mocked(photosApi.listDraftAlternatives).mock.calls.length).toBe(calls + 1),
    )
  })
})

describe('AlbumDraftPage: Fehlerfall je Handgriff', () => {
  it('shows a refused addition from the band inside the band and keeps it open', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) })],
      total: 1,
      ...NO_POSITION,
    })
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(ratingsApi.setRating).mockRejectedValueOnce(new ApiError(409, 'Nicht mehr da.'))

    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    const add = await screen.findByRole('button', { name: 'Hinzufügen: 3.jpg' })
    await user.click(add)

    expect(await screen.findByRole('alert')).toHaveTextContent('Nicht mehr da.')
    expect(add).toHaveFocus()
    expect(add).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Streichen: 3.jpg' })).toBeNull()
    expect(screen.getByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' })).toBeVisible()
  })

  it('shows a refused exchange from the expanded row inside the band', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) })],
      total: 1,
      ...NO_POSITION,
    })
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)
    vi.mocked(photosApi.exchangeDraftPhoto).mockRejectedValueOnce(
      new ApiError(409, 'Schon vergeben.'),
    )

    await user.click(await screen.findByRole('button', { name: 'Alternativen: 1.jpg' }))
    await user.click(await screen.findByRole('button', { name: 'Alle Fotos des Events' }))
    const choice = await screen.findByRole('button', { name: 'Tauschen: 3.jpg' })
    await user.click(choice)

    expect(await screen.findByRole('alert')).toHaveTextContent('Schon vergeben.')
    expect(choice).toHaveFocus()
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Weniger anzeigen' })).toBeInTheDocument()
  })

  it('keeps both photos and the band open when the exchange is refused', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) })],
      total: 1,
      ...NO_POSITION,
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
      ...NO_POSITION,
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
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: candidates,
      total: 2,
      ...NO_POSITION,
    })
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
