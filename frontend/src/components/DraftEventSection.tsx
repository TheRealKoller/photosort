import { useId, useState } from 'react'
import type { ReactNode } from 'react'

import type { EventOut, PhotoOut } from '../api/types'
import { useJustifiedRows } from '../hooks/useJustifiedRows'
import { formatDraftPhotoCount } from '../utils/albumDraft'
import type { JustifiedTile } from '../utils/justifiedRows'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Icon } from './ui/icon'

/** Der Text eines Events, in dem gerade kein Bild im Album steht. */
export const DRAFT_EMPTY_EVENT_TEXT = 'Kein Bild im Entwurf'

/** Das Planungsverhaeltnis der „Foto hinzufügen"-Zelle: ein Hochformat 2:3. */
const ADD_CELL_RATIO = 2 / 3

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
  /** Eine Kachel in ihrer gerechneten Breite und Bildhoehe. */
  renderAlbumTile: (photo: PhotoOut, tile: JustifiedTile) => ReactNode
  renderStruckTile: (photo: PhotoOut, tile: JustifiedTile) => ReactNode
  /** Das offene Band dieses Events, verankert am gewählten Foto. */
  band: { photoId: number; node: ReactNode } | null
  /** Das offene Hinzufügen-Panel dieses Events. */
  addPanel: { id: string; node: ReactNode } | null
  onToggleAdd: () => void
  /** Grund eines gescheiterten „Wieder aufnehmen", an der Gestrichen-Liste. */
  struckError: string | null
}

/** Die gerechnete Kachel einer Zelle - vor dem ersten Rendern der Reihen eine leere. */
function tileOf(tiles: readonly JustifiedTile[], index: number): JustifiedTile {
  return tiles[index] ?? { index, width: 0, height: 0 }
}

/**
 * EIN Eventabschnitt des Album-Entwurfs: Überschrift mit Bildzahl, Motivzeile, die Fotos im Album
 * als justierte Reihen mit dem Hinzufügen-Feld als letzter Zelle, und die Gestrichen-Zeile.
 *
 * Er steht auch ohne ein einziges Foto im Album („Kein Bild im Entwurf"). Der Aufklappzustand der
 * Gestrichen-Zeile gilt je Event und wird nicht gespeichert. Band und Panel stehen als volle Zeile
 * direkt nach der GERECHNETEN Reihe ihres Auslösers - nie nach einer festen Spaltenzahl.
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
  const album = useJustifiedRows<HTMLUListElement>([
    ...albumPhotos.map((photo) => photo.aspect_ratio ?? null),
    ADD_CELL_RATIO,
  ])
  const struck = useJustifiedRows<HTMLUListElement>(
    struckPhotos.map((photo) => photo.aspect_ratio ?? null),
  )
  const albumTiles = album.rows.flatMap((row) => row.tiles)
  const struckTiles = struck.rows.flatMap((row) => row.tiles)

  // Zellen: die Albumkacheln, dann das Hinzufügen-Feld. Das Band schliesst die Reihe seiner Kachel.
  const addIndex = albumPhotos.length
  const bandIndex = band === null ? -1 : albumPhotos.findIndex((photo) => photo.id === band.photoId)
  const bandRow = album.rows.find((row) => row.tiles.some((tile) => tile.index === bandIndex))
  const bandAfter = bandRow?.tiles.at(-1)?.index ?? -1
  const addTile = tileOf(albumTiles, addIndex)

  const cells: ReactNode[] = []
  albumPhotos.forEach((photo, index) => {
    cells.push(renderAlbumTile(photo, tileOf(albumTiles, index)))
    if (index === bandAfter && band !== null) {
      cells.push(band.node)
    }
  })
  cells.push(
    <li key="add" className="flex" style={{ width: addTile.width }}>
      <button
        type="button"
        data-focus-key={`add-trigger-${event.id}`}
        aria-label={`Foto hinzufügen: ${heading}`}
        aria-expanded={addPanel !== null}
        aria-controls={addPanel?.id}
        onClick={onToggleAdd}
        // Mindestens so hoch wie die Bildflaeche; in einer Reihe mit Kacheln dehnt die Liste die
        // Zelle auf Bild plus Knopfzeile.
        style={{ minHeight: addTile.height }}
        className="flex w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed border-separator p-3 text-sm text-text"
      >
        <Icon name="plus" size={20} />
        Foto hinzufügen
      </button>
    </li>,
  )
  if (bandAfter === addIndex && band !== null) {
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
      <ul ref={album.ref} className="flex flex-wrap gap-3">
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
            <ul id={struckPanelId} ref={struck.ref} className="flex flex-wrap gap-3">
              {struckPhotos.map((photo, index) =>
                renderStruckTile(photo, tileOf(struckTiles, index)),
              )}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
