import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

import { ApiError } from '../api/client'
import { PERSON_REFUSALS } from '../api/persons'
import type { PersonOut, UnnamedFaceOut } from '../api/types'
import { assignmentMessage, useFaceAssignment } from '../hooks/useFaceAssignment'
import type { FaceChoice } from '../hooks/useFaceAssignment'
import { PERSONS_QUERY_KEY } from '../hooks/usePersons'
import type { UnnamedFaces } from '../hooks/useUnnamedFaces'
import { photoCount, ROW_CARD_CLASSES, ROW_CARD_LIST_CLASSES } from '../utils/personOverview'
import { StaticFaceCropTile } from './FaceCropTile'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Progress } from './ui/progress'
import { Skeleton } from './ui/skeleton'

const SAVE_ERROR = 'Das Gesicht konnte nicht gespeichert werden.'
const SEARCH_ERROR = 'Die Suche nach Gesichtern ist unterbrochen.'

/*
 * HEISSER PFAD: Ein Fehlgriff benennt hier nicht nur ein Foto, er bringt PhotoSort ein falsches
 * Gesicht bei - deshalb sichtbare 44px unter `sm:`. `h-auto whitespace-normal break-words`: Namen
 * bis 40 Zeichen brechen um, statt gekürzt zu werden oder die Karte zu sprengen.
 */
const ASSIGN_BUTTON_CLASSES = 'h-auto min-h-11 whitespace-normal break-words sm:min-h-8'

interface Refusal {
  detail: string
  /** Die Ablehnung betrifft den eingegebenen Namen (`422` oder doppelter Name). */
  nameInvalid: boolean
}

function cardKey(face: UnnamedFaceOut): string {
  return `${face.photo_id}-${face.face_index}`
}

interface UnnamedFacesGroupProps {
  projectId: number
  /** Die festgelegten Personen in der Reihenfolge von `GET /persons`. */
  persons: readonly PersonOut[]
  unnamed: UnnamedFaces
  headingId: string
  headingRef: RefObject<HTMLHeadingElement | null>
}

/**
 * "Ohne Namen": jedes gefundene Gesicht des Projekts, das keiner Person zugeordnet ist, als
 * flache Liste in der Reihenfolge Foto-Id, dann Index. Ein Druck auf einen Namen ordnet das
 * Gesicht zu; die Karte verlässt die Liste, und die Statusleiste bleibt beim Scrollen sichtbar.
 *
 * Nichts hier zeigt eine Zahl zu einem Gesicht, schlägt eine Person vor oder fasst Gesichter
 * zusammen: Alle Namens-Schaltflächen sind auf jeder Karte gleich.
 */
export function UnnamedFacesGroup({
  projectId,
  persons,
  unnamed,
  headingId,
  headingRef,
}: UnnamedFacesGroupProps) {
  const queryClient = useQueryClient()
  const assignment = useFaceAssignment(projectId, { refreshGroup: true })
  const formId = useId()
  const progressId = useId()
  const [busy, setBusy] = useState<ReadonlyMap<string, FaceChoice>>(new Map())
  const [refusals, setRefusals] = useState<ReadonlyMap<string, Refusal>>(new Map())
  const [message, setMessage] = useState('')
  const [formFor, setFormFor] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  /** Die Stelle der Karte, die zuletzt gegangen ist - Fokusziel nach dem nächsten Rendern. */
  const [focusIndex, setFocusIndex] = useState<number | null>(null)
  /** Die Karte, deren "Neue Person…" nach dem Zuklappen den Fokus bekommt. */
  const [focusNewPersonOf, setFocusNewPersonOf] = useState<string | null>(null)
  const actionRefs = useRef(new Map<string, HTMLDivElement>())
  const newPersonRefs = useRef(new Map<string, HTMLButtonElement>())
  const facesRef = useRef(unnamed.faces)

  const { faces, status, progress } = unnamed

  useEffect(() => {
    facesRef.current = faces
  }, [faces])

  useLayoutEffect(() => {
    if (focusIndex === null) {
      return
    }
    const next = faces[focusIndex] ?? faces[focusIndex - 1]
    const column = next === undefined ? undefined : actionRefs.current.get(cardKey(next))
    const target = column?.querySelector('button') ?? headingRef.current
    target?.focus()
    setFocusIndex(null)
  }, [focusIndex, faces, headingRef])

  useLayoutEffect(() => {
    if (focusNewPersonOf !== null) {
      newPersonRefs.current.get(focusNewPersonOf)?.focus()
      setFocusNewPersonOf(null)
    }
  }, [focusNewPersonOf])

  function leaveCard(key: string): void {
    setFocusIndex(facesRef.current.findIndex((face) => cardKey(face) === key))
  }

  function closeForm(key: string): void {
    setFormFor(null)
    setDraftName('')
    setFocusNewPersonOf(key)
  }

  function openForm(key: string): void {
    setFormFor(key)
    setDraftName('')
    setRefusals((current) => {
      const next = new Map(current)
      next.delete(key)
      return next
    })
  }

  async function assign(face: UnnamedFaceOut, choice: FaceChoice): Promise<void> {
    const key = cardKey(face)
    setBusy((current) => new Map(current).set(key, choice))
    setRefusals((current) => {
      const next = new Map(current)
      next.delete(key)
      return next
    })
    try {
      const result = await assignment.mutateAsync({
        choice,
        photoId: face.photo_id,
        faceIndex: face.face_index,
      })
      unnamed.removeFace(face.photo_id, face.face_index)
      setMessage(assignmentMessage(choice.kind, result.person.name, result.learned))
      if (choice.kind === 'create') {
        setFormFor(null)
        setDraftName('')
      }
      leaveCard(key)
    } catch (cause) {
      const known = cause instanceof ApiError && [404, 409, 422].includes(cause.status)
      const detail = known && cause.detail.length > 0 ? cause.detail : SAVE_ERROR
      if (detail === PERSON_REFUSALS.faceNotFound) {
        // Die Datei hat sich geändert: Die Gesichter des Fotos werden an ihrer Stelle neu
        // gesucht, die Karte ist ersetzt - deshalb steht die Meldung in der Statusleiste.
        unnamed.removeFace(face.photo_id, face.face_index)
        unnamed.refreshPhoto(face.photo_id, null)
        setMessage(detail)
        leaveCard(key)
        return
      }
      if (detail === PERSON_REFUSALS.limitReached) {
        setFormFor(null)
        setDraftName('')
      }
      if (
        detail === PERSON_REFUSALS.limitReached ||
        (cause instanceof ApiError && cause.status === 404)
      ) {
        void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
      }
      const nameInvalid =
        choice.kind === 'create' &&
        cause instanceof ApiError &&
        (cause.status === 422 || detail === PERSON_REFUSALS.duplicateName)
      setRefusals((current) => new Map(current).set(key, { detail, nameInvalid }))
    } finally {
      setBusy((current) => {
        const next = new Map(current)
        next.delete(key)
        return next
      })
    }
  }

  let progressText: string
  if (status === 'initial') {
    progressText = 'Gesichter werden gesucht…'
  } else if (status === 'empty') {
    progressText = 'Das Projekt hat noch keine Fotos.'
  } else if (progress === null) {
    progressText = 'Suche unterbrochen.'
  } else if (status === 'running') {
    progressText = `Gesichter werden gesucht – ${progress.done} von ${photoCount(progress.total)} durchgesehen.`
  } else if (status === 'interrupted') {
    progressText = `Suche unterbrochen – ${progress.done} von ${photoCount(progress.total)} durchgesehen.`
  } else {
    progressText = `Suche abgeschlossen: ${photoCount(progress.total)} durchgesehen.`
  }
  const searching = status === 'initial' || status === 'running'

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id={headingId} ref={headingRef} tabIndex={-1} className="scroll-mt-header text-lg">
          Ohne Namen
        </h2>
        <p className="text-sm text-text">
          Gesichter, die noch keiner Person zugeordnet sind – auch auf Fotos, die schon einen Namen
          tragen. Fremde Gesichter bleiben hier stehen: Über andere Menschen speichert PhotoSort
          nichts.
        </p>
      </div>

      <div
        data-unnamed-status-bar
        className="sticky top-header z-10 flex flex-col gap-2 border-b border-separator bg-bg py-3"
      >
        <p id={progressId} className="text-sm text-text">
          {progressText}
        </p>
        {status === 'initial' && <Progress aria-labelledby={progressId} />}
        {status === 'running' && progress !== null && (
          <Progress aria-labelledby={progressId} value={progress.done} max={progress.total} />
        )}
        {status === 'interrupted' && (
          <Alert onRetry={unnamed.retry}>
            {unnamed.error instanceof ApiError && unnamed.error.detail.length > 0
              ? unnamed.error.detail
              : SEARCH_ERROR}
          </Alert>
        )}
        {unnamed.notReadyCount > 0 && (
          <p className="text-sm text-text">
            {photoCount(unnamed.notReadyCount)} nicht bereit – noch ohne Vorschau oder nicht lesbar.
            Gesichter darauf fehlen hier.
          </p>
        )}
        <p role="status" className="text-sm text-text">
          {message}
        </p>
        {unnamed.refreshFailures.map((failure) => (
          <Alert key={failure.photoId} onRetry={() => unnamed.retryRefresh(failure.photoId)}>
            {failure.fileName === null
              ? 'Die Gesichter eines Fotos konnten nicht neu gesucht werden.'
              : `Das Gesicht auf ${failure.fileName} konnte nicht wieder aufgenommen werden.`}
          </Alert>
        ))}
      </div>

      {(faces.length > 0 || searching) && (
        <ul className={ROW_CARD_LIST_CLASSES}>
          {faces.map((face) => {
            const key = cardKey(face)
            const pressed = busy.get(key)
            const refusal = refusals.get(key)
            const refusalId = `${formId}-${key}-meldung`
            const formOpen = formFor === key
            return (
              <li key={key} className={ROW_CARD_CLASSES}>
                <StaticFaceCropTile source={face.crop_jpeg} alt="Gesicht ohne Namen" />
                <div
                  ref={(element) => {
                    if (element === null) {
                      actionRefs.current.delete(key)
                    } else {
                      actionRefs.current.set(key, element)
                    }
                  }}
                  className="flex min-w-0 flex-1 flex-col gap-3"
                >
                  {formOpen ? (
                    <form
                      id={`${formId}-${key}`}
                      className="flex flex-col gap-2"
                      onSubmit={(event) => {
                        event.preventDefault()
                        const name = draftName.trim()
                        if (name.length > 0) {
                          void assign(face, { kind: 'create', name })
                        }
                      }}
                    >
                      <label
                        htmlFor={`${formId}-${key}-name`}
                        className="text-xs font-medium text-text-h"
                      >
                        Name der neuen Person
                      </label>
                      <Input
                        id={`${formId}-${key}-name`}
                        autoFocus
                        autoComplete="off"
                        value={draftName}
                        aria-invalid={refusal?.nameInvalid || undefined}
                        aria-describedby={refusal?.nameInvalid ? refusalId : undefined}
                        onChange={(event) => setDraftName(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Escape') {
                            event.preventDefault()
                            closeForm(key)
                          }
                        }}
                      />
                      <div className="flex flex-wrap gap-3">
                        <Button
                          type="submit"
                          busy={pressed !== undefined}
                          disabled={draftName.trim().length === 0}
                        >
                          {pressed === undefined ? 'Festlegen' : 'Wird gespeichert…'}
                        </Button>
                        <Button
                          variant="ghost"
                          disabled={pressed !== undefined}
                          onClick={() => closeForm(key)}
                        >
                          Abbrechen
                        </Button>
                      </div>
                    </form>
                  ) : (
                    <div className="flex flex-wrap gap-3">
                      {persons.map((person) => {
                        const isPressed =
                          pressed?.kind === 'reference' && pressed.personId === person.id
                        return (
                          <Button
                            key={person.id}
                            variant="outline"
                            size="sm"
                            className={ASSIGN_BUTTON_CLASSES}
                            disabled={pressed !== undefined}
                            busy={isPressed}
                            aria-label={isPressed ? undefined : `Zuordnen: ${person.name}`}
                            onClick={() =>
                              void assign(face, { kind: 'reference', personId: person.id })
                            }
                          >
                            {isPressed ? 'Wird gespeichert…' : person.name}
                          </Button>
                        )
                      })}
                      {persons.length < 2 && (
                        <Button
                          ref={(element) => {
                            if (element === null) {
                              newPersonRefs.current.delete(key)
                            } else {
                              newPersonRefs.current.set(key, element)
                            }
                          }}
                          variant="ghost"
                          size="sm"
                          disabled={pressed !== undefined}
                          aria-expanded={false}
                          aria-controls={`${formId}-${key}`}
                          onClick={() => openForm(key)}
                        >
                          Neue Person…
                        </Button>
                      )}
                    </div>
                  )}
                  {refusal !== undefined && (
                    <div id={refusalId}>
                      <Alert>{refusal.detail}</Alert>
                    </div>
                  )}
                </div>
              </li>
            )
          })}
          {searching &&
            [0, 1, 2].map((slot) => (
              <li key={`platzhalter-${slot}`} aria-hidden="true">
                <Skeleton className="h-28 w-full rounded-lg" />
              </li>
            ))}
        </ul>
      )}

      {status === 'complete' && faces.length === 0 && (
        <p className="text-sm text-text">Kein Gesicht ohne Namen.</p>
      )}
    </section>
  )
}
