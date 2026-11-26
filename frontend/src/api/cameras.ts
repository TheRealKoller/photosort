import { apiFetch } from './client'
import type { CameraTimeOffsetSuggestionOut, ProjectCameraOut } from './types'

/** Die Kameras eines Projekts, vom Server nach Hersteller/Modell sortiert - die Reihenfolge wird
 * hier NICHT nachsortiert. */
export function listCameras(projectId: number): Promise<ProjectCameraOut[]> {
  return apiFetch('/projects/{project_id}/cameras', { pathParams: { project_id: projectId } })
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
  return apiFetch('/projects/{project_id}/cameras/{camera_id}/time-offset', {
    method: 'PUT',
    pathParams: { project_id: projectId, camera_id: cameraId },
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
  return apiFetch('/projects/{project_id}/camera-time-offset-suggestion', {
    pathParams: { project_id: projectId },
    query: { photo_id: photoId, reference_photo_id: referencePhotoId },
  })
}
