import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { AusschussGroupEntry, AusschussPhotoEntry } from '../api/types'
import {
  AUSSCHUSS_AUTO_EMPTY_TEXT,
  AUSSCHUSS_AUTO_FILTER_TEXT,
  AUSSCHUSS_EMPTY_TEXT,
} from '../utils/ausschussTexts'
import { TARGET_ROW_HEIGHT_PX, naturalTiles } from '../utils/justifiedRows'
import type { JustifiedTile } from '../utils/justifiedRows'
import { ausschussStepPath } from '../utils/projectRoutes'
import { AusschussTile } from './AusschussTile'
import { DuplicateStackTile } from './DuplicateStackTile'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln" -
// dieselbe Annaeherung wie in der Fotoliste, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

export function AusschussOverview({
  autoFilter,
  loading,
  error,
  empty,
  entries,
  total,
  hasNextPage,
  isFetchingNextPage,
  gridRef,
  tiles,
  projectId,
  onOpen,
  onLoadMore,
  onRetry,
}: {
  autoFilter: boolean
  loading: boolean
  error: Error | null
  empty: boolean
  entries: (AusschussPhotoEntry | AusschussGroupEntry)[]
  total: number
  hasNextPage: boolean
  isFetchingNextPage: boolean
  gridRef: (node: HTMLUListElement | null) => void
  tiles: Map<number, JustifiedTile>
  projectId: number
  onOpen: (photoId: number) => void
  onLoadMore: () => void
  onRetry: () => void
}) {
  return (
    <div className="flex w-full flex-col items-start gap-3">
      {autoFilter && (
        <div className="flex flex-wrap items-center gap-3">
          <p data-testid="ausschuss-auto-filter" className="text-sm text-text">
            {AUSSCHUSS_AUTO_FILTER_TEXT}
          </p>
          <Button asChild variant="ghost" size="sm" className="h-11 sm:h-8">
            <Link to={ausschussStepPath(projectId)}>Alle Gruppen anzeigen</Link>
          </Button>
        </div>
      )}

      {loading && (
        <ul role="status" aria-label="Ausschnitt wird geladen…" className="flex flex-wrap gap-3">
          {naturalTiles(
            Array.from({ length: SKELETON_TILE_COUNT }, () => null),
            TARGET_ROW_HEIGHT_PX,
          ).map((tile) => (
            <li key={tile.index} aria-hidden="true" style={{ width: tile.width }}>
              <Skeleton className="size-full rounded-md" style={{ height: tile.height }} />
            </li>
          ))}
        </ul>
      )}

      {error !== null && (
        <Alert onRetry={onRetry}>
          {error instanceof ApiError ? error.detail : 'Fehler beim Laden des Ausschusses.'}
        </Alert>
      )}

      {empty && (
        <p className="text-sm text-text">
          {autoFilter ? AUSSCHUSS_AUTO_EMPTY_TEXT : AUSSCHUSS_EMPTY_TEXT}
        </p>
      )}

      {entries.length > 0 && (
        // `w-full`: Die Spalte darüber steht auf `items-start`, ohne volle Breite mäße
        // `useElementWidth` die Breite des INHALTS statt des Containers - eine einzelne
        // Panoramakachel der letzten Zeile hielte das Raster dann auf ihrer eigenen Breite
        // fest und die Übersicht scrollte bei 360px waagerecht.
        <ul data-ausschuss-grid ref={gridRef} className="flex w-full flex-wrap gap-3">
          {entries.map((eintrag, index) => {
            const tile = tiles.get(index)
            if (eintrag.kind === 'group') {
              return (
                <DuplicateStackTile
                  key={`gruppe-${eintrag.group_anchor_photo_id}`}
                  projectId={projectId}
                  entry={eintrag}
                  width={tile?.width ?? 0}
                  height={tile?.height ?? 0}
                />
              )
            }
            return (
              <AusschussTile
                key={eintrag.photo.id}
                entry={eintrag}
                width={tile?.width ?? 0}
                height={tile?.height ?? 0}
                onOpen={onOpen}
              />
            )
          })}
        </ul>
      )}

      {/* Der Sichtbarkeitsnachweis: Die geladene Seite ist nicht der ganze Bestand. */}
      {(hasNextPage || isFetchingNextPage) && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isFetchingNextPage}
          busy={isFetchingNextPage}
          onClick={onLoadMore}
        >
          Mehr laden
        </Button>
      )}
      {(hasNextPage || isFetchingNextPage) && (
        <p aria-live="polite" className="text-sm text-text">
          {entries.length} von {total} Einträgen geladen
        </p>
      )}
    </div>
  )
}
