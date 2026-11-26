import type { ClassificationReviewDetailOut } from '../api/types'
import { REVIEW_DETAIL_TEXTS } from '../utils/classificationReviewLabels'
import { CANCEL_TEXTS } from '../utils/operationTexts'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

/** Der Export der Pruefung samt Sperrgrund und Abbruch-Fehler. */
export function ReviewExportSection({
  status,
  exportPending,
  exportError,
  onExport,
  cancelError,
  onRetryCancel,
}: {
  status: ClassificationReviewDetailOut['status']
  exportPending: boolean
  exportError: boolean
  onExport: () => void
  cancelError: boolean
  onRetryCancel: () => void
}) {
  return (
    <section aria-labelledby="review-export-title" className="flex flex-col gap-2">
      <h2 id="review-export-title" className="text-lg">
        {REVIEW_DETAIL_TEXTS.exportTitle}
      </h2>
      <div>
        <Button
          disabled={status !== 'success'}
          busy={exportPending}
          aria-describedby="review-export-contents"
          onClick={onExport}
        >
          {REVIEW_DETAIL_TEXTS.exportButton}
        </Button>
      </div>
      {cancelError && (
        <Alert onRetry={onRetryCancel} retryLabel={CANCEL_TEXTS.retry}>
          {CANCEL_TEXTS.failed}
        </Alert>
      )}
      {status !== 'success' && (
        <p className="text-sm text-text">
          {status === 'running' || status === 'queued'
            ? REVIEW_DETAIL_TEXTS.exportBlockedRunning
            : status === 'cancelled'
              ? REVIEW_DETAIL_TEXTS.exportBlockedCancelled
              : REVIEW_DETAIL_TEXTS.exportBlockedFailed}
        </p>
      )}
      <p id="review-export-contents" className="text-sm text-text">
        {REVIEW_DETAIL_TEXTS.exportContents}
      </p>
      {exportError && <Alert>{REVIEW_DETAIL_TEXTS.exportError}</Alert>}
    </section>
  )
}
