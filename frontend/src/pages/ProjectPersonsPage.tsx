import { useCallback, useMemo, useRef, useState } from 'react'
import type { RefObject } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { CurationLightbox } from '../components/CurationLightbox'
import { PersonPhotoGroup } from '../components/PersonPhotoGroup'
import { UnnamedFacesGroup } from '../components/UnnamedFacesGroup'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useCurationLightbox } from '../hooks/useCurationLightbox'
import { usePersonsQuery } from '../hooks/usePersons'
import { useUnnamedFaces } from '../hooks/useUnnamedFaces'
import { ROW_CARD_LIST_CLASSES } from '../utils/personOverview'

const UNNAMED_HEADING_ID = 'ohne-namen'

/** Die Personenübersicht eines Projekts. Je Projekt eine eigene Instanz: Ein Wechsel des Projekts
 * beginnt die Suche in "Ohne Namen" von vorn, statt die Stelle eines anderen Projekts zu erben. */
export function ProjectPersonsPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  return <ProjectPersonsOverview key={id} projectId={id} />
}

/**
 * Sehen, welche Fotos welchen Namen tragen, falsche Namen entfernen und Gesichter ohne Namen
 * zuordnen - an einer Stelle. Je festgelegter Person eine Gruppe in der Reihenfolge von
 * `GET /persons`, danach IMMER zuletzt "Ohne Namen": Die Gruppe wächst während der Suche am Ende;
 * stünde sie oben, verschöbe jede nachgeladene Seite alles darunter.
 *
 * Die Personengruppen kommen rein aus der Datenbank und warten nicht auf die Gesichtssuche.
 */
function ProjectPersonsOverview({ projectId }: { projectId: number }) {
  const persons = usePersonsQuery()
  const unnamed = useUnnamedFaces(projectId)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const unnamedHeadingRef = useRef<HTMLHeadingElement>(null)
  const headingRefs = useRef(new Map<number, RefObject<HTMLHeadingElement | null>>())
  const [photosByPerson, setPhotosByPerson] = useState<ReadonlyMap<number, readonly PhotoOut[]>>(
    new Map(),
  )

  const onPhotosChange = useCallback((personId: number, photos: readonly PhotoOut[]) => {
    setPhotosByPerson((current) => new Map(current).set(personId, photos))
  }, [])

  // Die Großansicht der ganzen Seite: die geladenen Fotos aller Personengruppen, nach Id
  // entdoppelt. Solange eine Gruppe noch nichts gemeldet hat, gilt die Liste als ladend - sonst
  // schlösse ein nach Reload offenes Foto, bevor seine Gruppe da ist.
  const items = useMemo(() => {
    const list = persons.data
    if (list === undefined || list.some((person) => !photosByPerson.has(person.id))) {
      return undefined
    }
    const seen = new Set<number>()
    const result: PhotoOut[] = []
    for (const person of list) {
      for (const photo of photosByPerson.get(person.id) ?? []) {
        if (!seen.has(photo.id)) {
          seen.add(photo.id)
          result.push(photo)
        }
      }
    }
    return result
  }, [persons.data, photosByPerson])
  const lightbox = useCurationLightbox({ items, headingRef: titleRef })

  if (unnamed.error instanceof ApiError && unnamed.error.status === 404) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Projekt nicht gefunden.</p>
      </div>
    )
  }

  function headingRefFor(personId: number): RefObject<HTMLHeadingElement | null> {
    let ref = headingRefs.current.get(personId)
    if (ref === undefined) {
      ref = { current: null }
      headingRefs.current.set(personId, ref)
    }
    return ref
  }

  function jumpTo(headingId: string): void {
    const heading = document.getElementById(headingId)
    heading?.scrollIntoView?.({ block: 'start' })
    heading?.focus({ preventScroll: true })
  }

  const groups = [
    ...(persons.data ?? []).map((person) => ({
      headingId: `person-${person.id}`,
      label: person.name,
    })),
    { headingId: UNNAMED_HEADING_ID, label: 'Ohne Namen' },
  ]

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 ref={titleRef} tabIndex={-1} className="text-xl sm:text-2xl">
              Personen
            </h1>
            <p className="text-sm text-text">
              Alle Fotos dieses Projekts, auch im Ausschuss. Namen und gezeigte Gesichter gelten in
              allen Projekten.
            </p>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link to="/persons">Personen verwalten</Link>
          </Button>
        </div>
        {persons.data !== undefined && persons.data.length > 0 && (
          <nav aria-label="Gruppen">
            <ul className="flex flex-wrap gap-3">
              {groups.map((group) => (
                <li key={group.headingId}>
                  <Button asChild variant="outline" size="sm">
                    <a
                      href={`#${group.headingId}`}
                      onClick={(event) => {
                        event.preventDefault()
                        jumpTo(group.headingId)
                      }}
                    >
                      {group.label}
                    </a>
                  </Button>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      {persons.isPending && (
        <>
          <p role="status" className="sr-only">
            Personen werden geladen…
          </p>
          {[0, 1].map((slot) => (
            <div key={slot} aria-hidden="true" className="flex flex-col gap-3">
              <Skeleton className="h-6 w-40" />
              <div className={ROW_CARD_LIST_CLASSES}>
                {[0, 1, 2].map((card) => (
                  <Skeleton key={card} className="h-28 w-full rounded-lg" />
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {persons.isError && (
        <Alert onRetry={() => void persons.refetch()}>
          Die Personen konnten nicht geladen werden.
        </Alert>
      )}

      {persons.data !== undefined && persons.data.length === 0 && (
        <p className="text-sm text-text">
          Noch keine Person festgelegt. Wähle bei einem Gesicht unter „Ohne Namen“ „Neue Person…“,
          um sie festzulegen.
        </p>
      )}

      {persons.data?.map((person) => (
        <PersonPhotoGroup
          key={person.id}
          projectId={projectId}
          person={person}
          headingId={`person-${person.id}`}
          headingRef={headingRefFor(person.id)}
          onOpenLarge={lightbox.open}
          largeTriggerRef={lightbox.triggerRef}
          onPhotosChange={onPhotosChange}
          onNameRemoved={unnamed.refreshPhoto}
          onPersonGone={() => titleRef.current?.focus()}
        />
      ))}

      {persons.data !== undefined && (
        <UnnamedFacesGroup
          projectId={projectId}
          persons={persons.data}
          unnamed={unnamed}
          headingId={UNNAMED_HEADING_ID}
          headingRef={unnamedHeadingRef}
        />
      )}

      {lightbox.photo !== undefined && (
        <CurationLightbox key={lightbox.photo.id} photo={lightbox.photo} onClose={lightbox.close} />
      )}
    </div>
  )
}
