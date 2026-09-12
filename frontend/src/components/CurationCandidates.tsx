import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { useCurationCandidatesQuery } from '../hooks/usePhotos'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

/** Der Server hat zu dieser Partition nichts weiter geliefert. */
export const CANDIDATES_NONE_TEXT = 'Keine weiteren Kandidaten vorhanden.'

/** Wie viele Platzhalter waehrend des Ladens stehen - dieselbe Zahl wie in der Top-Auswahl. */
const SKELETON_TILE_COUNT = 4

/** Dasselbe Raster wie die Top-Foto-Reihe: kein zweites Raster, gleiche Kachelgroessen. */
const TILE_GRID_CLASS = 'grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4'

export interface CurationCandidatesProps {
  projectId: number
  eventId: number
  /** Es werden die Fotos mit `rank_position > afterRank` geladen. */
  afterRank: number
  /** Die Restmenge der Partition - sie steht in der Beschriftung des Auslösers. */
  remainingCount: number
  panelId: string
  expanded: boolean
  onToggle: () => void
  /** Baut die Kachel - die Seite besitzt den Verwerfen-Zustand und das Motivset. */
  renderTile: (photo: PhotoOut) => ReactNode
}

/**
 * Der Auslöser "Weitere Kandidaten laden" und der aufgeklappte Bereich darunter.
 *
 * Ob es weitere Kandidaten gibt, steht VOR jedem Laden fest (`partition_size` gegen die Zahl der
 * angezeigten Eintraege) - es braucht keinen Probe-Request, und der Kandidaten-Request laeuft
 * ausschliesslich im aufgeklappten Zustand (`enabled`).
 *
 * Der Aufklapp-Zustand folgt exakt dem bestehenden Tages-Aufklappen: `aria-expanded`/
 * `aria-controls`, Inhalt per bedingtem JSX statt CSS-versteckt.
 */
export function CurationCandidates({
  projectId,
  eventId,
  afterRank,
  remainingCount,
  panelId,
  expanded,
  onToggle,
  renderTile,
}: CurationCandidatesProps) {
  const query = useCurationCandidatesQuery(projectId, {
    eventId,
    afterRank,
    enabled: expanded,
  })

  const visible = query.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <>
      <div>
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={onToggle}
        >
          {expanded
            ? 'Weitere Kandidaten ausblenden'
            : `Weitere Kandidaten laden (${remainingCount})`}
        </Button>
      </div>
      {expanded && (
        <div id={panelId} className="flex flex-col gap-3">
          {query.isLoading && (
            <ul
              role="status"
              aria-label="Weitere Kandidaten werden geladen…"
              className={TILE_GRID_CLASS}
            >
              {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
                <li key={index} aria-hidden="true">
                  <Skeleton className="aspect-square w-full rounded-md" />
                </li>
              ))}
            </ul>
          )}

          {query.isError && (
            <Alert onRetry={() => void query.refetch()}>
              {query.error instanceof ApiError
                ? query.error.detail
                : 'Fehler beim Laden weiterer Kandidaten.'}
            </Alert>
          )}

          {/* Die Rangfolge kommt vom Server und wird nicht nachsortiert. */}
          {query.isSuccess && visible.length > 0 && (
            <ul className={TILE_GRID_CLASS}>{visible.map((photo) => renderTile(photo))}</ul>
          )}

          {query.isSuccess && visible.length === 0 && (
            <p className="text-sm text-text">{CANDIDATES_NONE_TEXT}</p>
          )}

          {query.hasNextPage && (
            <div>
              <Button
                variant="secondary"
                size="sm"
                disabled={query.isFetchingNextPage}
                busy={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                Noch mehr Kandidaten laden
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
