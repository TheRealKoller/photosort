import { useRef, useState } from 'react'

import type { CriterionScoreOut, RankingOut, SuggestionOut } from '../api/types'
import { cn } from '../lib/utils'
import { CriterionDetailsList } from './CriterionDetailsList'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './ui/popover'

interface CriterionDetailsPopoverProps {
  criterionScores: CriterionScoreOut[]
  ranking: RankingOut | null
  suggestion: SuggestionOut | null
  className?: string
}

/**
 * Info-Popover mit den berechneten Bewertungsdetails eines Fotos (specs/features/0040-
 * bewertungsdetails-info-popover.md) - feature-spezifische Komposition auf ui/popover.tsx, analog
 * zum bestehenden Muster ui/badge.tsx -> CategoryBadge.tsx. Rendert bewusst nichts, wenn
 * criterionScores leer ist (Akzeptanzkriterium 1) - EINE Stelle entscheidet das statt jeder der
 * drei Einbindungsstellen einzeln. Die eigentliche `<dl>`-Darstellung des Inhalts lebt seit Spec
 * 0041 in der wiederverwendbaren Praesentationskomponente CriterionDetailsList.tsx (hier mit
 * showSuggestion={true} eingebunden) - dieses Popover selbst traegt nur noch Trigger/Portal/
 * Oeffnungslogik.
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
 * Offen-Zustand NUR durch Hover ausgeloest wurde.
 *
 * Test-Review-Fund: eine fruehere Fassung schluckte dafuer JEDE erste Schliessen-Anfrage nach
 * einem Hover-Oeffnen generisch in `onOpenChange` - das schloss faelschlich auch Escape/
 * Aussenklick unmittelbar nach einem Hover-Oeffnen (entgegen Akzeptanzkriterium 4). Die
 * Unterdrueckung passiert deshalb jetzt gezielt NUR im `onClick` des Triggers selbst (als Prop an
 * `PopoverTrigger`, nicht an das Kind-Button - nur DORT komponiert Radix ueber
 * `composeEventHandlers`, das `event.preventDefault()` respektiert und dadurch selektiv genau
 * Radix' eigenes Klick-Toggle unterdrueckt; `PopoverTrigger`s Slot-Merge mit dem Kind-Button
 * wuerde `preventDefault()` ignorieren). Escape/Aussenklick/der "×"-Button laufen dadurch
 * unveraendert direkt ueber `Popover.onOpenChange={setOpen}`.
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

  function handleTriggerClick(event: { preventDefault: () => void }): void {
    if (justOpenedByHoverRef.current) {
      event.preventDefault()
    }
    justOpenedByHoverRef.current = false
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild onClick={handleTriggerClick}>
        <button
          type="button"
          aria-label="Bewertungsdetails anzeigen"
          onPointerEnter={handlePointerEnter}
          className={cn(
            'flex size-11 shrink-0 items-center justify-center rounded-md border border-border ' +
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
        <CriterionDetailsList
          criterionScores={criterionScores}
          ranking={ranking}
          suggestion={suggestion}
          showSuggestion={true}
        />
      </PopoverContent>
    </Popover>
  )
}
