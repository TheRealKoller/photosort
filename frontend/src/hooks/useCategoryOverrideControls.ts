import { useState } from 'react'

import type { CategoryKey } from '../api/types'
import { useDeleteCategoryOverrideMutation, useSetCategoryOverrideMutation } from './usePhotos'

/**
 * Geteilte Steuerungslogik fuer den Kategorie-Override (specs/features/0055-remote-kategorie-
 * klassifizierung-mit-kostenschaetzung.md) - EIN Mutation-Paar pro Seite (nicht pro Foto/Kachel),
 * da eine Seite potenziell Dutzende Kacheln gleichzeitig rendert. Verfolgt lokal, WELCHES Foto x
 * Kandidat gerade eine laufende Anfrage hat, damit nur der tatsaechlich angeklickte Button busy
 * wird (Design-System: "blockiert nicht die uebrige Liste") statt aller Buttons auf der Seite.
 * Genutzt von PhotoGridPage.tsx, CurateCategoriesPage.tsx und PhotoDetailPage.tsx - identische
 * Logik, keine drei separaten Kopien.
 */
export function useCategoryOverrideControls(projectId: number) {
  const setMutation = useSetCategoryOverrideMutation(projectId)
  const deleteMutation = useDeleteCategoryOverrideMutation(projectId)
  const [pendingOverride, setPendingOverride] = useState<{
    photoId: number
    categoryKey: CategoryKey
  } | null>(null)
  const [resettingPhotoId, setResettingPhotoId] = useState<number | null>(null)

  function overrideCategory(photoId: number, categoryKey: CategoryKey): void {
    setPendingOverride({ photoId, categoryKey })
    setMutation.mutate(
      { photoId, categoryKey },
      { onSettled: () => setPendingOverride(null) }
    )
  }

  function resetOverride(photoId: number): void {
    setResettingPhotoId(photoId)
    deleteMutation.mutate(photoId, { onSettled: () => setResettingPhotoId(null) })
  }

  function pendingOverrideKeyFor(photoId: number): CategoryKey | null {
    return pendingOverride !== null && pendingOverride.photoId === photoId
      ? pendingOverride.categoryKey
      : null
  }

  function isResetPendingFor(photoId: number): boolean {
    return resettingPhotoId === photoId
  }

  return { overrideCategory, resetOverride, pendingOverrideKeyFor, isResetPendingFor }
}
