import { render, screen, waitFor } from '@testing-library/react'
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
      new ApiError(404, 'Bild wird noch verarbeitet.')
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
})
