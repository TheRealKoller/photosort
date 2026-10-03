import { useId, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { ProjectOut } from '../api/types'
import { cn } from '../lib/utils'
import { DRAFT_CLOUD_CONSENT_TEXT, SETTINGS_LINK_LABEL } from '../pages/AlbumDraftPage'
import {
  deriveWorkflowOverview,
  PIPELINE_STEPS,
  type OverviewEntryState,
  type WorkflowOverviewEntry,
} from '../utils/pipelineSteps'
import { OVERVIEW_STATE_WORDS, OVERVIEW_TEXTS, overviewEntryLabel } from '../utils/workflowOverview'
import { StatusTag } from './StatusTag'
import { StepMarker, type StepMarkerAuspraegung } from './StepMarker'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'

interface WorkflowOverviewDialogProps {
  project: ProjectOut
  open: boolean
  /** "Schließen" und Esc. */
  onClose: () => void
  /** Ein Klick auf eine Schaltfläche eines Eintrags - zählt wie Schließen als "gesehen". */
  onOpenEntry: () => void
}

/** Die Marke wie in der Schrittleiste; `abgeschaltet` heißt dort „gesperrt". */
const MARKER_BY_STATE: Partial<Record<OverviewEntryState, StepMarkerAuspraegung>> = {
  erledigt: 'erledigt',
  aktuell: 'aktuell',
  offen: 'ausstehend',
  gesperrt: 'blockiert',
  abgeschaltet: 'blockiert',
}

const TERM_CLASSES =
  'text-xs font-semibold uppercase tracking-wide text-text-muted sm:w-28 sm:shrink-0'

function Pair({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:gap-3">
      <dt className={TERM_CLASSES}>{term}</dt>
      <dd className="text-text">{children}</dd>
    </div>
  )
}

function OverviewEntry({
  item,
  number,
  projectId,
  onOpenEntry,
}: {
  item: WorkflowOverviewEntry
  /** Die Schrittnummer - nur die vier Schritte tragen eine Marke. */
  number: number | null
  projectId: number
  onOpenEntry: () => void
}) {
  const label = overviewEntryLabel(item.id)
  const text = OVERVIEW_TEXTS[item.id]
  const marker = MARKER_BY_STATE[item.state]
  const isBlocked = item.state === 'gesperrt' || item.state === 'abgeschaltet'

  return (
    <li data-overview-entry={item.id} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {number !== null && marker !== undefined && (
          <span className="w-8 shrink-0">
            <StepMarker auspraegung={marker} nummer={number} istErledigt={item.isDone} />
          </span>
        )}
        <h3 className="text-base font-semibold text-text-h">{label}</h3>
        <span
          className={cn(
            'text-sm',
            item.state === 'aktuell' ? 'font-bold text-text-h' : 'text-text',
          )}
        >
          {OVERVIEW_STATE_WORDS[item.state]}
        </span>
        {item.run === 'running' && <StatusTag status="running" label="läuft…" />}
        {item.run === 'failed' && <StatusTag status="failed" label="fehlgeschlagen" />}
      </div>

      <p className="text-sm text-text">{text.purpose}</p>

      <dl className="flex flex-col gap-2 text-sm">
        <Pair term="Wer arbeitet">
          <span className="font-semibold text-text-h">{text.worker.kind}</span>
          {` – ${text.worker.detail}`}
        </Pair>
        {text.responsibility !== null && <Pair term="Zuständig">{text.responsibility}</Pair>}
        {text.prerequisite !== null && <Pair term="Vorher">{text.prerequisite.text}</Pair>}
      </dl>

      {item.id === 'album' && <p className="text-sm text-text">{DRAFT_CLOUD_CONSENT_TEXT}</p>}

      {isBlocked ? (
        <p className="text-sm text-text">{item.blockedReason}</p>
      ) : (
        <div className="flex flex-wrap gap-3">
          <Button asChild size="sm" variant={item.state === 'aktuell' ? 'default' : 'secondary'}>
            <Link to={item.to} onClick={onOpenEntry}>
              {`${label} öffnen`}
            </Link>
          </Button>
          {item.id === 'album' && (
            <Button asChild size="sm" variant="secondary">
              <Link to={`/projects/${projectId}/settings`} onClick={onOpenEntry}>
                {SETTINGS_LINK_LABEL}
              </Link>
            </Button>
          )}
        </div>
      )}
    </li>
  )
}

/**
 * Die Ablaufübersicht: alle Schritte eines Projekts mit Zweck, Kennzeichnung, Zuständigkeit,
 * Vorbedingung und dem Stand dieses Projekts.
 *
 * ZEIGT NUR FESTEN TEXT: Konstanten aus `utils/workflowOverview.ts`, die Schritt- und
 * Stationsnamen und die Sperrgründe aus `getBlockedReason`. Projektname, Fehlermeldungen eines
 * Laufs und Serverantworten stehen hier nie - ein Fremdtext im Dialog wäre ein Einfallstor.
 *
 * Kein `aria-live`: Die Zustände folgen dem gepollten Projekt, und jeder Poll würde sonst
 * vorgelesen. Navigieren kann nur die Schaltfläche eines Eintrags, nicht der ganze Eintrag - wer
 * beim Lesen tippt, um das Scrollen anzuhalten, springt nicht weg.
 */
export function WorkflowOverviewDialog({
  project,
  open,
  onClose,
  onOpenEntry,
}: WorkflowOverviewDialogProps) {
  const afterId = useId()
  const entries = deriveWorkflowOverview(project)
  const steps = entries.slice(0, PIPELINE_STEPS.length)
  const stations = entries.slice(PIPELINE_STEPS.length)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Ablauf im Überblick"
      icon="info"
      cancelLabel="Schließen"
      description="Von den Fotos im OpenCloud-Ordner bis zur gemeinsamen Endauswahl. Bei jedem Schritt siehst du, wie weit dieses Projekt ist."
    >
      <ol aria-label="Schritte" className="flex flex-col gap-6">
        {steps.map((item, index) => (
          <OverviewEntry
            key={item.id}
            item={item}
            number={index + 1}
            projectId={project.id}
            onOpenEntry={onOpenEntry}
          />
        ))}
      </ol>
      <p id={afterId} className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        Danach
      </p>
      <ul aria-labelledby={afterId} className="flex flex-col gap-6">
        {stations.map((item) => (
          <OverviewEntry
            key={item.id}
            item={item}
            number={null}
            projectId={project.id}
            onOpenEntry={onOpenEntry}
          />
        ))}
      </ul>
    </Dialog>
  )
}
