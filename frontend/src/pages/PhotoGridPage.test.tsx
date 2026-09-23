import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as duplicatesApi from '../api/duplicates'
import * as motifsApi from '../api/motifs'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import type { CriterionScoreOut, PhotoListOut, PhotoOut, SuggestionOut } from '../api/types'
import { setToken } from '../auth/token'
import { MOTIF_SET } from '../test/motifSetFixture'
import { installIntersectionObserver, installResizeObserver } from '../test/observers'
import type { IntersectionObserverHarness, ResizeObserverHarness } from '../test/observers'
import { GRID_GAP_PX } from '../utils/justifiedRows'
import { PhotoGridPage } from './PhotoGridPage'

// specs/features/0289-feste-kategorien.md: die Seite laedt das Kategorien-Set zur Laufzeit
// (`useCategoriesQuery`) - ohne Mock liefe diese Query in einen echten Request und die Seite
// stuende dauerhaft im Fallback-Zustand, statt in einem bewusst gewaehlten.
vi.mock('../api/motifs')
vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/duplicates')

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
    taken_at_original: '2026-07-20T10:00:00Z',
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
    // Basiszustand: klassifiziert per Cloud-Grundlage, ohne Ausschluss.
    motif_assessment: {
      source: 'cloud' as const,
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2026-07-21T09:00:00',
    },
    motifs: MOTIF_SET.items.map((item) => ({
      key: item.key,
      strength: 0.5,
      correction: null,
      present: false,
    })),
    ...overrides,
  }
}

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    // Default-Key ist `sharpness` (ohne Praesenz-Schwelle) - der Default muss dazu passen,
    // damit kein Bestandstest unbemerkt in den Bildinhalt-Block rutscht.
    has_presence_threshold: false,
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
    { wrapper },
  )
}

/** Die beiden Zeichen einer Kachel - ueber semantische `data-*`, nie ueber Klassennamen. */
function marksOf(item: HTMLElement): { mark: string; shape?: string; status?: string }[] {
  return Array.from(item.querySelectorAll<HTMLElement>('[data-mark]')).map((element) => ({
    mark: element.dataset.mark ?? '',
    ...(element.dataset.markShape === undefined ? {} : { shape: element.dataset.markShape }),
    ...(element.dataset.markStatus === undefined ? {} : { status: element.dataset.markStatus }),
  }))
}

describe('PhotoGridPage', () => {
  let resizeObserver: ResizeObserverHarness
  let intersectionObserver: IntersectionObserverHarness

  beforeEach(() => {
    // Beide Beobachter fehlen in jsdom und bekommen TREIBBARE Attrappen
    // (specs/architecture/0002-testkonzept.md): Eine No-op-Attrappe nach dem `matchMedia`-Muster
    // reichte hier nicht - an ihnen haengen die gemessene Containerbreite und das Nachladen, also
    // genau das, was zu pruefen ist.
    resizeObserver = installResizeObserver()
    intersectionObserver = installIntersectionObserver()
    // window.matchMedia existiert in jsdom nicht - die Kachel fragt es nach der Geraeteklasse
    // (Hover oder langer Druck). Hier durchgaengig "kein feiner Zeiger"; die Geste selbst deckt
    // PhotoGridTile.test.tsx in ihren vier Faellen ab.
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(motifsApi.listMotifs).mockReset()
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
    vi.mocked(projectsApi.confirmAusschussGate).mockReset()
    vi.mocked(projectsApi.confirmAusschussGate).mockResolvedValue({ status: 'confirmed' })
    vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockReset()
    vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockResolvedValue({
      total: 0,
      first_photo_id: null,
    })
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
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

  it('renders one tile per photo, each with its own dot for the own album decision', async () => {
    // UMGESCHRIEBEN, NICHT GESTRICHEN: Die Aussage bleibt "je Foto eine Kachel, und die EIGENE
    // Albumentscheidung ist an ihr ablesbar". Sie haengt seit AK3/AK5 am Punkt statt am
    // beschrifteten Kennzeichen - das Wort "Neu" gibt es in dieser Ansicht nicht mehr.
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          relative_path: 'a.jpg',
          ratings: [{ user_id: 1, username: 'testuser', status: 'album_worthy', favorite: false }],
        }),
        photo({ id: 2, relative_path: 'b.jpg', ratings: [] }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    const items = await screen.findAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(marksOf(items[0])).toEqual([{ mark: 'album', shape: 'filled', status: 'album_worthy' }])
    // Ohne Entscheidung und ohne Vorschlag traegt die Kachel GAR KEIN Zeichen (AK3).
    expect(marksOf(items[1])).toEqual([])
  })

  it("only shows the current user's own rating, not another user's", async () => {
    // Die Sicherheitszusage bleibt der Kern des Falls, nur ihre Beobachtungsstelle wandert vom
    // Kennzeichen auf die beiden Zeichen: `ownFavorite`/`ownRatingStatus`, nie
    // `ratings.some(r => r.favorite)` - das zeigte die Auszeichnung der anderen Person als die
    // eigene. Beide Felder der Fremdbewertung sind hier gesetzt.
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 2, username: 'other-user', status: 'rejected', favorite: true }],
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    const [item] = await screen.findAllByRole('listitem')
    expect(marksOf(item)).toEqual([])
    expect(item).not.toHaveTextContent('Favorit')
    expect(item).not.toHaveTextContent('Verworfen')
  })

  it('shows the star next to the dot when the photo is an own favourite and decided', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'album_worthy', favorite: true }],
        }),
      ],
      total: 1,
    })

    renderPage()

    const [item] = await screen.findAllByRole('listitem')
    expect(marksOf(item)).toEqual([
      { mark: 'favorite' },
      { mark: 'album', shape: 'filled', status: 'album_worthy' },
    ])
  })

  it('shows the star alone when only the favourite marker is set', async () => {
    // "Favorit ohne Albumzeichen daneben IST die Aussage: noch nicht entschieden." Das fruehere
    // Wort "Neu" entfaellt - die Abwesenheit des Punktes sagt dasselbe, ohne Platz zu kosten.
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: null, favorite: true }],
        }),
      ],
      total: 1,
    })

    renderPage()

    const [item] = await screen.findAllByRole('listitem')
    expect(marksOf(item)).toEqual([{ mark: 'favorite' }])
    expect(item).not.toHaveTextContent('Neu')
  })

  it('shows a ring, not a filled dot, for an unconfirmed suggestion', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, ratings: [], suggestion: suggestion({ status: 'rejected' }) })],
      total: 1,
    })

    renderPage()

    const [item] = await screen.findAllByRole('listitem')
    expect(marksOf(item)).toEqual([{ mark: 'album', shape: 'ring', status: 'rejected' }])
  })

  describe('das justierte Zeilenraster (AK1, AK2)', () => {
    it('lays the tiles out to the measured container width, without cropping', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({ id: 1, relative_path: 'quer.jpg', aspect_ratio: 1.5 }),
          photo({ id: 2, relative_path: 'hoch.jpg', aspect_ratio: 0.75 }),
          photo({ id: 3, relative_path: 'breit.jpg', aspect_ratio: 2.4 }),
        ],
        total: 3,
      })

      renderPage()
      await screen.findAllByRole('listitem')
      resizeObserver.resizeTo(900)

      const items = screen.getAllByRole('listitem')
      const widths = items.map((item) => Number.parseInt(item.style.width, 10))
      const heights = items.map((item) => Number.parseInt(item.style.height, 10))
      // Eine volle Zeile: gemeinsame Hoehe, und Bildbreiten plus Zwischenraeume ergeben EXAKT
      // die gemessene Breite.
      expect(new Set(heights).size).toBe(1)
      expect(widths.reduce((sum, width) => sum + width, 0) + GRID_GAP_PX * 2).toBe(900)
      // Jede Breite folgt dem eigenen Verhaeltnis - kein Bild wird auf eine feste Form gezwungen.
      expect(widths[0]).toBeGreaterThan(widths[1])
      expect(widths[2]).toBeGreaterThan(widths[0])
    })

    it('shows every photo even before the first measurement', async () => {
      // Ohne Ausfallrichtung stuende hier dauerhaft ein leeres Raster - still und ohne Meldung.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1 }), photo({ id: 2 })],
        total: 2,
      })

      renderPage()

      const items = await screen.findAllByRole('listitem')
      expect(items).toHaveLength(2)
      for (const item of items) {
        expect(Number.parseInt(item.style.width, 10)).toBeGreaterThan(0)
      }
    })

    it('plans a photo without a known ratio as 3:2 instead of dropping it', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, aspect_ratio: null })],
        total: 1,
      })

      renderPage()
      await screen.findAllByRole('listitem')
      resizeObserver.resizeTo(900)

      const [item] = screen.getAllByRole('listitem')
      const width = Number.parseInt(item.style.width, 10)
      const height = Number.parseInt(item.style.height, 10)
      expect(width / height).toBeCloseTo(1.5, 1)
    })
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
        expect.objectContaining({ ratingStatus: undefined }),
      ),
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
        expect.objectContaining({ ratingStatus: 'favorite' }),
      ),
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
        expect.objectContaining({ ratingStatus: 'suggested' }),
      ),
    )
  })

  it('marks the suggested filter button as active when linked directly via URL', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage('/projects/1/photos?filter=suggested')

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ ratingStatus: 'suggested' }),
      ),
    )
    expect(screen.getByRole('button', { name: 'Vorgeschlagen' })).toHaveAttribute(
      'aria-pressed',
      'true',
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
        expect.objectContaining({ ratingStatus: undefined }),
      ),
    )
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  describe('Nachladen am Sichtbarkeitsanker (AK10)', () => {
    it('loads the next batch without any click, once the anchor becomes visible', async () => {
      // UMGESCHRIEBEN, NICHT GESTRICHEN: Die Aussage bleibt "die zweite Seite kommt an und die
      // Kacheln verdoppeln sich". Ausgeloest wird sie jetzt vom Anker statt von einer
      // Schaltflaeche - eine Schaltflaeche zum Nachladen gibt es nicht mehr.
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({ items: [photo({ id: 1 })], total: 2 })
        .mockResolvedValueOnce({ items: [photo({ id: 2 })], total: 2 })

      renderPage()
      await screen.findAllByRole('listitem')
      expect(screen.queryByRole('button', { name: /weitere laden/i })).not.toBeInTheDocument()

      intersectionObserver.setIntersecting(true)

      await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(2))
    })

    it('names how many of how many are loaded, across two pages', async () => {
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({ items: [photo({ id: 1 })], total: 2 })
        .mockResolvedValueOnce({ items: [photo({ id: 2 })], total: 2 })

      renderPage()
      expect(await screen.findByText(/1 von 2 geladen/)).toBeInTheDocument()

      intersectionObserver.setIntersecting(true)

      expect(await screen.findByText(/2 von 2 geladen/)).toBeInTheDocument()
    })

    it('stops observing once everything is loaded', async () => {
      // Auflage S7: kein neuer Abruf, sobald alles da ist. Ohne das Ende feuerte der Beobachter
      // bei jedem Scroll-Schritt weiter.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })

      renderPage()
      await screen.findAllByRole('listitem')

      expect(intersectionObserver.observedCount()).toBe(0)
      intersectionObserver.setIntersecting(true)
      expect(photosApi.listPhotos).toHaveBeenCalledTimes(1)
    })

    it('never fires a second request while one is still in flight', async () => {
      // Auflage S7: EIN Abruf gleichzeitig. Zehn Anker-Meldungen hintereinander duerfen nicht
      // zehn Anfragen erzeugen - je Antwort bis zu 200 Fotos samt ihrer Bildabrufe gegen den
      // Homeserver, auf dem PhotoSort und OpenCloud zusammen laufen.
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({ items: [photo({ id: 1 })], total: 3 })
        .mockReturnValue(new Promise(() => {}))

      renderPage()
      await screen.findAllByRole('listitem')

      for (let attempt = 0; attempt < 10; attempt += 1) {
        intersectionObserver.setIntersecting(true)
      }

      await waitFor(() => expect(photosApi.listPhotos).toHaveBeenCalledTimes(2))
      expect(photosApi.listPhotos).toHaveBeenCalledTimes(2)
    })

    it('shows the failure of a follow-up load where the counter stands, keeping the tiles', async () => {
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({ items: [photo({ id: 1 })], total: 2 })
        .mockRejectedValueOnce(new ApiError(500, 'Nachladen fehlgeschlagen'))

      renderPage()
      await screen.findAllByRole('listitem')

      intersectionObserver.setIntersecting(true)

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Nachladen fehlgeschlagen')
      expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeInTheDocument()
      expect(screen.getAllByRole('listitem')).toHaveLength(1)
    })

    it('sends the retry through the same lock as the anchor', async () => {
      // Auflage S7 sagt "ein Abruf gleichzeitig" OHNE Einschraenkung auf den Beobachterpfad. Ein
      // `fetchNextPage()` direkt am Wiederholknopf ginge an der Sperre vorbei; hier druecken
      // Knopf und Anker im selben Tick, und es darf trotzdem nur EIN weiterer Abruf entstehen.
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({ items: [photo({ id: 1 })], total: 3 })
        .mockRejectedValueOnce(new ApiError(500, 'Nachladen fehlgeschlagen'))
        .mockReturnValue(new Promise(() => {}))
      renderPage()
      await screen.findAllByRole('listitem')
      intersectionObserver.setIntersecting(true)
      await screen.findByRole('alert')
      expect(photosApi.listPhotos).toHaveBeenCalledTimes(2)

      // Fuenf Klicks OHNE Warten dazwischen - genau das Fenster, in dem `isFetchingNextPage` noch
      // falsch ist. Mit `await` dazwischen bestuende der Fall auch gegen einen Aufruf, der an der
      // Sperre vorbeigeht, weil React zwischendurch neu rendert.
      const wiederholen = screen.getByRole('button', { name: /erneut versuchen/i })
      act(() => {
        for (let versuch = 0; versuch < 5; versuch += 1) {
          fireEvent.click(wiederholen)
        }
      })

      await waitFor(() => expect(photosApi.listPhotos).toHaveBeenCalledTimes(3))
      expect(photosApi.listPhotos).toHaveBeenCalledTimes(3)
    })

    it('does not place the anchor in the empty state', async () => {
      // Sonst loeste er dort sofort einen Abruf aus.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

      renderPage()
      await screen.findByText('Keine Fotos mit diesem Filter.')

      expect(intersectionObserver.observedCount()).toBe(0)
    })
  })

  describe('der Rueckbau des Gate-Modus (Spec 0525)', () => {
    /*
     * DIE FRUEHEREN FAELLE DIESES BLOCKS SIND ERSATZLOS ENTFALLEN, NICHT STILL. "Übernehmen" und
     * "Vergleichen" unter der Kachel sowie der Knopf "Ausschuss gesichtet, weiter" hat Spec 0525
     * mit dem `?gate=1`-Modus aufgehoben; die Sichtung und ihr Abschluss stehen seitdem im
     * Ausschuss-Schritt. An ihre Stelle tritt hier die GEGENPROBE: Der Parameter in der Adresse
     * darf nichts mehr ausloesen.
     */
    const ALTE_GATE_ADRESSE = '/projects/1/photos?filter=suggested&gate=1'

    it('setzt den Gate-Bestaetigungsaufruf auch unter `?gate=1` nie ab', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, ratings: [], suggestion: suggestion() })],
        total: 1,
      })

      renderPage(ALTE_GATE_ADRESSE)
      await screen.findAllByRole('listitem')

      // UEBER DEN AUFRUFZAEHLER, nicht ueber ein Suchelement: Der Knopf hiess "Ausschuss
      // gesichtet, weiter", sein Fehlen belegte nur die halbe Zusage - ein Aufruf koennte auch
      // ohne ihn laufen.
      expect(projectsApi.confirmAusschussGate).not.toHaveBeenCalled()
      expect(screen.queryByRole('button', { name: /ausschuss gesichtet/i })).not.toBeInTheDocument()
    })

    it('zeigt unter keinem Filter eine Aktion unter der Kachel', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            relative_path: 'serie.jpg',
            ratings: [],
            suggestion: suggestion({ reason: 'duplicate', duplicate_of: 3 }),
          }),
        ],
        total: 1,
      })

      renderPage(ALTE_GATE_ADRESSE)
      await screen.findAllByRole('listitem')

      expect(screen.queryByRole('button', { name: /übernehmen/i })).not.toBeInTheDocument()
      expect(
        screen.queryByRole('link', { name: /^Duplikate vergleichen:/ }),
      ).not.toBeInTheDocument()
    })
  })

  /* --------------------------------------------------------------------------------------
   * AK7/AK8 (Spec 0486) - der listenweite Einstieg
   * ------------------------------------------------------------------------------------ */

  describe('Listenweiter Einstieg in den Duplikat-Durchgang', () => {
    const VORGESCHLAGENE_LISTE = {
      items: [
        photo({
          id: 7,
          relative_path: 'serie.jpg',
          ratings: [],
          suggestion: suggestion({ reason: 'duplicate' as const, duplicate_of: 3 }),
        }),
      ],
      total: 1,
    }

    it('steht GENAU EINMAL da und fuehrt auf die erste Gruppe', async () => {
      // Ein Weg fuer die ganze Liste, nicht je Kachel - und ausserhalb des Kachelrasters. Die
      // Zaehlung ist die Zusage: In das Raster gerutscht staende er n-mal da.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(VORGESCHLAGENE_LISTE)
      vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockResolvedValue({
        total: 2,
        first_photo_id: 42,
      })

      renderPage('/projects/1/photos?filter=suggested')

      const einstiege = await screen.findAllByRole('link', {
        name: 'Duplikate vergleichen — alle Gruppen der Reihe nach durchgehen',
      })
      expect(einstiege).toHaveLength(1)
      expect(einstiege[0]).toHaveAttribute('href', '/projects/1/photos/42/duplicates')
    })

    it('heisst sichtbar `Duplikate vergleichen` und traegt den Zusatz nach einem Gedankenstrich', async () => {
      // Der Zusatz im zugaenglichen Namen folgt nach einem GEDANKENSTRICH, nie nach einem
      // Doppelpunkt: `/^Duplikate vergleichen:/` kennzeichnet die kachelgenaue Fassung dieses
      // Wegs, die Spec 0525 mit dem Gate-Modus entfernt hat. Ein Name nach demselben Muster waere
      // von ihr nicht zu unterscheiden, sobald sie zurueckkaeme; der Anfang bleibt trotzdem die
      // sichtbare Beschriftung (WCAG 2.5.3).
      vi.mocked(photosApi.listPhotos).mockResolvedValue(VORGESCHLAGENE_LISTE)
      vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockResolvedValue({
        total: 2,
        first_photo_id: 42,
      })

      renderPage('/projects/1/photos?filter=suggested')

      const einstieg = await screen.findByRole('link', { name: /durchgehen$/ })
      expect(einstieg.textContent).toBe('Duplikate vergleichen')
      expect(einstieg.getAttribute('aria-label')).toMatch(/^Duplikate vergleichen\b/)
      expect(einstieg.getAttribute('aria-label')).toMatch(/—/)
      expect(einstieg.getAttribute('aria-label')).not.toMatch(/^Duplikate vergleichen:/)
      expect(screen.queryAllByRole('link', { name: /^Duplikate vergleichen:/ })).toHaveLength(0)
    })

    it('steht NICHT da, wenn es keine einzige Gruppe gibt', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(VORGESCHLAGENE_LISTE)
      vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockResolvedValue({
        total: 0,
        first_photo_id: null,
      })

      renderPage('/projects/1/photos?filter=suggested')

      await screen.findAllByRole('listitem')
      expect(screen.queryByRole('link', { name: /durchgehen/i })).not.toBeInTheDocument()
    })

    it('steht auch WAEHREND DES LADENS nicht da - er soll nicht kurz aufblitzen', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(VORGESCHLAGENE_LISTE)
      vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockReturnValue(new Promise(() => {}))

      renderPage('/projects/1/photos?filter=suggested')

      await screen.findAllByRole('listitem')
      expect(screen.queryByRole('link', { name: /durchgehen/i })).not.toBeInTheDocument()
    })

    it('steht NICHT da, solange die Liste nicht nach Vorschlaegen gefiltert ist', async () => {
      // Der Einstieg gehoert an die Sichtung des Ausschusses, nicht an jede Fotoliste. Ohne die
      // Bedingung stuende er auch unter "Alle" und unter jedem anderen Filter - und die Anfrage
      // liefe dort ebenfalls.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(VORGESCHLAGENE_LISTE)
      vi.mocked(duplicatesApi.getDuplicateGroupIndex).mockResolvedValue({
        total: 2,
        first_photo_id: 42,
      })

      renderPage()

      await screen.findAllByRole('listitem')
      expect(screen.queryByRole('link', { name: /durchgehen/i })).not.toBeInTheDocument()
      expect(duplicatesApi.getDuplicateGroupIndex).not.toHaveBeenCalled()
    })
  })

  /*
   * ERSATZ, KEINE STREICHUNG (specs/features/0489-fotouebersicht-ohne-beschnitt.md, AK3 und
   * Daniels Entscheidung vom 2026-09-14). Der Info-Ausloeser der Bewertungsdetails und der
   * Motiv-Marker entfallen in DIESER Ansicht ersatzlos - die Kachel traegt genau zwei Zeichen.
   *
   * Ein ersatzloses Streichen dieser Faelle waere der Verlust der Zusage, nicht ihre Erfuellung:
   * Geprueft wird jetzt die ABWESENHEIT, und zwar mit einem Foto, das beide fruehere Ausloeser
   * ausgeloest haette. Der getragene Preis steht in der Spec: Die Bewertungsdetails sind aus dem
   * Raster nicht mehr erreichbar, nur noch in der Detailansicht (dort weiterhin geprueft, siehe
   * PhotoDetailPage.test.tsx und CriterionDetailsPopover.test.tsx).
   */
  describe('kein drittes Ecken-Element mehr (AK3)', () => {
    it('shows neither the info trigger nor the motif marker, even where both used to appear', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            motif_assessment: null,
            motifs: [],
          }),
        ],
        total: 1,
      })

      renderPage()
      const [item] = await screen.findAllByRole('listitem')

      expect(
        screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' }),
      ).not.toBeInTheDocument()
      expect(screen.queryByLabelText('Motive noch nicht bestimmt')).not.toBeInTheDocument()
      // Und daraus folgend: hoechstens die beiden Zeichen, nie ein drittes.
      expect(marksOf(item).length).toBeLessThanOrEqual(2)
    })

    it('keeps the tile a list item with exactly one photo link', async () => {
      // Daran haengt der Auffinde-Ausdruck des E2E-Pruefstacks und damit vier Specs. Ein Bruch
      // faellt hier in vitest auf, nicht erst im Browser.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })

      renderPage()

      const [item] = await screen.findAllByRole('listitem')
      const photoLinks = Array.from(item.querySelectorAll('a')).filter((anchor) =>
        /\/photos\/\d+(\?|$)/.test(anchor.getAttribute('href') ?? ''),
      )
      expect(photoLinks).toHaveLength(1)
    })
  })

  // specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt "Kachel und Raster" - die Zusage
  // "kein Motivname und keine Staerke auf der Kachel selbst" gilt unveraendert weiter und wird
  // durch den Wegfall des Info-Ausloesers nur noch strenger.
  describe('Motive auf der Kachel', () => {
    it('shows no motif name or strength on the tile itself', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })

      renderPage()
      await screen.findAllByRole('listitem')

      for (const item of MOTIF_SET.items) {
        expect(screen.queryByText(item.display_name)).toBeNull()
      }
      expect(screen.queryByRole('list', { name: 'Motive' })).toBeNull()
    })
  })
})
