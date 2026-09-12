import { useId, useState } from 'react'

import { ApiError } from '../api/client'
import type { PhotoOut, ProjectCameraOut } from '../api/types'
import {
  useCameraTimeOffsetSuggestionMutation,
  usePhotosOfCameraQuery,
  useSetCameraTimeOffsetMutation,
} from '../hooks/useCameras'
import { formatDateTime } from '../utils/formatStats'
import {
  type ClockDirection,
  type OffsetFields,
  applyOffsetToIsoTime,
  offsetFromFields,
  offsetToFields,
  validateOffsetFields,
} from '../utils/timeOffset'
import { PhotoImage } from './PhotoImage'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'
import { Input } from './ui/input'
import { Skeleton } from './ui/skeleton'

interface CameraTimeOffsetDialogProps {
  open: boolean
  onClose: () => void
  projectId: number
  camera: ProjectCameraOut
  /** Alle Kameras des Projekts - Grundlage der Referenzauswahl (alle ausser dieser). Das Handy
   * IST eine Kamera der Liste; ein Filter auf "keine Kamera" traefe die Fotos mit unbestimmbarem
   * Geraet. */
  cameras: ProjectCameraOut[]
}

/** Die beiden Richtungen im KLARTEXT. Ein nacktes `+`/`−` ist die Stelle, an der eine
 * Fehlbedienung den Fehler verdoppelt statt ihn zu beheben. */
const DIRECTION_LABEL: Record<ClockDirection, string> = {
  ahead: 'Kamerauhr ging vor',
  behind: 'Kamerauhr ging nach',
}

const DIRECTION_HINT: Record<ClockDirection, string> = {
  ahead: 'Die Aufnahmezeiten werden zurückgestellt.',
  behind: 'Die Aufnahmezeiten werden vorgestellt.',
}

/** Was der Server geantwortet hat - bestimmt Ausprägung und Titel der Meldung. */
interface SaveFailure {
  status: number | null
  detail: string
}

function toFailure(error: unknown): SaveFailure {
  if (error instanceof ApiError) {
    return { status: error.status, detail: error.detail }
  }
  return {
    status: null,
    detail: 'Der Versatz konnte nicht gespeichert werden. Bitte versuche es erneut.',
  }
}

/** Ein Zahlenfeld des Versatzes. `value` bleibt als String im Zustand: ein geleertes Feld ist
 * eine Zwischenstufe des Tippens, kein `0`. */
function OffsetNumberField({
  label,
  value,
  invalid,
  onChange,
}: {
  label: string
  value: string
  invalid: boolean
  onChange: (next: string) => void
}) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-xs font-medium text-text-h">{label}</span>
      <Input
        type="number"
        inputMode="numeric"
        value={value}
        aria-invalid={invalid ? true : undefined}
        onChange={(event) => {
          onChange(event.target.value)
        }}
      />
    </label>
  )
}

/** Ein Vorschaustreifen: je Foto Bild und AUFNAHMEZEIT. Ohne die Zeit am Bild ist "derselbe
 * Moment" nicht zu finden. */
function PhotoStrip({
  photos,
  isLoading,
  selectedId,
  onSelect,
  label,
}: {
  photos: PhotoOut[]
  isLoading: boolean
  selectedId: number | null
  onSelect: (photoId: number) => void
  label: string
}) {
  if (isLoading) {
    return (
      <div role="status" aria-label={`${label} werden geladen`} className="flex gap-3">
        <Skeleton className="h-24 w-24" />
        <Skeleton className="h-24 w-24" />
        <Skeleton className="h-24 w-24" />
      </div>
    )
  }
  if (photos.length === 0) {
    return <p className="text-sm text-text">Für diese Kamera liegt kein Foto vor.</p>
  }
  return (
    <ul aria-label={label} className="flex gap-3 overflow-x-auto">
      {photos.map((photo) => (
        <li key={photo.id} className="shrink-0">
          {/* Auswahl ANLIEGEND (durchgezogene Kante am Element), Fokus abgesetzt ueber die
              globale Regel - der Akzent trägt hier zusätzlich eine Formaussage. */}
          <button
            type="button"
            aria-pressed={selectedId === photo.id}
            onClick={() => {
              onSelect(photo.id)
            }}
            className="flex w-24 flex-col gap-1 rounded-md border border-border-control bg-surface p-1 hover:bg-overlay active:bg-border aria-pressed:border-accent"
          >
            <PhotoImage
              photoId={photo.id}
              variant="thumbnail"
              alt=""
              className="aspect-square w-full rounded-sm"
            />
            <span className="font-mono text-xs text-text">{formatDateTime(photo.taken_at)}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

/**
 * Dialog „Zeitversatz für <Kamera>" - trägt Handeingabe UND Vorschlagsrechnung an EINER Stelle,
 * damit ein Vorschlag in dieselben Felder fällt, die auch von Hand bedient werden.
 *
 * Zwei getrennte Handlungen, damit „vorgeschlagen" und „gilt" nicht verwechselbar sind:
 * „Vorschlag übernehmen" füllt nur die Felder (und lässt sie änderbar), „Versatz speichern" ist
 * die EINZIGE Schaltfläche, die schreibt.
 *
 * Die lebende Vorschau an einem echten Foto dieser Kamera ist die tragende Maßnahme gegen ein
 * falsches Vorzeichen: Der Nutzer prüft das ERGEBNIS, nicht die Rechnung.
 */
export function CameraTimeOffsetDialog({
  open,
  onClose,
  projectId,
  camera,
  cameras,
}: CameraTimeOffsetDialogProps) {
  const initial = offsetToFields(camera.offset_minutes)
  const [direction, setDirection] = useState<ClockDirection>(initial.direction)
  const [days, setDays] = useState(String(initial.days))
  const [hours, setHours] = useState(String(initial.hours))
  const [minutes, setMinutes] = useState(String(initial.minutes))
  const [failure, setFailure] = useState<SaveFailure | null>(null)
  const [referenceCameraId, setReferenceCameraId] = useState<number | null>(null)
  const [cameraPhotoId, setCameraPhotoId] = useState<number | null>(null)
  const [referencePhotoId, setReferencePhotoId] = useState<number | null>(null)

  const saveMutation = useSetCameraTimeOffsetMutation(projectId)
  const suggestionMutation = useCameraTimeOffsetSuggestionMutation(projectId)
  const directionGroupId = useId()
  const problemId = useId()

  const ownPhotos = usePhotosOfCameraQuery(projectId, camera.id, open)
  const referencePhotos = usePhotosOfCameraQuery(projectId, referenceCameraId, open)

  // Ein leeres Feld ist eine Zwischenstufe des Tippens; als Zahl ist es `NaN`, und genau das
  // beanstandet die Validierung - kein stilles `0`.
  const fields: OffsetFields = {
    direction,
    days: days.trim() === '' ? Number.NaN : Number(days),
    hours: hours.trim() === '' ? Number.NaN : Number(hours),
    minutes: minutes.trim() === '' ? Number.NaN : Number(minutes),
  }
  const problem = validateOffsetFields(fields)
  const offsetMinutes = problem === null ? offsetFromFields(fields) : 0
  const isPending = saveMutation.isPending

  const previewPhoto = ownPhotos.data?.items[0] ?? null
  const previewEffective =
    previewPhoto === null || problem !== null
      ? null
      : applyOffsetToIsoTime(previewPhoto.taken_at_original, offsetMinutes)

  const otherCameras = cameras.filter((entry) => entry.id !== camera.id)
  const suggestion = suggestionMutation.data ?? null

  function handleClose(): void {
    if (isPending) {
      return
    }
    onClose()
  }

  function handleSave(): void {
    if (problem !== null) {
      return
    }
    setFailure(null)
    saveMutation.mutate(
      { cameraId: camera.id, offsetMinutes },
      {
        onSuccess: () => {
          onClose()
        },
        onError: (error) => {
          setFailure(toFailure(error))
        },
      },
    )
  }

  function handleComputeSuggestion(): void {
    if (cameraPhotoId === null || referencePhotoId === null) {
      return
    }
    suggestionMutation.mutate({ photoId: cameraPhotoId, referencePhotoId })
  }

  /** Füllt NUR die Felder - es wird nichts geschrieben, und die Werte bleiben von Hand
   * änderbar. */
  function handleAdoptSuggestion(): void {
    if (suggestion === null) {
      return
    }
    const next = offsetToFields(suggestion.offset_minutes)
    setDirection(next.direction)
    setDays(String(next.days))
    setHours(String(next.hours))
    setMinutes(String(next.minutes))
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title={`Zeitversatz für ${camera.label}`}
      description="Die Aufnahmezeiten der Fotos dieser Kamera werden um den Versatz verschoben. Die Originaldateien bleiben unverändert."
      cancelDisabled={isPending}
      actions={
        <Button busy={isPending} disabled={problem !== null} onClick={handleSave}>
          {isPending ? 'Wird gespeichert…' : 'Versatz speichern'}
        </Button>
      }
    >
      <fieldset className="flex flex-col gap-2">
        <legend id={directionGroupId} className="text-xs font-medium text-text-h">
          Richtung
        </legend>
        {(['ahead', 'behind'] as const).map((option) => (
          <label key={option} className="flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name={directionGroupId}
              value={option}
              checked={direction === option}
              onChange={() => {
                setDirection(option)
              }}
              className="size-4 accent-accent"
            />
            <span className="text-sm text-text-h">{DIRECTION_LABEL[option]}</span>
            <span className="text-xs text-text-muted">{DIRECTION_HINT[option]}</span>
          </label>
        ))}
      </fieldset>

      <div className="flex gap-3">
        <OffsetNumberField
          label="Tage"
          value={days}
          invalid={problem?.field === 'days'}
          onChange={setDays}
        />
        <OffsetNumberField
          label="Stunden"
          value={hours}
          invalid={problem?.field === 'hours'}
          onChange={setHours}
        />
        <OffsetNumberField
          label="Minuten"
          value={minutes}
          invalid={problem?.field === 'minutes'}
          onChange={setMinutes}
        />
      </div>
      {problem !== null && (
        <p id={problemId} role="alert" className="text-sm text-danger-text">
          {problem.message}
        </p>
      )}

      {/* LEBENDE VORSCHAU an einem echten Foto dieser Kamera. */}
      {previewPhoto !== null && previewEffective !== null && (
        <p className="text-sm text-text">
          <span className="text-text-muted">aufgezeichnet </span>
          <span className="font-mono">{formatDateTime(previewPhoto.taken_at_original)}</span>
          <span aria-hidden="true"> → </span>
          <span className="text-text-muted">wirksam </span>
          <span className="font-mono text-text-h">{formatDateTime(previewEffective)}</span>
        </p>
      )}

      {/* VORSCHLAG - klar abgesetzter, eigener Teil des Dialogs. */}
      <section className="flex flex-col gap-3 border-t border-separator pt-4">
        <h3 className="text-base text-text-h">Vorschlag ausrechnen</h3>
        <p className="text-sm text-text">
          Wähle zwei Fotos desselben Moments: eines von dieser Kamera, eines von einer anderen.
        </p>
        {otherCameras.length === 0 ? (
          <p className="text-sm text-text">
            Für einen Vorschlag braucht das Projekt eine zweite Kamera.
          </p>
        ) : (
          <>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-text-h">Referenzkamera</span>
              <select
                value={referenceCameraId === null ? '' : String(referenceCameraId)}
                onChange={(event) => {
                  setReferenceCameraId(
                    event.target.value === '' ? null : Number(event.target.value),
                  )
                  setReferencePhotoId(null)
                }}
                className="h-11 w-full rounded-sm border border-border-control bg-surface px-3 text-sm text-text-h"
              >
                <option value="">Bitte wählen</option>
                {otherCameras.map((entry) => (
                  <option key={entry.id} value={entry.id}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </label>

            <PhotoStrip
              label={`Fotos von ${camera.label}`}
              photos={ownPhotos.data?.items ?? []}
              isLoading={ownPhotos.isLoading}
              selectedId={cameraPhotoId}
              onSelect={setCameraPhotoId}
            />
            {referenceCameraId !== null && (
              <PhotoStrip
                label="Fotos der Referenzkamera"
                photos={referencePhotos.data?.items ?? []}
                isLoading={referencePhotos.isLoading}
                selectedId={referencePhotoId}
                onSelect={setReferencePhotoId}
              />
            )}

            <div className="flex flex-wrap gap-3">
              <Button
                variant="secondary"
                busy={suggestionMutation.isPending}
                disabled={cameraPhotoId === null || referencePhotoId === null}
                onClick={handleComputeSuggestion}
              >
                Vorschlag ausrechnen
              </Button>
              {suggestion !== null && (
                <Button variant="secondary" onClick={handleAdoptSuggestion}>
                  Vorschlag übernehmen
                </Button>
              )}
            </div>

            {suggestionMutation.isError && (
              <Alert variant="error" title="Vorschlag nicht möglich">
                {suggestionMutation.error instanceof ApiError
                  ? suggestionMutation.error.detail
                  : 'Der Vorschlag konnte nicht berechnet werden.'}
              </Alert>
            )}

            {suggestion !== null && (
              <div className="flex flex-col gap-1 rounded-md border border-info bg-elevated p-3">
                <p className="text-xs font-semibold text-text-h">Vorschlag</p>
                <p className="text-sm text-text">
                  <span className="font-mono text-text-h">
                    {formatDateTime(suggestion.reference_taken_at)}
                  </span>
                  <span className="text-text-muted"> gegenüber </span>
                  <span className="font-mono text-text-h">
                    {formatDateTime(suggestion.photo_taken_at_original)}
                  </span>
                </p>
                <p className="text-sm text-text-muted">
                  Dieser Vorschlag gilt noch nicht. Übernimm ihn in die Felder oben und speichere
                  ihn dort.
                </p>
              </div>
            )}
          </>
        )}
      </section>

      {/* Der Meldungsbereich steht UNTER den Feldern, direkt ueber der Schaltflaechenzeile -
          dieselbe Abweichung wie im Loeschdialog: eine oben eingefuegte Meldung schoebe die
          Eingabefelder unter dem Finger nach unten. */}
      {failure !== null && failure.status === 409 && (
        <Alert variant="warning" title="Ein Vorgang läuft gerade">
          Ein Vorgang dieses Projekts läuft gerade; der Versatz kann danach gesetzt werden.
        </Alert>
      )}
      {failure !== null && failure.status === 422 && (
        <Alert variant="error" title="Versatz nicht anwendbar">
          Mit diesem Versatz liegt die Aufnahmezeit eines Fotos außerhalb des darstellbaren
          Bereichs. Es wurde nichts gespeichert.
        </Alert>
      )}
      {failure !== null && failure.status !== 409 && failure.status !== 422 && (
        <Alert variant="error">{failure.detail}</Alert>
      )}
    </Dialog>
  )
}
