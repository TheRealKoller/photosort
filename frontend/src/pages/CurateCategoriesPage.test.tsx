import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut, PhotoOut, RankingOut } from '../api/types'
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

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00Z',
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

  it('groups photos by cluster then category, showing the category chip and name', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ranking: ranking({ cluster_key: 'cluster-0', category_key: 'landscape' }) }),
        photo({ id: 2, ranking: ranking({ cluster_key: 'cluster-0', category_key: 'people' }) }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    expect(await screen.findByText('cluster-0')).toBeInTheDocument()
    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('People')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(2)
  })

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
    'keeps a section visible with an empty-pool placeholder once its last photo is rejected ' +
      'instead of silently disappearing',
    async () => {
      // test-engineer-Review-Fund: der Kernfall, fuer den knownGroupKeysRef ueberhaupt gebaut
      // wurde - eine Partition, deren letztes Foto per Live-Ablehnung entfernt wird, MUSS mit
      // eigenem Leerzustand sichtbar bleiben statt spurlos aus der Gruppierung zu verschwinden.
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
      expect(screen.getByText('cluster-0')).toBeInTheDocument()
      expect(screen.getByText('Landscape')).toBeInTheDocument()
      expect(screen.getByText('Kein weiteres Foto verfügbar')).toBeInTheDocument()
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

  it('links back to the project detail page', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage()

    const link = await screen.findByRole('link', { name: /zurück zum projekt/i })
    expect(link).toHaveAttribute('href', '/projects/1')
  })
})
