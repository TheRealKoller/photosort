import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import type { PhotoListOut, PhotoOut } from '../api/types'
import { setToken } from '../auth/token'
import { PhotoGridPage } from './PhotoGridPage'

vi.mock('../api/photos')

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
        <Route path="/projects/:projectId/photos" element={<PhotoGridPage />} />
        <Route path="/projects/:projectId/photos/:photoId" element={<p>Einzelbild-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('PhotoGridPage', () => {
  beforeEach(() => {
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    setToken(makeToken({ sub: '1', username: 'testuser' }))
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
})
