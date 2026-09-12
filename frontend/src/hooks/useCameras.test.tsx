import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as camerasApi from '../api/cameras'
import type { ProjectCameraOut } from '../api/types'
import {
  camerasQueryKey,
  useCameraTimeOffsetSuggestionMutation,
  useCamerasQuery,
  useSetCameraTimeOffsetMutation,
} from './useCameras'
import { projectStatsQueryKey } from './useProjects'

vi.mock('../api/cameras')

const PROJECT_ID = 3

const CAMERA: ProjectCameraOut = {
  id: 7,
  label: 'Canon EOS 5D',
  photo_count: 42,
  offset_minutes: 0,
}

function makeWrapper(queryClient: QueryClient) {
  return function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

describe('useCamerasQuery', () => {
  beforeEach(() => {
    vi.mocked(camerasApi.listCameras).mockReset()
    vi.mocked(camerasApi.listCameras).mockResolvedValue([CAMERA])
  })

  it('loads the camera list of the project', async () => {
    const { result } = renderHook(() => useCamerasQuery(PROJECT_ID), {
      wrapper: makeWrapper(makeQueryClient()),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(camerasApi.listCameras).toHaveBeenCalledWith(PROJECT_ID)
    expect(result.current.data).toEqual([CAMERA])
  })
})

describe('useSetCameraTimeOffsetMutation', () => {
  beforeEach(() => {
    vi.mocked(camerasApi.setCameraTimeOffset).mockReset()
    vi.mocked(camerasApi.setCameraTimeOffset).mockResolvedValue({
      ...CAMERA,
      offset_minutes: -120,
    })
  })

  it('sends project, camera and offset to the endpoint', async () => {
    const { result } = renderHook(() => useSetCameraTimeOffsetMutation(PROJECT_ID), {
      wrapper: makeWrapper(makeQueryClient()),
    })

    result.current.mutate({ cameraId: 7, offsetMinutes: -120 })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(camerasApi.setCameraTimeOffset).toHaveBeenCalledWith(PROJECT_ID, 7, -120)
  })

  // VIER eigene Assertions statt einer Sammelpruefung: jeder Bestand hat einen eigenen Grund,
  // und faellt einer der vier Aufrufe weg, soll genau EIN Fall roeten und benennen, welcher.
  it('entwertet die Kameraliste', async () => {
    const queryClient = makeQueryClient()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useSetCameraTimeOffsetMutation(PROJECT_ID), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ cameraId: 7, offsetMinutes: -120 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidate).toHaveBeenCalledWith({ queryKey: camerasQueryKey(PROJECT_ID) })
  })

  it('entwertet die Fotoliste', async () => {
    const queryClient = makeQueryClient()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useSetCameraTimeOffsetMutation(PROJECT_ID), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ cameraId: 7, offsetMinutes: -120 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['photos', PROJECT_ID] })
  })

  it('entwertet die Kuratierungskandidaten ueber denselben breiten Praefix', async () => {
    // Die Kandidaten liegen unter ['photos', projectId, 'curate', 'candidates', ...]. Geprueft
    // wird nicht der Aufruf (den deckt der Fall oben), sondern die WIRKUNG: ein Versatzwechsel
    // vergibt neue Event-Ids, und eine Ansicht mit alten Ids zeigte Ueberschriften zu Events,
    // die es nicht mehr gibt.
    const queryClient = makeQueryClient()
    const candidatesKey = ['photos', PROJECT_ID, 'curate', 'candidates', 1, 'landschaft', 0]
    queryClient.setQueryData(candidatesKey, { items: [], total: 0 })
    const { result } = renderHook(() => useSetCameraTimeOffsetMutation(PROJECT_ID), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ cameraId: 7, offsetMinutes: -120 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(queryClient.getQueryState(candidatesKey)?.isInvalidated).toBe(true)
  })

  it('entwertet die Projektstatistik', async () => {
    const queryClient = makeQueryClient()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useSetCameraTimeOffsetMutation(PROJECT_ID), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ cameraId: 7, offsetMinutes: -120 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidate).toHaveBeenCalledWith({ queryKey: projectStatsQueryKey(PROJECT_ID) })
  })

  it('entwertet nichts, wenn der Aufruf fehlschlaegt', async () => {
    // Ein 409/422 hat NICHTS geschrieben - eine Entwertung wuerde die Oberflaeche unnoetig neu
    // laden lassen und den Anschein einer Aenderung erzeugen.
    vi.mocked(camerasApi.setCameraTimeOffset).mockRejectedValue(new Error('409'))
    const queryClient = makeQueryClient()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useSetCameraTimeOffsetMutation(PROJECT_ID), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ cameraId: 7, offsetMinutes: -120 })
    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(invalidate).not.toHaveBeenCalled()
  })
})

describe('useCameraTimeOffsetSuggestionMutation', () => {
  beforeEach(() => {
    vi.mocked(camerasApi.getCameraTimeOffsetSuggestion).mockReset()
    vi.mocked(camerasApi.getCameraTimeOffsetSuggestion).mockResolvedValue({
      camera_id: 7,
      camera_label: 'Canon EOS 5D',
      offset_minutes: -120,
      photo_taken_at_original: '2026-08-12T14:32:00',
      reference_taken_at: '2026-08-12T12:32:00',
    })
  })

  it('sends both photo ids', async () => {
    const { result } = renderHook(() => useCameraTimeOffsetSuggestionMutation(PROJECT_ID), {
      wrapper: makeWrapper(makeQueryClient()),
    })

    result.current.mutate({ photoId: 11, referencePhotoId: 12 })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(camerasApi.getCameraTimeOffsetSuggestion).toHaveBeenCalledWith(PROJECT_ID, 11, 12)
    expect(result.current.data?.offset_minutes).toBe(-120)
  })

  it('entwertet keinen Datenbestand - der Vorschlag gilt noch nicht', async () => {
    const queryClient = makeQueryClient()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useCameraTimeOffsetSuggestionMutation(PROJECT_ID), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ photoId: 11, referencePhotoId: 12 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidate).not.toHaveBeenCalled()
  })
})
