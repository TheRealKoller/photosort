import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { CriterionScoreOut, PhotoListOut, PhotoOut, RankingOut } from '../api/types'
import { setToken } from '../auth/token'
import { CurateCategoriesPage } from './CurateCategoriesPage'

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
    ...overrides,
  }
}

function renderPage(initialPath = '/projects/1/curate?topN=3') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId" element={<p>Projekt-Detailseite</p>} />
        <Route path="/projects/:projectId/curate" element={<CurateCategoriesPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
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

    const headings = await screen.findAllByRole('heading', { level: 2 })
    expect(headings.map((heading) => heading.textContent)).toEqual([
      'Montag 20.07.2026',
      'Dienstag 21.07.2026',
    ])
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
})
