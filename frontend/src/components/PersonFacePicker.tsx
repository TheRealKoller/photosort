import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseQueryResult } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '../api/client'
import {
  PERSON_REFUSALS,
  addReference,
  createPerson,
  fetchFaceImage,
  listFaces,
} from '../api/persons'
import type { FaceOut, PersonOut, PhotoOut } from '../api/types'
import { PERSONS_QUERY_KEY } from '../hooks/usePersons'
import { storePhotoPersons } from '../hooks/usePhotoPersons'
import { cn } from '../lib/utils'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Skeleton } from './ui/skeleton'

const GENERIC_DETAIL = 'Das Gesicht konnte nicht gespeichert werden.'
const FAILED = 'failed'

interface PersonFacePickerProps {
  projectId: number
  photo: PhotoOut
  persons: PersonOut[]
}

type Choice = { kind: 'reference'; personId: number } | { kind: 'create'; name: string }

/** Die Ablehnung eines Festlegens oder Zeigens - `nameInvalid` markiert das Namensfeld. */
interface Refusal {
  detail: string
  nameInvalid: boolean
}

/**
 * Die Gesichterwahl des Personenabschnitts: ein Gesicht des Fotos als Person zeigen
 * oder mit ihm eine neue Person festlegen - der einzige Weg, eine Person festzulegen.
 *
 * `GET /photos/{id}/faces` läuft erst beim Aufklappen, nie beim Blättern. Die Ausschnitte kommen
 * nur als Blob-URL und werden beim Zuklappen freigegeben; beim Fotowechsel bindet der Aufrufer den
 * Abschnitt neu ein, was dieselbe Freigabe auslöst.
 */
export function PersonFacePicker({ projectId, photo, persons }: PersonFacePickerProps) {
  const queryClient = useQueryClient()
  const panelId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const [expanded, setExpanded] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [refusal, setRefusal] = useState<Refusal | null>(null)
  const [status, setStatus] = useState('')

  const facesQuery = useQuery({
    queryKey: ['photo-faces', photo.id],
    queryFn: () => listFaces(photo.id),
    enabled: expanded,
  })

  const mutation = useMutation({
    mutationFn: ({ choice, faceIndex }: { choice: Choice; faceIndex: number }) =>
      choice.kind === 'create'
        ? createPerson(choice.name, photo.id, faceIndex)
        : addReference(choice.personId, photo.id, faceIndex),
    // Am Hook, nicht am Aufruf: Auch nach einem Fotowechsel mitten in der Anfrage landet die
    // Zuordnung im Cache. Eine gezeigte Referenz ordnet die Person dem Foto per Korrektur zu.
    onSuccess: (person) => {
      void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
      storePhotoPersons(queryClient, projectId, photo.id, [
        ...photo.persons.filter((entry) => entry.person_id !== person.id),
        { person_id: person.id, origin: 'corrected' },
      ])
    },
  })

  function collapse(): void {
    setExpanded(false)
    setSelected(null)
    setRefusal(null)
    triggerRef.current?.focus()
  }

  async function choose(choice: Choice, faceIndex: number): Promise<void> {
    setRefusal(null)
    try {
      const person = await mutation.mutateAsync({ choice, faceIndex })
      setStatus(
        choice.kind === 'create'
          ? `${person.name} ist festgelegt.`
          : `Gesicht als ${person.name} gezeigt.`,
      )
      collapse()
    } catch (cause) {
      const detail =
        cause instanceof ApiError && cause.detail.length > 0 ? cause.detail : GENERIC_DETAIL
      const conflict = cause instanceof ApiError && cause.status === 409
      setRefusal({
        detail,
        nameInvalid:
          choice.kind === 'create' &&
          cause instanceof ApiError &&
          (cause.status === 422 || (conflict && detail === PERSON_REFUSALS.duplicateName)),
      })
      if (conflict && detail === PERSON_REFUSALS.limitReached) {
        void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
      }
      if (conflict && detail === PERSON_REFUSALS.faceNotFound) {
        setSelected(null)
        void facesQuery.refetch()
      }
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          ref={triggerRef}
          type="button"
          variant="secondary"
          size="sm"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => (expanded ? collapse() : setExpanded(true))}
        >
          Gesicht zeigen
        </Button>
        <p role="status" className="text-sm text-text">
          {status}
        </p>
      </div>
      {expanded && (
        <div id={panelId} className="flex flex-col gap-3">
          <FacesBody
            query={facesQuery}
            photoId={photo.id}
            selected={selected}
            disabled={mutation.isPending}
            onSelect={(index) => setSelected((current) => (current === index ? null : index))}
          />
          {refusal !== null && (
            <div id={`${panelId}-refusal`}>
              <Alert>{refusal.detail}</Alert>
            </div>
          )}
          {selected !== null && (
            <ChoiceGroup
              persons={persons}
              pending={mutation.isPending ? mutation.variables.choice : undefined}
              refusal={refusal}
              refusalId={`${panelId}-refusal`}
              onChoose={(choice) => void choose(choice, selected)}
              onCancel={collapse}
            />
          )}
        </div>
      )}
    </div>
  )
}

function FacesBody({
  query,
  photoId,
  selected,
  disabled,
  onSelect,
}: {
  query: UseQueryResult<FaceOut[]>
  photoId: number
  selected: number | null
  disabled: boolean
  onSelect: (index: number) => void
}) {
  if (query.isPending) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex gap-3">
          <Skeleton className="size-16 rounded-md" />
          <Skeleton className="size-16 rounded-md" />
          <Skeleton className="size-16 rounded-md" />
        </div>
        <p role="status" className="sr-only">
          Gesichter werden gesucht…
        </p>
      </div>
    )
  }
  if (query.isError) {
    // 404/409: Die Display-Variante fehlt noch - kein Fehler, sondern ein Zustand.
    if (query.error instanceof ApiError && [404, 409].includes(query.error.status)) {
      return (
        <p className="text-sm text-text">
          Für dieses Foto gibt es noch keine Vorschau – Gesichter lassen sich erst danach zeigen.
        </p>
      )
    }
    return (
      <Alert onRetry={() => void query.refetch()}>
        Die Gesichter konnten nicht geladen werden.
      </Alert>
    )
  }
  if (query.data.length === 0) {
    return (
      <p className="text-sm text-text">
        Auf diesem Foto ist kein Gesicht zu finden, das sich zeigen lässt.
      </p>
    )
  }
  // Neu geladene Gesichter (nach "kein Gesicht an diesem Index") binden die Kacheln neu ein - die
  // alten Ausschnitte werden dabei freigegeben.
  return (
    <FaceTiles
      key={query.dataUpdatedAt}
      faces={query.data}
      photoId={photoId}
      selected={selected}
      disabled={disabled}
      onSelect={onSelect}
    />
  )
}

function FaceTiles({
  faces,
  photoId,
  selected,
  disabled,
  onSelect,
}: {
  faces: FaceOut[]
  photoId: number
  selected: number | null
  disabled: boolean
  onSelect: (index: number) => void
}) {
  const [urls, setUrls] = useState<Record<number, string>>({})

  useEffect(() => {
    let cancelled = false
    const created: string[] = []
    for (const face of faces) {
      fetchFaceImage(photoId, face.index).then(
        (blob) => {
          const url = URL.createObjectURL(blob)
          if (cancelled) {
            URL.revokeObjectURL(url)
            return
          }
          created.push(url)
          setUrls((current) => ({ ...current, [face.index]: url }))
        },
        () => {
          if (!cancelled) {
            setUrls((current) => ({ ...current, [face.index]: FAILED }))
          }
        },
      )
    }
    return () => {
      cancelled = true
      for (const url of created) {
        URL.revokeObjectURL(url)
      }
    }
  }, [faces, photoId])

  return (
    <ul className="flex flex-wrap gap-3">
      {faces.map((face, position) => {
        const url = urls[face.index]
        const failed = url === FAILED
        const label = `Gesicht ${position + 1} von ${faces.length}`
        return (
          <li key={face.index}>
            <button
              type="button"
              className={cn(
                'size-16 overflow-hidden rounded-md border-2',
                selected === face.index ? 'border-accent' : 'border-border-control',
                failed && 'bg-separator',
              )}
              aria-label={failed ? `${label} – Ausschnitt nicht verfügbar` : label}
              aria-pressed={selected === face.index}
              aria-disabled={failed || undefined}
              disabled={disabled}
              onClick={failed ? undefined : () => onSelect(face.index)}
            >
              {url !== undefined && !failed && (
                <img src={url} alt="" className="size-full object-cover" />
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function ChoiceGroup({
  persons,
  pending,
  refusal,
  refusalId,
  onChoose,
  onCancel,
}: {
  persons: PersonOut[]
  pending: Choice | undefined
  refusal: Refusal | null
  refusalId: string
  onChoose: (choice: Choice) => void
  onCancel: () => void
}) {
  const labelId = useId()
  const fieldId = useId()
  const [name, setName] = useState('')
  const busy = pending !== undefined

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (!busy && name.trim() !== '') {
      onChoose({ kind: 'create', name: name.trim() })
    }
  }

  return (
    <div role="group" aria-labelledby={labelId} className="flex flex-col gap-3">
      <p id={labelId} className="text-sm text-text-h">
        Wer ist das?
      </p>
      {persons.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {persons.map((person) => {
            const saving = pending?.kind === 'reference' && pending.personId === person.id
            return (
              <Button
                key={person.id}
                type="button"
                variant="outline"
                size="sm"
                busy={busy}
                onClick={() => onChoose({ kind: 'reference', personId: person.id })}
              >
                {saving ? 'Wird gespeichert…' : person.name}
              </Button>
            )
          })}
        </div>
      )}
      {persons.length < 2 && (
        <form className="flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={submit}>
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor={fieldId} className="text-xs font-medium text-text-h">
              Name der neuen Person
            </label>
            <Input
              id={fieldId}
              value={name}
              autoComplete="off"
              aria-invalid={refusal?.nameInvalid || undefined}
              aria-describedby={refusal?.nameInvalid ? refusalId : undefined}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <Button type="submit" busy={busy} disabled={name.trim() === ''}>
            {pending?.kind === 'create' ? 'Wird gespeichert…' : 'Festlegen'}
          </Button>
        </form>
      )}
      <Button type="button" variant="ghost" className="self-start" onClick={onCancel}>
        Abbrechen
      </Button>
    </div>
  )
}
