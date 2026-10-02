import type { Ref } from 'react'

import type { MotifSetOut, PhotoOut, RatingStatus } from '../api/types'
import { albumState, isTakenWithoutProposal } from '../utils/albumDraft'
import { qualityLevel } from '../utils/qualityLevel'
import { AlbumStateBadge } from './AlbumStateBadge'
import { CriterionDetailsPopover } from './CriterionDetailsPopover'
import { MotifAssessmentMarker } from './MotifAssessmentMarker'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

/**
 * Die Kennzeichnung von „aufgenommen, vom aktuellen Vorschlag nicht getragen".
 *
 * EINE Zeichenkette für BEIDE Datenformen (`ranking: null` und `ranking.proposed === false`) -
 * dieselbe Lage sieht nicht je nach Datenform verschieden aus.
 */
export const NOT_PROPOSED_BADGE_TEXT = 'nicht vorgeschlagen'

export interface CurationPhotoTileProps {
  photo: PhotoOut
  /** Das geladene Motivset - reine Durchreichung an das Info-Popover. */
  motifSet: MotifSetOut | undefined
  motifSetLoading: boolean
  motifSetError: string | undefined
  onMotifSetRetry: () => void
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
 * EINE Kachel des Album-Entwurfs: im Album („Vorschlag" oder „Aufgenommen") oder in der
 * Gestrichen-Zeile („Gestrichen").
 *
 * DIE ENTSCHEIDUNGSFLÄCHE NENNT DIE HANDLUNG, nie den Zustand, und trägt kein `aria-pressed`: „Streichen"
 * bzw. „Wieder aufnehmen", zugänglicher Name mit Dateinamen. Ein Druck handelt sofort, ohne
 * Bestätigung; während der Anfrage ist die Fläche `busy` und nimmt keinen zweiten Druck an (der
 * Unique-Constraint der Bewertungszeile). Nicht `destructive`: das kollidierte mit dem Kennzeichen
 * „Gestrichen".
 *
 * Fokusziele trägt die Seite über `data-focus-key` (numerische Foto-Id, nie ein Name - S11).
 */
export function CurationPhotoTile({
  photo,
  motifSet,
  motifSetLoading,
  motifSetError,
  onMotifSetRetry,
  ownStatus,
  deciding,
  onDecide,
  alternatives,
  error,
  onOpenLarge,
  largeTriggerRef,
}: CurationPhotoTileProps) {
  // `?? null` fuer den FEHLENDEN Wert, nie fuer die Zahl selbst: `0` ist ein gueltiger
  // Qualitaetswert, und ein `||` verloere ihn lautlos.
  const level = qualityLevel(photo.ranking?.rank_score ?? null)
  const reason = photo.album_suitability?.reason ?? null
  const struck = ownStatus === 'rejected'
  const takenWithoutProposal = isTakenWithoutProposal(photo, ownStatus)
  const actionLabel = struck ? 'Wieder aufnehmen' : 'Streichen'

  return (
    <PhotoCard
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
      // Die Durchstreichung des Dateinamens ohne das Raster-Kennzeichen „Verworfen": das Wort der
      // Kachel ist „Gestrichen" aus der Begriffsquelle, unten im Kartenkörper.
      setAside={struck}
      anchored={alternatives?.expanded === true}
      topLeft={photo.motif_assessment === null ? <MotifAssessmentMarker /> : undefined}
      topRight={
        <CriterionDetailsPopover
          criterionScores={photo.criterion_scores}
          ranking={photo.ranking ?? null}
          suggestion={photo.suggestion}
          fineLabels={photo.fine_labels}
          motifSet={motifSet}
          motifSetLoading={motifSetLoading}
          motifSetError={motifSetError}
          onMotifSetRetry={onMotifSetRetry}
          assessment={photo.motif_assessment ?? null}
          motifs={photo.motifs}
          albumSuitability={photo.album_suitability ?? null}
        />
      }
      footer={
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-1">
            <AlbumStateBadge state={albumState(ownStatus)} />
            {takenWithoutProposal && <Badge tone="neutral">{NOT_PROPOSED_BADGE_TEXT}</Badge>}
          </div>
          <QualityMeter level={level} className="text-xs" />
          {/* Die Begruendung des Modells: visuell gekuerzt, im DOM vollstaendig. Reiner
              React-Textknoten - freier Modelltext, nie als HTML. */}
          {reason !== null && (
            <p data-album-suitability-reason="" className="line-clamp-2 text-xs text-text">
              {reason}
            </p>
          )}
          {error !== null && <Alert>{error}</Alert>}
          <div className="flex flex-col gap-4">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-11 sm:h-8"
              data-focus-key={`${struck ? 'readd' : 'decide'}-${photo.id}`}
              busy={deciding}
              aria-label={`${actionLabel}: ${photo.relative_path}`}
              onClick={onDecide}
            >
              {actionLabel}
            </Button>
            {!struck && alternatives !== undefined && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-11 sm:h-8"
                data-focus-key={`alternatives-${photo.id}`}
                aria-label={`Alternativen: ${photo.relative_path}`}
                aria-expanded={alternatives.expanded}
                aria-controls={alternatives.controls}
                onClick={alternatives.onToggle}
              >
                Alternativen
              </Button>
            )}
          </div>
        </div>
      }
    />
  )
}
