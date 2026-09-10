import { useId, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { ProjectOut } from '../api/types'
import { cn } from '../lib/utils'
import {
  getBlockedReason,
  PIPELINE_STEPS,
  stepProgress,
  type PipelineStepState,
  type StepId,
} from '../utils/pipelineSteps'
import { StepMarker, type StepMarkerAuspraegung } from './StepMarker'
import { Button } from './ui/button'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './ui/popover'
import { Progress } from './ui/progress'

interface StepperProps {
  projectId: number
  project: ProjectOut
  states: PipelineStepState[]
  activeStepId: StepId
}

/*
 * DAS BEDIENELEMENT EINES SCHRITTS - es fuellt seine Spalte vollstaendig und traegt die
 * Trefferflaeche (specs/features/0387-schrittleiste-fortschritt.md, Architektur-Abschnitt 6).
 *
 * `tap-target` statt `tap-target-square`: die Aufspannung gilt NUR senkrecht. Waagerecht fuellt
 * das Element seine Spalte ohnehin, ein beidachsiges Aufspannen erzeugte einen Ueberhang von bis
 * zu 6px je Seite - und damit ueberlappende Trefferflaechen zwischen Nachbarn, weil die Spalten
 * bewusst ohne Abstand aneinanderstossen (siehe die Geometrie-Anmerkung an der Liste unten).
 *
 * `group`: ERSTE VERWENDUNG DIESES MUSTERS IM PROJEKT. Der Zustand "ueberfahren"/"gedrueckt"
 * entsteht hier, dargestellt wird er am Marker (StepMarker.tsx, `group-hover:`/`group-active:`).
 * Der Zustandstraeger ist damit ueber zwei Dateien verteilt; die `quellen`-Angabe des Bausteins
 * `step-marker` zeigt deshalb auf StepMarker.tsx, wo die Varianten tatsaechlich stehen.
 */
const STEP_CONTROL_CLASSES =
  'tap-target group flex w-full min-w-0 items-center gap-2 px-1 text-left sm:gap-3'

/**
 * Die ausgeschriebene Schrittbeschriftung NEBEN der Marke (Entwurf `step-marker`: der Baustein ist
 * die Marke allein, die Umrandung fasst nur noch das Zeichen des Schritts). Unterhalb `sm:`
 * verborgen - dort steht der Name des aktuellen Schritts in der Orientierungszeile ueber der
 * Leiste. Bleibt `aria-hidden`: der zugaengliche Name kommt vollstaendig aus dem `aria-label` des
 * Bedienelements und enthaelt dasselbe Wort.
 *
 * UMBRECHEND, NIE GEKUERZT (`whitespace-normal`, kein `truncate`): bei knapper Breite entstehen
 * zweizeilige Beschriftungen statt abgeschnittener - waagerechtes Scrollen ist
 * Ausschlusskriterium, Kuerzen ebenso.
 */
function StepLabel({ label, auspraegung }: { label: string; auspraegung: StepMarkerAuspraegung }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'hidden min-w-0 whitespace-normal text-left text-xs font-semibold sm:block',
        auspraegung === 'aktuell' && 'font-bold text-accent',
        // Blockierte Schritte treten auch in der Beschriftung zurueck - rein visuell, die
        // Zustandsangabe steht im aria-label, es geht keine Information verloren.
        auspraegung === 'blockiert' && 'text-text-muted',
        (auspraegung === 'erledigt' || auspraegung === 'ausstehend') &&
          'text-text group-hover:text-text-h'
      )}
    >
      {label}
    </span>
  )
}

/**
 * DER GESPERRTE SCHRITT IST SELBST DER AUSLOESER seines Sperrgrunds (Architektur-Abschnitt 3 der
 * Spec 0387) - der bisherige eigene `i`-Knopf daneben ist ersatzlos entfallen. Wiederverwendet
 * wird das dokumentierte Muster "Info-Popover fuer situative Kurzerklaerungen" samt
 * geraeteunabhaengigem Oeffnungsverhalten (Vorlage: components/CriterionDetailsPopover.tsx). Kein
 * Radix-Tooltip: das ARIA-Tooltip-Muster ist hover/focus-only und oeffnet nicht per Tippen.
 *
 * `<button type="button">` mit `aria-disabled="true"`, NIE `disabled`: `disabled` naehme das
 * Element aus der Tab-Reihenfolge UND schaltete Zeigerereignisse ab - genau die Luecke, die diese
 * Spec schliesst ("der Grund war fuer Tastaturnutzer gar nicht erreichbar"). Es wird kein `<Link>`
 * gerendert; es gibt keinen Navigationspfad.
 *
 * Der Grund steht zusaetzlich als `sr-only`-Text im Baum und ist per `aria-describedby` verlinkt -
 * damit hat Screenreader-Bedienung ihn auch ohne Oeffnen.
 *
 * OHNE GRUND KEIN PANEL: `getBlockedReason` liefert fuer `scan`/`ausschuss` einen leeren Text
 * (defensiver Fallback - beide sind nie gesperrt). Dann bleibt es beim blossen Knopf: ein leeres
 * Panel und ein leeres `aria-describedby`-Ziel waeren beide schlechter als nichts.
 */
function BlockedStep({
  ariaLabel,
  stepLabel,
  reason,
  children,
}: {
  ariaLabel: string
  stepLabel: string
  reason: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  // Unterdrueckt GENAU den einen Klick direkt nach einem Hover-Oeffnen (ein echter Mausklick loest
  // immer erst `pointerenter` aus; ohne das schloesse Radix' eigenes Klick-Toggle sofort wieder).
  const justOpenedByHoverRef = useRef(false)
  // Ueber die gesamte Offen-Dauer persistent: haelt fest, ob der aktuelle Zustand per Ueberfahren
  // zustandegekommen ist. Steuert Auto-Close beim Verlassen UND die Fokus-Unterdrueckung.
  const openedByHoverRef = useRef(false)
  const reasonId = useId()

  function handleOpenChange(nextOpen: boolean): void {
    if (!nextOpen) {
      openedByHoverRef.current = false
      justOpenedByHoverRef.current = false
    }
    setOpen(nextOpen)
  }

  function handlePointerEnter(): void {
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      if (!open) {
        justOpenedByHoverRef.current = true
      }
      openedByHoverRef.current = true
      setOpen(true)
    }
  }

  function handleTriggerClick(event: { preventDefault: () => void }): void {
    if (justOpenedByHoverRef.current) {
      event.preventDefault()
    }
    justOpenedByHoverRef.current = false
  }

  function handleMouseLeave(): void {
    // Kein Grace-Bereich ueber die Portal-Grenze wie in CriterionDetailsPopover: der Panelinhalt
    // ist EIN SATZ ohne Bedienelement - es gibt dort nichts zu erreichen.
    if (openedByHoverRef.current) {
      handleOpenChange(false)
    }
  }

  const trigger = (
    <button
      type="button"
      aria-disabled="true"
      aria-label={ariaLabel}
      aria-describedby={reason === '' ? undefined : reasonId}
      onPointerEnter={handlePointerEnter}
      onMouseLeave={handleMouseLeave}
      className={STEP_CONTROL_CLASSES}
    >
      {children}
    </button>
  )

  if (reason === '') {
    return trigger
  }

  return (
    <>
      <Popover open={open} onOpenChange={handleOpenChange}>
        <PopoverTrigger asChild onClick={handleTriggerClick}>
          {trigger}
        </PopoverTrigger>
        <PopoverContent
          onOpenAutoFocus={(event) => {
            // Beim blossen Darueberfahren darf der Fokus NICHT ins Panel springen. Beim frueheren,
            // nicht fokussierbaren Ausloeser war das folgenlos - beim jetzigen waere es ein
            // Rueckschritt: der Zeiger streift einen Schritt, und die Tastaturposition ist weg.
            if (openedByHoverRef.current) {
              event.preventDefault()
            }
          }}
        >
          <div className="flex items-center justify-between gap-3 pb-2">
            <p className="text-sm font-semibold text-text-h">{stepLabel}</p>
            {/* Der einzige nicht-raeumliche Weg zurueck beim Tippen - bleibt. */}
            <PopoverClose asChild>
              <Button variant="ghost" size="icon" aria-label="Schließen" className="shrink-0">
                <span aria-hidden="true">×</span>
              </Button>
            </PopoverClose>
          </div>
          <p className="text-sm text-text">{reason}</p>
        </PopoverContent>
      </Popover>
      <span id={reasonId} className="sr-only">
        {reason}
      </span>
    </>
  )
}

/**
 * Sticky Stepper-Fortschrittsnavigation (specs/architecture/0004-design-system.md, Muster "Sticky
 * Stepper-Fortschrittsnavigation") - rein praesentational, steuert nichts selbst: die
 * Erreichbarkeit haengt ausschliesslich an `isReachable`, der "aktuelle" Schritt kommt
 * ausschliesslich aus der URL (`activeStepId`) und wird nicht algorithmisch aus `states`
 * hergeleitet.
 */
export function Stepper({ projectId, project, states, activeStepId }: StepperProps) {
  const stateById = new Map(states.map((state) => [state.id, state]))
  const activeIndex = PIPELINE_STEPS.findIndex((step) => step.id === activeStepId)
  const activeLabel = PIPELINE_STEPS[activeIndex]?.label ?? ''
  const progress = stepProgress(activeIndex)

  return (
    <>
      {/* Erste Verwendung eines Skip-Links im Produkt - visuell verborgen bis zum Fokus
          (Standard-sr-only/focus:not-sr-only-Muster). */}
      <a
        href="#pipeline-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-20 focus:rounded-sm focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-accent-fg"
      >
        Zum Seiteninhalt springen
      </a>
      {/*
        DIE ORIENTIERUNGSZEILE STEHT AUSSERHALB DES `<nav>` (Spec 0387, Architektur-Abschnitt 2):
        Sie scrollt mit dem Inhalt weg, statt Platz im dauerhaft fixierten Bereich zu belegen -
        schmal bleibt die haftende Leiste dadurch rund 25px flacher. Der aktuelle Schritt bleibt
        auch danach markiert (Akzentrand, fetter Schnitt, `aria-current="step"`).

        Bewusst KEIN gemeinsamer Behaelter mit dem `<nav>`: ein haftendes Element kann seinen
        Elternkasten nicht verlassen: in einem nur zwei Zeilen hohen Wrapper waere die Leiste gar
        nicht mehr haftend. Der Abstand zur Leiste kommt deshalb aus dem Spaltenraster der Seite.
      */}
      {activeIndex >= 0 && (
        <p className="text-xs text-text-muted sm:hidden" aria-hidden="true">
          {`Schritt ${activeIndex + 1} von 5: ${activeLabel}`}
        </p>
      )}
      <nav
        aria-label="Fortschritt der Pipeline"
        className="sticky top-header z-10 border-b border-separator bg-bg/95 px-4 py-3 backdrop-blur-sm sm:px-6"
      >
        {/*
          DIE SPALTENGEOMETRIE IST TRAGEND, KEIN KOSMETIKDETAIL (Spec 0387, Abschnitt 4): Die fuenf
          Schritte stehen in exakt gleich breiten Spalten OHNE Abstand zwischen den Spalten, und
          der Fortschrittsbalken darunter spannt denselben x-Bereich auf. Nur dann endet die
          Fuellung (`2*index+1` von `2*5`) wirklich unter der Mitte der aktuellen Spalte.

          Ein `gap-*` an dieser Liste verschoebe die Spaltenmitten gegenueber der Balkenskala - bei
          `gap-3` um bis zu ~5px an den Raendern, in der mittleren Spalte um exakt 0px. Der
          sichtbare Abstand zwischen den Marken kommt deshalb aus `px-1` INNERHALB der Spalte.
          `e2e/tests/stepper-progress.spec.ts` macht eine Umstellung darauf unmittelbar rot.
        */}
        <ol className="flex">
          {PIPELINE_STEPS.map((definition, index) => {
            const state = stateById.get(definition.id)
            const isDone = state?.isDone ?? false
            const isReachable = state?.isReachable ?? false
            const isCurrent = definition.id === activeStepId
            const isBlocked = !isReachable

            /*
             * DIE RANGFOLGE DER AUSPRAEGUNGEN, wenn mehrere Merkmale zugleich wahr sind
             * (Spec 0387, Edge Cases 2 und 3): blockiert vor aktuell vor erledigt vor ausstehend.
             * "aktuell" gewinnt gegen "erledigt", weil ein bereits erledigter Schritt beim
             * erneuten Aufrufen wieder der aktuelle ist - wo man gerade steht, ist dann die
             * wichtigere Information; dass er erledigt ist, sagt weiterhin der Haken.
             *
             * Die GLYPHE folgt einer eigenen, davon unabhaengigen Rangfolge: Haken vor Schloss
             * (siehe StepMarker.tsx). Beide zusammen sind als vollstaendige Wahrheitstabelle ueber
             * alle acht Kombinationen gebunden.
             */
            const auspraegung: StepMarkerAuspraegung = isBlocked
              ? 'blockiert'
              : isCurrent
                ? 'aktuell'
                : isDone
                  ? 'erledigt'
                  : 'ausstehend'
            const stepLabel = `Schritt ${index + 1} von 5: ${definition.label}`
            const ariaLabel = `${stepLabel}, ${auspraegung}`

            const inhalt = (
              <>
                <StepMarker auspraegung={auspraegung} nummer={index + 1} istErledigt={isDone} />
                <StepLabel label={definition.label} auspraegung={auspraegung} />
              </>
            )

            return (
              // `basis-0` neben `flex-1`: sonst flossen die unterschiedlich langen Beschriftungen
              // in die Spaltenbreite ein und die Spalten waeren ungleich breit.
              <li key={definition.id} className="flex min-w-0 flex-1 basis-0">
                {isBlocked ? (
                  <BlockedStep
                    ariaLabel={ariaLabel}
                    stepLabel={stepLabel}
                    reason={getBlockedReason(definition.id, project)}
                  >
                    {inhalt}
                  </BlockedStep>
                ) : (
                  <Link
                    to={`/projects/${projectId}/pipeline/${definition.id}`}
                    aria-label={ariaLabel}
                    aria-current={isCurrent ? 'step' : undefined}
                    className={STEP_CONTROL_CLASSES}
                  >
                    {inhalt}
                  </Link>
                )}
              </li>
            )
          })}
        </ol>
        {/*
          Der Fortschrittsbalken - das vorhandene `<progress>`-Primitiv, keine neue Komponente: ein
          gerechneter Prozentwert laesst sich weder als Tailwind-Klasse ausdruecken (willkuerliche
          Werte sind verboten, dynamische Klassennamen erzeugt Tailwind ohnehin nicht) noch per
          Inline-Style, den dieses Frontend an keiner Stelle verwendet.

          `aria-hidden`, weil die Information vollstaendig und besser im Schrittlisten-Baum steht
          (`aria-current`, der Zustand im Namen, die Orientierungszeile) - ein zweites, prozentual
          vorgelesenes Fortschrittselement waere Laerm. Er loest zugleich die frueheren
          Verbindungslinien zwischen den Marken ab.
        */}
        <Progress aria-hidden="true" value={progress.value} max={progress.max} className="mt-2" />
      </nav>
    </>
  )
}
