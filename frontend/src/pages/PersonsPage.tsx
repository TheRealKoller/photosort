import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { PersonOut } from '../api/types'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Dialog } from '../components/ui/dialog'
import { Input } from '../components/ui/input'
import { Skeleton } from '../components/ui/skeleton'
import { useDeletePersonMutation, usePersonsQuery } from '../hooks/usePersons'

const SKELETON_CARD_COUNT = 2

function referenceCountText(count: number): string {
  if (count === 0) {
    // Tritt nach einem Modellwechsel ein: Die alten Referenzen passen nicht mehr zum Modell.
    return 'Noch kein Gesicht gezeigt – ohne gezeigtes Gesicht wird die Person nicht erkannt.'
  }
  return count === 1 ? 'einmal gezeigt' : `${count}-mal gezeigt`
}

interface RemovePersonDialogProps {
  person: PersonOut
  onClose: () => void
  onRemoved: () => void
}

/**
 * Bestätigung vor dem Entfernen einer Person, nach dem Vorbild von `DeleteProjectDialog`: kein
 * `icon`, kein `<form>` (die Eingabetaste löst nicht aus), exakter Vergleich ohne Trim und ohne
 * Groß-/Kleinschreibung zu ignorieren - die Reibung ist der Zweck. Ein Fehler lässt den getippten
 * Namen stehen; "Entfernen" IST die Wiederholung, ein zweites "Erneut versuchen" gibt es nicht.
 */
function RemovePersonDialog({ person, onClose, onRemoved }: RemovePersonDialogProps) {
  const [confirmation, setConfirmation] = useState('')
  const [failure, setFailure] = useState<string | null>(null)
  const removeMutation = useDeletePersonMutation()
  const nameId = useId()
  const isPending = removeMutation.isPending

  function handleClose(): void {
    // Während der Anfrage ignoriert: Esc schlösse sonst den Dialog, ohne die Anfrage abzubrechen.
    if (!isPending) {
      onClose()
    }
  }

  function handleRemove(): void {
    setFailure(null)
    removeMutation.mutate(person.id, {
      onSuccess: onRemoved,
      onError: (error) => {
        setFailure(
          error instanceof ApiError && error.detail.length > 0
            ? error.detail
            : 'Die Person konnte nicht entfernt werden. Bitte versuche es erneut.',
        )
      },
    })
  }

  return (
    <Dialog
      open
      onClose={handleClose}
      title="Person entfernen?"
      description={`${person.name} wird auf allen Fotos in allen Projekten entfernt, samt der von Hand vorgenommenen Zuordnungen und aller gezeigten Gesichter. Das lässt sich nicht rückgängig machen.`}
      cancelDisabled={isPending}
      actions={
        <Button
          variant="destructive"
          busy={isPending}
          disabled={confirmation !== person.name}
          onClick={handleRemove}
        >
          {isPending ? 'Wird entfernt…' : 'Entfernen'}
        </Button>
      }
    >
      <label className="flex flex-col gap-2">
        <span className="text-xs font-medium text-text-h">Zur Bestätigung den Namen eingeben:</span>
        {/* Der zu tippende Name steht sichtbar und wie das Feld in `font-mono`, damit l/1/I und
            O/0 unterscheidbar sind. Namen sind Fremdtext und stehen nur als Textknoten. */}
        <span id={nameId} className="font-mono text-sm break-words text-text-h">
          {person.name}
        </span>
        <Input
          className="font-mono"
          value={confirmation}
          onChange={(event) => {
            setConfirmation(event.target.value)
          }}
          disabled={isPending}
          aria-describedby={nameId}
          // Mobilgeräte schrieben den ersten Buchstaben sonst groß und brächen den exakten Vergleich.
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </label>
      {/* Über der Schaltflächenzeile, unter dem Feld: Eine oben eingefügte Meldung schöbe das
          Feld unter dem Finger weg. */}
      {failure !== null && <Alert variant="error">{failure}</Alert>}
    </Dialog>
  )
}

/**
 * Die festgelegten Personen, global für alle Projekte. Auf den Karten
 * gibt es keine Aktion; entfernt wird ausschließlich über die Gefahrenzone am Seitenende.
 */
export function PersonsPage() {
  const query = usePersonsQuery()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [removing, setRemoving] = useState<PersonOut | null>(null)
  // Ein neues Objekt je Entfernen, damit auch ein zweites Entfernen desselben Namens den Fokus
  // erneut setzt.
  const [removed, setRemoved] = useState<{ name: string } | null>(null)

  // Als Effekt statt direkt im Erfolgsfall: Das Schließen des Dialogs gibt den Fokus in seiner
  // Aufräumfunktion an den Auslöser zurück, und die läuft vor den Effekten des nächsten Renderns.
  // Der Auslöser verschwindet mit der neu geladenen Liste - der Fokus gehört auf das `h1`.
  useEffect(() => {
    if (removed !== null) {
      headingRef.current?.focus()
    }
  }, [removed])

  const persons = query.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 ref={headingRef} tabIndex={-1} className="text-xl sm:text-2xl">
          Personen
        </h1>
        <p className="text-sm text-text">Gilt für alle Projekte.</p>
      </header>

      <p role="status" className="text-sm text-text empty:hidden">
        {removed === null ? null : `${removed.name} ist entfernt.`}
      </p>

      {query.isLoading && (
        <ul role="status" aria-label="Personen werden geladen…" className="flex flex-col gap-3">
          {Array.from({ length: SKELETON_CARD_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="h-22 w-full rounded-lg" />
            </li>
          ))}
        </ul>
      )}

      {query.isError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Personen.'}
        </Alert>
      )}

      {query.isSuccess && persons.length === 0 && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">
            Noch keine Person festgelegt. Eine Person legst du in der Detailansicht eines Fotos
            fest, im Abschnitt „Personen“ mit „Gesicht zeigen“.
          </p>
          <Button asChild variant="secondary">
            <Link to="/">Zu den Projekten</Link>
          </Button>
        </div>
      )}

      {persons.length > 0 && (
        <ul className="flex flex-col gap-3">
          {persons.map((person) => (
            <li
              key={person.id}
              className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4"
            >
              <h2 className="text-lg break-words">{person.name}</h2>
              <p className="text-sm text-text">{referenceCountText(person.reference_count)}</p>
            </li>
          ))}
        </ul>
      )}

      {/* Gefahrenzone nach dem Muster der Projekteinstellungen: ein dauerhafter Abschnitt, keine
          Meldung - kein `Alert`, kein Symbol; Farbe tragen nur Rand und Schaltflächen. */}
      {persons.length > 0 && (
        <section className="border-t border-separator pt-6">
          <div className="flex flex-col gap-3 rounded-lg border border-danger bg-surface p-4">
            <h2 className="text-lg text-text-h">Person entfernen</h2>
            <p className="text-sm text-text">
              Entfernt den Namen auf allen Fotos in allen Projekten, auch von Hand vorgenommene
              Zuordnungen, und alle gezeigten Gesichter. Die Fotos und ihre Bewertungen bleiben
              unverändert.
            </p>
            <div className="flex flex-wrap gap-3">
              {persons.map((person) => (
                <Button
                  key={person.id}
                  variant="destructive"
                  onClick={() => {
                    setRemoving(person)
                  }}
                  // Namen werden nie gekürzt: Ein langer Name bricht um, statt die Seite
                  // waagerecht scrollen zu lassen.
                  className="h-auto min-h-8 whitespace-normal break-words"
                >
                  {`${person.name} entfernen`}
                </Button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Nur gerendert, solange er offen ist: Das Unmount verwirft den getippten Namen, statt ihn
          beim nächsten Öffnen bereits freigeschaltet stehen zu lassen. */}
      {removing !== null && (
        <RemovePersonDialog
          person={removing}
          onClose={() => {
            setRemoving(null)
          }}
          onRemoved={() => {
            setRemoving(null)
            setRemoved({ name: removing.name })
          }}
        />
      )}
    </div>
  )
}
