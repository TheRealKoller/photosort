import type { RefObject } from 'react'
import { Link } from 'react-router'

import { Button } from './ui/button'

export interface AlbumDraftBarProps {
  barRef: RefObject<HTMLDivElement | null>
  dayNumber: number
  dayCount: number
  position: number
  eventCount: number
  selectionPath: string
  groupHeading: string
  sizeText: string | null
  smallerProposal: string | null
}

/** Die mitlaufende Leiste des Album-Entwurfs: Position, Weg zur Endauswahl, Event und Größe. */
export function AlbumDraftBar({
  barRef,
  dayNumber,
  dayCount,
  position,
  eventCount,
  selectionPath,
  groupHeading,
  sizeText,
  smallerProposal,
}: AlbumDraftBarProps) {
  return (
    <div
      ref={barRef}
      data-draft-bar=""
      className="sticky top-header z-10 flex flex-col gap-1 border-b border-separator bg-bg py-2"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-text-h">
          {`Tag ${dayNumber} von ${dayCount} · Event ${position} von ${eventCount}`}
        </p>
        <Button asChild variant="secondary" size="sm" className="shrink-0">
          <Link to={selectionPath}>Zur Endauswahl</Link>
        </Button>
      </div>
      <p className="truncate text-sm text-text">{groupHeading}</p>
      {sizeText !== null && <p className="text-sm text-text">{sizeText}</p>}
      {smallerProposal !== null && (
        <p data-testid="smaller-proposal" className="text-sm text-text-muted">
          {smallerProposal}
        </p>
      )}
    </div>
  )
}
