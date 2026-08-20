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
    vi.mocked(opencloudApi.fetchFolderCounts).mockReset()
    // Standard-Fixture fuer Tests, denen die konkreten Zaehler egal sind - vermeidet ein
    // dauerhaft haengendes Ladeicon (unresolved Promise) in jedem bereits bestehenden Test.
    vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([])
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

  describe('Dateianzahl pro Unterordner (specs/features/0050-dateianzahl-im-ordner-browser.md)', () => {
    it('eagerly fetches folder counts for the same path as the browse request, without a click', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 3, at_limit: false, error: false },
      ])

      renderBrowser('CostaRica')

      await waitFor(() => expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledWith('CostaRica'))
    })

    it('shows a loading indicator while the count request is pending', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
      vi.mocked(opencloudApi.fetchFolderCounts).mockReturnValue(new Promise(() => {}))

      renderBrowser('CostaRica')

      expect(await screen.findByTestId('folder-count-loading')).toBeInTheDocument()
    })

    it('shows the exact count once loaded', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 42, at_limit: false, error: false },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('42')).toBeInTheDocument()
    })

    it('shows "0" (not hidden) for a folder with zero images', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 0, at_limit: false, error: false },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('0')).toBeInTheDocument()
    })

    it('shows "500+" when the folder is at the count limit', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Sub', count: 500, at_limit: true, error: false },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('500+')).toBeInTheDocument()
    })

    it('shows an error indicator for a subfolder whose count failed, without affecting others', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Good', path: 'CostaRica/Good' },
        { name: 'Bad', path: 'CostaRica/Bad' },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
        { path: 'CostaRica/Good', count: 7, at_limit: false, error: false },
        { path: 'CostaRica/Bad', count: 0, at_limit: false, error: true },
      ])

      renderBrowser('CostaRica')

      expect(await screen.findByText('7')).toBeInTheDocument()
      expect(await screen.findByText('?')).toBeInTheDocument()
      // Navigation in den fehlerhaften Ordner bleibt unangetastet (kein disabled-Button).
      expect(screen.getByRole('button', { name: 'Bad' })).toBeEnabled()
    })

    it('does not block or delay rendering the folder list while counts are still loading', async () => {
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])
      vi.mocked(opencloudApi.fetchFolderCounts).mockReturnValue(new Promise(() => {}))

      renderBrowser('CostaRica')

      expect(await screen.findByRole('button', { name: 'Sub' })).toBeInTheDocument()
    })

    it('shows an error indicator for every row when the whole count request fails, without breaking the list', async () => {
      // Review-Fund (test-engineer): der bisherige "Fehler"-Test deckte nur einen einzelnen
      // error:true-Eintrag ab, nicht den kompletten Fehlschlag der Anfrage selbst (z.B.
      // Netzwerkfehler) - der Code behandelt das bereits ueber counts.isError, aber es fehlte
      // eine Testabsicherung dafuer.
      vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
        { name: 'Sub1', path: 'CostaRica/Sub1' },
        { name: 'Sub2', path: 'CostaRica/Sub2' },
      ])
      vi.mocked(opencloudApi.fetchFolderCounts).mockRejectedValue(new Error('Netzwerkfehler'))

      renderBrowser('CostaRica')

      const errorIndicators = await screen.findAllByText('?')
      expect(errorIndicators).toHaveLength(2)
      // Die Liste selbst bleibt unbeeinflusst - beide Ordner weiterhin navigierbar.
      expect(screen.getByRole('button', { name: 'Sub1' })).toBeEnabled()
      expect(screen.getByRole('button', { name: 'Sub2' })).toBeEnabled()
    })
  })
})
