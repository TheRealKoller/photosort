import { CURATION_TARGET_ROW_HEIGHT_PX } from '../utils/curationLayout'
import { naturalTiles } from '../utils/justifiedRows'
import { Skeleton } from './ui/skeleton'

/**
 * Die Ladeplatzhalter eines Kuratierungsrasters: Kacheln in natürlicher Breite zur Zielhöhe, je mit
 * einem Block für die Knopfzeile darunter, damit beim Eintreffen nichts springt. Ein Platzhalter
 * wird nie breiter als die Liste.
 */
export function CurationSkeletonList({ count, id }: { count: number; id?: string }) {
  return (
    <ul id={id} role="status" aria-label="Fotos werden geladen…" className="flex flex-wrap gap-3">
      {naturalTiles(
        Array.from({ length: count }, () => null),
        CURATION_TARGET_ROW_HEIGHT_PX,
      ).map((tile) => (
        <li
          key={tile.index}
          aria-hidden="true"
          style={{ width: tile.width }}
          className="flex max-w-full flex-col gap-2"
        >
          <Skeleton className="w-full rounded-md" style={{ height: tile.height }} />
          <Skeleton className="h-8 w-full rounded-sm" />
        </li>
      ))}
    </ul>
  )
}
