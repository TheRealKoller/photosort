import { useId, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import type { EventOut, PhotoOut } from '../api/types'
import { formatDraftPhotoCount } from '../utils/albumDraft'
import { PHOTO_CARD_GRID_CLASS } from './PhotoCard'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

/** Der Text eines Events, in dem gerade kein Bild im Album steht. */
export const DRAFT_EMPTY_EVENT_TEXT = 'Kein Bild im Entwurf'

export interface DraftEventSectionProps {
  event: EventOut
  /** Der Eventname aus `formatEventHeading` - Textknoten, nie Schlüssel oder DOM-Id (S11). */
  heading: string
  /** Die sichtbaren Fotos im Album (Personenfilter angewandt), in Serverreihenfolge. */
  albumPhotos: PhotoOut[]
  /** k: Fotos im Album dieses Events. */
  albumCount: number
  motifText: string | null
  /** Die gestrichenen Fotos des Events - der Personenfilter filtert sie nicht. */
  struckPhotos: PhotoOut[]
  renderAlbumTile: (photo: PhotoOut) => ReactNode
  renderStruckTile: (photo: PhotoOut) => ReactNode
  /** Das offene Band dieses Events, verankert am gewählten Foto. */
  band: { photoId: number; node: ReactNode } | null
  /** Das offene Hinzufügen-Panel dieses Events. */
  addPanel: { id: string; node: ReactNode } | null
  onToggleAdd: () => void
  /** Grund eines gescheiterten „Wieder aufnehmen", an der Gestrichen-Liste. */
  struckError: string | null
}

/** Die Spaltenzahl des gerenderten Rasters - das Band schließt die Zeile des gewählten Fotos ab. */
function columnCount(grid: HTMLElement | null): number {
  if (grid === null) {
    return 1
  }
  const template = window.getComputedStyle(grid).gridTemplateColumns
  return Math.max(1, template.split(' ').filter((part) => part.length > 0).length)
}

/**
 * EIN Eventabschnitt des Album-Entwurfs: Überschrift mit Bildzahl, Motivzeile, Raster der Fotos im
 * Album mit dem Hinzufügen-Feld als letzter Zelle, und die Gestrichen-Zeile.
 *
 * Er steht auch ohne ein einziges Foto im Album („Kein Bild im Entwurf"). Der Aufklappzustand der
 * Gestrichen-Zeile gilt je Event und wird nicht gespeichert. Band und Panel stehen als volle
 * Rasterzeile nach der Zeile ihres Auslösers.
 */
export function DraftEventSection({
  event,
  heading,
  albumPhotos,
  albumCount,
  motifText,
  struckPhotos,
  renderAlbumTile,
  renderStruckTile,
  band,
  addPanel,
  onToggleAdd,
  struckError,
}: DraftEventSectionProps) {
  const [struckExpanded, setStruckExpanded] = useState(false)
  const struckPanelId = useId()
  const gridRef = useRef<HTMLUListElement>(null)
  const [columns, setColumns] = useState(1)

  useLayoutEffect(() => {
    const measure = () => setColumns(columnCount(gridRef.current))
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  // Zellen: die Albumkacheln, dann das Hinzufügen-Feld.
  const cellCount = albumPhotos.length + 1
  const bandIndex = band === null ? -1 : albumPhotos.findIndex((photo) => photo.id === band.photoId)
  const bandAfter =
    bandIndex === -1 ? -1 : Math.min(cellCount, (Math.floor(bandIndex / columns) + 1) * columns) - 1

  const cells: ReactNode[] = []
  albumPhotos.forEach((photo, index) => {
    cells.push(renderAlbumTile(photo))
    if (index === bandAfter && band !== null) {
      cells.push(band.node)
    }
  })
  cells.push(
    <li key="add" className="flex">
      <button
        type="button"
        data-focus-key={`add-trigger-${event.id}`}
        aria-label={`Foto hinzufügen: ${heading}`}
        aria-expanded={addPanel !== null}
        aria-controls={addPanel?.id}
        onClick={onToggleAdd}
        className="flex min-h-32 w-full items-center justify-center rounded-lg border border-border-control bg-surface p-3 text-sm text-text-h"
      >
        Foto hinzufügen
      </button>
    </li>,
  )
  if (bandAfter === cellCount - 1 && band !== null) {
    cells.push(band.node)
  }
  if (addPanel !== null) {
    cells.push(addPanel.node)
  }

  return (
    <section data-draft-position={event.position} className="flex scroll-mt-40 flex-col gap-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-base">{heading}</h3>
        <span className="text-sm text-text">{`(${formatDraftPhotoCount(albumCount)})`}</span>
      </div>
      {motifText !== null && <p className="text-sm text-text">{motifText}</p>}
      {albumCount === 0 && <p className="text-sm text-text">{DRAFT_EMPTY_EVENT_TEXT}</p>}
      <ul ref={gridRef} className={PHOTO_CARD_GRID_CLASS}>
        {cells}
      </ul>
      {struckPhotos.length > 0 && (
        <div className="flex flex-col gap-2">
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-focus-key={`struck-toggle-${event.id}`}
              aria-expanded={struckExpanded}
              aria-controls={struckPanelId}
              onClick={() => setStruckExpanded((previous) => !previous)}
            >
              {`${struckPhotos.length} gestrichen – ${struckExpanded ? 'ausblenden' : 'anzeigen'}`}
            </Button>
          </div>
          {struckError !== null && <Alert>{struckError}</Alert>}
          {struckExpanded && (
            <ul id={struckPanelId} className={PHOTO_CARD_GRID_CLASS}>
              {struckPhotos.map((photo) => renderStruckTile(photo))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
