import { useId } from 'react'

import type { ClassificationReviewCaseOut, ClassificationVerdict } from '../api/types'
import { Button } from './ui/button'
import { cn } from '../lib/utils'
import {
  caseSideValueText,
  reviewCaseTitle,
  SIDE_LABELS,
  SIDE_MARKS,
  VERDICT_KEYS,
  VERDICT_LABELS,
  VERDICT_ORDER,
  verdictGroupLabel,
  verdictWriterText,
} from '../utils/classificationReviewLabels'
import type { MotifSet } from '../utils/motifLabels'

const SIDE_LETTERS = ['a', 'b'] as const

/*
 * Sichtbar 44 px auch am Schreibtisch: heisser Pfad, ein Fehlgriff schreibt ein falsches Urteil.
 * Das gesetzte Urteil traegt nur den Rand in `--accent` - KEINE Bewertungsfarbe und keine
 * gefuellte Flaeche: ein Urteil ist keine Bewertung des Fotos.
 */
const VERDICT_BUTTON_CLASSES =
  'h-auto min-h-11 w-full justify-between whitespace-normal text-left aria-pressed:border-accent'

interface ClassificationReviewCaseProps {
  reviewCase: ClassificationReviewCaseOut
  motifs: MotifSet
  /** Der markierte Fall nimmt die Tasten A/B/O/F entgegen. */
  marked: boolean
  /** `false`, solange die Pruefung nicht abgeschlossen ist. */
  judgeable: boolean
  onMark: () => void
  onJudge: (verdict: ClassificationVerdict) => void
}

/**
 * EIN Fall der Fallansicht (Spec 0616, UI/UX): Zweck als Ueberschrift, beide Rohwerte mit
 * Seitenmarke, darunter die vier Urteile als Gruppe in fester Reihenfolge.
 *
 * Die Urteile sind Umschaltflaechen mit `aria-pressed` in einer benannten Gruppe statt echter
 * Radio-Eingaben: ein Urteil wird beim Druck sofort geschrieben, und ein Radio, das schon beim
 * Pfeiltasten-Durchlauf schriebe, setzte unbeabsichtigte Urteile.
 */
export function ClassificationReviewCase({
  reviewCase,
  motifs,
  marked,
  judgeable,
  onMark,
  onJudge,
}: ClassificationReviewCaseProps) {
  const titleId = useId()
  const title = reviewCaseTitle(reviewCase.purpose, reviewCase.motif_key, motifs)
  return (
    <li
      aria-labelledby={titleId}
      aria-current={marked ? 'true' : undefined}
      data-testid={`review-case-${reviewCase.id}`}
      onFocusCapture={onMark}
      onClick={onMark}
      className={cn(
        'flex flex-col gap-3 rounded-md border bg-surface p-3',
        marked ? 'border-accent' : 'border-border',
      )}
    >
      <h3 id={titleId} className="text-sm font-semibold text-text-h">
        {title}
      </h3>
      <dl className="flex flex-col gap-1 text-sm">
        {SIDE_LETTERS.map((letter) => (
          <div key={letter} className="flex items-start gap-2">
            <dt className="shrink-0">
              <span
                aria-hidden="true"
                className="rounded-xs bg-overlay px-1 font-mono text-xs text-text-h"
              >
                {SIDE_MARKS[letter]}
              </span>
              <span className="sr-only">{SIDE_LABELS[letter]}</span>
            </dt>
            <dd className="break-words text-text">
              {caseSideValueText(reviewCase.purpose, reviewCase[letter], motifs)}
            </dd>
          </div>
        ))}
      </dl>
      <div role="group" aria-label={verdictGroupLabel(title)} className="grid grid-cols-2 gap-2">
        {VERDICT_ORDER.map((verdict) => {
          const pressed = reviewCase.verdict === verdict
          return (
            <Button
              key={verdict}
              variant="secondary"
              className={VERDICT_BUTTON_CLASSES}
              aria-pressed={pressed}
              aria-keyshortcuts={VERDICT_KEYS[verdict]}
              disabled={!judgeable}
              onClick={() => onJudge(verdict)}
            >
              <span className="flex flex-col gap-1">
                <span>{VERDICT_LABELS[verdict]}</span>
                {pressed && reviewCase.updated_by !== null && (
                  <span className="text-xs font-normal text-text">
                    {verdictWriterText(reviewCase.updated_by.username)}
                  </span>
                )}
              </span>
              <kbd
                aria-hidden="true"
                className="rounded-xs border border-border-control px-1 font-mono text-xs"
              >
                {VERDICT_KEYS[verdict]}
              </kbd>
            </Button>
          )
        })}
      </div>
    </li>
  )
}
