import type { RefObject } from 'react'

import type { DuplicateGroupOut } from '../api/types'
import { formatSpan } from '../utils/duplicateMetrics'
import { Button } from './ui/button'
import { Progress } from './ui/progress'

export interface DuplicateGroupHeaderProps {
  /** Die gefüllte Gruppe; `null` zeigt die allgemeine Überschrift (laden, leer, Fehler). */
  group: DuplicateGroupOut | null
  previousRef: RefObject<HTMLButtonElement | null>
  nextRef: RefObject<HTMLButtonElement | null>
  onPrevious: () => void
  onNext: () => void
}

/** Kopf der Vergleichsansicht: Stelle, Gesamtzahl, Mitglieder und Spanne, dazu die Gruppennavigation. */
export function DuplicateGroupHeader({
  group,
  previousRef,
  nextRef,
  onPrevious,
  onNext,
}: DuplicateGroupHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      {group !== null ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl sm:text-2xl">
              Gruppe {group.position} von {group.total}{' '}
              <span className="text-base font-normal text-text sm:text-lg">
                {`· ${group.items.length} Aufnahmen in ${formatSpan(group.span_seconds)}`}
              </span>
            </h1>
            {/* Nie die einzige Quelle der Zahl - beide stehen als Text im h1. */}
            <Progress
              aria-hidden="true"
              value={group.position}
              max={group.total}
              className="w-24 sm:w-40"
            />
          </div>
          {/* Am Rand `disabled` statt abwesend: Ein verschwindender Knopf verschöbe die übrigen
              unter dem Finger. Der zugängliche Name ist der sichtbare Text (WCAG 2.5.3). */}
          <div role="group" aria-label="Duplikat-Gruppen" className="flex flex-wrap gap-3">
            <Button
              ref={previousRef}
              type="button"
              variant="outline"
              size="sm"
              className="h-11 sm:h-8"
              disabled={group.previous_photo_id === null}
              onClick={onPrevious}
            >
              Vorherige Gruppe
            </Button>
            <Button
              ref={nextRef}
              type="button"
              variant="outline"
              size="sm"
              className="h-11 sm:h-8"
              disabled={group.next_photo_id === null}
              onClick={onNext}
            >
              Nächste Gruppe
            </Button>
          </div>
        </>
      ) : (
        <h1 className="text-xl sm:text-2xl">Duplikate vergleichen</h1>
      )}
    </div>
  )
}
