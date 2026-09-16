import { useRef, useState } from 'react'

import type {
  AlbumSuitabilityOut,
  CriterionScoreOut,
  FineLabelOut,
  MotifAssessmentOut,
  MotifSetOut,
  MotifStrengthOut,
  RankingOut,
  SuggestionOut,
} from '../api/types'
import { cn } from '../lib/utils'
import { Button } from './ui/button'
import { CriterionDetailsList } from './CriterionDetailsList'
import { MotifStrengthSection } from './MotifStrengthSection'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './ui/popover'

/**
 * Der Verweis unter der schreibgeschützten Motivliste. 24 Bedienelemente in einem Popover sind
 * am Telefon nicht bedienbar, und die Kachel führt ohnehin in die Einzelbildansicht - der Satz
 * benennt deshalb den Ort, statt einen deaktivierten Schalter anzubieten.
 */
export const MOTIF_CORRECTION_HINT = 'Korrigieren in der Einzelbildansicht.'

interface CriterionDetailsPopoverProps {
  criterionScores: CriterionScoreOut[]
  /** Die Rangzeile des Fotos. `null`, solange kein erfolgreicher Lauf existiert. */
  ranking: RankingOut | null
  suggestion: SuggestionOut | null
  className?: string
  // Reine Durchreichung an CriterionDetailsList.tsx (siehe dortige Props-Dokumentation) - dieselben
  // neutralen Defaults, kein eigenes Verhalten hier.
  fineLabels?: FineLabelOut[]
  /** Das geladene Motivset. `undefined` während des Ladens bzw. nach einem Fehlschlag - die Liste
   * stellt beide Zustände selbst dar. Ohne jede der drei Motiv-Props bleibt der Motivteil
   * weg. */
  motifSet?: MotifSetOut
  motifSetLoading?: boolean
  motifSetError?: string
  onMotifSetRetry?: () => void
  assessment?: MotifAssessmentOut | null
  motifs?: readonly MotifStrengthOut[]
  /** Reine Durchreichung an CriterionDetailsList.tsx - `undefined` laesst die Zeile weg, `null`
   * traegt den Satz "Noch nicht bewertet". */
  albumSuitability?: AlbumSuitabilityOut | null
}

/**
 * Info-Popover mit den berechneten Bewertungsdetails eines Fotos - feature-spezifische Komposition
 * auf ui/popover.tsx, analog zum bestehenden Muster ui/progress.tsx -> CriterionDetailsList.tsx.
 * Rendert
 * bewusst nichts, wenn criterionScores leer ist - EINE Stelle entscheidet das statt jeder der drei
 * Einbindungsstellen einzeln. Die eigentliche `<dl>`-Darstellung des Inhalts lebt in der
 * wiederverwendbaren Praesentationskomponente CriterionDetailsList.tsx (hier mit
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
 *
 * Hover-Auto-Close mit Grace-Bereich ueber Trigger UND Content: `openedByHoverRef` ist - anders als
 * `justOpenedByHoverRef` oben, der nur den EINEN Klick direkt nach einem Hover-Oeffnen unterdrueckt
 * und danach zurueckgesetzt wird - ueber die gesamte Offen-Dauer persistent und haelt fest, ob der
 * aktuelle Offen-Zustand ueberhaupt per Hover zustandegekommen ist. `handleOpenChange` setzt ihn
 * synchron zu `justOpenedByHoverRef` beim Oeffnen und setzt ihn beim Schliessen zurueck.
 * `handlePossibleHoverClose` haengt an `onMouseLeave` von Trigger-Button UND `PopoverContent` und
 * prueft bei `openedByHoverRef.current === true` per `Node.contains()` gegen
 * `triggerRef`/`contentRef`, ob `event.relatedTarget` (das neue Ziel des Pointers) ausserhalb
 * beider liegt - nur dann schliesst es. Ref-basiert statt eines naiven
 * `event.currentTarget.contains(event.relatedTarget)`- Bubbling-Checks, weil `PopoverContent` ueber
 * `PopoverPrimitive.Portal` an einer anderen Stelle im DOM-Baum liegt als der Trigger - ein
 * Uebergang Trigger->Content wuerde sonst faelschlich als "verlassen" gewertet. Kein Timer/Delay
 * noetig.
 */
export function CriterionDetailsPopover({
  criterionScores,
  ranking,
  suggestion,
  className,
  fineLabels,
  motifSet,
  motifSetLoading,
  motifSetError,
  onMotifSetRetry,
  assessment,
  motifs,
  albumSuitability,
}: CriterionDetailsPopoverProps) {
  const [open, setOpen] = useState(false)
  const justOpenedByHoverRef = useRef(false)
  const openedByHoverRef = useRef(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  if (criterionScores.length === 0) {
    return null
  }

  function handlePointerEnter(): void {
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      if (!open) {
        justOpenedByHoverRef.current = true
      }
      handleOpenChange(true)
    }
  }

  function handleTriggerClick(event: { preventDefault: () => void }): void {
    if (justOpenedByHoverRef.current) {
      event.preventDefault()
    }
    justOpenedByHoverRef.current = false
  }

  function handleOpenChange(nextOpen: boolean): void {
    if (nextOpen) {
      openedByHoverRef.current = justOpenedByHoverRef.current
    } else {
      openedByHoverRef.current = false
      // Ohne diesen Reset blieb justOpenedByHoverRef nach einem Schliessen ueber einen anderen Weg
      // als den direkt folgenden Trigger-Klick (Escape/Aussenklick/"x"-Button/Hover-Auto-Close)
      // faelschlich `true` stehen - ein spaeterer, voellig unabhaengiger Klick (z.B. per Tastatur)
      // haette dadurch faelschlich per preventDefault() unterdrueckt und das Popover nicht
      // geoeffnet.
      justOpenedByHoverRef.current = false
    }
    setOpen(nextOpen)
  }

  function handlePossibleHoverClose(event: { relatedTarget: EventTarget | null }): void {
    if (!openedByHoverRef.current) {
      return
    }
    const relatedTarget = event.relatedTarget instanceof Node ? event.relatedTarget : null
    const staysWithinTrigger = relatedTarget !== null && triggerRef.current?.contains(relatedTarget)
    const staysWithinContent = relatedTarget !== null && contentRef.current?.contains(relatedTarget)
    if (!staysWithinTrigger && !staysWithinContent) {
      handleOpenChange(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild onClick={handleTriggerClick}>
        <Button
          ref={triggerRef}
          variant="ghost"
          size="icon"
          aria-label="Bewertungsdetails anzeigen"
          onPointerEnter={handlePointerEnter}
          onMouseLeave={handlePossibleHoverClose}
          className={cn(
            // Runder Backdrop ueber der Fotokachel - eine der wenigen verbleibenden Rundformen: der
            // Trigger liegt auf dem Bild, ein Kreis grenzt sich dort von jeder rechteckigen
            // Bildstruktur ab.
            'shrink-0 rounded-full border border-border-control bg-bg/85 backdrop-blur-sm',
            className,
          )}
        >
          i
        </Button>
      </PopoverTrigger>
      <PopoverContent ref={contentRef} onMouseLeave={handlePossibleHoverClose}>
        <div className="flex items-center justify-between gap-3 pb-3">
          <p className="text-sm font-semibold text-text-h">Bewertungsdetails</p>
          <PopoverClose asChild>
            <Button variant="ghost" size="icon" aria-label="Schließen" className="shrink-0">
              <span aria-hidden="true">×</span>
            </Button>
          </PopoverClose>
        </div>
        <CriterionDetailsList
          criterionScores={criterionScores}
          ranking={ranking}
          suggestion={suggestion}
          showSuggestion={true}
          fineLabels={fineLabels}
          albumSuitability={albumSuitability}
        />
        {/* Die Motivstärken SCHREIBGESCHÜTZT (`editable={false}`) - einsehbar bleibt einsehbar,
            aber ohne die 24 Korrektur-Schaltflächen. Darunter der Verweis auf den Ort, an dem
            korrigiert wird. */}
        {assessment !== undefined && (
          <div className="mt-4 flex flex-col gap-2 border-t border-separator pt-4">
            <h3 className="text-xs font-medium text-text-h">Motive</h3>
            <MotifStrengthSection
              motifSet={motifSet}
              motifSetLoading={motifSetLoading}
              motifSetError={motifSetError}
              onMotifSetRetry={onMotifSetRetry}
              assessment={assessment}
              motifs={motifs}
              editable={false}
            />
            <p className="text-xs text-text">{MOTIF_CORRECTION_HINT}</p>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
