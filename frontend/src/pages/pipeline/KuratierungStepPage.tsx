import { useEffect, useId, useState } from 'react'
import { Link, useOutletContext } from 'react-router'

import { ApiError } from '../../api/client'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { useSetSelectionTargetMutation } from '../../hooks/useProjects'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * Kuratierungs-Schritt der Pipeline: die Richtwert-Einstellung und der Weg in die Ansicht.
 *
 * LEER HEISST VORBELEGUNG. Ist `selection_target === null`, bleibt das Feld leer und die wirksame
 * Zahl steht im Hinweistext darunter - stünde sie im Feld, wäre "vom System vorbelegt" von
 * "selbst eingestellt" nicht mehr zu unterscheiden, und das Speichern schriebe die Vorbelegung
 * fest. `0` ist kein Weg dorthin; das Leeren des Feldes ist der einzige.
 *
 * GESPEICHERT WIRD BEIM VERLASSEN DES FELDES und bei `Enter`, nicht bei jedem Tastendruck und
 * nicht zeitgesteuert: jedes Speichern rechnet den gesamten Vorschlag neu, und beim Tippen von
 * "150" entstünden sonst drei Neuberechnungen.
 *
 * DAS FELD KLEMMT NICHT. Es setzt `min={1}` als Hinweis, die Grenze durchsetzen tut allein der
 * Endpunkt - eine clientseitige Obergrenze wäre eine zweite Wahrheit darüber.
 */
/** Wie lange die Bestätigung "Vorschlag neu berechnet" stehen bleibt. */
export const SAVED_HINT_MS = 4000

/** `null` ("nicht selbst eingestellt") ist das LEERE Feld, nie die vorbelegte Zahl. */
function fieldValueOf(target: number | null): string {
  return target === null ? '' : String(target)
}

export function KuratierungStepPage() {
  const { project } = useOutletContext<PipelineOutletContext>()
  const hintId = useId()
  const save = useSetSelectionTargetMutation(project.id)

  // `''` ist der Zustand "Vorbelegung" und zugleich der erlaubte Zwischenzustand eines geleerten
  // Feldes - beides derselbe Wert, weil beides dieselbe Eingabe ist.
  const [value, setValue] = useState(fieldValueOf(project.selection_target))
  const [saved, setSaved] = useState(false)

  // Der gespeicherte Wert führt, sobald er sich ändert: nach einem Speichern liefert der Server
  // den kanonischen Stand, und ein zwischenzeitlich gelaufener Kriterien-Lauf kann ihn ebenfalls
  // verändert haben. Angleichung WÄHREND des Renderns statt in einem Effekt (Reacts Muster
  // "adjusting state when a prop changes") - ein Effekt bräuchte hier eine unvollständige
  // Abhängigkeitsliste, um die gerade getippte Eingabe nicht zu überschreiben.
  const [lastSavedTarget, setLastSavedTarget] = useState(project.selection_target)
  if (project.selection_target !== lastSavedTarget) {
    setLastSavedTarget(project.selection_target)
    setValue(fieldValueOf(project.selection_target))
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

  function commit(): void {
    const trimmed = value.trim()
    const next = trimmed === '' ? null : Number(trimmed)
    if (next !== null && !Number.isFinite(next)) {
      return
    }
    if (next === project.selection_target) {
      return
    }
    setSaved(false)
    save.mutate(next, { onSuccess: () => setSaved(true) })
  }

  const errorText = save.isError
    ? save.error instanceof ApiError
      ? save.error.detail
      : 'Der Richtwert konnte nicht gespeichert werden.'
    : undefined

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col items-start gap-3">
        <h2 className="text-lg">Kuratierung</h2>
        <p className="text-sm text-text">
          Der Vorschlag deckt alle Foto-Momente ab und mischt in jedem die vorkommenden Motive. Der
          Richtwert ist ein Ziel, keine Obergrenze — reicht der Bildbestand nicht, wird der
          Vorschlag kleiner; damit jeder Foto-Moment vorkommt, kann er auch größer werden.
        </p>

        <div className="flex flex-wrap items-end gap-3">
          <label htmlFor="selection-target" className="flex flex-col gap-1 text-sm text-text">
            Richtwert (Bilder)
            <Input
              id="selection-target"
              type="number"
              min={1}
              value={value}
              disabled={save.isPending}
              aria-describedby={hintId}
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
          <Button asChild variant="secondary">
            <Link to={`/projects/${project.id}/curate`}>Kuratierung öffnen</Link>
          </Button>
        </div>

        <p id={hintId} className="text-sm text-text-muted">
          {`Leer = ein Zehntel der Bilderzahl (zurzeit ${project.effective_selection_target}).`}
          {saved && !save.isPending && !save.isError && ' Vorschlag neu berechnet.'}
        </p>

        {errorText !== undefined && (
          <Alert variant="error" title="Richtwert nicht gespeichert">
            {errorText}
          </Alert>
        )}
      </section>
    </div>
  )
}
