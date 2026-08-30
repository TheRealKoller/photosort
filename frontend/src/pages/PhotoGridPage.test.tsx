import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import type { CriterionScoreOut, PhotoListOut, PhotoOut, SuggestionOut } from '../api/types'
import { setToken } from '../auth/token'
import { PhotoGridPage } from './PhotoGridPage'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')

function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant`
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00Z',
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    remote_category: null,
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
    ...overrides,
  }
}

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    // Default-Key ist `sharpness` (nicht kategoriefaehig) - der Default muss dazu passen,
    // damit kein Bestandstest unbemerkt in den Kategorien-Block rutscht (Spec 0209).
    category_eligible: false,
    ...overrides,
  }
}

function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    sharpness: 1.0,
    exposure: 0.5,
    cluster_key: null,
    computed_at: '2026-07-20T10:00:00Z',
    ...overrides,
  }
}

function renderPage(initialPath = '/projects/1/photos') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId/pipeline" element={<p>Projekt-Pipeline-Uebersicht</p>} />
        <Route path="/projects/:projectId/photos" element={<PhotoGridPage />} />
        <Route path="/projects/:projectId/photos/:photoId" element={<p>Einzelbild-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('PhotoGridPage', () => {
  beforeEach(() => {
    // window.matchMedia existiert in jsdom nicht (specs/architecture/0002-testkonzept.md) -
    // CriterionDetailsPopover fragt es beim Pointer-Enter des Info-Triggers ab, das auch
    // userEvent.click() vor dem eigentlichen Klick ausloest. Nur das Klick-Verhalten selbst wird
    // hier getestet, Hover-spezifisches Verhalten deckt CriterionDetailsPopover.test.tsx ab.
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(projectsApi.confirmAusschussGate).mockReset()
    vi.mocked(projectsApi.confirmAusschussGate).mockResolvedValue({ status: 'confirmed' })
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  it('no longer renders its own "Zurück zum Projekt" link (specs/features/0033, AK7 - now covered by the sticky header link)', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage()

    await screen.findByText('Keine Fotos mit diesem Filter.')
    expect(screen.queryByRole('link', { name: /zurück zum projekt/i })).not.toBeInTheDocument()
  })

  it('shows skeleton placeholder tiles instead of a blocking spinner while loading', () => {
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage()

    const status = screen.getByRole('status')
    expect(status.tagName).toBe('UL')
    expect(status.children.length).toBeGreaterThan(1)
  })

  it('renders one tile per photo with the own rating badge', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          relative_path: 'a.jpg',
          ratings: [{ user_id: 1, username: 'testuser', status: 'favorite' }],
        }),
        photo({ id: 2, relative_path: 'b.jpg', ratings: [] }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    expect(await screen.findAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByLabelText('Favorit')).toBeInTheDocument()
    expect(screen.getByLabelText('Unbewertet')).toBeInTheDocument()
  })

  it('only shows the current user\'s own rating, not another user\'s', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 2, username: 'other-user', status: 'rejected' }],
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    expect(await screen.findByLabelText('Unbewertet')).toBeInTheDocument()
    expect(screen.queryByLabelText('Verworfen')).not.toBeInTheDocument()
  })

  it('links a tile to the detail view, preserving the active filter', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 5 })], total: 1 })

    renderPage('/projects/1/photos?filter=unrated')

    const [item] = await screen.findAllByRole('listitem')
    const link = item.querySelector('a')
    expect(link).toHaveAttribute('href', '/projects/1/photos/5?filter=unrated')
  })

  it('ignores an unknown/tampered filter value in the URL instead of forwarding it to the API', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })

    renderPage('/projects/1/photos?filter=not-a-real-filter')

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ ratingStatus: undefined })
      )
    )
    expect(screen.getByRole('button', { name: 'Alle' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('requests the selected filter and reflects it in the URL', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
    const user = userEvent.setup()

    renderPage()
    await waitFor(() => expect(photosApi.listPhotos).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenLastCalledWith(
        1,
        expect.objectContaining({ ratingStatus: 'favorite' })
      )
    )
  })

  it('requests the suggested filter and reflects it in the URL', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
    const user = userEvent.setup()

    renderPage()
    await waitFor(() => expect(photosApi.listPhotos).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: 'Vorgeschlagen' }))

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenLastCalledWith(
        1,
        expect.objectContaining({ ratingStatus: 'suggested' })
      )
    )
  })

  it('marks the suggested filter button as active when linked directly via URL', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage('/projects/1/photos?filter=suggested')

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ ratingStatus: 'suggested' })
      )
    )
    expect(screen.getByRole('button', { name: 'Vorgeschlagen' })).toHaveAttribute(
      'aria-pressed',
      'true'
    )
  })

  it('shows an empty state with a filter-reset option when the filter matches nothing', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
    const user = userEvent.setup()

    renderPage('/projects/1/photos?filter=rejected')
    expect(await screen.findByText(/keine fotos/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /filter zurücksetzen/i }))

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenLastCalledWith(
        1,
        expect.objectContaining({ ratingStatus: undefined })
      )
    )
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('loads the next batch on "Weitere laden" click', async () => {
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce({ items: [photo({ id: 1 })], total: 2 })
      .mockResolvedValueOnce({ items: [photo({ id: 2 })], total: 2 })
    const user = userEvent.setup()

    renderPage()
    await screen.findAllByRole('listitem')
    const loadMoreButton = screen.getByRole('button', { name: /weitere laden/i })

    await user.click(loadMoreButton)

    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(2))
    expect(screen.queryByRole('button', { name: /weitere laden/i })).not.toBeInTheDocument()
  })

  it('shows a suggestion badge and an "Übernehmen" button when a photo has an open suggestion', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, relative_path: 'sunset.jpg', ratings: [], suggestion: suggestion() })],
      total: 1,
    })

    renderPage()

    expect(await screen.findByLabelText('Vorschlag: Verworfen')).toBeInTheDocument()
    // Photo-spezifisches aria-label (UI/UX-Review-Fund): mehrere offene Vorschlaege in einem Grid
    // sind sonst per Tastatur/Screenreader nicht auseinanderzuhalten, da alle Buttons denselben
    // sichtbaren Text "Uebernehmen" tragen.
    expect(
      screen.getByRole('button', { name: 'Vorschlag übernehmen: sunset.jpg' })
    ).toBeInTheDocument()
  })

  it('does not show a suggestion badge/button when the photo has no open suggestion', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, ratings: [], suggestion: null })],
      total: 1,
    })

    renderPage()

    await screen.findAllByRole('listitem')
    expect(screen.queryByRole('button', { name: /übernehmen/i })).not.toBeInTheDocument()
  })

  it('shows a busy state only on the confirming tile\'s own button while its request is in flight', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({ id: 1, ratings: [], suggestion: suggestion() }),
        photo({ id: 2, ratings: [], suggestion: suggestion() }),
      ],
      total: 2,
    })
    vi.mocked(ratingsApi.setRating).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()

    renderPage()
    const [firstButton, secondButton] = await screen.findAllByRole('button', {
      name: /übernehmen/i,
    })
    await user.click(firstButton)

    await waitFor(() => expect(firstButton).toBeDisabled())
    expect(secondButton).toBeEnabled()
  })

  it('allows confirming a second tile while an earlier tile\'s confirm is still in flight', async () => {
    // Regression fuer einen im UI/UX-Review gefundenen Bug: eine gemeinsam genutzte
    // useSetRatingMutation-Instanz fuer die ganze Seite hat frueher jeden weiteren Klick
    // stillschweigend ignoriert, solange irgendeine andere Kachel noch "isPending" war - genau
    // das Batch-Bestaetigen, das dieser Button laut Spec ermoeglichen soll, war dadurch kaputt.
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({ id: 1, ratings: [], suggestion: suggestion() }),
        photo({ id: 2, ratings: [], suggestion: suggestion() }),
      ],
      total: 2,
    })
    vi.mocked(ratingsApi.setRating).mockImplementation((photoId) =>
      photoId === 1
        ? new Promise(() => {})
        : Promise.resolve({ user_id: 1, username: 'testuser', status: 'rejected' })
    )
    const user = userEvent.setup()

    renderPage()
    const [firstButton, secondButton] = await screen.findAllByRole('button', {
      name: /übernehmen/i,
    })
    await user.click(firstButton)
    await user.click(secondButton)

    await waitFor(() => expect(ratingsApi.setRating).toHaveBeenCalledWith(2, 'rejected'))
  })

  it('confirms a suggestion on click without navigating to the detail view', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 7, ratings: [], suggestion: suggestion({ status: 'rejected' }) })],
      total: 1,
    })
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })
    const user = userEvent.setup()

    renderPage()
    const confirmButton = await screen.findByRole('button', { name: /übernehmen/i })
    await user.click(confirmButton)

    expect(ratingsApi.setRating).toHaveBeenCalledWith(7, 'rejected')
    expect(screen.queryByText('Einzelbild-Seite')).not.toBeInTheDocument()
  })

  // Spec 0040 (Bewertungsdetails-Info-Popover), Akzeptanzkriterien 1, 2, 17.
  describe('info popover trigger', () => {
    it('shows the trigger as a sibling of the tile link when criterion_scores is not empty', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })

      renderPage()

      const trigger = await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      const [item] = await screen.findAllByRole('listitem')
      const link = item.querySelector('a')
      // Geschwisterelement NEBEN, nicht INNERHALB des <Link>-Kachel-Wrappers (Akzeptanzkriterium
      // 17) - ein Klick auf den Trigger darf nicht zur Detailseite navigieren.
      expect(link?.contains(trigger)).toBe(false)
      expect(item.contains(trigger)).toBe(true)
    })

    it('does not show the trigger when criterion_scores is empty', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [] })],
        total: 1,
      })

      renderPage()

      await screen.findAllByRole('listitem')
      expect(
        screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' })
      ).not.toBeInTheDocument()
    })

    // Copilot-Review-Fund: die RatingBadge zieht als absolut positioniertes Geschwisterelement
    // UEBER den <Link>, damit sie mit dem Info-Trigger in derselben Ecke gruppiert werden kann -
    // ohne Gegenmassnahme wuerde ein Klick in ihrem (rein dekorativen) Bereich den darunterliegenden
    // <Link> nicht mehr erreichen und die Kachel dort nicht mehr navigieren. jsdom hat keine echte
    // Layout-/Hit-Testing-Engine (vgl. specs/architecture/0002-testkonzept.md, "Popover-
    // Positionierungsverhalten" - bleibt manueller visueller Smoke-Test), ein tatsaechlicher
    // Ueberlappungs-Klicktest ist hier deshalb nicht moeglich - stattdessen wird die dafuer
    // verantwortliche CSS-Absicherung strukturell verifiziert: der umschliessende Overlay-Wrapper
    // ist `pointer-events-none` (Klicks fallen durch zum <Link>), der Info-Trigger reaktiviert
    // Pointer-Events explizit fuer sich selbst (`pointer-events-auto`).
    it('keeps the decorative rating-badge overlay pointer-events-none so clicks fall through to the tile link', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })

      renderPage()

      const trigger = await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      const overlay = trigger.closest('div.absolute')
      expect(overlay).toHaveClass('pointer-events-none')
      expect(trigger).toHaveClass('pointer-events-auto')
    })

    it('clicking the trigger does not navigate to the detail view', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })
      const user = userEvent.setup()

      renderPage()
      const trigger = await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      await user.click(trigger)

      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.queryByText('Einzelbild-Seite')).not.toBeInTheDocument()
    })
  })

  describe('gate mode (&gate=1)', () => {
    it('shows a banner with candidate count and confirm button, hidden without the gate param', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1 }), photo({ id: 2 })],
        total: 2,
      })

      renderPage('/projects/1/photos?filter=suggested')
      await screen.findAllByRole('listitem')
      expect(
        screen.queryByRole('button', { name: /ausschuss gesichtet/i })
      ).not.toBeInTheDocument()
    })

    it('shows the banner and candidate count when gate=1', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1 }), photo({ id: 2 })],
        total: 2,
      })

      renderPage('/projects/1/photos?filter=suggested&gate=1')

      expect(await screen.findByText(/2 kandidaten/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Ausschuss gesichtet, weiter' })).toBeInTheDocument()
    })

    it('confirms the gate and navigates to the project pipeline overview on click (Spec 0042, AK9)', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1 })],
        total: 1,
      })
      const user = userEvent.setup()

      renderPage('/projects/1/photos?filter=suggested&gate=1')
      const confirmButton = await screen.findByRole('button', {
        name: 'Ausschuss gesichtet, weiter',
      })
      await user.click(confirmButton)

      await waitFor(() => expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1))
      expect(await screen.findByText('Projekt-Pipeline-Uebersicht')).toBeInTheDocument()
    })

    it('shows an error alert when confirming the gate fails', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })
      vi.mocked(projectsApi.confirmAusschussGate).mockRejectedValue(
        new ApiError(409, 'Kein erfolgreicher Ausschuss-Lauf.')
      )
      const user = userEvent.setup()

      renderPage('/projects/1/photos?filter=suggested&gate=1')
      const confirmButton = await screen.findByRole('button', {
        name: 'Ausschuss gesichtet, weiter',
      })
      await user.click(confirmButton)

      expect(await screen.findByRole('alert')).toHaveTextContent('Kein erfolgreicher Ausschuss-Lauf.')
    })
  })

  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt.
  describe('category override', () => {
    it('shows the override marker only for a photo with an active override', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({ id: 1, category_override: 'hund' }),
          photo({ id: 2, category_override: null }),
        ],
        total: 2,
      })

      renderPage()

      // Beide Fotos laden asynchron ueber PhotoImage (role="status" waehrend des Ladens) - erst
      // abwarten, bis beide fertig sind, bevor die role="img"-Elemente gezaehlt werden. Sonst
      // koennte "findAllByRole('img')" (loest bereits beim ERSTEN Treffer auf, wartet NICHT bis
      // sich nichts mehr aendert) faelschlich schon beim synchron gerenderten Override-Marker
      // allein aufloesen, bevor die beiden async geladenen Foto-<img>-Elemente ueberhaupt
      // existieren - Flaky-Test-Fund, entdeckt beim Nachziehen des Copilot-Accessibility-Fixes
      // (PR #201: CategoryOverrideMarker bekam zusaetzlich role="img").
      await waitFor(() => {
        expect(screen.queryAllByRole('status')).toHaveLength(0)
      })

      // Zwei geladene Foto-Thumbnails (role="img" ueber das native <img alt=...>) + ein
      // Override-Marker (role="img", nur fuer das eine Foto mit aktivem Override).
      expect(screen.getAllByRole('img')).toHaveLength(3)
      expect(screen.getAllByLabelText('Kategorie manuell übersteuert')).toHaveLength(1)
    })

    it('overrides the category from the info popover and invalidates the photo list', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            ranking: {
              cluster_key: 'cluster-0',
              category_key: 'people',
              rank_score: 0.5,
              rank_position: 1,
              partition_size: 1,
            },
            category_candidates: [
              { category_key: 'tier', origin: 'remote', provider: 'anthropic' },
              { category_key: 'menschen', origin: 'local', provider: null },
            ],
          }),
        ],
        total: 1,
      })
      vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
        photo_id: 1,
        category_key: 'hund',
      })
      const user = userEvent.setup()

      renderPage()
      await screen.findAllByRole('img')
      await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
      await user.click(screen.getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() =>
        expect(photosApi.setCategoryOverride).toHaveBeenCalledWith(1, 'hund')
      )
    })
  })
})
