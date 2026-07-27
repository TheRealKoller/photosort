import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import type { PhotoListOut, PhotoOut } from '../api/types'
import { setToken } from '../auth/token'
import { PhotoComparePage } from './PhotoComparePage'

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

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={['/projects/1/compare']}>
      <Routes>
        <Route path="/projects/:projectId/compare" element={<PhotoComparePage />} />
        <Route path="/projects/:projectId/photos/:photoId" element={<p>Einzelbild-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('PhotoComparePage', () => {
  beforeEach(() => {
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  it('shows a loading state before photos arrive', () => {
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows both ratings side by side, own and the other user\'s', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [
            { user_id: 1, username: 'testuser', status: 'favorite' },
            { user_id: 2, username: 'other-user', status: 'rejected' },
          ],
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    expect(await screen.findByLabelText('Favorit')).toBeInTheDocument()
    expect(screen.getByLabelText('Verworfen')).toBeInTheDocument()
  })

  it('shows "unbewertet" as an explicit, visible state for a missing rating', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1, ratings: [] })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    expect((await screen.findAllByLabelText('Unbewertet')).length).toBeGreaterThanOrEqual(2)
  })

  it('links a photo to the shared detail view (deep link)', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 7 })], total: 1 })

    renderPage()

    const [item] = await screen.findAllByRole('listitem')
    const link = item.querySelector('a')
    expect(link).toHaveAttribute('href', '/projects/1/photos/7')
  })

  it('shows an inline error banner on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows an empty state when the project has no photos', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage()

    expect(await screen.findByText(/keine fotos/i)).toBeInTheDocument()
  })
})
