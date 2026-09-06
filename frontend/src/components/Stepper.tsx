import { useRef, useState } from 'react'
import { Link } from 'react-router'

import type { ProjectOut } from '../api/types'
import { cn } from '../lib/utils'
import { getBlockedReason, PIPELINE_STEPS, type PipelineStepState, type StepId } from '../utils/pipelineSteps'
import { Button } from './ui/button'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './ui/popover'

interface StepperProps {
  projectId: number
  project: ProjectOut
  states: PipelineStepState[]
  activeStepId: StepId
}

// Gemeinsames Mass fuer JEDEN Schritt-Eintrag, auch die nicht-klickbaren (Akzeptanzkriterium 15,
// UI/UX-Abschnitt der Spec 0042: "Konsistenz wichtiger als Platzersparnis"). Board-Mass 32px mit
// aufgespannter Trefferflaeche auf beiden Achsen (`tap-target-square`) statt der frueheren 44px
// Sichtgroesse; Radius 8px wie das Navigationselement des Boards statt der frueheren Vollrundung.
// Keine eigene Fokusdarstellung mehr - die eine globale, abgesetzte Kontur in index.css traegt sie.
const STEP_MARKER_BASE_CLASSES =
  'tap-target-square flex size-8 shrink-0 items-center justify-center rounded-md border-2 text-xs ' +
  'font-semibold transition-colors'

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="size-4" fill="none">
      <path
        d="M3 8.5 6.5 12 13 4.5"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function LockIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="size-4" fill="none">
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth={1.5} />
      <path
        d="M5 7V5a3 3 0 0 1 6 0v2"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
      />
    </svg>
  )
}

/**
 * Info-Popover fuer den Blockiert-Grund eines Schritts (Akzeptanzkriterium 5, UI/UX-Abschnitt) -
 * wiederverwendet dieselbe Radix-Popover-Primitive samt geraeteunabhaengigem Oeffnungsverhalten
 * wie components/CriterionDetailsPopover.tsx (specs/architecture/0004-design-system.md, Muster
 * "Info-Popover fuer situative Kurzerklaerungen"). Bewusst dateilokal statt extrahiert - analog zur
 * bisherigen "erst ab drittem Konsumenten auslagern"-Praxis dieses Projekts (siehe historischer
 * Kommentar zu useTriggerConfirmation vor dessen Umzug nach hooks/) - aktuell nur hier gebraucht.
 */
function BlockedReasonPopover({ stepLabel, reason }: { stepLabel: string; reason: string }) {
  const [open, setOpen] = useState(false)
  const justOpenedByHoverRef = useRef(false)

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
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Grund für Sperrung von ${stepLabel} anzeigen`}
          onPointerEnter={handlePointerEnter}
          className="shrink-0"
        >
          i
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-center justify-between gap-3 pb-2">
          <p className="text-sm font-semibold text-text-h">{stepLabel}</p>
          <PopoverClose asChild>
            <Button variant="ghost" size="icon" aria-label="Schließen" className="shrink-0">
              <span aria-hidden="true">×</span>
            </Button>
          </PopoverClose>
        </div>
        <p className="text-sm text-text">{reason}</p>
      </PopoverContent>
    </Popover>
  )
}

/**
 * Sticky Stepper-Fortschrittsuebersicht (Akzeptanzkriterien 1-2, 5-6, 15 der Spec 0042,
 * specs/architecture/0004-design-system.md, Muster "Sticky Stepper-Fortschrittsnavigation") - rein
 * praesentational, steuert nichts selbst: Klickbarkeit (AK5) haengt ausschliesslich von
 * `isReachable` ab, der "aktuelle" Schritt kommt ausschliesslich aus der URL (`activeStepId`), nicht
 * algorithmisch aus `states` hergeleitet.
 */
export function Stepper({ projectId, project, states, activeStepId }: StepperProps) {
  const stateById = new Map(states.map((state) => [state.id, state]))
  const activeIndex = PIPELINE_STEPS.findIndex((step) => step.id === activeStepId)
  const activeLabel = PIPELINE_STEPS[activeIndex]?.label ?? ''

  return (
    <>
      {/* Erste Verwendung eines Skip-Links im Produkt (UI/UX-Abschnitt) - visuell verborgen bis
          zum Fokus (Standard-sr-only/focus:not-sr-only-Muster). */}
      <a
        href="#pipeline-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-20 focus:rounded-sm focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-accent-fg"
      >
        Zum Seiteninhalt springen
      </a>
      <nav
        aria-label="Fortschritt der Pipeline"
        className="sticky top-0 z-10 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur-sm sm:px-6"
      >
        {/* Schmale Orientierungszeile unterhalb sm: (UI/UX-Abschnitt) - ersetzt die ab sm:
            sichtbaren Labels unter den Kreisen, verhindert Umbruch/Horizontal-Scroll der Leiste. */}
        <p className="mb-2 text-sm text-text sm:hidden" aria-hidden="true">
          {activeIndex >= 0 && `Schritt ${activeIndex + 1} von 5: ${activeLabel}`}
        </p>
        <ol className="flex items-center gap-3">
          {PIPELINE_STEPS.map((definition, index) => {
            const state = stateById.get(definition.id)
            const isDone = state?.isDone ?? false
            const isReachable = state?.isReachable ?? false
            const isCurrent = definition.id === activeStepId
            const isBlocked = !isReachable
            const statusLabel = isBlocked ? 'blockiert' : isDone ? 'erledigt' : isCurrent ? 'aktuell' : 'ausstehend'
            const stepLabel = `Schritt ${index + 1} von 5: ${definition.label}`
            const ariaLabel = `${stepLabel}, ${statusLabel}`

            /*
             * Die vier Schrittzustaende der Vorlage (Artboard 4, "Step states"). Reihenfolge der
             * Faelle ist bedeutungstragend: "aktuell" gewinnt gegen "erledigt", weil ein bereits
             * erledigter Schritt beim erneuten Aufrufen wieder der aktuelle ist - wo man gerade
             * steht, ist dann die wichtigere Information. Dass er erledigt ist, sagt weiterhin das
             * Hakensymbol im Kreis, die Zustandsbenennung steckt ohnehin im aria-label.
             */
            const markerClasses = cn(
              STEP_MARKER_BASE_CLASSES,
              // Prozessstufen nach Board (Abschnitt 6): die AKTUELLE Stufe traegt Akzent UND
              // fetten Schnitt - ueber Schnitt und Farbe, nie ueber Farbe allein. Erledigt/kommend
              // in Sekundaertext, noch nicht begonnen (blockiert) in `--text-muted`.
              isCurrent && 'border-accent bg-accent font-bold text-accent-fg',
              !isCurrent && isDone && 'border-accent-2 bg-transparent text-accent-2',
              !isCurrent && !isDone && !isBlocked && 'border-border-control bg-transparent text-text',
              // Blockiert: schwaecherer Rahmen und gedaempfte Beschriftung statt eines pauschalen
              // opacity-50 auf dem ganzen Marker - so bleibt das Schloss-Symbol selbst lesbar.
              !isCurrent && !isDone && isBlocked && 'border-border bg-transparent text-text-muted'
            )

            return (
              <li key={definition.id} className="flex flex-1 items-center gap-3 last:flex-initial">
                <div className="flex flex-col items-center gap-3 sm:flex-row">
                  {isBlocked ? (
                    <span
                      aria-disabled="true"
                      tabIndex={-1}
                      aria-label={ariaLabel}
                      data-step-state={statusLabel}
                      className={markerClasses}
                    >
                      {isDone ? <CheckIcon /> : <LockIcon />}
                    </span>
                  ) : (
                    <Link
                      to={`/projects/${projectId}/pipeline/${definition.id}`}
                      aria-label={ariaLabel}
                      aria-current={isCurrent ? 'step' : undefined}
                      data-step-state={statusLabel}
                      className={markerClasses}
                    >
                      {/* Erledigt zeigt den Haken, sonst die Schrittnummer (Vorlage) - der leere
                          Kreis von zuvor liess offen, welcher Schritt gemeint ist. Rein visuell,
                          die zugaengliche Benennung steht vollstaendig im aria-label. */}
                      {isDone ? <CheckIcon /> : <span aria-hidden="true">{index + 1}</span>}
                    </Link>
                  )}
                  {isBlocked && (
                    <BlockedReasonPopover
                      stepLabel={stepLabel}
                      reason={getBlockedReason(definition.id, project)}
                    />
                  )}
                  <span
                    aria-hidden="true"
                    className={cn(
                      'hidden text-xs text-text sm:block',
                      isCurrent && 'font-semibold text-text-h',
                      // Blockierte Schritte treten auch in der Beschriftung zurueck (Vorlage) -
                      // rein dekorativ (aria-hidden), die Zustandsangabe steht im aria-label des
                      // Kreises, hier geht also keine Information verloren.
                      isBlocked && 'opacity-40'
                    )}
                  >
                    {definition.label}
                  </span>
                </div>
                {index < PIPELINE_STEPS.length - 1 && (
                  <span aria-hidden="true" className="h-0.5 flex-1 bg-border" />
                )}
              </li>
            )
          })}
        </ol>
      </nav>
    </>
  )
}
