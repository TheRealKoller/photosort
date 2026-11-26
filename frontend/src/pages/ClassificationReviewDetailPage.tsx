import { useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { ClassificationReviewCaseOut, ClassificationVerdict } from '../api/types'
import { ClassificationReviewOverview } from '../components/ClassificationReviewOverview'
import { ReviewCaseView } from '../components/ReviewCaseView'
import { ReviewExportSection } from '../components/ReviewExportSection'
import { ReviewOrigins } from '../components/ReviewOrigins'
import { ReviewStand } from '../components/ReviewStand'
import { Alert } from '../components/ui/alert'
import {
  useClassificationReviewCasesQuery,
  useClassificationReviewQuery,
  useExportClassificationReviewMutation,
  useSetClassificationReviewVerdictMutation,
} from '../hooks/useClassificationReviews'
import { useCancelOperation } from '../hooks/useOperations'
import { useMotifsQuery } from '../hooks/useMotifs'
import { useReviewKeys } from '../hooks/useReviewKeys'
import { useReviewPhotoPosition } from '../hooks/useReviewPhotoPosition'
import {
  CLASSIFICATION_REVIEW_TITLE,
  REVIEW_DETAIL_TEXTS,
  VERDICT_ORDER,
} from '../utils/classificationReviewLabels'

/**
 * Seite 2 der Klassifizierungspruefung: Kopf mit beiden Herkuenften, die
 * Fallansicht EINES Fotos, die Uebersicht und der Export.
 *
 * Das Foto der Fallansicht steht in `?foto=<Position>` - die laufende Nummer der Pruefmenge, die
 * auch der Export traegt. Ein ungueltiger Wert (keine reine Ziffernfolge oder ausserhalb
 * 1…`photo_count`) wird ohne Serverrunde per `replace` auf das erste offene Foto gesetzt: ein
 * kaputter Link soll weder einen Fehler noch einen zusaetzlichen Verlaufseintrag hinterlassen.
 */
export function ClassificationReviewDetailPage() {
  const params = useParams()
  const projectId = Number(params.projectId)
  const reviewId = Number(params.reviewId)
  const [searchParams, setSearchParams] = useSearchParams()

  const reviewQuery = useClassificationReviewQuery(projectId, reviewId)
  const review = reviewQuery.data
  // Eine fehlgeschlagene Pruefung zeigt die bis dahin geschriebenen Faelle (gesperrt).
  const casesQuery = useClassificationReviewCasesQuery(
    projectId,
    reviewId,
    review !== undefined && review.status !== 'running' && review.status !== 'queued',
  )
  const motifsQuery = useMotifsQuery()
  const verdictMutation = useSetClassificationReviewVerdictMutation(projectId, reviewId)
  const exportMutation = useExportClassificationReviewMutation(projectId, reviewId)
  const cancelMutation = useCancelOperation(projectId)

  // Der Abbruch adressiert GENAU diese Pruefung.
  function handleCancelReview(): void {
    cancelMutation.mutate({ kind: 'review', runId: reviewId })
  }

  const motifs = motifsQuery.data?.items ?? []
  const cases = casesQuery.data?.cases ?? []
  const photoCount = review?.photo_count ?? 0
  const judgeable = review?.status === 'success'

  const { position, photoCases, previousPosition, nextPosition, nextOpenPosition } =
    useReviewPhotoPosition(searchParams, setSearchParams, cases, photoCount, casesQuery.isSuccess)

  // Die Markierung gilt je Foto: steht sie auf keinem Fall dieses Fotos, faellt sie auf den
  // ersten offenen, sonst auf den ersten Fall zurueck.
  const [markedCaseId, setMarkedCaseId] = useState<number | null>(null)
  const markedCase =
    photoCases.find((reviewCase) => reviewCase.id === markedCaseId) ??
    photoCases.find((reviewCase) => reviewCase.verdict === null) ??
    photoCases.at(0)

  const photoHeadingRef = useRef<HTMLHeadingElement>(null)
  // Synchron statt `isPending`: zwei Tastendruecke im selben Takt sehen beide noch den alten
  // Render-Stand, und der zweite erzeugte sonst einen zweiten Request. Der zusaetzliche
  // Render-Stand sperrt die vier Urteilsflaechen sichtbar, statt den Klick still zu verschlucken.
  const savingRef = useRef(false)
  const [saving, setSaving] = useState(false)

  function goToPosition(target: number | undefined, focusHeading: boolean): void {
    if (target === undefined) {
      return
    }
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('foto', String(target))
      return next
    })
    setMarkedCaseId(null)
    if (focusHeading) {
      photoHeadingRef.current?.focus()
    }
  }

  function judge(reviewCase: ClassificationReviewCaseOut, verdict: ClassificationVerdict): void {
    if (!judgeable || savingRef.current) {
      return
    }
    savingRef.current = true
    setSaving(true)
    setMarkedCaseId(reviewCase.id)
    verdictMutation.mutate(
      { caseId: reviewCase.id, verdict },
      {
        // Weiter zum naechsten offenen Fall DESSELBEN Fotos - nie auf ein anderes Foto.
        onSuccess: () => {
          const index = photoCases.findIndex((candidate) => candidate.id === reviewCase.id)
          const ordered = [...photoCases.slice(index + 1), ...photoCases.slice(0, index)]
          const nextOpen = ordered.find((candidate) => candidate.verdict === null)
          if (nextOpen !== undefined) {
            setMarkedCaseId(nextOpen.id)
          }
        },
        onSettled: () => {
          savingRef.current = false
          setSaving(false)
        },
      },
    )
  }

  useReviewKeys({ judge, goToPosition, markedCase, previousPosition, nextPosition })

  if (reviewQuery.isPending) {
    return (
      <p role="status" className="text-sm text-text">
        {REVIEW_DETAIL_TEXTS.loading}
      </p>
    )
  }

  if (reviewQuery.isError) {
    return (
      <Alert onRetry={() => void reviewQuery.refetch()}>
        {reviewQuery.error instanceof ApiError
          ? reviewQuery.error.detail
          : REVIEW_DETAIL_TEXTS.loadError}
      </Alert>
    )
  }

  const reviewData = reviewQuery.data
  const caseTotal = VERDICT_ORDER.reduce(
    (sum, verdict) => sum + reviewData.verdict_counts[verdict],
    reviewData.verdict_counts.open,
  )

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4">
        <h1 className="text-xl sm:text-2xl">{CLASSIFICATION_REVIEW_TITLE}</h1>
        <ReviewOrigins review={reviewData} />
        <ReviewStand
          review={reviewData}
          caseTotal={caseTotal}
          onCancel={handleCancelReview}
          cancelPending={cancelMutation.isPending}
          cancelFocusToken={cancelMutation.data ?? null}
        />
        {reviewData.status === 'failed' && (
          <Alert>{reviewData.error_message ?? REVIEW_DETAIL_TEXTS.failedFallback}</Alert>
        )}
      </header>

      {casesQuery.isError && (
        <Alert onRetry={() => void casesQuery.refetch()}>
          {REVIEW_DETAIL_TEXTS.casesLoadError}
        </Alert>
      )}

      {position !== null && photoCases.length > 0 && (
        <ReviewCaseView
          position={position}
          photoCount={photoCount}
          photoCases={photoCases}
          photoId={photoCases[0].photo_id}
          previousPosition={previousPosition}
          nextPosition={nextPosition}
          nextOpenPosition={nextOpenPosition}
          headingRef={photoHeadingRef}
          onGoToPosition={goToPosition}
          motifs={motifs}
          markedCaseId={markedCase?.id}
          judgeable={judgeable}
          saving={saving}
          onMark={(reviewCase) => setMarkedCaseId(reviewCase.id)}
          onJudge={judge}
          saveError={verdictMutation.isError}
        />
      )}

      {reviewData.status === 'success' && <ClassificationReviewOverview review={reviewData} />}

      <ReviewExportSection
        status={reviewData.status}
        exportPending={exportMutation.isPending}
        exportError={exportMutation.isError}
        onExport={() => exportMutation.mutate()}
        cancelError={cancelMutation.isError}
        onRetryCancel={handleCancelReview}
      />
    </div>
  )
}
