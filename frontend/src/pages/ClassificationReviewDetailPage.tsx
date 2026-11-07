import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type {
  ClassificationReviewCaseOut,
  ClassificationReviewDetailOut,
  ClassificationVerdict,
} from '../api/types'
import { ClassificationReviewCase } from '../components/ClassificationReviewCase'
import { ClassificationReviewOverview } from '../components/ClassificationReviewOverview'
import { EyeAttribution } from '../components/EyeAttribution'
import { PhotoImage } from '../components/PhotoImage'
import { StatusTag } from '../components/StatusTag'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import {
  useClassificationReviewCasesQuery,
  useClassificationReviewQuery,
  useExportClassificationReviewMutation,
  useSetClassificationReviewVerdictMutation,
} from '../hooks/useClassificationReviews'
import { useMotifsQuery } from '../hooks/useMotifs'
import {
  CLASSIFICATION_REVIEW_TITLE,
  NO_DEVIATION_TEXT,
  noPhotosComparedText,
  photoPositionLabel,
  REVIEW_DETAIL_TEXTS,
  reviewListStand,
  reviewPhaseText,
  reviewProgressText,
  SIDE_LABELS,
  SIDE_MARKS,
  sideCostText,
  sideOriginText,
  unclassifiableText,
  VERDICT_KEYS,
  VERDICT_ORDER,
} from '../utils/classificationReviewLabels'
import { isTextInputFocused } from '../utils/textInputFocus'

const SIDE_LETTERS = ['a', 'b'] as const
const VALID_POSITION = /^\d+$/

/** Taste (klein geschrieben) → Urteil. Ziffern stehen bewusst nicht darin: 1/2/3 bleiben inert. */
const VERDICT_BY_KEY = new Map<string, ClassificationVerdict>(
  VERDICT_ORDER.map((verdict) => [VERDICT_KEYS[verdict].toLowerCase(), verdict]),
)

/**
 * Das Foto, auf das ein fehlender oder ungueltiger `?foto=` zeigt: das erste mit offenem Fall,
 * sonst das erste mit ueberhaupt einem Fall.
 */
function firstOpenPosition(cases: readonly ClassificationReviewCaseOut[]): number | null {
  const open = cases.find((reviewCase) => reviewCase.verdict === null)
  return (open ?? cases.at(0))?.photo_position ?? null
}

/**
 * Seite 2 der Klassifizierungspruefung (Spec 0616, UI/UX): Kopf mit beiden Herkuenften, die
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
  // Waehrend des Laufs gibt es noch keine Faelle; eine fehlgeschlagene Pruefung zeigt die bis
  // dahin geschriebenen (gesperrt).
  const casesQuery = useClassificationReviewCasesQuery(
    projectId,
    reviewId,
    review !== undefined && review.status !== 'running',
  )
  const motifsQuery = useMotifsQuery()
  const verdictMutation = useSetClassificationReviewVerdictMutation(projectId, reviewId)
  const exportMutation = useExportClassificationReviewMutation(projectId, reviewId)

  const motifs = motifsQuery.data?.items ?? []
  const cases = casesQuery.data?.cases ?? []
  const photoCount = review?.photo_count ?? 0
  const judgeable = review?.status === 'success'

  const fotoParam = searchParams.get('foto')
  const requestedPosition =
    fotoParam !== null && VALID_POSITION.test(fotoParam) ? Number(fotoParam) : null
  const position =
    requestedPosition !== null && requestedPosition >= 1 && requestedPosition <= photoCount
      ? requestedPosition
      : null
  const fallbackPosition = firstOpenPosition(cases)

  // Ein ungueltiger oder fehlender Wert wird erst ersetzt, wenn die Faelle da sind - vorher ist
  // das erste offene Foto unbekannt.
  useEffect(() => {
    if (position === null && casesQuery.isSuccess && fallbackPosition !== null) {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.set('foto', String(fallbackPosition))
          return next
        },
        { replace: true },
      )
    }
  }, [position, casesQuery.isSuccess, fallbackPosition, setSearchParams])

  const positions = [...new Set(cases.map((reviewCase) => reviewCase.photo_position))]
  const photoCases = cases.filter((reviewCase) => reviewCase.photo_position === position)
  const previousPosition = positions.findLast(
    (candidate) => position !== null && candidate < position,
  )
  const nextPosition = positions.find((candidate) => position !== null && candidate > position)
  const openPositions = [
    ...new Set(
      cases
        .filter(
          (reviewCase) => reviewCase.verdict === null && reviewCase.photo_position !== position,
        )
        .map((reviewCase) => reviewCase.photo_position),
    ),
  ]
  const nextOpenPosition =
    openPositions.find((candidate) => position !== null && candidate > position) ??
    openPositions.at(0)

  // Die Markierung gilt je Foto: steht sie auf keinem Fall dieses Fotos, faellt sie auf den
  // ersten offenen, sonst auf den ersten Fall zurueck.
  const [markedCaseId, setMarkedCaseId] = useState<number | null>(null)
  const markedCase =
    photoCases.find((reviewCase) => reviewCase.id === markedCaseId) ??
    photoCases.find((reviewCase) => reviewCase.verdict === null) ??
    photoCases.at(0)

  const photoHeadingRef = useRef<HTMLHeadingElement>(null)
  // Synchron statt `isPending`: zwei Tastendruecke im selben Takt sehen beide noch den alten
  // Render-Stand, und der zweite erzeugte sonst einen zweiten Request.
  const savingRef = useRef(false)

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
        },
      },
    )
  }

  // Ref-Indirektion wie in PhotoDetailPage: EIN Listener, der bei jedem Druck die aktuellen
  // Handler liest.
  const handlersRef = useRef({ judge, goToPosition, markedCase, previousPosition, nextPosition })
  handlersRef.current = { judge, goToPosition, markedCase, previousPosition, nextPosition }

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent): void {
      // Strg/Meta/Alt sind Browser- und Systemkuerzel: Strg+A markiert alles, Strg+F sucht - beides
      // darf kein Urteil schreiben.
      if (isTextInputFocused() || event.ctrlKey || event.metaKey || event.altKey) {
        return
      }
      const handlers = handlersRef.current
      if (event.key === 'ArrowLeft') {
        handlers.goToPosition(handlers.previousPosition, true)
        return
      }
      if (event.key === 'ArrowRight') {
        handlers.goToPosition(handlers.nextPosition, true)
        return
      }
      const verdict = VERDICT_BY_KEY.get(event.key.toLowerCase())
      if (verdict !== undefined && handlers.markedCase !== undefined) {
        event.preventDefault()
        handlers.judge(handlers.markedCase, verdict)
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])

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
        <ReviewStand review={reviewData} caseTotal={caseTotal} />
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
        <section
          aria-labelledby="review-photo-title"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        >
          <div className="flex min-w-0 flex-col gap-3">
            <h2 id="review-photo-title" ref={photoHeadingRef} tabIndex={-1} className="text-lg">
              {photoPositionLabel(position, photoCount)}
            </h2>
            <nav
              aria-label={photoPositionLabel(position, photoCount)}
              className="flex flex-wrap gap-2"
            >
              <Button
                variant="secondary"
                disabled={previousPosition === undefined}
                onClick={() => goToPosition(previousPosition, false)}
              >
                {REVIEW_DETAIL_TEXTS.previousPhoto}
              </Button>
              <Button
                variant="secondary"
                disabled={nextOpenPosition === undefined}
                onClick={() => goToPosition(nextOpenPosition, false)}
              >
                {REVIEW_DETAIL_TEXTS.nextOpenPhoto}
              </Button>
              <Button
                variant="secondary"
                disabled={nextPosition === undefined}
                onClick={() => goToPosition(nextPosition, false)}
              >
                {REVIEW_DETAIL_TEXTS.nextPhoto}
              </Button>
            </nav>
            {/* Bewusst KEIN Link: die Fallansicht beurteilt Verfahren, nicht das Foto. */}
            <PhotoImage
              key={photoCases[0].photo_id}
              photoId={photoCases[0].photo_id}
              variant="display"
              alt={photoPositionLabel(position, photoCount)}
              className="w-full rounded-md object-contain"
            />
          </div>
          <div className="flex min-w-0 flex-col gap-3">
            {verdictMutation.isError && <Alert>{REVIEW_DETAIL_TEXTS.saveError}</Alert>}
            <ul aria-label={REVIEW_DETAIL_TEXTS.casesOfPhoto} className="flex flex-col gap-3">
              {photoCases.map((reviewCase) => (
                <ClassificationReviewCase
                  key={reviewCase.id}
                  reviewCase={reviewCase}
                  motifs={motifs}
                  marked={reviewCase.id === markedCase?.id}
                  judgeable={judgeable}
                  onMark={() => setMarkedCaseId(reviewCase.id)}
                  onJudge={(verdict) => judge(reviewCase, verdict)}
                />
              ))}
            </ul>
          </div>
        </section>
      )}

      {reviewData.status === 'success' && <ClassificationReviewOverview review={reviewData} />}

      <section aria-labelledby="review-export-title" className="flex flex-col gap-2">
        <h2 id="review-export-title" className="text-lg">
          {REVIEW_DETAIL_TEXTS.exportTitle}
        </h2>
        <div>
          <Button
            disabled={reviewData.status !== 'success'}
            busy={exportMutation.isPending}
            aria-describedby="review-export-contents"
            onClick={() => exportMutation.mutate()}
          >
            {REVIEW_DETAIL_TEXTS.exportButton}
          </Button>
        </div>
        {reviewData.status !== 'success' && (
          <p className="text-sm text-text">
            {reviewData.status === 'running'
              ? REVIEW_DETAIL_TEXTS.exportBlockedRunning
              : REVIEW_DETAIL_TEXTS.exportBlockedFailed}
          </p>
        )}
        <p id="review-export-contents" className="text-sm text-text">
          {REVIEW_DETAIL_TEXTS.exportContents}
        </p>
        {exportMutation.isError && <Alert>{REVIEW_DETAIL_TEXTS.exportError}</Alert>}
      </section>
    </div>
  )
}

/**
 * Beide Herkuenfte als zwei Bloecke nebeneinander. Die Zeile bricht um statt abzuschneiden - zwei
 * Fassungen desselben Modells unterscheiden sich oft erst am Ende. Die Marke ist nur der
 * Buchstabe; den zugaenglichen Namen ("Seite A") traegt der versteckte Text daneben.
 */
function ReviewOrigins({ review }: { review: ClassificationReviewDetailOut }) {
  return (
    <ul
      aria-label={REVIEW_DETAIL_TEXTS.originRegion}
      className="grid grid-cols-1 gap-2 sm:grid-cols-2"
    >
      {SIDE_LETTERS.map((letter) => (
        <li
          key={letter}
          className="flex min-w-0 flex-col gap-1 rounded-md border border-border bg-surface p-3"
        >
          <span className="flex items-start gap-2 text-sm text-text">
            <span
              aria-hidden="true"
              className="rounded-xs bg-overlay px-1 font-mono text-xs text-text-h"
            >
              {SIDE_MARKS[letter]}
            </span>
            <span className="sr-only">{SIDE_LABELS[letter]}:</span>
            <span className="break-words">{sideOriginText(review.sides[letter])}</span>
          </span>
          <span className="break-words text-xs text-text-muted">
            {sideCostText(review.sides[letter])}
          </span>
          {review.sides[letter].kind === 'eye' && <EyeAttribution />}
        </li>
      ))}
    </ul>
  )
}

/** Der Stand der Pruefung als `aria-live`-Region - Fortschritt, Abschluss und Fotofehler. */
function ReviewStand({
  review,
  caseTotal,
}: {
  review: ClassificationReviewDetailOut
  caseTotal: number
}) {
  const open = review.verdict_counts.open
  // "stimmen auf allen Fotos ueberein" ist eine Aussage UEBER verglichene Fotos. Ohne ein einziges
  // verglichenes Foto ist sie falsch, auch wenn kein Fall vorgelegt wurde (Edge Case 4) - dann
  // nennt der Kopf stattdessen die Zahl der fehlgeschlagenen Fotos (AK 9).
  const compared = Object.values(review.counts_by_purpose).reduce(
    (sum, counts) => sum + counts.compared,
    0,
  )
  const nothingCompared = review.status === 'success' && caseTotal === 0 && compared === 0
  return (
    <div aria-live="polite" className="flex flex-col gap-1 text-sm text-text">
      {review.status === 'running' && (
        <p className="flex flex-wrap items-center gap-2">
          <StatusTag
            status="running"
            label={reviewListStand({ status: 'running', case_count: 0, case_open: 0 }).label}
          />
          <span>{reviewPhaseText(review.phase, review.photos_processed, review.photo_count)}</span>
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
