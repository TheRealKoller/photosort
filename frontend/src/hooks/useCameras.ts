import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getCameraTimeOffsetSuggestion, listCameras, setCameraTimeOffset } from '../api/cameras'
import { listPhotos } from '../api/photos'
import { projectStatsQueryKey } from './useProjects'

/** Wie viele Fotos der Vorschaustreifen des Vorschlags anbietet. Klein gehalten: der Streifen
 * ist eine Auswahlhilfe für „derselbe Moment", keine Durchsicht. */
export const CAMERA_PHOTO_STRIP_SIZE = 12

export function camerasQueryKey(projectId: number) {
  return ['cameras', projectId] as const
}

export function useCamerasQuery(projectId: number) {
  return useQuery({
    queryKey: camerasQueryKey(projectId),
    queryFn: () => listCameras(projectId),
  })
}

/**
 * Setzt den Zeitversatz einer Kamera und entwertet danach VIER Datenbestände - jeder einzeln
 * begründet, keiner vorsorglich:
 *
 * 1. **Kameraliste** - der geltende Versatz steht dort.
 * 2. **Fotoliste** (`['photos', projectId]`, breit) - `taken_at`, `taken_at_original`,
 *    `time_offset_minutes` und die SORTIERUNG ändern sich für jedes Foto dieser Kamera.
 * 3. **Kuratierungskandidaten** - liegen unter demselben `['photos', projectId]`-Präfix und
 *    werden von 2. mit erfasst. Sie sind der Grund, warum die Invalidierung breit sein MUSS:
 *    Ein Versatzwechsel baut die Gliederung neu auf und vergibt dabei NEUE Event-Ids. Eine
 *    Ansicht, die Event-Ids aus einer älteren Antwort weiterverwendet (der `eventMetaRef`-Cache
 *    in `CurateCategoriesPage.tsx` hält sie über Nachladungen hinweg), zeigte danach
 *    Überschriften zu Events, die es nicht mehr gibt.
 * 4. **Projektstatistik** - der Aufnahmezeitraum (`min`/`max` über `taken_at`) folgt dem Versatz.
 */
export function useSetCameraTimeOffsetMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ cameraId, offsetMinutes }: { cameraId: number; offsetMinutes: number }) =>
      setCameraTimeOffset(projectId, cameraId, offsetMinutes),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: camerasQueryKey(projectId) })
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
      void queryClient.invalidateQueries({ queryKey: projectStatsQueryKey(projectId) })
    },
  })
}

/**
 * Die Fotos EINER Kamera für den Vorschaustreifen des Vorschlags.
 *
 * Der Schlüssel liegt unter demselben `['photos', projectId]`-Präfix wie die übrigen
 * Fotolisten - er MUSS von der Invalidierung oben mit erfasst werden: nach einem Versatzwechsel
 * tragen dieselben Fotos andere wirksame Zeiten, und der Streifen zeigt diese Zeiten an.
 *
 * `cameraId === null` heißt "noch keine Referenzkamera gewählt" - dann läuft keine Anfrage.
 */
export function usePhotosOfCameraQuery(
  projectId: number,
  cameraId: number | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['photos', projectId, 'of-camera', cameraId] as const,
    queryFn: () =>
      listPhotos(projectId, {
        cameraId: cameraId ?? undefined,
        limit: CAMERA_PHOTO_STRIP_SIZE,
      }),
    enabled: enabled && cameraId !== null,
  })
}

/**
 * Holt einen Versatz-Vorschlag für ein Fotopaar. Als MUTATION modelliert, obwohl der Endpunkt
 * nur liest: Der Aufruf passiert auf ausdrückliche Anforderung mit zwei vom Nutzer gewählten
 * Fotos - eine Query müsste dafür ihren Schlüssel aus dem Auswahlzustand bilden und liefe bei
 * jeder Zwischenauswahl erneut.
 *
 * Entwertet NICHTS: Der Vorschlag gilt noch nicht, und bis der Nutzer ihn übernimmt, hat sich
 * kein Datenbestand geändert.
 */
export function useCameraTimeOffsetSuggestionMutation(projectId: number) {
  return useMutation({
    mutationFn: ({ photoId, referencePhotoId }: { photoId: number; referencePhotoId: number }) =>
      getCameraTimeOffsetSuggestion(projectId, photoId, referencePhotoId),
  })
}
