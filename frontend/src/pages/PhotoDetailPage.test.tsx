import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut, PhotoOut, SuggestionOut } from '../api/types'
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
    suggestion: null,
    ...overrides,
  }
}

function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    local_quality_score: null,
    sharpness: 1.0,
    exposure: 0.5,
    cluster_key: null,
    category: null,
    computed_at: '2026-07-20T10:00:00Z',
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

  it('ignores an unknown/tampered filter value in the URL instead of forwarding it to the API', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1?filter=not-a-real-filter')
    await screen.findByText('1/1')

    expect(photosApi.listPhotos).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ ratingStatus: undefined })
    )
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
    // Anders als beim Setzen einer Bewertung (spec: "Nach dem Setzen einer Bewertung springt...")
    // ist ein Toggle-zurueck-auf-unbewertet eine Korrektur, kein "fertig mit diesem Foto" -
    // Auto-Advance waere hier ueberraschend (Nutzer klickt erneut, um einen Fehlklick
    // rueckgaengig zu machen, nicht um weiterzuspringen).
    await waitFor(() => expect(ratingsApi.deleteRating).toHaveBeenCalled())
    expect(screen.getByText('1/2')).toBeInTheDocument()
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

    expect(await screen.findByRole('status')).toHaveTextContent(/keine weiteren unbewerteten fotos/i)
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')

    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    await screen.findByText('1/1')
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

  it('shows the suggestion reason and a confirm button for a low-quality suggestion', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1, ratings: [], suggestion: suggestion({ reason: 'low_quality' }) })],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText(/automatischer vorschlag: verworfen/i)).toBeInTheDocument()
    expect(screen.getByText(/geringe bildqualität/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /vorschlag übernehmen/i })).toBeInTheDocument()
  })

  it('shows the duplicate-of reason for a duplicate suggestion', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [],
          suggestion: suggestion({ reason: 'duplicate', duplicate_of: 42 }),
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText(/duplikat von foto #42/i)).toBeInTheDocument()
  })

  it('does not show a suggestion once an own rating exists', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }],
          suggestion: null,
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    await screen.findByText('1/1')
    expect(screen.queryByText(/automatischer vorschlag/i)).not.toBeInTheDocument()
  })

  it('confirms a suggestion via the same mutation path as a manual rating and auto-advances', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [], suggestion: suggestion({ status: 'rejected' }) }),
        photo({ id: 2, ratings: [] }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    const confirmButton = await screen.findByRole('button', { name: /vorschlag übernehmen/i })
    await user.click(confirmButton)

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    await screen.findByText('2/2')
  })
})
