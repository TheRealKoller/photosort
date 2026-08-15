import { useRef, useState } from 'react'

import type { CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { formatCategoryKey } from '../utils/categoryLabels'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { cn } from '../lib/utils'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './ui/popover'

interface CriterionDetailsPopoverProps {
  criterionScores: CriterionScoreOut[]
  ranking: RankingOut | null
  suggestion: SuggestionOut | null
  className?: string
}

// Kaufmaennisch gerundete Prozentzahl ohne Nachkommastelle (Akzeptanzkriterium 9 der Spec) -
// vermeidet eine Scheingenauigkeit, die die zugrundeliegenden, teils heuristischen Scores nicht
// hergeben. Kriterien-Werte sind immer bereits auf [0, 1] normiert (backend criteria.py), also nie
// negativ - Math.round rundet in diesem Bereich identisch zu "kaufmaennisch" (0.5 aufwaerts).
function formatCriterionPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/**
 * Info-Popover mit den berechneten Bewertungsdetails eines Fotos (specs/features/0040-
 * bewertungsdetails-info-popover.md) - feature-spezifische Komposition auf ui/popover.tsx, analog
 * zum bestehenden Muster ui/badge.tsx -> CategoryBadge.tsx. Rendert bewusst nichts, wenn
 * criterionScores leer ist (Akzeptanzkriterium 1) - EINE Stelle entscheidet das statt jeder der
 * drei Einbindungsstellen einzeln.
 *
 * Geraeteunabhaengige Interaktion (Akzeptanzkriterien 3-6): Klick/Tap oeffnet/schliesst ueberall
 * (Radix' eigener Trigger-Klick-Handler beim kontrollierten `open`-State), zusaetzlich oeffnet
 * Hover auf dem Trigger NUR, wenn `matchMedia('(hover: hover) and (pointer: fine)').matches` zum
 * Zeitpunkt der Interaktion `true` ist (nicht am Mount gecached) - vermeidet, dass ein
 * synthetisches Hover-Event auf einem Touch-Geraet (z.B. als Teil von userEvent.click) das
 * Popover faelschlich oeffnet. Escape/Aussenklick werden von Radix' Popover.Content bereits
 * intern gehandhabt.
 *
 * Hover-vor-Klick-Falle: ein echter Mausklick loest IMMER erst `pointerenter`, dann erst
 * `click` aus (der Zeiger muss das Element physisch betreten, bevor er es druecken kann) - ohne
 * Gegenmassnahme wuerde Hover das Popover oeffnen und der DIREKT folgende Klick es ueber Radix'
 * eigene Toggle-Logik sofort wieder schliessen, sodass ein Klick auf einem hover-faehigen Geraet
 * nie sichtbar oeffnen wuerde (widerspricht Testkonzept-Punkt 3: Klick muss geraeteunabhaengig
 * gleich funktionieren). `justOpenedByHoverRef` merkt sich deshalb, dass der aktuelle
 * Offen-Zustand NUR durch Hover ausgeloest wurde, und schluckt genau die eine, unmittelbar
 * folgende Schliessen-Anfrage - ein zweiter, davon unabhaengiger Klick schliesst wie in
 * Akzeptanzkriterium 4 gefordert ganz normal.
 */
export function CriterionDetailsPopover({
  criterionScores,
  ranking,
  suggestion,
  className,
}: CriterionDetailsPopoverProps) {
  const [open, setOpen] = useState(false)
  const justOpenedByHoverRef = useRef(false)

  if (criterionScores.length === 0) {
    return null
  }

  function handlePointerEnter(): void {
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      if (!open) {
        justOpenedByHoverRef.current = true
      }
      setOpen(true)
    }
  }

  function handleOpenChange(next: boolean): void {
    if (!next && justOpenedByHoverRef.current) {
      justOpenedByHoverRef.current = false
      return
    }
    justOpenedByHoverRef.current = false
    setOpen(next)
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Bewertungsdetails anzeigen"
          onPointerEnter={handlePointerEnter}
          className={cn(
            'flex size-11 shrink-0 items-center justify-center rounded-full border border-border ' +
              'bg-bg/85 text-xs font-semibold text-text backdrop-blur-sm transition-colors ' +
              'hover:bg-border/50 focus-visible:outline-none focus-visible:ring-2 ' +
              'focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
            className
          )}
        >
          i
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-center justify-between gap-3 pb-3">
          <p className="text-sm font-semibold text-text-h">Bewertungsdetails</p>
          <PopoverClose
            aria-label="Schließen"
            className="flex size-8 shrink-0 items-center justify-center rounded-md text-text hover:bg-border/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <span aria-hidden="true">×</span>
          </PopoverClose>
        </div>
        <dl className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            {criterionScores.map((score) => (
              <div
                key={score.criterion_key}
                className="flex items-baseline justify-between gap-3"
              >
                <dt className="text-text">{score.display_name}</dt>
                <dd className="font-medium text-text-h">{formatCriterionPercent(score.value)}</dd>
              </div>
            ))}
          </div>
          {ranking !== null && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-text">Kategorie</dt>
                <dd className="font-medium text-text-h">{formatCategoryKey(ranking.category_key)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-text">Rang</dt>
                <dd className="font-medium text-text-h">
                  Rang {ranking.rank_position} von {ranking.partition_size}
                </dd>
              </div>
            </div>
          )}
          {suggestion !== null && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-text">Ausschuss-Vorschlag</dt>
                <dd className="font-medium text-text-h">
                  {formatSuggestionStatusLabel(suggestion)}
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-text">Grund</dt>
                <dd className="font-medium text-text-h">{formatSuggestionReason(suggestion)}</dd>
              </div>
            </div>
          )}
        </dl>
      </PopoverContent>
    </Popover>
  )
}
