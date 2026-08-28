import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { CriterionScoreOut, PhotoListOut, PhotoOut, RankingOut } from '../api/types'
import { setToken } from '../auth/token'
import { countPhotosInDay, CurateCategoriesPage, toggleDayCollapse } from './CurateCategoriesPage'

vi.mock('../api/photos')
vi.mock('../api/ratings')

function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant`
}

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    cluster_key: 'cluster-0',
    category_key: 'landscape',
    rank_score: 0.8,
    rank_position: 1,
    partition_size: 1,
    ...overrides,
  }
}

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    // taken_at ist ein naives, zeitzonenloses Backend-Datetime ohne `Z`-Suffix (Spec 0039,
    // specs/architecture/0002-testkonzept.md) - die Fixture spiegelte das reale Format zuvor
    // fälschlich mit `Z` wider.
    taken_at: '2026-07-20T10:00:00',
    ratings: [],
    suggestion: null,
    ranking: ranking(),
    criterion_scores: [],
    remote_category_labels: [],
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
    ...overrides,
  }
}

describe('countPhotosInDay', () => {
  it('returns 0 for a day with no clusters', () => {
    expect(countPhotosInDay({})).toBe(0)
  })

  it('sums photos.length across every cluster and category of the day', () => {
    const clustersForDay = {
      'cluster-a': {
        landscape: [photo({ id: 1 }), photo({ id: 2 })],
        people: [photo({ id: 3 })],
      },
      'cluster-b': {
        landscape: [photo({ id: 4 })],
      },
    }

    expect(countPhotosInDay(clustersForDay)).toBe(4)
  })

  it('ignores categories whose pool is already exhausted (photos.length === 0)', () => {
    const clustersForDay = {
      'cluster-a': {
        landscape: [] as PhotoOut[],
        people: [photo({ id: 1 })],
      },
    }

    expect(countPhotosInDay(clustersForDay)).toBe(1)
  })
})

describe('toggleDayCollapse', () => {
  it('adds a dayKey that is not yet in the set (collapses it)', () => {
    const result = toggleDayCollapse(new Set(), '2026-07-20')

    expect(result.has('2026-07-20')).toBe(true)
  })

  it('removes a dayKey that is already in the set (expands it)', () => {
    const result = toggleDayCollapse(new Set(['2026-07-20']), '2026-07-20')

    expect(result.has('2026-07-20')).toBe(false)
  })

  it('leaves other dayKeys in the set untouched', () => {
    const result = toggleDayCollapse(new Set(['2026-07-19', '2026-07-20']), '2026-07-20')

    expect(result.has('2026-07-19')).toBe(true)
    expect(result.has('2026-07-20')).toBe(false)
  })

  it('returns a new Set instance instead of mutating the argument', () => {
    const original = new Set<string>()

    const result = toggleDayCollapse(original, '2026-07-20')

    expect(result).not.toBe(original)
    expect(original.has('2026-07-20')).toBe(false)
  })
})

function renderPage(initialPath = '/projects/1/curate?topN=3') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  // `queryClient` wird mit zurueckgegeben (Erweiterung fuer Spec 0043): einzelne Tests loesen
  // damit gezielt einen Refetch aus (`queryClient.invalidateQueries(...)`), ohne denselben Pfad
  // wie eine echte Verwerfen-Mutation ueber die UI nachstellen zu muessen.
  return { ...render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId" element={<p>Projekt-Detailseite</p>} />
        <Route path="/projects/:projectId/curate" element={<CurateCategoriesPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  ), queryClient }
}

describe('CurateCategoriesPage', () => {
  beforeEach(() => {
    // window.matchMedia existiert in jsdom nicht (specs/architecture/0002-testkonzept.md) -
    // CriterionDetailsPopover fragt es beim Pointer-Enter des Info-Triggers ab, das auch
    // userEvent.click() vor dem eigentlichen Klick ausloest.
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
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  it('requests photos with the top-N from the query string', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage('/projects/1/curate?topN=5')

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { topNPerCategory: 5 })
    )
  })

  it('defaults to top-N 3 when the query string is missing/invalid', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage('/projects/1/curate')

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { topNPerCategory: 3 })
    )
  })

  it('groups photos by day, then cluster, then category, showing day/cluster headings and the category chip/name', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0', category_key: 'landscape' }) }),
        photo({ id: 2, ranking: ranking({ cluster_key: 'cluster-0', category_key: 'people' }) }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    // Beide Fotos sind am 20.07.2026 (Montag) um 10:00 Uhr entstanden (Fixture-Default) - ein
    // Tag-Abschnitt, ein Cluster mit Tageszeit-Ueberschrift statt der technischen cluster_key-ID.
    expect(await screen.findByText('Montag 20.07.2026')).toBeInTheDocument()
    expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
    expect(screen.queryByText('cluster-0')).not.toBeInTheDocument()
    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('People')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(2)
  })

  it('groups photos into day sections sorted chronologically ascending (Akzeptanzkriterium 1)', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          taken_at: '2026-07-21T10:00:00',
          ranking: ranking({ cluster_key: 'cluster-b', category_key: 'landscape' }),
        }),
        photo({
          id: 2,
          taken_at: '2026-07-20T10:00:00',
          ranking: ranking({ cluster_key: 'cluster-a', category_key: 'landscape' }),
        }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    // Die Tages-Kopfzeile ist seit Spec 0043 ein <button> innerhalb des <h2> (klappbarer
    // Trigger, dessen textContent zusätzlich das rein dekorative Auf-/Zuklapp-Symbol enthält) -
    // die Reihenfolge wird deshalb per Regex auf den Wochentag/Datum-Teil geprüft statt über
    // exakte Gleichheit des rohen h2-textContent.
    const headings = await screen.findAllByRole('heading', { level: 2 })
    const dayLabels = headings.map(
      (heading) => heading.textContent?.match(/(Montag|Dienstag) \d{2}\.\d{2}\.\d{4}/)?.[0]
    )
    expect(dayLabels).toEqual(['Montag 20.07.2026', 'Dienstag 21.07.2026'])
  })

  it(
    'sorts clusters within a day chronologically by earliest taken_at, not lexicographically ' +
      'by cluster_key (Akzeptanzkriterium 2, behebt "cluster-10" < "cluster-2")',
    async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            taken_at: '2026-07-20T14:00:00',
            ranking: ranking({ cluster_key: 'cluster-10', category_key: 'landscape' }),
          }),
          photo({
            id: 2,
            taken_at: '2026-07-20T09:00:00',
            ranking: ranking({ cluster_key: 'cluster-2', category_key: 'landscape' }),
          }),
        ],
        total: 2,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage()

      const headings = await screen.findAllByRole('heading', { level: 3 })
      expect(headings.map((heading) => heading.textContent)).toEqual([
        'Vormittags (09:00 Uhr)',
        'Nachmittags (14:00 Uhr)',
      ])
    }
  )

  it(
    'derives day and time-of-day bucket from the earliest photo for a midnight-spanning ' +
      'cluster, while the displayed range covers all visible photos (Akzeptanzkriterium 6)',
    async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            taken_at: '2026-07-21T00:10:00',
            ranking: ranking({ cluster_key: 'cluster-0', category_key: 'landscape' }),
          }),
          photo({
            id: 2,
            taken_at: '2026-07-20T23:50:00',
            ranking: ranking({ cluster_key: 'cluster-0', category_key: 'people' }),
          }),
        ],
        total: 2,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage()

      expect(await screen.findByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Nachts (23:50–00:10 Uhr)')).toBeInTheDocument()
    }
  )

  it('shows an empty-pool placeholder when a category has fewer than N photos', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1 })],
      total: 1,
    })

    renderPage('/projects/1/curate?topN=3')

    expect(await screen.findByText('Kein weiteres Foto verfügbar')).toBeInTheDocument()
  })

  it('shows a loading skeleton while fetching', () => {
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage()

    const status = screen.getByRole('status')
    expect(status.tagName).toBe('UL')
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows an explanatory empty state before any curation data exists', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage()

    expect(
      await screen.findByText(/noch keine kategorie-kuratierung verfügbar/i)
    ).toBeInTheDocument()
  })

  it('rejects a photo and shows a skeleton in its tile until the backfilled photo arrives', async () => {
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce({
        items: [photo({ id: 1, ranking: ranking({ rank_position: 1 }) })],
        total: 1,
      })
      .mockResolvedValueOnce({
        items: [photo({ id: 2, relative_path: 'b.jpg', ranking: ranking({ rank_position: 2 }) })],
        total: 1,
      })
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })
    const user = userEvent.setup()

    renderPage()
    const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
    await user.click(rejectButton)

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Verwerfen: b.jpg' })).toBeInTheDocument()
    )
  })

  it(
    'keeps the day section visible with its own empty-state text once all its photos are ' +
      'rejected instead of silently disappearing (Akzeptanzkriterium 7, Tag-Ebene)',
    async () => {
      // test-engineer-Review-Fund (urspruenglich fuer die 2-Ebenen-Gruppierung, jetzt auf die
      // Tag-Ebene uebertragen): der Kernfall, fuer den knownGroupKeysRef ueberhaupt gebaut wurde
      // - eine Partition, deren letztes Foto per Live-Ablehnung entfernt wird, MUSS mit eigenem
      // Leerzustand sichtbar bleiben statt spurlos aus der Gruppierung zu verschwinden. Da hier
      // Tag/Cluster/Kategorie gleichzeitig auf genau ein Element schrumpfen, kollabiert die
      // Anzeige auf die oberste (Tag-)Ebene statt verschachtelte Leerzustaende zu zeigen.
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 1,
              ranking: ranking({ cluster_key: 'cluster-0', category_key: 'landscape' }),
            }),
          ],
          total: 1,
        })
        .mockResolvedValueOnce({ items: [], total: 0 })
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        user_id: 1,
        username: 'testuser',
        status: 'rejected',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/curate?topN=1')
      const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
      await user.click(rejectButton)

      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
      )
      expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Keine Fotos für diesen Tag')).toBeInTheDocument()
      expect(screen.queryByText('Vormittags (10:00 Uhr)')).not.toBeInTheDocument()
    }
  )

  it(
    'keeps a category section visible with the unchanged empty-pool placeholder once it alone ' +
      'is exhausted, while a sibling category in the same cluster still has photos ' +
      '(Akzeptanzkriterium 7, Kategorie-Ebene, unverändert)',
    async () => {
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 1,
              ranking: ranking({ cluster_key: 'cluster-0', category_key: 'landscape' }),
            }),
            photo({
              id: 2,
              relative_path: 'b.jpg',
              ranking: ranking({ cluster_key: 'cluster-0', category_key: 'people' }),
            }),
          ],
          total: 2,
        })
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 2,
              relative_path: 'b.jpg',
              ranking: ranking({ cluster_key: 'cluster-0', category_key: 'people' }),
            }),
          ],
          total: 1,
        })
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        user_id: 1,
        username: 'testuser',
        status: 'rejected',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/curate?topN=1')
      const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
      await user.click(rejectButton)

      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
      )
      expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
      expect(screen.getByText('Landscape')).toBeInTheDocument()
      expect(screen.getByText('People')).toBeInTheDocument()
      expect(screen.getByText('Kein weiteres Foto verfügbar')).toBeInTheDocument()
      expect(screen.queryByText('Keine Fotos in dieser Tageszeit')).not.toBeInTheDocument()
    }
  )

  it(
    'keeps a cluster heading available from the clusterMetaRef cache once that cluster is ' +
      'fully exhausted, while a sibling cluster in the same day still has photos ' +
      '(Regressionstest laut Architektur-Abschnitt der Spec)',
    async () => {
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 1,
              taken_at: '2026-07-20T09:00:00',
              ranking: ranking({ cluster_key: 'cluster-a', category_key: 'landscape' }),
            }),
            photo({
              id: 2,
              relative_path: 'b.jpg',
              taken_at: '2026-07-20T14:00:00',
              ranking: ranking({ cluster_key: 'cluster-b', category_key: 'landscape' }),
            }),
          ],
          total: 2,
        })
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 2,
              relative_path: 'b.jpg',
              taken_at: '2026-07-20T14:00:00',
              ranking: ranking({ cluster_key: 'cluster-b', category_key: 'landscape' }),
            }),
          ],
          total: 1,
        })
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        user_id: 1,
        username: 'testuser',
        status: 'rejected',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/curate?topN=1')
      const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
      await user.click(rejectButton)

      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
      )
      expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Vormittags (09:00 Uhr)')).toBeInTheDocument()
      expect(screen.getByText('Keine Fotos in dieser Tageszeit')).toBeInTheDocument()
      expect(screen.getByText('Nachmittags (14:00 Uhr)')).toBeInTheDocument()

      const clusterHeadings = screen.getAllByRole('heading', { level: 3 })
      expect(clusterHeadings.map((heading) => heading.textContent)).toEqual([
        'Vormittags (09:00 Uhr)',
        'Nachmittags (14:00 Uhr)',
      ])
    }
  )

  it('shows a quality meter derived from rank_score', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, ranking: ranking({ rank_score: 0.9 }) })],
      total: 1,
    })

    renderPage()

    expect(await screen.findByText('Hohe Bildqualität')).toBeInTheDocument()
  })

  // Spec 0040 (Bewertungsdetails-Info-Popover), Akzeptanzkriterien 1, 2.
  describe('info popover trigger', () => {
    it('shows the trigger when the photo has criterion_scores', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })

      renderPage()

      expect(
        await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      ).toBeInTheDocument()
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
  })

  it('links back to the project detail page', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage()

    const link = await screen.findByRole('link', { name: /zurück zum projekt/i })
    expect(link).toHaveAttribute('href', '/projects/1')
  })

  // Spec 0043 (Kuratierung: Tage auf-/zuklappbar).
  describe('collapsible day sections (Spec 0043)', () => {
    function twoCategoryDayList(): PhotoListOut {
      return {
        items: [
          photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0', category_key: 'landscape' }) }),
          photo({ id: 2, ranking: ranking({ cluster_key: 'cluster-0', category_key: 'people' }) }),
        ],
        total: 2,
      }
    }

    it('renders every day header as an expanded trigger by default (Akzeptanzkriterium 2)', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoCategoryDayList())

      renderPage()

      const trigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
      expect(trigger).toHaveAttribute('aria-expanded', 'true')
      // Kein Kurzinfo-Text im aufgeklappten Zustand (Akzeptanzkriterium 5).
      expect(screen.queryByText(/\(\d+ Fotos\)/)).not.toBeInTheDocument()
      // Cluster-/Kategorie-Teilbaum ist sichtbar.
      expect(screen.getByText('Landscape')).toBeInTheDocument()
    })

    it(
      'collapses only the clicked day on trigger click, removes its subtree from the DOM and ' +
        'shows the (X Fotos) short info, leaving other days untouched (Akzeptanzkriterien 1, 3, 4, 5, 6)',
      async () => {
        const list: PhotoListOut = {
          items: [
            ...twoCategoryDayList().items,
            // Bewusst ein anderer Zeitstempel/Bucket (Nachmittags statt Vormittags) als der
            // Montags-Cluster, damit sich die beiden Tage per eindeutiger Cluster-Ueberschrift
            // unterscheiden lassen statt ueber die (in beiden Tagen gleich benannte)
            // Kategorie "Landscape".
            photo({
              id: 3,
              taken_at: '2026-07-21T14:00:00',
              ranking: ranking({ cluster_key: 'cluster-1', category_key: 'landscape' }),
            }),
          ],
          total: 3,
        }
        vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
        const user = userEvent.setup()

        renderPage()
        const mondayTrigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        const tuesdayTrigger = screen.getByRole('button', { name: 'Dienstag 21.07.2026' })
        expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
        expect(screen.getByText('Nachmittags (14:00 Uhr)')).toBeInTheDocument()

        await user.click(mondayTrigger)

        expect(mondayTrigger).toHaveAttribute('aria-expanded', 'false')
        expect(screen.getByRole('button', { name: 'Montag 20.07.2026 (2 Fotos)' })).toBe(
          mondayTrigger
        )
        // Teilbaum ist nicht nur CSS-versteckt, sondern per conditional JSX gar nicht gerendert.
        expect(screen.queryByText('Vormittags (10:00 Uhr)')).not.toBeInTheDocument()
        expect(screen.queryByText('People')).not.toBeInTheDocument()
        // Der andere Tag bleibt unveraendert aufgeklappt.
        expect(tuesdayTrigger).toHaveAttribute('aria-expanded', 'true')
        expect(screen.getByText('Nachmittags (14:00 Uhr)')).toBeInTheDocument()
      }
    )

    it(
      'shows the correct (0 Fotos) short info for a collapsed empty day and hides its ' +
        'empty-state text (Akzeptanzkriterium 8)',
      async () => {
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0' }) })],
            total: 1,
          })
          .mockResolvedValueOnce({ items: [], total: 0 })
        vi.mocked(ratingsApi.setRating).mockResolvedValue({
          user_id: 1,
          username: 'testuser',
          status: 'rejected',
        })
        const user = userEvent.setup()

        renderPage('/projects/1/curate?topN=1')
        const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
        await user.click(rejectButton)
        await waitFor(() =>
          expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
        )
        expect(screen.getByText('Keine Fotos für diesen Tag')).toBeInTheDocument()

        const trigger = screen.getByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(trigger)

        expect(trigger).toHaveAttribute('aria-expanded', 'false')
        expect(screen.getByRole('button', { name: 'Montag 20.07.2026 (0 Fotos)' })).toBeInTheDocument()
        expect(screen.queryByText('Keine Fotos für diesen Tag')).not.toBeInTheDocument()
      }
    )

    it(
      'sets aria-expanded/aria-controls correctly and links the trigger to an existing panel ' +
        'id while expanded (Akzeptanzkriterium 11)',
      async () => {
        vi.mocked(photosApi.listPhotos).mockResolvedValue(twoCategoryDayList())

        renderPage()

        const trigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        const controlsId = trigger.getAttribute('aria-controls')
        expect(controlsId).toBeTruthy()
        expect(trigger).toHaveAttribute('aria-expanded', 'true')
        // eslint-disable-next-line testing-library/no-node-access -- Verifiziert die aria-controls-Verknuepfung selbst per ID-Lookup, kein Ersatz fuer eine Rollen-Query.
        expect(document.getElementById(controlsId as string)).not.toBeNull()
      }
    )

    it(
      'renders two always-visible global "expand/collapse all" buttons above the day list that ' +
        'work with a single day in the project (Akzeptanzkriterium 7)',
      async () => {
        vi.mocked(photosApi.listPhotos).mockResolvedValue(twoCategoryDayList())
        const user = userEvent.setup()

        renderPage()
        const dayTrigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        const collapseAll = screen.getByRole('button', { name: 'Alle Tage zuklappen' })
        const expandAll = screen.getByRole('button', { name: 'Alle Tage aufklappen' })

        await user.click(collapseAll)
        expect(dayTrigger).toHaveAttribute('aria-expanded', 'false')

        await user.click(expandAll)
        expect(dayTrigger).toHaveAttribute('aria-expanded', 'true')
      }
    )

    it(
      'does not retroactively collapse a dayKey that appears only after "Alle Tage zuklappen" ' +
        'was clicked (Akzeptanzkriterium 10)',
      async () => {
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0' }) })],
            total: 1,
          })
          .mockResolvedValueOnce({
            items: [
              photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0' }) }),
              photo({
                id: 2,
                taken_at: '2026-07-21T10:00:00',
                ranking: ranking({ cluster_key: 'cluster-1' }),
              }),
            ],
            total: 2,
          })
        const user = userEvent.setup()

        const { queryClient } = renderPage()
        await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(screen.getByRole('button', { name: 'Alle Tage zuklappen' }))
        expect(screen.getByRole('button', { name: /Montag 20\.07\.2026/ })).toHaveAttribute(
          'aria-expanded',
          'false'
        )

        // Der neue Tag "erscheint" ueber denselben Invalidierungs-/Refetch-Pfad, den auch eine
        // echte Verwerfen-Mutation ausloest (useSetRatingMutation:
        // `queryClient.invalidateQueries({ queryKey: ['photos', projectId] })`) - hier direkt
        // ausgeloest, um unabhaengig vom (im zugeklappten Zustand ohnehin unsichtbaren)
        // Verwerfen-Button ausschliesslich das Klapp-Verhalten des neuen Tages zu pruefen.
        await act(async () => {
          await queryClient.invalidateQueries({ queryKey: ['photos', 1] })
        })

        await screen.findByRole('button', { name: 'Dienstag 21.07.2026' })

        expect(screen.getByRole('button', { name: /Montag 20\.07\.2026/ })).toHaveAttribute(
          'aria-expanded',
          'false'
        )
        expect(screen.getByRole('button', { name: 'Dienstag 21.07.2026' })).toHaveAttribute(
          'aria-expanded',
          'true'
        )
      }
    )

    it(
      'live-updates the (X Fotos) short info of a collapsed day once its last visible photo ' +
        'resolves as rejected, without changing any collapse state (Akzeptanzkriterium 9)',
      async () => {
        let resolveRefetch: (value: PhotoListOut) => void = () => {}
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0' }) })],
            total: 1,
          })
          .mockReturnValueOnce(
            new Promise((resolve) => {
              resolveRefetch = resolve
            })
          )
        vi.mocked(ratingsApi.setRating).mockResolvedValue({
          user_id: 1,
          username: 'testuser',
          status: 'rejected',
        })
        const user = userEvent.setup()

        renderPage('/projects/1/curate?topN=1')
        const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
        await user.click(rejectButton)
        // Kurzinfo erscheint erst nach dem Zuklappen (Akzeptanzkriterium 5) - vorher traegt der
        // Trigger noch keine Fotoanzahl im Namen.
        const trigger = screen.getByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(trigger)
        expect(trigger).toHaveAttribute('aria-expanded', 'false')
        expect(trigger).toHaveTextContent('(1 Fotos)')

        resolveRefetch({ items: [], total: 0 })

        await waitFor(() =>
          expect(
            screen.getByRole('button', { name: 'Montag 20.07.2026 (0 Fotos)' })
          ).toBeInTheDocument()
        )
        expect(
          screen.getByRole('button', { name: 'Montag 20.07.2026 (0 Fotos)' })
        ).toHaveAttribute('aria-expanded', 'false')
      }
    )

    it(
      'leaves no permanently hanging skeleton tile after collapsing and re-expanding a day ' +
        'while its reject mutation is still pending (Akzeptanzkriterium 12)',
      async () => {
        let resolveRefetch: (value: PhotoListOut) => void = () => {}
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, ranking: ranking({ rank_position: 1 }) })],
            total: 1,
          })
          .mockReturnValueOnce(
            new Promise((resolve) => {
              resolveRefetch = resolve
            })
          )
        vi.mocked(ratingsApi.setRating).mockResolvedValue({
          user_id: 1,
          username: 'testuser',
          status: 'rejected',
        })
        const user = userEvent.setup()

        renderPage()
        const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
        await user.click(rejectButton)

        // Kurzinfo erscheint erst nach dem Zuklappen (Akzeptanzkriterium 5), der Trigger wird
        // deshalb ueber seinen aufgeklappten Namen gefunden - `trigger` bleibt danach dieselbe
        // DOM-Referenz, unabhaengig vom sich aendernden zugaenglichen Namen.
        const trigger = screen.getByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(trigger) // collapse while the mutation is still pending
        expect(trigger).toHaveTextContent('(1 Fotos)')
        await user.click(trigger) // expand again, still pending

        resolveRefetch({
          items: [photo({ id: 2, relative_path: 'b.jpg', ranking: ranking({ rank_position: 2 }) })],
          total: 1,
        })

        await waitFor(() =>
          expect(screen.getByRole('button', { name: 'Verwerfen: b.jpg' })).toBeInTheDocument()
        )
        expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
        expect(screen.queryByTestId('button-spinner')).not.toBeInTheDocument()
      }
    )
  })

  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt.
  describe('category override', () => {
    it('shows the override marker for a photo with an active override', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, category_override: 'hund' })],
        total: 1,
      })

      renderPage()

      expect(await screen.findByLabelText('Kategorie manuell übersteuert')).toBeInTheDocument()
    })

    it('overrides the category from the info popover', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            ranking: ranking({ category_key: 'people' }),
            category_candidates: [
              { category_key: 'hund', origin: 'remote', score: 0.9, provider: 'anthropic' },
              { category_key: 'people', origin: 'local', score: 0.4, provider: null },
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
      await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
      await user.click(screen.getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() => expect(photosApi.setCategoryOverride).toHaveBeenCalledWith(1, 'hund'))
    })
  })
})
