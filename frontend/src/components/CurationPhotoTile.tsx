import type { Ref } from 'react'

import type { PhotoOut, RatingStatus } from '../api/types'
import { albumState, isTakenWithoutProposal } from '../utils/albumDraft'
import { iconOnly } from '../utils/curationLayout'
import { AlbumStateBadge } from './AlbumStateBadge'
import { CurationDetails } from './CurationDetails'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { TileAction } from './TileAction'

export interface CurationPhotoTileProps {
  photo: PhotoOut
  /** Gerechnete Kachelbreite und Bildhoehe (`useJustifiedRows`). */
  width: number
  imageHeight: number
  /** Die EIGENE Bewertung (`utils/ownRating.ts::ownRatingStatus`), nie eine zweite Ableitung aus
   * `photo.ratings[]` (S6/S10). `rejected` macht die Kachel zur gestrichenen Kachel. */
  ownStatus: RatingStatus | null
  /** true, solange ein Handgriff an DIESEM Foto läuft. */
  deciding: boolean
  /** „Streichen" an der Albumkachel, „Wieder aufnehmen" an der gestrichenen. */
  onDecide: () => void
  /** Der Aufklapper des Alternativen-Bands - nur an der Albumkachel. */
  alternatives?: { expanded: boolean; controls: string; onToggle: () => void }
  /** Grund eines gescheiterten Handgriffs an diesem Foto, aus der Serverantwort. */
  error: string | null
  onOpenLarge: (photoId: number) => void
  largeTriggerRef: Ref<HTMLButtonElement>
}

/**
 * EINE Kachel des Album-Entwurfs: im Album („Vorschlag" oder „Aufgenommen") mit „Streichen" und
 * „Alternativen", oder in der Gestrichen-Zeile („Gestrichen") mit „Wieder aufnehmen".
 *
 * DIE KNÖPFE NENNEN DIE HANDLUNG, nie den Zustand, und tragen kein `aria-pressed`. Ein Druck
 * handelt sofort, ohne Bestätigung; während der Anfrage ist die Fläche `busy` und nimmt keinen
 * zweiten Druck an (der Unique-Constraint der Bewertungszeile).
 *
 * Fokusziele trägt die Seite über `data-focus-key` (numerische Foto-Id, nie ein Name - S11).
 */
export function CurationPhotoTile({
  photo,
  width,
  imageHeight,
  ownStatus,
  deciding,
  onDecide,
  alternatives,
  error,
  onOpenLarge,
  largeTriggerRef,
}: CurationPhotoTileProps) {
  const struck = ownStatus === 'rejected'
  const takenWithoutProposal = isTakenWithoutProposal(photo, ownStatus)
  const symbolsOnly = iconOnly(width, struck ? 'struck' : 'draft')

  return (
    <PhotoCard
      width={width}
      imageHeight={imageHeight}
      relativePath={photo.relative_path}
      onImageActivate={() => onOpenLarge(photo.id)}
      imageTriggerLabel={`Großansicht: ${photo.relative_path}`}
      imageTriggerRef={largeTriggerRef}
      image={
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt={photo.relative_path}
          className="size-full object-contain"
        />
      }
      setAside={struck}
      anchored={alternatives?.expanded === true}
      stateMark={
        <AlbumStateBadge state={albumState(ownStatus)} notProposed={takenWithoutProposal} />
      }
      details={<CurationDetails photo={photo} notProposed={takenWithoutProposal} />}
      actions={
        struck ? (
          <TileAction
            icon="book"
            label="Wieder aufnehmen"
            accessibleName={`Wieder aufnehmen: ${photo.relative_path}`}
            iconOnly={symbolsOnly}
            tileWidth={width}
            align="start"
            data-focus-key={`readd-${photo.id}`}
            busy={deciding}
            onClick={onDecide}
          />
        ) : (
          <>
            <TileAction
              icon="x-circle"
              label="Streichen"
              accessibleName={`Streichen: ${photo.relative_path}`}
              iconOnly={symbolsOnly}
              tileWidth={width}
              align="start"
              data-focus-key={`decide-${photo.id}`}
              busy={deciding}
              onClick={onDecide}
            />
            {alternatives !== undefined && (
              <TileAction
                icon="repeat"
                label="Alternativen"
                accessibleName={`Alternativen: ${photo.relative_path}`}
                iconOnly={symbolsOnly}
                tileWidth={width}
                align="end"
                data-focus-key={`alternatives-${photo.id}`}
                aria-expanded={alternatives.expanded}
                aria-controls={alternatives.controls}
                onClick={alternatives.onToggle}
              />
            )}
          </>
        )
      }
      error={error}
    />
  )
}
