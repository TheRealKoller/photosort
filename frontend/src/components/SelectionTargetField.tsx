import { useEffect, useId, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import type { ProjectOut } from '../api/types'
import { useSetSelectionTargetMutation } from '../hooks/useProjects'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'

/** Wie lange die Bestätigung nach dem Speichern stehen bleibt. */
export const SAVED_HINT_MS = 4000

/**
 * Die feste Vorbelegung des Richtwerts, gespiegelt aus `selection.py::DEFAULT_TARGET`.
 *
 * NUR für den Vergleichssatz „Standard wäre …" einer eigenen Angabe und als Platzhalter. Im
 * Zustand „Standard" steht dagegen `effective_selection_target` vom Server - die wirksame Zahl
 * leitet das Frontend nie selbst ab.
 */
export const DEFAULT_SELECTION_TARGET = 150

export const SELECTION_TARGET_LOCKED_TEXT =
  'Während die Klassifizierung läuft, lässt sich der Richtwert nicht ändern.'

/** `null` („nicht selbst eingestellt") ist das LEERE Feld, nie die vorbelegte Zahl. */
function fieldValueOf(target: number | null): string {
  return target === null ? '' : String(target)
}

interface SelectionTargetFieldProps {
  project: ProjectOut
}

/**
 * Das EINE Richtwert-Feld - im Klassifizierungs-Schritt und in der Kuratierung.
 *
 * LEER HEISST STANDARD. Ist `selection_target === null`, bleibt das Feld leer und der Hinweis
 * nennt die wirksame Zahl vom Server - stünde sie im Feld, wäre „vom System vorbelegt" von
 * „selbst eingestellt" nicht mehr zu unterscheiden, und das Speichern schriebe die Vorbelegung
 * fest. Zurück zum Standard führen das Leeren des Feldes und „Auf Standard zurücksetzen"; beide
 * senden `null`, `0` ist kein Weg dorthin.
 *
 * GESPEICHERT WIRD BEIM VERLASSEN DES FELDES und bei `Enter`, nie bei jedem Tastendruck: jedes
 * Speichern rechnet den gesamten Vorschlag neu (Sicherheitskonzept, S3).
 *
 * DAS FELD KLEMMT NICHT. `min={1}` ist ein Hinweis; die Grenze setzt allein der Endpunkt durch.
 *
 * GESPERRT, solange die Klassifizierung läuft - nur Bedienkomfort, maßgeblich ist der `409` des
 * Servers. Der Feldinhalt wird dabei nie zurückgesetzt, und der 2-s-Poll des Projekts gibt das
 * Feld nach dem Laufende von selbst wieder frei.
 */
export function SelectionTargetField({ project }: SelectionTargetFieldProps) {
  const hintId = useId()
  const lockId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const save = useSetSelectionTargetMutation(project.id)

  const locked = project.last_criterion_scoring_run?.status === 'running'
  // Neu berechnet wird nur ein vorhandener Vorschlag - der eines erfolgreichen Laufs, auch wenn
  // danach ein Lauf gescheitert ist. Ohne ihn sagt die Bestätigung nur, was sicher stimmt: der
  // Wert gilt für den nächsten Vorschlag.
  const hasProposal = project.has_selection_proposal

  // `''` ist der Zustand „Standard" und zugleich der erlaubte Zwischenzustand eines geleerten
  // Feldes - beides derselbe Wert, weil beides dieselbe Eingabe ist.
  const [value, setValue] = useState(fieldValueOf(project.selection_target))
  const [saved, setSaved] = useState(false)

  // Was während eines laufenden Speicherns eingegeben und bestätigt wurde. Gespeichert wird
  // SERIELL: Zwei parallele Anfragen könnten vertauscht ankommen und den älteren Wert
  // festschreiben. Vorgemerkt wird nur der letzte Wert; er geht nach dem Abschluss hinaus.
  const queuedRef = useRef<{ value: number | null } | null>(null)

  // Ändert sich der gespeicherte Wert, übernimmt das Feld ihn NUR, wenn es seit dem letzten
  // gespeicherten Stand nicht bearbeitet wurde. Eine Eingabe verschwindet nie stillschweigend -
  // weder beim Sperren noch durch die Antwort eines vorigen Speicherns. Angleichung WÄHREND des
  // Renderns statt in einem Effekt (Reacts Muster „adjusting state when a prop changes").
  const [lastSavedTarget, setLastSavedTarget] = useState(project.selection_target)
  if (project.selection_target !== lastSavedTarget) {
    setLastSavedTarget(project.selection_target)
    if (value === fieldValueOf(lastSavedTarget)) {
      setValue(fieldValueOf(project.selection_target))
    }
  }

  // Die Bestätigung verschwindet von selbst: ein dauerhafter Erfolgshinweis stünde nach Minuten
  // noch da und behauptete etwas über einen Vorgang, an den sich niemand mehr erinnert.
  useEffect(() => {
    if (!saved) {
      return
    }
    const timer = window.setTimeout(() => setSaved(false), SAVED_HINT_MS)
    return () => window.clearTimeout(timer)
  }, [saved])

  function send(next: number | null): void {
    setSaved(false)
    save.mutate(next, {
      onSuccess: () => setSaved(true),
      onSettled: () => {
        const queued = queuedRef.current
        queuedRef.current = null
        if (queued !== null && queued.value !== next) {
          send(queued.value)
        }
      },
    })
  }

  function commit(): void {
    const trimmed = value.trim()
    const next = trimmed === '' ? null : Number(trimmed)
    if (next !== null && !Number.isFinite(next)) {
      return
    }
    if (save.isPending) {
      // Gleich dem Wert, der gerade gespeichert wird: nichts vormerken, eine ältere Vormerkung
      // ist damit überholt.
      queuedRef.current = save.variables === next ? null : { value: next }
      return
    }
    if (next === project.selection_target) {
      // Nichts zu speichern - und deshalb auch nichts mehr zu melden: eine stehengebliebene
      // Fehlermeldung behauptete sonst etwas über eine Eingabe, die der Nutzer gerade
      // zurückgenommen hat.
      save.reset()
      return
    }
    send(next)
  }

  function resetToDefault(): void {
    // Der Fokus geht SOFORT ins Feld: die Schaltfläche wird gleich deaktiviert und verschwindet
    // danach - der Fokus fiele sonst auf `body`.
    setValue('')
    inputRef.current?.focus()
    send(null)
  }

  const errorText = save.isError
    ? save.error instanceof ApiError
      ? save.error.detail
      : 'Der Richtwert konnte nicht gespeichert werden.'
    : undefined

  const ownTarget = project.selection_target !== null
  const hintText = ownTarget
    ? `Eigene Angabe – Standard wäre ${DEFAULT_SELECTION_TARGET} Bilder.`
    : `Standard: ${project.effective_selection_target} Bilder.`
  const savedText = hasProposal ? ' Vorschlag neu berechnet.' : ' Gilt für den nächsten Vorschlag.'

  return (
    <div className="flex flex-col items-start gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label
          htmlFor={`selection-target-${project.id}`}
          className="flex flex-col gap-1 text-sm text-text"
        >
          Richtwert (Bilder)
          <Input
            ref={inputRef}
            id={`selection-target-${project.id}`}
            type="number"
            min={1}
            placeholder={String(DEFAULT_SELECTION_TARGET)}
            value={value}
            disabled={locked}
            aria-describedby={locked ? `${hintId} ${lockId}` : hintId}
            onChange={(event) => setValue(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                commit()
              }
            }}
            className="w-24"
          />
        </label>
        {ownTarget && (
          <Button
            variant="ghost"
            size="sm"
            disabled={locked}
            busy={save.isPending}
            onClick={resetToDefault}
          >
            Auf Standard zurücksetzen
          </Button>
        )}
      </div>

      <p id={hintId} className="text-sm text-text-muted">
        {hintText}
        {saved && !save.isPending && !save.isError && savedText}
      </p>

      {locked && (
        <p id={lockId} className="text-sm text-text">
          {SELECTION_TARGET_LOCKED_TEXT}
        </p>
      )}

      {errorText !== undefined && (
        <Alert variant="error" title="Richtwert nicht gespeichert">
          {errorText}
        </Alert>
      )}
    </div>
  )
}
