import { useId, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { ClassificationReviewListItemOut } from '../api/types'
import { ClassificationReviewCreatePanel } from '../components/ClassificationReviewCreatePanel'
import { StatusTag } from '../components/StatusTag'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { useClassificationReviewsQuery } from '../hooks/useClassificationReviews'
import {
  CLASSIFICATION_REVIEW_TEXTS,
  CLASSIFICATION_REVIEW_TITLE,
  NO_DEVIATION_TEXT,
  reviewListStand,
  SIDE_MARKS,
  sideOriginText,
} from '../utils/classificationReviewLabels'
import { formatDateTime } from '../utils/formatStats'
import { classificationReviewPath } from '../utils/projectRoutes'

const SIDE_LETTERS = ['a', 'b'] as const

/**
 * EINE Zeile der Liste. Die GANZE Zeile ist der Link (`min-h-11`, mindestens 44 px), nicht nur
 * ihre Ueberschrift: auf dem Telefon waere ein 16-px-Ziel am Datum nicht zu treffen.
 */
function ReviewRow({
  projectId,
  review,
}: {
  projectId: number
  review: ClassificationReviewListItemOut
}) {
  const stand = reviewListStand(review)
  return (
    <li>
      <Link
        to={classificationReviewPath(projectId, review.id)}
        className={
          'flex min-h-11 w-full flex-col gap-2 rounded-sm border border-border bg-surface px-3 ' +
          'py-2 hover:bg-overlay active:bg-overlay sm:flex-row sm:items-start sm:justify-between'
        }
      >
        <span className="flex min-w-0 flex-col gap-1">
          <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-sm font-medium text-text-h">
              {formatDateTime(review.created_at)}
            </span>
            <span className="text-sm text-text">angelegt von {review.created_by.username}</span>
          </span>
          {/* Beide Herkuenfte mit Buchstabenmarke. Die Zeile bricht um statt abzuschneiden - zwei
              Fassungen desselben Modells unterscheiden sich oft erst am Ende. */}
          {SIDE_LETTERS.map((letter) => (
            <span key={letter} className="flex items-start gap-2 text-xs text-text">
              <span className="rounded-xs bg-overlay px-1 font-mono text-xs text-text-h">
                {SIDE_MARKS[letter]}
              </span>
              <span className="break-words">{sideOriginText(review.sides[letter])}</span>
            </span>
          ))}
        </span>
        <span className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
          <StatusTag status={stand.tone} label={stand.label} />
          {review.status === 'success' && review.case_count === 0 && (
            <span className="text-xs text-text-muted">{NO_DEVIATION_TEXT}</span>
          )}
        </span>
      </Link>
    </li>
  )
}

/**
 * Seite 1 der Klassifizierungspruefung (Spec 0616, UI/UX): Liste der Pruefungen und das
 * Anlegen-Panel.
 *
 * Das Panel steht inline unter dem Kopf, nicht in einem Dialog; der Umschalter traegt
 * `aria-expanded`/`aria-controls`. Bei leerer Liste ist es von Anfang an offen - dann ist Anlegen
 * der einzige sinnvolle naechste Schritt. Die Reihenfolge der Liste kommt vom Server (neueste
 * zuerst) und wird hier nicht neu bestimmt.
 */
export function ClassificationReviewsPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const navigate = useNavigate()
  const panelId = useId()
  const reviewsQuery = useClassificationReviewsQuery(id)
  // `null` heisst "der Nutzer hat noch nicht umgeschaltet"; dann entscheidet der Listenstand.
  const [panelOpen, setPanelOpen] = useState<boolean | null>(null)

  const reviews = reviewsQuery.data ?? []
  const isEmpty = reviewsQuery.isSuccess && reviews.length === 0
  const isPanelOpen = panelOpen ?? isEmpty
  const latest = reviews.at(0)

  const loadErrorDetail =
    reviewsQuery.error instanceof ApiError
      ? reviewsQuery.error.detail
      : 'Fehler beim Laden der Prüfungen.'

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-xl sm:text-2xl">{CLASSIFICATION_REVIEW_TITLE}</h1>
          <p className="text-sm text-text">{CLASSIFICATION_REVIEW_TEXTS.intro}</p>
        </div>
        <Button
          aria-expanded={isPanelOpen}
          aria-controls={panelId}
          onClick={() => setPanelOpen(!isPanelOpen)}
        >
          {CLASSIFICATION_REVIEW_TEXTS.createOpen}
        </Button>
      </header>

      {/* Nur der JUENGSTE Fehlschlag bekommt die Meldung: die Liste kann viele gescheiterte
          Pruefungen enthalten, und ein Stapel gleicher Alerts hilft niemandem. "Erneut anlegen"
          ist die Handlung, nicht "Erneut versuchen" - eine gescheiterte Pruefung wird nie
          automatisch wiederholt. */}
      {latest?.status === 'failed' && (
        <Alert
          onRetry={() => setPanelOpen(true)}
          retryLabel={CLASSIFICATION_REVIEW_TEXTS.retryCreate}
        >
          {CLASSIFICATION_REVIEW_TEXTS.failedLatest}
        </Alert>
      )}

      {isPanelOpen && (
        <ClassificationReviewCreatePanel
          projectId={id}
          id={panelId}
          onCreated={(created) => navigate(classificationReviewPath(id, created.id))}
        />
      )}

      {reviewsQuery.isPending && (
        <p role="status" className="text-sm text-text">
          Prüfungen werden geladen…
        </p>
      )}

      {reviewsQuery.isError && (
        <Alert onRetry={() => void reviewsQuery.refetch()}>{loadErrorDetail}</Alert>
      )}

      {reviewsQuery.isSuccess && reviews.length === 0 && (
        <p role="status" className="text-sm text-text">
          Noch keine Prüfung angelegt.
        </p>
      )}

      {reviews.length > 0 && (
        <ul aria-label="Prüfungen" className="flex flex-col gap-2">
          {reviews.map((review) => (
            <ReviewRow key={review.id} projectId={id} review={review} />
          ))}
        </ul>
      )}
    </div>
  )
}
