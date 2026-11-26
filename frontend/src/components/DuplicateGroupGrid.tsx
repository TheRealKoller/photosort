import { useMemo } from 'react'

import type { DuplicateDecision, DuplicateGroupItem } from '../api/types'
import { useElementWidth } from '../hooks/useElementWidth'
import { DUPLICATE_TILE_INSET_X_PX, duplicateGridRows } from '../utils/duplicateLayout'
import { bestExposureIndices, bestSharpnessIndices } from '../utils/duplicateMetrics'
import type { JustifiedRow } from '../utils/justifiedRows'
import { DuplicateEnlargedView } from './DuplicateEnlargedView'
import { DuplicatePhotoTile } from './DuplicatePhotoTile'
import { Skeleton } from './ui/skeleton'

const SKELETON_TILE_COUNT = 4

/** Raster und Platzhalterliste: umbrechend, oben bündig, mit dem gerechneten `GRID_GAP_PX`. */
const GRID_LIST_CLASSES = 'flex w-full flex-wrap items-start gap-3'

/** Die Bildmaße je Index aus den Reihen - `duplicateGridRows` führt jeden Index genau einmal. */
function tileSizesByIndex(
  count: number,
  rows: readonly JustifiedRow[],
): { width: number; height: number }[] {
  const sizes = Array.from({ length: count }, () => ({ width: 0, height: 0 }))
  for (const row of rows) {
    for (const tile of row.tiles) {
      sizes[tile.index] = { width: tile.width, height: tile.height }
    }
  }
  return sizes
}

export interface DuplicateGroupGridProps {
  loading: boolean
  /** Die Aufnahmen der gefüllten Gruppe; leer zeigt weder Platzhalter noch Raster. */
  items: DuplicateGroupItem[]
  enlargedItem: DuplicateGroupItem | undefined
  decidingIds: ReadonlySet<number>
  onOpen: (photoId: number) => void
  onClose: () => void
  onSelect: (photoId: number) => void
  onDecide: (photoId: number, decision: DuplicateDecision) => void
  imageRef: (photoId: number, element: HTMLButtonElement | null) => void
}

/** Platzhalter, Raster oder Großansicht - an derselben Stelle, mit EINER Breitenmessung. */
export function DuplicateGroupGrid({
  loading,
  items,
  enlargedItem,
  decidingIds,
  onOpen,
  onClose,
  onSelect,
  onDecide,
  imageRef,
}: DuplicateGroupGridProps) {
  const bestSharpness = useMemo(
    () => bestSharpnessIndices(items.map((item) => item.sharpness)),
    [items],
  )
  const bestExposure = useMemo(
    () => bestExposureIndices(items.map((item) => item.exposure)),
    [items],
  )

  // EIN gemessener Ref für beide Listen: Er hängt an der gerade gerenderten - Platzhalter oder
  // Raster, nie beide -, und ein Knotenwechsel meldet die neue Liste beim Beobachter an.
  const { ref: gridRef, width: gridWidth } = useElementWidth<HTMLUListElement>()
  const tileSizes = useMemo(
    () =>
      tileSizesByIndex(
        items.length,
        duplicateGridRows(
          items.map((item) => item.photo.aspect_ratio ?? null),
          gridWidth,
        ),
      ),
    [items, gridWidth],
  )
  const skeletonSizes = useMemo(
    () =>
      tileSizesByIndex(
        SKELETON_TILE_COUNT,
        duplicateGridRows(Array<null>(SKELETON_TILE_COUNT).fill(null), gridWidth),
      ),
    [gridWidth],
  )

  if (loading) {
    return (
      <ul
        ref={gridRef}
        role="status"
        aria-label="Duplikat-Gruppe wird geladen…"
        className={GRID_LIST_CLASSES}
      >
        {skeletonSizes.map((size, index) => (
          // `border-2 border-transparent` steht für den Zustandsrahmen der echten Kachel - ohne
          // ihn wäre der Platzhalter 4 px schmaler als die Rechnung.
          <li
            key={index}
            aria-hidden="true"
            style={{ width: size.width + DUPLICATE_TILE_INSET_X_PX }}
            className="flex max-w-full flex-col gap-3 rounded-lg border-2 border-transparent bg-elevated px-2 py-2 sm:py-3"
          >
            <Skeleton
              style={{ width: size.width, height: size.height }}
              className="max-w-full rounded-md"
            />
            <Skeleton className="h-3 w-full rounded-xs" />
            <Skeleton className="h-3 w-full rounded-xs" />
            <Skeleton className="h-3 w-full rounded-xs" />
            <Skeleton className="h-8 w-full rounded-sm" />
          </li>
        ))}
      </ul>
    )
  }

  if (items.length === 0) {
    return null
  }

  return enlargedItem !== undefined ? (
    <DuplicateEnlargedView
      items={items}
      currentId={enlargedItem.photo.id}
      bestSharpness={bestSharpness}
      bestExposure={bestExposure}
      decidingIds={decidingIds}
      onSelect={onSelect}
      onClose={onClose}
      onDecide={onDecide}
    />
  ) : (
    <ul ref={gridRef} className={GRID_LIST_CLASSES}>
      {items.map((item, index) => (
        <DuplicatePhotoTile
          key={item.photo.id}
          photo={item.photo}
          effectiveDecision={item.effective_decision}
          keepPossible={item.keep_possible}
          sharpness={item.sharpness}
          exposure={item.exposure}
          bestSharpness={bestSharpness.has(index)}
          bestExposure={bestExposure.has(index)}
          deciding={decidingIds.has(item.photo.id)}
          imageWidth={tileSizes[index].width}
          imageHeight={tileSizes[index].height}
          onOpen={() => onOpen(item.photo.id)}
          onDecide={(decision) => onDecide(item.photo.id, decision)}
          imageRef={(element) => imageRef(item.photo.id, element)}
        />
      ))}
    </ul>
  )
}
