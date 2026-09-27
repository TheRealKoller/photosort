import { Link } from 'react-router'

import type { PersonOrigin, PersonOut, PhotoOut } from '../api/types'
import { usePhotoPersonControls } from '../hooks/usePhotoPersons'
import { usePersonsQuery } from '../hooks/usePersons'
import { PersonFacePicker } from './PersonFacePicker'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

interface PhotoPersonsSectionProps {
  projectId: number
  photo: PhotoOut
}

/** Das Zustandswort einer Zeile. Die Herkunft ist nur ein Wort - kein Badge, keine Farbe, kein
 * Symbol (Design-System: "Zuordnung mit Herkunft"). */
const STATE_WORDS: Record<PersonOrigin | 'unassigned', string> = {
  recognized: 'Erkannt',
  corrected: 'Von Hand zugeordnet',
  unassigned: 'Nicht zugeordnet',
}

/**
 * Der Personenabschnitt der Detailansicht (Spec 0292, UI/UX 1): je festgelegter Person eine Zeile
 * mit Zustand und Ergänzen/Entfernen, darunter die Gesichterwahl. Namen sind Fremdtext und stehen
 * nur als Textknoten.
 *
 * Der Aufrufer bindet den Abschnitt je Foto neu ein (`key`): Ein Fotowechsel setzt Busy, Meldung
 * und Gesichterwahl zurück.
 */
export function PhotoPersonsSection({ projectId, photo }: PhotoPersonsSectionProps) {
  const personsQuery = usePersonsQuery()

  return (
    <section
      className="flex flex-col gap-3 rounded-md border border-border bg-surface p-4"
      aria-labelledby="persons-heading"
    >
      <div className="flex items-center justify-between gap-3">
        <h2
          id="persons-heading"
          className="text-xs font-semibold tracking-wide text-text-h uppercase"
        >
          Personen
        </h2>
        <Button asChild variant="ghost" size="sm">
          <Link to="/persons">Personen verwalten</Link>
        </Button>
      </div>
      {personsQuery.isPending ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-8 w-full rounded-lg" />
          <Skeleton className="h-8 w-full rounded-lg" />
          <p role="status" className="sr-only">
            Personen werden geladen…
          </p>
        </div>
      ) : personsQuery.isError ? (
        <Alert onRetry={() => void personsQuery.refetch()}>
          Die Personen konnten nicht geladen werden.
        </Alert>
      ) : (
        <>
          <PersonRows projectId={projectId} photo={photo} persons={personsQuery.data} />
          <PersonFacePicker projectId={projectId} photo={photo} persons={personsQuery.data} />
        </>
      )}
    </section>
  )
}

function PersonRows({
  projectId,
  photo,
  persons,
}: {
  projectId: number
  photo: PhotoOut
  persons: PersonOut[]
}) {
  const controls = usePhotoPersonControls(projectId)

  return (
    <>
      {persons.length === 0 ? (
        <p className="text-sm text-text">Noch keine Person festgelegt.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {persons.map((person) => {
            const assigned = photo.persons.find((entry) => entry.person_id === person.id)
            const state = assigned?.origin ?? 'unassigned'
            const action = assigned ? 'Entfernen' : 'Ergänzen'
            return (
              <li
                key={person.id}
                className="flex items-center justify-between gap-3"
                data-person-state={state}
              >
                <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-medium text-text-h">{person.name}</span>
                  <span className="text-sm text-text">{STATE_WORDS[state]}</span>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label={`${action}: ${person.name}`}
                  busy={controls.pendingIds.includes(person.id)}
                  onClick={() => void controls.setApplies(photo.id, person.id, !assigned)}
                >
                  {action}
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      {controls.error !== null && <Alert>{controls.error}</Alert>}
    </>
  )
}
