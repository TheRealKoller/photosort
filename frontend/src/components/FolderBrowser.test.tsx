import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as opencloudApi from '../api/opencloud'
import { ApiError } from '../api/client'
import { FolderBrowser } from './FolderBrowser'

vi.mock('../api/opencloud')

function renderBrowser(value: string, onChange = vi.fn(), onErrorChange = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const utils = render(
    <FolderBrowser value={value} onChange={onChange} onErrorChange={onErrorChange} />,
    { wrapper }
  )
  return { ...utils, onChange, onErrorChange }
}

describe('FolderBrowser', () => {
  beforeEach(() => {
    vi.mocked(opencloudApi.browseFolder).mockReset()
  })

  it('loads the root level (no path) when value is empty', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'CostaRica', path: 'CostaRica' }])

    renderBrowser('')

    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledWith(''))
    expect(await screen.findByText('CostaRica')).toBeInTheDocument()
  })

  it('calls onChange with the child path when a folder entry is clicked', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
    const user = userEvent.setup()

    const { onChange } = renderBrowser('CostaRica')

    const entry = await screen.findByRole('button', { name: 'Sub' })
    await user.click(entry)

    expect(onChange).toHaveBeenCalledWith('CostaRica/Sub')
  })

  it('renders a breadcrumb for the current path with a clickable root and each segment', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])
    const user = userEvent.setup()

    const { onChange } = renderBrowser('CostaRica/Sub')

    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledWith('CostaRica/Sub'))

    await user.click(screen.getByRole('button', { name: /wurzel|root/i }))
    expect(onChange).toHaveBeenCalledWith('')

    await user.click(screen.getByRole('button', { name: 'CostaRica' }))
    expect(onChange).toHaveBeenCalledWith('CostaRica')
  })

  it('shows a hint instead of an empty area when the folder has no subfolders', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])

    renderBrowser('CostaRica')

    expect(await screen.findByText(/keine unterordner/i)).toBeInTheDocument()
  })

  it('shows an inline error and reports it via onErrorChange on a backend error', async () => {
    vi.mocked(opencloudApi.browseFolder).mockRejectedValue(
      new ApiError(400, 'Ordner nicht gefunden')
    )

    const { onErrorChange } = renderBrowser('Nope')

    expect(await screen.findByText('Ordner nicht gefunden')).toBeInTheDocument()
    await waitFor(() => expect(onErrorChange).toHaveBeenCalledWith(true))
  })

  it('reports no error via onErrorChange once loading succeeds', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])

    const { onErrorChange } = renderBrowser('CostaRica')

    await waitFor(() => expect(onErrorChange).toHaveBeenCalledWith(false))
  })

  it('does not refetch an already-loaded level when navigating back to it via the breadcrumb', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { rerender } = render(
      <FolderBrowser value="CostaRica" onChange={vi.fn()} onErrorChange={vi.fn()} />,
      { wrapper }
    )
    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(1))

    rerender(<FolderBrowser value="CostaRica/Sub" onChange={vi.fn()} onErrorChange={vi.fn()} />)
    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(2))

    rerender(<FolderBrowser value="CostaRica" onChange={vi.fn()} onErrorChange={vi.fn()} />)
    await waitFor(() => screen.findByText('Sub'))

    // Zurueckspringen auf eine bereits geladene Ebene darf keinen dritten Request ausloesen
    // (React-Query-Cache pro Pfad, siehe specs/features/0005-minimal-project-frontend.md).
    expect(opencloudApi.browseFolder).toHaveBeenCalledTimes(2)
  })
})
