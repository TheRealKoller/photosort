import { useRef, useState } from 'react'

import { ApiError } from '../api/client'
import type { PhotoOut, RatingStatus } from '../api/types'
import { reAddDecision } from '../utils/albumDraft'
import { EXCHANGED_TITLE } from '../utils/albumDraftTexts'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import { ownRatingStatus } from '../utils/ownRating'
import {
  useDraftDecisionMutation,
  useDraftExchangeMutation,
  useDraftExchangeUndoMutation,
} from './usePhotos'

const ACTION_FAILED_TEXT = 'Die Aktion ist fehlgeschlagen.'

type UndoTarget =
  | { kind: 'strike'; photo: PhotoOut; previous: RatingStatus | null }
  | {
      kind: 'exchange'
      replaced: PhotoOut
      chosen: PhotoOut
      chosenPrevious: 'rejected' | null
      replacedPrevious: 'album_worthy' | null
    }

export interface DraftFocusRequest {
  key: string
  scroll: boolean
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.detail : ACTION_FAILED_TEXT
}

export interface UseDraftDecisionsOptions {
  projectId: number
  username: string | null
  albumOf: (eventId: number) => PhotoOut[]
  struckOf: (eventId: number) => PhotoOut[]
  onRequestFocus: (request: DraftFocusRequest) => void
  /** Nach einem Schreibweg: `photoId` schließt das Band nur, wenn es an diesem Foto offen ist;
   * `null` schließt jedes offene Panel. */
  onCloseBand: (photoId: number | null) => void
  /** Nach einem gelungenen Tausch: wohin die Aufmerksamkeit geht, entscheidet die Seite. */
  onExchanged: (chosen: PhotoOut) => void
}

/**
 * Die Schreibwege des Album-Entwurfs - Streichen, Wieder aufnehmen, Hinzufügen, Tauschen,
 * Rückgängig - samt Sperre je Foto, Fehlerplatz und Rückgängig-Ziel.
 */
export function useDraftDecisions({
  projectId,
  username,
  albumOf,
  struckOf,
  onRequestFocus,
  onCloseBand,
  onExchanged,
}: UseDraftDecisionsOptions) {
  const decisionMutation = useDraftDecisionMutation(projectId, username)
  const exchangeMutation = useDraftExchangeMutation(projectId, username)
  const undoMutation = useDraftExchangeUndoMutation(projectId, username)
  const ownStatusOf = (photo: PhotoOut) => ownRatingStatus(photo.ratings, username)

  // Die Sperre je Foto: der Ref ist die SYNCHRONE Wahrheit, der State löst das Neurendern aus.
  const lockedRef = useRef<Set<number>>(new Set())
  const [locked, setLocked] = useState<Set<number>>(new Set())
  function lock(ids: number[]): boolean {
    if (ids.some((photoId) => lockedRef.current.has(photoId))) {
      return false
    }
    lockedRef.current = new Set([...lockedRef.current, ...ids])
    setLocked(lockedRef.current)
    return true
  }
  function unlock(ids: number[]): void {
    lockedRef.current = new Set([...lockedRef.current].filter((photoId) => !ids.includes(photoId)))
    setLocked(lockedRef.current)
  }

  const [actionError, setActionError] = useState<{ where: string; message: string } | null>(null)
  const errorAt = (where: string) => (actionError?.where === where ? actionError.message : null)
  const clearError = () => setActionError(null)

  const [undo, setUndo] = useState<{ key: number; target: UndoTarget } | null>(null)
  const [undoError, setUndoError] = useState<string | null>(null)
  const [undoRestart, setUndoRestart] = useState(0)
  const undoKeyRef = useRef(0)
  function showUndo(target: UndoTarget): void {
    undoKeyRef.current += 1
    setUndo({ key: undoKeyRef.current, target })
    setUndoError(null)
  }
  function endUndo(): void {
    setUndo(null)
    setUndoError(null)
  }

  function handleStrike(photo: PhotoOut): void {
    if (!lock([photo.id])) {
      return
    }
    endUndo()
    setActionError(null)
    const previous = ownStatusOf(photo)
    const siblings = albumOf(photo.event?.id ?? 0)
    const index = siblings.findIndex((candidate) => candidate.id === photo.id)
    const neighbor = siblings[index + 1] ?? siblings[index - 1]
    decisionMutation.mutate(
      { photoId: photo.id, status: 'rejected' },
      {
        onSuccess: () => {
          onCloseBand(photo.id)
          showUndo({ kind: 'strike', photo, previous })
          onRequestFocus({
            key: neighbor ? `decide-${neighbor.id}` : `struck-toggle-${photo.event?.id ?? 0}`,
            scroll: false,
          })
        },
        onError: (error) =>
          setActionError({ where: `tile-${photo.id}`, message: errorText(error) }),
        onSettled: () => unlock([photo.id]),
      },
    )
  }

  function handleReAdd(photo: PhotoOut): void {
    if (!lock([photo.id])) {
      return
    }
    endUndo()
    setActionError(null)
    const struck = struckOf(photo.event?.id ?? 0)
    const index = struck.findIndex((candidate) => candidate.id === photo.id)
    const neighbor = struck[index + 1] ?? struck[index - 1]
    decisionMutation.mutate(
      { photoId: photo.id, status: reAddDecision(photo) },
      {
        onSuccess: () =>
          onRequestFocus({
            key: neighbor ? `readd-${neighbor.id}` : `decide-${photo.id}`,
            scroll: false,
          }),
        onError: (error) =>
          setActionError({ where: `struck-${photo.event?.id ?? 0}`, message: errorText(error) }),
        onSettled: () => unlock([photo.id]),
      },
    )
  }

  /** Hinzufügen aus Hinzufügen-Panel, Band oder aufgeklappter Reihe - derselbe Schreibweg
   * (`decisionMutation` mit `album_worthy`), ohne Rückgängig. Es schließt nichts: Das Foto
   * verlässt die Liste über `excludedIds`, der Fokus wandert zum Nachbarn. Andere Alternativen
   * bleiben bedienbar, zwei Hinzufügungen können sich also überlappen - deshalb `mutateAsync` je
   * Aufruf statt der Aufruf-Callbacks, die nur für den jeweils letzten Aufruf feuern; sonst
   * verlöre ein früherer Aufruf Fehlermeldung, Fokus und das Lösen seiner Sperre. */
  async function handleAdd(
    candidate: PhotoOut,
    neighborId: number | null,
    where: string,
    fallbackFocusKey: string,
  ): Promise<void> {
    if (!lock([candidate.id])) {
      return
    }
    endUndo()
    setActionError(null)
    try {
      await decisionMutation.mutateAsync({
        photoId: candidate.id,
        status: 'album_worthy',
        insert: candidate,
      })
      onRequestFocus({
        key: neighborId === null ? fallbackFocusKey : `add-${neighborId}`,
        scroll: false,
      })
    } catch (error) {
      setActionError({ where, message: errorText(error) })
    } finally {
      unlock([candidate.id])
    }
  }

  function handleExchange(replaced: PhotoOut, chosen: PhotoOut, where: string): void {
    if (!lock([replaced.id, chosen.id])) {
      return
    }
    endUndo()
    setActionError(null)
    const chosenPrevious = ownStatusOf(chosen) === 'rejected' ? 'rejected' : null
    const replacedPrevious = ownStatusOf(replaced) === 'album_worthy' ? 'album_worthy' : null
    exchangeMutation.mutate(
      { replaced, chosen },
      {
        onSuccess: () => {
          onCloseBand(null)
          showUndo({ kind: 'exchange', replaced, chosen, chosenPrevious, replacedPrevious })
          onExchanged(chosen)
        },
        onError: (error) => setActionError({ where, message: errorText(error) }),
        onSettled: () => unlock([replaced.id, chosen.id]),
      },
    )
  }

  function handleUndo(): void {
    if (undo === null) {
      return
    }
    const { target } = undo
    const onError = (error: unknown) => {
      setUndoError(errorText(error))
      setUndoRestart((previous) => previous + 1)
    }
    if (target.kind === 'strike') {
      if (!lock([target.photo.id])) {
        return
      }
      decisionMutation.mutate(
        // Ohne Rangzeile hat das Streichen das Foto aus der Antwortmenge genommen.
        { photoId: target.photo.id, status: target.previous, insert: target.photo },
        {
          onSuccess: () => {
            endUndo()
            onRequestFocus({ key: `decide-${target.photo.id}`, scroll: false })
          },
          onError,
          onSettled: () => unlock([target.photo.id]),
        },
      )
      return
    }
    const ids = [target.replaced.id, target.chosen.id]
    if (!lock(ids)) {
      return
    }
    undoMutation.mutate(
      {
        photo_id: target.chosen.id,
        replaced_photo_id: target.replaced.id,
        photo_previous_status: target.chosenPrevious,
        replaced_previous_status: target.replacedPrevious,
      },
      {
        onSuccess: () => {
          endUndo()
          onRequestFocus({ key: `decide-${target.replaced.id}`, scroll: false })
        },
        onError,
        onSettled: () => unlock(ids),
      },
    )
  }

  const undoView =
    undo === null
      ? null
      : undo.target.kind === 'strike'
        ? {
            key: undo.key,
            title: ALBUM_STATE_LABELS.struck,
            photoId: undo.target.photo.id,
            relativePath: undo.target.photo.relative_path,
          }
        : {
            key: undo.key,
            title: EXCHANGED_TITLE,
            photoId: undo.target.replaced.id,
            relativePath: undo.target.replaced.relative_path,
          }
  const undoBusy = undo !== null && (decisionMutation.isPending || undoMutation.isPending)

  return {
    locked,
    errorAt,
    clearError,
    undoView,
    undoBusy,
    undoError,
    undoRestart,
    endUndo,
    handleStrike,
    handleReAdd,
    handleAdd,
    handleExchange,
    handleUndo,
  }
}
