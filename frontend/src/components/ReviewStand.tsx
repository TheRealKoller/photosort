import type { ClassificationReviewDetailOut } from '../api/types'
import { useCancelRequestFocus } from '../hooks/useCancelRequestFocus'
import {
  NO_DEVIATION_TEXT,
  noPhotosComparedText,
  REVIEW_DETAIL_TEXTS,
  reviewCancelledText,
  reviewListStand,
  reviewPhaseText,
  reviewProgressText,
  unclassifiableText,
} from '../utils/classificationReviewLabels'
import { cancelRequestedText, waitingText } from '../utils/operationTexts'
import { OperationCancelButton } from './OperationCancelButton'
import { StatusTag } from './StatusTag'

/** Der Stand der Pruefung als `aria-live`-Region - Fortschritt, Abschluss und Fotofehler. */
export function ReviewStand({
  review,
  caseTotal,
  onCancel,
  cancelPending,
  cancelFocusToken,
}: {
  review: ClassificationReviewDetailOut
  caseTotal: number
  onCancel: () => void
  cancelPending: boolean
  /** Die Antwort der EIGENEN erfolgreichen Abbruch-Anfrage - nur sie bewegt den Fokus. */
  cancelFocusToken: unknown
}) {
  const open = review.verdict_counts.open
  // "stimmen auf allen Fotos ueberein" ist eine Aussage UEBER verglichene Fotos. Ohne ein einziges
  // verglichenes Foto ist sie falsch, auch wenn kein Fall vorgelegt wurde - dann
  // nennt der Kopf stattdessen die Zahl der fehlgeschlagenen Fotos.
  const compared = Object.values(review.counts_by_purpose).reduce(
    (sum, counts) => sum + counts.compared,
    0,
  )
  const nothingCompared = review.status === 'success' && caseTotal === 0 && compared === 0
  const isCancelRequested = review.cancel_requested_at != null
  const statusRef = useCancelRequestFocus<HTMLDivElement>(cancelFocusToken)
  return (
    <div
      ref={statusRef}
      tabIndex={-1}
      aria-live="polite"
      className="flex flex-col gap-1 text-sm text-text"
    >
      {(review.status === 'running' || review.status === 'queued') && (
        <p className="flex flex-wrap items-center gap-2">
          <StatusTag
            status={review.status}
            label={reviewListStand({ status: review.status, case_count: 0, case_open: 0 }).label}
          />
          <span>
            {review.status === 'queued'
              ? isCancelRequested
                ? cancelRequestedText('review')
                : waitingText('review')
              : isCancelRequested
                ? cancelRequestedText('review')
                : reviewPhaseText(review.phase, review.photos_processed, review.photo_count)}
          </span>
          <OperationCancelButton
            operation="review"
            cancelRequested={isCancelRequested}
            pending={cancelPending}
            onCancel={onCancel}
          />
        </p>
      )}
      {review.status === 'cancelled' && (
        <p className="flex flex-wrap items-center gap-2">
          <StatusTag status="cancelled" label="abgebrochen" />
          <span>
            {reviewCancelledText(review.phase, review.photos_processed, review.photo_count)}
          </span>
        </p>
      )}
      {review.status === 'success' && caseTotal > 0 && <p>{reviewProgressText(open, caseTotal)}</p>}
      {review.status === 'success' && caseTotal > 0 && open === 0 && (
        <p>{REVIEW_DETAIL_TEXTS.allJudged}</p>
      )}
      {review.status === 'success' && caseTotal === 0 && !nothingCompared && (
        <p>{NO_DEVIATION_TEXT}</p>
      )}
      {nothingCompared && <p>{noPhotosComparedText(review.unclassifiable_photo_count)}</p>}
      {review.unclassifiable_photo_count > 0 && !nothingCompared && (
        <p>{unclassifiableText(review.unclassifiable_photo_count)}</p>
      )}
    </div>
  )
}
