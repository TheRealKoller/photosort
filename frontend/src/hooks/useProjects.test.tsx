import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import * as projectsApi from '../api/projects'
import type { ProjectOut, ProjectStatsOut } from '../api/types'
import { setToken } from '../auth/token'
import {
  useClassificationEstimateQuery,
  useConfirmAusschussGateMutation,
  useCreateProjectMutation,
  PROJECT_STATS_STALE_TIME_MS,
  projectStatsQueryKey,
  projectStatsQueryOptions,
  useProjectQuery,
  useProjectsQuery,
  useProjectStatsQuery,
  useSetCloudVisionConsentMutation,
  useTriggerScanMutation,
  useTriggerClassificationMutation,
  useTriggerScoreMutation,
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
    last_criterion_scoring_run: null,
    last_remote_category_classification_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
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

  it('keeps polling while the last scoring run is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_scoring_run: runningScoringRun() })
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

  it('keeps polling while the last criterion-scoring run is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_criterion_scoring_run: runningCriterionScoringRun() })
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

  it('keeps polling while the last remote category classification run is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_remote_category_classification_run: runningRemoteCategoryRun() })
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

describe('useTriggerScoreMutation', () => {
  it('invalidates the project detail query after a successful trigger', async () => {
    vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
    const { wrapper, queryClient } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useTriggerScoreMutation(1), { wrapper })
    result.current.mutate()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.triggerScore).toHaveBeenCalledWith(1)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['project', 1] })
  })
})

describe('useConfirmAusschussGateMutation', () => {
  it('invalidates the project detail query after a successful confirm', async () => {
    vi.mocked(projectsApi.confirmAusschussGate).mockResolvedValue({ status: 'confirmed' })
    const { wrapper, queryClient } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useConfirmAusschussGateMutation(1), { wrapper })
    result.current.mutate()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['project', 1] })
  })
})

describe('useTriggerClassificationMutation', () => {
  it('forwards scoring_run_id and use_cloud, and invalidates project, estimate and fine labels', async () => {
    vi.mocked(projectsApi.triggerClassification).mockResolvedValue({ status: 'queued' })
    const { wrapper, queryClient } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useTriggerClassificationMutation(1), { wrapper })
    result.current.mutate({ scoringRunId: 5, useCloud: true })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 5, true)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['project', 1] })
    // Beide haengen am Ergebnis der Remote-Phase, die dieser eine Lauf mit ausfuehren kann
    // (specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md).
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['classification-estimate', 1] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['fine-labels', 1] })
  })

  it('forwards use_cloud false unchanged', async () => {
    vi.mocked(projectsApi.triggerClassification).mockResolvedValue({ status: 'queued' })
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useTriggerClassificationMutation(1), { wrapper })
    result.current.mutate({ scoringRunId: 5, useCloud: false })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 5, false)
  })
})

describe('useSetCloudVisionConsentMutation', () => {
  it('invalidates the project detail query after a successful update, forwarding enabled', async () => {
    vi.mocked(projectsApi.setCloudVisionConsent).mockResolvedValue({
      cloud_vision_detection_enabled: true,
      cloud_vision_consent_at: '2026-08-21T10:00:00Z',
    })
    const { wrapper, queryClient } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useSetCloudVisionConsentMutation(1), { wrapper })
    result.current.mutate(true)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.setCloudVisionConsent).toHaveBeenCalledWith(1, true)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['project', 1] })
  })
})

describe('useClassificationEstimateQuery', () => {
  it('fetches the estimate for a project, covering both cloud shares', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue({
      candidate_count: 42,
      remote_category_candidate_count: 40,
      landmark_candidate_count: 2,
      provider: 'anthropic',
      model: 'claude-haiku-4-5',
      price_per_image_usd: 0.0052,
      estimated_cost_usd: 0.2184,
    })
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useClassificationEstimateQuery(1), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.getClassificationEstimate).toHaveBeenCalledWith(1)
    expect(result.current.data?.candidate_count).toBe(42)
    expect(result.current.data?.landmark_candidate_count).toBe(2)
  })
})


function runningScan(): ProjectOut['last_scan'] {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    files_found: 0,
    total_files: null,
    photos_added: 0,
    photos_updated: 0,
    photos_removed: 0,
    files_skipped: 0,
    error_message: null,
  }
}

function runningScoringRun(): ProjectOut['last_scoring_run'] {
  return {
    id: 1,
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    photos_total: 10,
    photos_processed: 3,
    suggestions_found: 0,
    error_message: null,
    gate_confirmed_at: null,
  }
}

function runningCriterionScoringRun(): ProjectOut['last_criterion_scoring_run'] {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    photos_total: 10,
    photos_processed: 3,
    error_message: null,
    phase: 'criteria',
    cloud_requested: false,
    cloud_error_message: null,
  }
}

function runningRemoteCategoryRun(): ProjectOut['last_remote_category_classification_run'] {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    photos_total: 10,
    photos_processed: 3,
    error_message: null,
  }
}

// specs/features/0207-projekt-statistikseite.md: Momentaufnahme statt Live-Ansicht - kein
// Polling, und der Query-Key traegt die angemeldete Identitaet.

function stats(): ProjectStatsOut {
  return {
    photo_count: 0,
    storage: { opencloud_bytes: 0, local_cache_bytes: 0, local_database_bytes_estimate: null },
    taken_at_earliest: null,
    taken_at_latest: null,
    categories: { classified_photo_count: 0, unclassified_photo_count: 0, entries: [] },
    manual_category_override_count: 0,
    cost: { currency: 'USD', total_usd: 0, by_purpose: [] },
    progress: {
      scanned: 0,
      thumbnails_ready: 0,
      ausschuss_scored: 0,
      ranked: 0,
      remote_classified: 0,
    },
    ratings: { favorite: 0, album_worthy: 0, rejected: 0, unrated: 0 },
    last_successful_runs: {
      scan: null,
      scoring: null,
      classification: null,
      remote_category_classification: null,
    },
    diagnostics: {
      last_scan_files_skipped: null,
      duplicate_photo_count: 0,
      remote_failures: [],
    },
  }
}

/** Ein syntaktisch gueltiges JWT mit dem gegebenen `username`-Claim - `decodeUsername` liest den
 * Payload rein clientseitig, ohne Signaturpruefung. */
function tokenFor(username: string): string {
  const payload = btoa(JSON.stringify({ sub: '1', username }))
  return `header.${payload}.signature`
}

describe('useProjectStatsQuery', () => {
  afterEach(() => {
    window.localStorage.clear()
  })

  it('fetches the stats of the given project', async () => {
    vi.mocked(projectsApi.getProjectStats).mockResolvedValue(stats())
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useProjectStatsQuery(7), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(projectsApi.getProjectStats).toHaveBeenCalledWith(7)
  })

  it('keeps the project id and the signed-in identity in the query key', () => {
    setToken(tokenFor('daniel'))

    const key = projectStatsQueryKey(7)

    expect(key).toContain(7)
    expect(key).toContain('daniel')
  })

  it('gives a second identity its own cache entry', () => {
    // Sicherheits-Muss der Spec: die Anmeldung ist eine reine SPA-Navigation ohne Full Reload,
    // der QueryClient wird beim Nutzerwechsel nicht geleert - ohne Identitaet im Key zeigte der
    // zweite Nutzer auf einem gemeinsam genutzten Familiengeraet kurzzeitig den
    // zwischengespeicherten Bewertungsstand des ersten.
    setToken(tokenFor('daniel'))
    const first = projectStatsQueryKey(7)
    setToken(tokenFor('ehefrau'))
    const second = projectStatsQueryKey(7)

    expect(second).not.toEqual(first)
  })

  it('does not poll - several minutes produce exactly one request', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(projectsApi.getProjectStats).mockResolvedValue(stats())
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useProjectStatsQuery(7), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const callsAfterFirstFetch = vi.mocked(projectsApi.getProjectStats).mock.calls.length

    await vi.advanceTimersByTimeAsync(5 * 60 * 1000)

    expect(vi.mocked(projectsApi.getProjectStats).mock.calls.length).toBe(callsAfterFirstFetch)
    vi.useRealTimers()
  })

  it('does not refetch on window focus and keeps the result fresh for a while', () => {
    // Zweite Haelfte der Selbst-DoS-Gegenmassnahme (Security-Abschnitt der Spec, Punkt 3): der
    // Endpunkt misst zwei os.stat je Foto - ohne diese beiden Optionen liefe der QueryClient auf
    // seinen Defaults und stiesse bei jedem Tab-Wechsel eine vollstaendige neue Messung an.
    expect(PROJECT_STATS_STALE_TIME_MS).toBeGreaterThan(0)
    expect(projectStatsQueryOptions(7).refetchOnWindowFocus).toBe(false)
    expect(projectStatsQueryOptions(7).staleTime).toBe(PROJECT_STATS_STALE_TIME_MS)
    expect('refetchInterval' in projectStatsQueryOptions(7)).toBe(false)
  })
})
