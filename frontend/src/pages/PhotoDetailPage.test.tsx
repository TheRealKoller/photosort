import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut, PhotoOut } from '../api/types'
import { setToken } from '../auth/token'
import { PhotoDetailPage } from './PhotoDetailPage'

vi.mock('../api/photos')
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
    ...overrides,
  }
}

function renderPage(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId/photos" element={<p>Grid-Seite</p>} />
        <Route path="/projects/:projectId/photos/:photoId" element={<PhotoDetailPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('PhotoDetailPage', () => {
  beforeEach(() => {
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(ratingsApi.deleteRating).mockReset()
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  it('shows a loading state before the sequence arrives', () => {
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage('/projects/1/photos/1')

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders the photo with progress "index/total" and the own rating highlighted', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [{ user_id: 1, username: 'testuser', status: 'favorite' }] }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText('1/2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /favorit/i })).toHaveAttribute('aria-pressed', 'true')
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(1, 'display')
  })

  it('disables the previous button on the first photo and the next button on the last', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    expect(screen.getByRole('button', { name: /zurück|vorherig/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /weiter|nächst/i })).toBeEnabled()
  })

  it('navigates to the next photo on next-button click, preserving the filter', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1?filter=unrated')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /weiter|nächst/i }))

    await screen.findByText('2/2')
  })

  it('navigates to the next photo on ArrowRight', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('{ArrowRight}')

    await screen.findByText('2/2')
  })

  it('sets a rating and auto-advances to the next unrated photo', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1 }), photo({ id: 2 }), photo({ id: 3 })],
      total: 3,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'favorite',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/3')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'favorite')
    await screen.findByText('2/3')
  })

  it('sets a rating via keyboard shortcut "1"', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'favorite',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('1')

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'favorite')
  })

  it('toggles an existing rating back to unrated when the same button is clicked again', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [{ user_id: 1, username: 'testuser', status: 'favorite' }] }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
  })

  it('shows a completion message instead of a fatal error once no unrated photo is left', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'favorite',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(await screen.findByText(/keine weiteren unbewerteten fotos/i)).toBeInTheDocument()
  })

  it('ignores keyboard shortcuts while a text input is focused elsewhere on the page', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await userEvent.keyboard('1')

    await waitFor(() => expect(ratingsApi.setRating).not.toHaveBeenCalled())
    document.body.removeChild(input)
  })
})
