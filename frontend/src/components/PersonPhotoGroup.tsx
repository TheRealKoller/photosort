import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

import { ApiError } from '../api/client'
import { setPhotoPerson } from '../api/persons'
import type { PersonOut, PhotoOut } from '../api/types'
import { PERSONS_QUERY_KEY } from '../hooks/usePersons'
import { storePhotoPersons } from '../hooks/usePhotoPersons'
import { usePersonGroupQuery } from '../hooks/usePersonGroupQuery'
import { PhotoImage } from './PhotoImage'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

const GROUP_LOAD_ERROR = 'Die Fotos konnten nicht geladen werden.'
const REMOVE_ERROR = 'Die Zuordnung konnte nicht gespeichert werden.'

/** Die Zeilenkarte beider Gruppen der Übersicht - Liste und Karte. */
export const ROW_CARD_LIST_CLASSES = 'grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'
export const ROW_CARD_CLASSES =
  'flex items-start gap-3 rounded-lg border border-border bg-elevated p-2'

/** "1 Foto" bzw. "{n} Fotos" - die eine Zählform beider Gruppen. */
export function photoCount(count: number): string {
  return count === 1 ? '1 Foto' : `${count} Fotos`
}

export function baseName(path: string): string {
  return path.split('/').pop() ?? path
}

interface PersonPhotoGroupProps {
  projectId: number
  person: PersonOut
  /** Stabile `id` der Überschrift - Sprungziel und Name der `section`. */
  headingId: string
  headingRef: RefObject<HTMLHeadingElement | null>
  /** Öffnet die Großansicht; der Auslöserschlüssel ist `${personId}:${photoId}`. */
  onOpenLarge: (photoId: number, triggerKey: string) => void
  largeTriggerRef: (triggerKey: string) => (element: HTMLElement | null) => void
  /** Meldet die geladenen Fotos dieser Gruppe - Grundlage der Großansicht der Seite. */
  onPhotosChange: (personId: number, photos: readonly PhotoOut[]) => void
  /** Nach "Name entfernen": das Gesicht des Fotos in "Ohne Namen" wieder einfügen. */
  onNameRemoved: (photoId: number, fileName: string) => void
  /** `404`: Die Person ist inzwischen entfernt, der Fokus geht auf das `h1`. */
  onPersonGone: () => void
}

/**
 * Die Gruppe einer Person: genau die Fotos des Projekts mit ihrem Namen, erkannt oder von Hand
 * zugeordnet, samt Herkunft und gebundenem Gesicht. Der Name eines Fotos lässt sich hier ohne
 * Detailansicht entfernen; die Karte verlässt dann die Gruppe.
 */
export function PersonPhotoGroup({
  projectId,
  person,
  headingId,
  headingRef,
  onOpenLarge,
  largeTriggerRef,
  onPhotosChange,
  onNameRemoved,
  onPersonGone,
}: PersonPhotoGroupProps) {
  const queryClient = useQueryClient()
  const group = usePersonGroupQuery(projectId, person.id)
  const { photos } = group
  const [pendingIds, setPendingIds] = useState<readonly number[]>([])
  const [errors, setErrors] = useState<ReadonlyMap<number, string>>(new Map())
  const [message, setMessage] = useState('')
  const actionRefs = useRef(new Map<number, HTMLButtonElement>())
  const photosRef = useRef(photos)
  /** Die Stelle der Karte, die zuletzt gegangen ist - Fokusziel nach dem nächsten Rendern. */
  const [focusIndex, setFocusIndex] = useState<number | null>(null)

  const mutation = useMutation({
    mutationFn: (photoId: number) => setPhotoPerson(photoId, person.id, false),
    onSuccess: (persons, photoId) => storePhotoPersons(queryClient, projectId, photoId, persons),
  })

  useEffect(() => {
    photosRef.current = photos
    onPhotosChange(person.id, photos)
  }, [photos, person.id, onPhotosChange])

  useLayoutEffect(() => {
    if (focusIndex === null) {
      return
    }
    const next = photos[focusIndex] ?? photos[focusIndex - 1]
    const target = next === undefined ? null : actionRefs.current.get(next.id)
    ;(target ?? headingRef.current)?.focus()
    setFocusIndex(null)
  }, [focusIndex, photos, headingRef])

  async function removeName(photo: PhotoOut): Promise<void> {
    const fileName = baseName(photo.relative_path)
    const shown = photo.persons.some(
      (entry) => entry.person_id === person.id && entry.face === 'shown',
    )
    setPendingIds((ids) => [...ids, photo.id])
    setErrors((current) => {
      const next = new Map(current)
      next.delete(photo.id)
      return next
    })
    try {
      await mutation.mutateAsync(photo.id)
      setFocusIndex(photosRef.current.findIndex((entry) => entry.id === photo.id))
      setMessage(
        shown
          ? `Gesicht auf ${fileName} zurückgenommen. Es steht wieder unter „Ohne Namen“ und wirkt ab dem nächsten Klassifizierungslauf nicht mehr auf die Erkennung.`
          : `${person.name} auf ${fileName} entfernt.`,
      )
      onNameRemoved(photo.id, fileName)
    } catch (cause) {
      const detail = cause instanceof ApiError && cause.detail.length > 0 ? cause.detail : null
      setErrors((current) => new Map(current).set(photo.id, detail ?? REMOVE_ERROR))
      if (cause instanceof ApiError && cause.status === 404) {
        void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
        onPersonGone()
      }
    } finally {
      setPendingIds((ids) => ids.filter((id) => id !== photo.id))
    }
  }

  const count = group.count
  const loadedCount = photos.length

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id={headingId} ref={headingRef} tabIndex={-1} className="scroll-mt-header text-lg">
          {person.name}
        </h2>
        {count !== undefined && <p className="text-sm text-text">{photoCount(count)}</p>}
        <p role="status" className="text-sm text-text">
          {group.isPending ? <span className="sr-only">Fotos werden geladen…</span> : message}
        </p>
      </div>

      {group.isPending && (
        <ul aria-hidden="true" className={ROW_CARD_LIST_CLASSES}>
          {[0, 1, 2].map((slot) => (
            <li key={slot}>
              <Skeleton className="h-28 w-full rounded-lg" />
            </li>
          ))}
        </ul>
      )}

      {group.isError && group.data === undefined && (
        <Alert onRetry={() => void group.refetch()}>
          {group.error instanceof ApiError ? group.error.detail : GROUP_LOAD_ERROR}
        </Alert>
      )}

      {group.data !== undefined && photos.length === 0 && !group.hasNextPage && (
        <p className="text-sm text-text">Kein Foto in diesem Projekt trägt diesen Namen.</p>
      )}

      {photos.length > 0 && (
        <ul className={ROW_CARD_LIST_CLASSES}>
          {photos.map((photo) => {
            const entry = photo.persons.find((candidate) => candidate.person_id === person.id)
            const fileName = baseName(photo.relative_path)
            const pending = pendingIds.includes(photo.id)
            const shown = entry?.face === 'shown'
            const error = errors.get(photo.id)
            const triggerKey = `${person.id}:${photo.id}`
            return (
              <li key={photo.id} className={ROW_CARD_CLASSES}>
                <button
                  type="button"
                  ref={largeTriggerRef(triggerKey)}
                  aria-label={`Großansicht: ${photo.relative_path}`}
                  onClick={() => onOpenLarge(photo.id, triggerKey)}
                  className="size-24 shrink-0 cursor-zoom-in overflow-hidden rounded-md"
                >
                  <PhotoImage
                    photoId={photo.id}
                    variant="thumbnail"
                    alt={photo.relative_path}
                    className="size-24 object-cover"
                  />
                </button>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <p className="min-w-6 truncate font-mono text-xs text-text-muted">{fileName}</p>
                  <p className="text-sm text-text">
                    {entry?.origin === 'recognized' ? 'Erkannt' : 'Von Hand zugeordnet'}
                  </p>
                  {entry?.face === 'shown' && <p className="text-sm text-text">Gesicht gezeigt</p>}
                  {entry?.face === 'assigned' && (
                    <p className="text-sm text-text">Gesicht gewählt, nicht gelernt</p>
                  )}
                  <Button
                    ref={(element) => {
                      if (element === null) {
                        actionRefs.current.delete(photo.id)
                      } else {
                        actionRefs.current.set(photo.id, element)
                      }
                    }}
                    variant="outline"
                    size="sm"
                    className="mt-2 self-start"
                    busy={pending}
                    aria-label={
                      pending
                        ? undefined
                        : `${shown ? 'Gesicht zurücknehmen' : 'Name entfernen'}: ${fileName}`
                    }
                    onClick={() => void removeName(photo)}
                  >
                    {shown
                      ? pending
                        ? 'Wird zurückgenommen…'
                        : 'Gesicht zurücknehmen'
                      : pending
                        ? 'Wird entfernt…'
                        : 'Name entfernen'}
                  </Button>
                  {error !== undefined && <Alert>{error}</Alert>}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {group.isFetchNextPageError ? (
        <Alert onRetry={() => void group.fetchNextPage()}>
          {group.error instanceof ApiError ? group.error.detail : GROUP_LOAD_ERROR}
        </Alert>
      ) : (
        (group.hasNextPage || group.isFetchingNextPage) && (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              busy={group.isFetchingNextPage}
              onClick={() => void group.fetchNextPage()}
            >
              Mehr laden
            </Button>
            {count !== undefined && (
              <p aria-live="polite" className="text-sm text-text">
                {loadedCount} von {count} Fotos geladen
              </p>
            )}
          </div>
        )
      )}
    </section>
  )
}
