import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as exportApi from '../api/export'
import { useExport } from './useExport'
import * as useProjects from './useProjects'
import * as useTriggerConfirmation from './useTriggerConfirmation'

vi.mock('../api/export')
vi.mock('./useProjects')
vi.mock('./useTriggerConfirmation')

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(exportApi.getExportPreview).mockResolvedValue({ photo_count: 3 })
  vi.mocked(exportApi.getExportRun).mockResolvedValue({
    id: 1,
    status: 'success',
    started_at: '2026-11-01T10:00:00Z',
    finished_at: '2026-11-01T10:00:05Z',
    target_path: 'PhotoSort-Export/Costa Rica',
    photo_count: 3,
    exported_count: 3,
    failed_count: 0,
    error_message: null,
    failed_photos: [],
  })
  vi.mocked(useProjects.useProjectQuery).mockReturnValue({
    data: undefined,
    refetch: vi.fn(),
  } as never)
})

describe('useExport', () => {
  it('resets the awaiting state when the trigger fails', async () => {
    const setAwaiting = vi.fn()
    vi.mocked(useTriggerConfirmation.useTriggerConfirmation).mockReturnValue([false, setAwaiting])
    vi.mocked(exportApi.triggerExport).mockRejectedValue(new Error('Fehler beim Auslösen'))

    const { result } = renderHook(() => useExport(7), { wrapper: makeWrapper() })

    await expect(result.current.trigger.mutateAsync()).rejects.toThrow('Fehler beim Auslösen')

    // Ohne dieses Zuruecksetzen bliebe `awaiting` dauerhaft `true` und der Ausloeser permanent
    // gesperrt (Muster ScanStepPage).
    expect(setAwaiting).toHaveBeenCalledWith(false)
  })

  it('does not reset awaiting when the trigger succeeds', async () => {
    const setAwaiting = vi.fn()
    vi.mocked(useTriggerConfirmation.useTriggerConfirmation).mockReturnValue([false, setAwaiting])
    vi.mocked(exportApi.triggerExport).mockResolvedValue({ status: 'queued' })

    const { result } = renderHook(() => useExport(7), { wrapper: makeWrapper() })

    await result.current.trigger.mutateAsync()

    expect(setAwaiting).not.toHaveBeenCalled()
  })
})
