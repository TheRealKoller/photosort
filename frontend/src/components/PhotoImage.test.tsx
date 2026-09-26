import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import { PhotoImage } from './PhotoImage'

vi.mock('../api/photos')

describe('PhotoImage', () => {
  beforeEach(() => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.stubGlobal('URL', { ...URL, revokeObjectURL: vi.fn() })
  })

  it('shows a loading indicator before the image resolves', () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReturnValue(new Promise(() => {}))

    render(<PhotoImage photoId={1} variant="thumbnail" alt="Foto 1" />)

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders the img with the resolved object URL once loaded', async () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')

    render(<PhotoImage photoId={1} variant="thumbnail" alt="Foto 1" />)

    const img = await screen.findByRole('img', { name: 'Foto 1' })
    expect(img).toHaveAttribute('src', 'blob:fake-url')
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(1, 'thumbnail')
  })

  it('shows a placeholder state on a 404 (not yet processed)', async () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockRejectedValue(
      new ApiError(404, 'Bild wird noch verarbeitet.'),
    )

    render(<PhotoImage photoId={1} variant="thumbnail" alt="Foto 1" />)

    expect(await screen.findByLabelText(/wird noch verarbeitet/i)).toBeInTheDocument()
  })

  it('shows an error state on a non-404 failure', async () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    render(<PhotoImage photoId={1} variant="thumbnail" alt="Foto 1" />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('revokes the object URL on unmount', async () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')

    const { unmount } = render(<PhotoImage photoId={1} variant="thumbnail" alt="Foto 1" />)
    await screen.findByRole('img')

    unmount()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake-url')
  })

  it('fetches the display variant again when photoId changes, revoking the old URL', async () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl)
      .mockResolvedValueOnce('blob:url-1')
      .mockResolvedValueOnce('blob:url-2')

    const { rerender } = render(<PhotoImage photoId={1} variant="display" alt="Foto 1" />)
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:url-1'))

    rerender(<PhotoImage photoId={2} variant="display" alt="Foto 2" />)

    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:url-2'))
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:url-1')
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(2, 'display')
  })

  it('offers no retry without `retryable`', async () => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    render(<PhotoImage photoId={1} variant="thumbnail" alt="Foto 1" />)

    await screen.findByRole('alert')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  describe('retryable (Spec 0531, AK13)', () => {
    it('shows the server detail with a retry that starts a new fetch', async () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl)
        .mockRejectedValueOnce(new ApiError(500, 'Speicher nicht erreichbar'))
        .mockResolvedValueOnce('blob:url-2')
      const onRetry = vi.fn()

      render(<PhotoImage photoId={7} variant="display" alt="a/b.jpg" retryable onRetry={onRetry} />)

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Bild konnte nicht geladen werden')
      expect(alert).toHaveTextContent('Speicher nicht erreichbar')
      fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

      expect(await screen.findByRole('img', { name: 'a/b.jpg' })).toHaveAttribute(
        'src',
        'blob:url-2',
      )
      expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledTimes(2)
      expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenLastCalledWith(7, 'display')
      expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it('falls back to a fixed sentence when the failure is no ApiError', async () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockRejectedValue(new TypeError('offline'))

      render(<PhotoImage photoId={7} variant="display" alt="a/b.jpg" retryable />)

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Das große Bild ist gerade nicht abrufbar.')
      expect(alert).not.toHaveTextContent('offline')
    })

    /* Kinder von `role=img` sind praesentational: Laege der Knopf darunter, waere er fuer
       Hilfstechnik unsichtbar. Ein 404 ist kein Fehler - deshalb auch kein `alert`. */
    it('shows the processing placeholder with a reachable retry and without error semantics', async () => {
      vi.mocked(photosApi.fetchPhotoImageBlobUrl)
        .mockRejectedValueOnce(new ApiError(404, 'nicht da'))
        .mockResolvedValueOnce('blob:url-2')

      render(<PhotoImage photoId={7} variant="display" alt="a/b.jpg" retryable />)

      expect(await screen.findByText('Bild wird noch verarbeitet.')).toBeVisible()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      const retry = screen.getByRole('button', { name: 'Erneut versuchen' })
      expect(retry.closest('[role="img"]')).toBeNull()

      fireEvent.click(retry)

      expect(await screen.findByRole('img', { name: 'a/b.jpg' })).toBeInTheDocument()
      expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledTimes(2)
    })
  })
})
