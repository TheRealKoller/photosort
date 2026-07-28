import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import * as projectsApi from '../api/projects'
import type { ProjectOut } from '../api/types'
import {
  useCreateProjectMutation,
  useProjectQuery,
  useProjectsQuery,
  useTriggerScanMutation,
} from './useProjects'

vi.mock('../api/projects')

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    ...overrides,
  }
}

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  }
}

describe('useProjectsQuery', () => {
  it('fetches the project list', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([project()])
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useProjectsQuery(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([project()])
  })
})

describe('useProjectQuery', () => {
  it('fetches a single project by id', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useProjectQuery(1), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.getProject).toHaveBeenCalledWith(1)
  })

  it('keeps polling while the last scan is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_scan: runningScan() })
    )
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useProjectQuery(1), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const callsAfterFirstFetch = vi.mocked(projectsApi.getProject).mock.calls.length

    await vi.advanceTimersByTimeAsync(5000)

    expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBeGreaterThan(
      callsAfterFirstFetch
    )
    vi.useRealTimers()
  })

  it('does not poll when no scan is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useProjectQuery(1), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const callsAfterFirstFetch = vi.mocked(projectsApi.getProject).mock.calls.length

    await vi.advanceTimersByTimeAsync(10000)

    expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBe(callsAfterFirstFetch)
    vi.useRealTimers()
  })
})

describe('useCreateProjectMutation', () => {
  it('invalidates the project list after a successful create', async () => {
    vi.mocked(projectsApi.createProject).mockResolvedValue(project())
    vi.mocked(projectsApi.listProjects).mockResolvedValue([project()])
    const { wrapper, queryClient } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useCreateProjectMutation(), { wrapper })
    result.current.mutate({ name: 'Costa Rica', opencloud_path: 'CostaRica' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['projects'] })
  })
})

describe('useTriggerScanMutation', () => {
  it('invalidates the project detail query after a successful trigger', async () => {
    vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
    const { wrapper, queryClient } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useTriggerScanMutation(1), { wrapper })
    result.current.mutate()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.triggerScan).toHaveBeenCalledWith(1)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['project', 1] })
  })
})

function runningScan(): ProjectOut['last_scan'] {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    files_found: 0,
    photos_added: 0,
    photos_updated: 0,
    photos_removed: 0,
    files_skipped: 0,
    error_message: null,
  }
}
