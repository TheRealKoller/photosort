import { apiFetch } from './client'
import type { CameraTimeOffsetSuggestionOut, ProjectCameraOut } from './types'

/** Die Kameras eines Projekts, vom Server nach Hersteller/Modell sortiert - die Reihenfolge wird
 * hier NICHT nachsortiert. */
export function listCameras(projectId: number): Promise<ProjectCameraOut[]> {
  return apiFetch<ProjectCameraOut[]>(`/projects/${projectId}/cameras`)
}

/**
 * Setzt den Zeitversatz einer Kamera. Der einzige schreibende Aufruf dieses Moduls.
 *
 * Wirkt unmittelbar auf Gliederung, Reihenfolge, Statistik und Ortsübernahme - deshalb entwertet
 * der zugehörige Hook mehr als nur die Kameraliste (siehe `hooks/useCameras.ts`).
 */
export function setCameraTimeOffset(
  projectId: number,
  cameraId: number,
  offsetMinutes: number,
): Promise<ProjectCameraOut> {
  return apiFetch<ProjectCameraOut>(`/projects/${projectId}/cameras/${cameraId}/time-offset`, {
    method: 'PUT',
    body: { offset_minutes: offsetMinutes },
  })
}

/**
 * Errechnet einen Versatz-Vorschlag aus einem Fotopaar desselben Moments - ein reiner
 * Lesevorgang, der NICHTS speichert. Übernommen wird der Wert über `setCameraTimeOffset`.
 *
 * `photoId` ist das Foto der betroffenen Kamera, `referencePhotoId` eines von einer anderen.
 */
export function getCameraTimeOffsetSuggestion(
  projectId: number,
  photoId: number,
  referencePhotoId: number,
): Promise<CameraTimeOffsetSuggestionOut> {
  const query = new URLSearchParams({
    photo_id: String(photoId),
    reference_photo_id: String(referencePhotoId),
  })
  return apiFetch<CameraTimeOffsetSuggestionOut>(
    `/projects/${projectId}/camera-time-offset-suggestion?${query.toString()}`,
  )
}
