import { describe, expect, it, vi } from 'vitest'

import { getCameraTimeOffsetSuggestion, listCameras, setCameraTimeOffset } from './cameras'
import { ApiError, apiFetch } from './client'
import type { CameraTimeOffsetSuggestionOut, ProjectCameraOut } from './types'

vi.mock('./client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./client')>()),
  apiFetch: vi.fn(),
}))

const CAMERA: ProjectCameraOut = {
  id: 7,
  label: 'Canon EOS 5D',
  photo_count: 42,
  offset_minutes: -120,
}

const SUGGESTION: CameraTimeOffsetSuggestionOut = {
  camera_id: 7,
  camera_label: 'Canon EOS 5D',
  offset_minutes: -120,
  photo_taken_at_original: '2026-08-12T14:32:00',
  reference_taken_at: '2026-08-12T12:32:00',
}

describe('api/cameras', () => {
  it('fetches the camera list from GET /projects/{id}/cameras', async () => {
    vi.mocked(apiFetch).mockResolvedValue([CAMERA])

    const result = await listCameras(3)

    expect(apiFetch).toHaveBeenCalledWith('/projects/3/cameras')
    expect(result).toEqual([CAMERA])
  })

  it('keeps the order the server sent', async () => {
    // Der Server sortiert nach Hersteller/Modell - eine zweite Sortierung hier waere eine zweite,
    // driftende Aussage darueber, wie die Liste aussieht.
    const nikon: ProjectCameraOut = { ...CAMERA, id: 1, label: 'Nikon Z6' }
    vi.mocked(apiFetch).mockResolvedValue([nikon, CAMERA])

    const result = await listCameras(3)

    expect(result.map((camera) => camera.label)).toEqual(['Nikon Z6', 'Canon EOS 5D'])
  })

  it('puts the offset to the time-offset route and returns the updated camera', async () => {
    vi.mocked(apiFetch).mockResolvedValue(CAMERA)

    const result = await setCameraTimeOffset(3, 7, -120)

    expect(apiFetch).toHaveBeenCalledWith('/projects/3/cameras/7/time-offset', {
      method: 'PUT',
      body: { offset_minutes: -120 },
    })
    expect(result).toEqual(CAMERA)
  })

  it('sends a zero offset as a real value, not as an omitted field', async () => {
    // Auf `0` zu setzen ist die RUECKNAHME des Versatzes und muss den Endpunkt erreichen - ein
    // weggelassenes Feld waere ein Validierungsfehler, kein Zuruecksetzen.
    vi.mocked(apiFetch).mockResolvedValue({ ...CAMERA, offset_minutes: 0 })

    await setCameraTimeOffset(3, 7, 0)

    expect(apiFetch).toHaveBeenCalledWith('/projects/3/cameras/7/time-offset', {
      method: 'PUT',
      body: { offset_minutes: 0 },
    })
  })

  it('fetches the suggestion with both photo ids as query parameters', async () => {
    vi.mocked(apiFetch).mockResolvedValue(SUGGESTION)

    const result = await getCameraTimeOffsetSuggestion(3, 11, 12)

    expect(apiFetch).toHaveBeenCalledWith(
      '/projects/3/camera-time-offset-suggestion?photo_id=11&reference_photo_id=12',
    )
    expect(result).toEqual(SUGGESTION)
  })

  it.each([
    ['listCameras', () => listCameras(3)],
    ['setCameraTimeOffset', () => setCameraTimeOffset(3, 7, -120)],
    ['getCameraTimeOffsetSuggestion', () => getCameraTimeOffsetSuggestion(3, 11, 12)],
  ])('leitet einen Fehler von %s unveraendert durch', async (_name, call) => {
    // Der Backend-`detail`-Text traegt die Klartextmeldung fuer 409/422 - er darf hier nicht
    // gegen eine eigene Formulierung getauscht oder verschluckt werden.
    const failure = new ApiError(409, 'Fuer dieses Projekt laeuft gerade ein Vorgang.')
    vi.mocked(apiFetch).mockRejectedValue(failure)

    await expect(call()).rejects.toBe(failure)
  })
})
