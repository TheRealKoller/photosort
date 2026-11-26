import type { RefObject } from 'react'

import type { ClassificationReviewCaseOut, ClassificationVerdict } from '../api/types'
import { photoPositionLabel, REVIEW_DETAIL_TEXTS } from '../utils/classificationReviewLabels'
import type { MotifSet } from '../utils/motifLabels'
import { ClassificationReviewCase } from './ClassificationReviewCase'
import { PhotoImage } from './PhotoImage'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

/** Die Fallansicht EINES Fotos: Ueberschrift, Navigation, Foto und seine Faelle. */
export function ReviewCaseView({
  position,
  photoCount,
  photoCases,
  photoId,
  previousPosition,
  nextPosition,
  nextOpenPosition,
  headingRef,
  onGoToPosition,
  motifs,
  markedCaseId,
  judgeable,
  saving,
  onMark,
  onJudge,
  saveError,
}: {
  position: number
  photoCount: number
  photoCases: readonly ClassificationReviewCaseOut[]
  photoId: number
  previousPosition: number | undefined
  nextPosition: number | undefined
  nextOpenPosition: number | undefined
  headingRef: RefObject<HTMLHeadingElement | null>
  onGoToPosition: (target: number | undefined, focusHeading: boolean) => void
  motifs: MotifSet
  markedCaseId: number | undefined
  judgeable: boolean
  saving: boolean
  onMark: (reviewCase: ClassificationReviewCaseOut) => void
  onJudge: (reviewCase: ClassificationReviewCaseOut, verdict: ClassificationVerdict) => void
  saveError: boolean
}) {
  return (
    <section aria-labelledby="review-photo-title" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="flex min-w-0 flex-col gap-3">
        <h2 id="review-photo-title" ref={headingRef} tabIndex={-1} className="text-lg">
          {photoPositionLabel(position, photoCount)}
        </h2>
        <nav aria-label={photoPositionLabel(position, photoCount)} className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={previousPosition === undefined}
            onClick={() => onGoToPosition(previousPosition, false)}
          >
            {REVIEW_DETAIL_TEXTS.previousPhoto}
          </Button>
          <Button
            variant="secondary"
            disabled={nextOpenPosition === undefined}
            onClick={() => onGoToPosition(nextOpenPosition, false)}
          >
            {REVIEW_DETAIL_TEXTS.nextOpenPhoto}
          </Button>
          <Button
            variant="secondary"
            disabled={nextPosition === undefined}
            onClick={() => onGoToPosition(nextPosition, false)}
          >
            {REVIEW_DETAIL_TEXTS.nextPhoto}
          </Button>
        </nav>
        {/* Bewusst KEIN Link: die Fallansicht beurteilt Verfahren, nicht das Foto. */}
        <PhotoImage
          key={photoId}
          photoId={photoId}
          variant="display"
          alt={photoPositionLabel(position, photoCount)}
          className="w-full rounded-md object-contain"
        />
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        {saveError && <Alert>{REVIEW_DETAIL_TEXTS.saveError}</Alert>}
        <ul aria-label={REVIEW_DETAIL_TEXTS.casesOfPhoto} className="flex flex-col gap-3">
          {photoCases.map((reviewCase) => (
            <ClassificationReviewCase
              key={reviewCase.id}
              reviewCase={reviewCase}
              motifs={motifs}
              marked={reviewCase.id === markedCaseId}
              judgeable={judgeable}
              saving={saving}
              onMark={() => onMark(reviewCase)}
              onJudge={(verdict) => onJudge(reviewCase, verdict)}
            />
          ))}
        </ul>
      </div>
    </section>
  )
}
