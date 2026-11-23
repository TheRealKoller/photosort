/*
 * Entwurfsseite - Teil: Streichen, Tauschen, Hinzufuegen, Kopf und Reihen (Spec 0651; gemeinsamer Unterbau in src/test/albumDraftPage.tsx).
 */
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import { DRAFT_EMPTY_EVENT_TEXT } from '../components/DraftEventSection'
import type { ObserverFactory } from '../hooks/useDraftPosition'
import { installResizeObserver } from '../test/observers'
import { DRAFT_CLOUD_CONSENT_TEXT, DRAFT_EMPTY_TEXT } from '../utils/albumDraftTexts'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  projectOut,
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

describe('AlbumDraftPage: Schaltfläche „Foto hinzufügen"', () => {
  it('is the last cell of the event, with the plus symbol and its exact accessible name', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [photo(3, { ranking: ranking(false) })],
      total: 1,
      ...NO_POSITION,
    })
    renderPage({ events: [EVENT_A], items: [photo(1), photo(2)] }, noObserver)

    const trigger = await screen.findByRole('button', { name: /^Foto hinzufügen: / })
    expect(trigger.querySelector('[data-icon="plus"]')).toHaveAttribute('aria-hidden', 'true')
    expect(trigger).not.toHaveTextContent('+')
    expect(trigger).toHaveTextContent(/^Foto hinzufügen$/)
    expect(trigger.getAttribute('aria-label')).toMatch(/^Foto hinzufügen: [^+]*$/)
    const cell = trigger.closest('li')!
    expect(cell.nextElementSibling).toBeNull()
    expect(cell.parentElement?.className).toContain('flex-wrap')

    await user.click(trigger)
    for (const button of await screen.findAllByRole('button', { name: /^Hinzufügen: / })) {
      expect(button).not.toHaveTextContent('+')
      expect(button.querySelector('[data-icon="plus"]')).not.toBeNull()
    }
  })
})

describe('AlbumDraftPage: justierte Reihen', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const landscapes = [1, 2, 3, 4].map((id) => photo(id, { aspect_ratio: 1.5 }))

  async function bandAfterOpening(width: number) {
    const user = userEvent.setup()
    const observer = installResizeObserver()
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }))
    renderPage({ events: [EVENT_A], items: landscapes }, noObserver)
    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })
    observer.resizeTo(width)
    await user.click(screen.getByRole('button', { name: 'Alternativen: 1.jpg' }))
    const heading = await screen.findByRole('heading', { level: 4, name: 'Alternativen zu 1.jpg' })
    return heading.closest('li')!
  }

  it.each([
    // 900px: zwei Querformate je Reihe (ein drittes drueckte die Reihe unter 200px).
    [900, '2.jpg'],
    // 1280px: drei Querformate je Reihe.
    [1280, '3.jpg'],
  ])(
    'puts the band as a full-width item right after the computed row at %s px',
    async (width, last) => {
      const band = await bandAfterOpening(width)

      expect(band.className).toContain('w-full')
      const previous = band.previousElementSibling
      expect(previous).toBe(
        screen.getByRole('button', { name: `Streichen: ${last}` }).closest('li'),
      )
    },
  )

  it('gives every album tile its computed width as a number', async () => {
    const observer = installResizeObserver()
    renderPage({ events: [EVENT_A], items: landscapes }, noObserver)
    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })

    observer.resizeTo(1280)

    const tile = screen.getByRole('button', { name: 'Streichen: 1.jpg' }).closest('li')!
    // (1280 - 2 * 12) / 4.5 = 279.1 hoch, ein Querformat davon 1.5-fach breit.
    expect(tile.style.width).toBe(`${Math.round(1.5 * ((1280 - 24) / 4.5))}px`)
    expect(tile.className).not.toMatch(/aspect-square|grid-cols/)
  })

  it('puts the add panel after the last row, as a full-width item', async () => {
    const user = userEvent.setup()
    const observer = installResizeObserver()
    renderPage({ events: [EVENT_A], items: landscapes }, noObserver)
    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })
    observer.resizeTo(1280)

    await user.click(screen.getByRole('button', { name: /^Foto hinzufügen: / }))
    const heading = await screen.findByRole('heading', {
      level: 4,
      name: /^Foto zu .* hinzufügen$/,
    })
    const panel = heading.closest('li')!

    expect(panel.className).toContain('w-full')
    expect(panel.previousElementSibling).toBe(
      screen.getByRole('button', { name: /^Foto hinzufügen: / }).closest('li'),
    )
  })
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

  it('adds a neutral line when the proposal stays below the target for lack of candidates', async () => {
    /* 150 ist ein Ziel, keine Obergrenze. Die Zeile ist ein Hinweis, kein Fehler - kein Alert,
     * keine Rolle, gedämpfter Text. */
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ effective_selection_target: 150 }),
    )
    // Eine dritte Rangzeile der Partition ist ein ausgeschlossenes Dokument: `partition_size` zählt
    // sie, auswahlfähig ist sie nicht. Maßgeblich ist allein `eligible_candidate_count`.
    const withExcludedDocument = { ...ranking(true), partition_size: 3 }
    renderPage(
      {
        events: [EVENT_A],
        items: [
          photo(1, { ranking: withExcludedDocument }),
          photo(2, { ranking: withExcludedDocument }),
        ],
        eligible_candidate_count: 2,
      },
      noObserver,
    )

    const line = await screen.findByText(
      'Der Vorschlag umfasst 2 Fotos statt etwa 150 – mehr auswahlfähige Fotos gibt dieses Projekt nicht her.',
    )
    expect(line).not.toHaveAttribute('role')
    expect(line.className).toContain('text-text-muted')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows no such line while candidates are left, even below the target', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ effective_selection_target: 150 }),
    )
    renderPage(
      {
        events: [EVENT_A],
        items: [photo(1), photo(2)],
        eligible_candidate_count: 40,
      },
      noObserver,
    )

    expect(
      await screen.findByText('2 im Album · Richtwert etwa 150 · 0 aufgenommen · 0 gestrichen'),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('smaller-proposal')).toBeNull()
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
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [candidate],
      total: 1,
      ...NO_POSITION,
    })
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
      ...NO_POSITION,
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
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      items: [struck],
      total: 1,
      ...NO_POSITION,
    })
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
