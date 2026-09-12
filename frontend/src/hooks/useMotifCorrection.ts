import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../api/client'
import { deleteMotifCorrection, setMotifCorrection } from '../api/photos'
import type { MotifKey } from '../api/types'

/** Die fehlgeschlagene Korrektur: welche Zeile, und der `detail` des Backends WOERTLICH. Die
 * Meldung unter der Liste zeigt ihn als Textknoten, nicht umformuliert. */
export interface MotifCorrectionError {
  motifKey: MotifKey
  detail: string
}

const GENERIC_DETAIL = 'Die Korrektur konnte nicht gespeichert werden.'

function detailOf(error: unknown): string {
  return error instanceof ApiError && error.detail.length > 0 ? error.detail : GENERIC_DETAIL
}

/**
 * Geteilte Steuerungslogik der Motivkorrektur - EIN Mutation-Paar pro Seite (nicht pro Foto oder
 * pro Zeile), da eine Seite potenziell Dutzende Kacheln gleichzeitig rendert. Muster wie
 * `useCategoryOverrideControls`.
 *
 * Verfolgt lokal, WELCHES Foto x Motiv gerade eine laufende Anfrage hat, damit nur die
 * Schaltflaechen DIESER ZEILE busy werden und die uebrige Liste bedienbar bleibt - der globale
 * `isPending` der Mutation sperrte dagegen acht Zeilen auf einmal.
 *
 * Der Fehler wird lokal gehalten statt aus der Mutation gelesen: ein erneuter, erfolgreicher
 * Versuch loescht ihn, und die Meldung muss den Motivschluessel nennen - der steckt in der
 * Mutation nicht mehr, sobald sie zurueckgesetzt ist.
 */
export function useMotifCorrectionControls(projectId: number) {
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<{ photoId: number; motifKey: MotifKey } | null>(null)
  const [error, setError] = useState<MotifCorrectionError | null>(null)

  function invalidate(): void {
    // Dieselbe breite Invalidierung wie bei der Bewertung: die wirksame Staerke steht in JEDER
    // Filtervariante der Fotoliste dieses Projekts.
    void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
  }

  const setMutation = useMutation({
    mutationFn: ({
      photoId,
      motifKey,
      applies,
    }: {
      photoId: number
      motifKey: MotifKey
      applies: boolean
    }) => setMotifCorrection(photoId, motifKey, applies),
    onSuccess: invalidate,
  })

  const deleteMutation = useMutation({
    mutationFn: ({ photoId, motifKey }: { photoId: number; motifKey: MotifKey }) =>
      deleteMotifCorrection(photoId, motifKey),
    onSuccess: invalidate,
  })

  function correctMotif(photoId: number, motifKey: MotifKey, applies: boolean): void {
    setPending({ photoId, motifKey })
    setError(null)
    setMutation.mutate(
      { photoId, motifKey, applies },
      {
        onError: (cause) => setError({ motifKey, detail: detailOf(cause) }),
        onSettled: () => setPending(null),
      },
    )
  }

  function withdrawCorrection(photoId: number, motifKey: MotifKey): void {
    setPending({ photoId, motifKey })
    setError(null)
    deleteMutation.mutate(
      { photoId, motifKey },
      {
        onError: (cause) => setError({ motifKey, detail: detailOf(cause) }),
        onSettled: () => setPending(null),
      },
    )
  }

  function pendingMotifKeyFor(photoId: number): MotifKey | null {
    return pending !== null && pending.photoId === photoId ? pending.motifKey : null
  }

  return { correctMotif, withdrawCorrection, pendingMotifKeyFor, error }
}
