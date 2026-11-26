import type { ClassificationReviewDetailOut } from '../api/types'
import {
  REVIEW_DETAIL_TEXTS,
  SIDE_LABELS,
  SIDE_MARKS,
  sideCostText,
  sideOriginText,
} from '../utils/classificationReviewLabels'
import { EyeAttribution } from './EyeAttribution'

const SIDE_LETTERS = ['a', 'b'] as const

/**
 * Beide Herkuenfte als zwei Bloecke nebeneinander. Die Zeile bricht um statt abzuschneiden - zwei
 * Fassungen desselben Modells unterscheiden sich oft erst am Ende. Die Marke ist nur der
 * Buchstabe; den zugaenglichen Namen ("Seite A") traegt der versteckte Text daneben.
 */
export function ReviewOrigins({ review }: { review: ClassificationReviewDetailOut }) {
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
