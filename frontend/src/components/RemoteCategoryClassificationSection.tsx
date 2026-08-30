import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { ProjectOut } from '../api/types'
import {
  useClassifyCategoriesRemoteEstimateQuery,
  useTriggerClassifyCategoriesRemoteMutation,
} from '../hooks/useProjects'
import { useTriggerConfirmation } from '../hooks/useTriggerConfirmation'
import { formatProviderLabel } from '../utils/categoryLabels'
import { StatusDot } from './StatusDot'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Progress } from './ui/progress'

interface RemoteCategoryClassificationSectionProps {
  project: ProjectOut
  refetchProject: () => unknown
}

function formatUsd(value: number): string {
  return `$${value.toFixed(2)}`
}

/**
 * "Remote-Kategorisierung"-Section auf KuratierungStepPage.tsx (specs/features/0055-remote-
 * kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt) - Eager-Schaetzung (beim
 * Seitenaufruf geladen, nicht erst beim Oeffnen des Dialogs), proaktive Deaktivierung bei
 * fehlendem Consent/leerem Kandidatenpool/laufendem Job, Bestaetigungsdialog vor der
 * kostenpflichtigen Aktion (erster echter <dialog>-Einsatz im Produkt, Design-System: bewusst
 * nativ statt eines neuen @radix-ui/react-dialog-Pakets, analog switch.tsx).
 *
 * `useTriggerConfirmation` (bereits etabliert fuer Scan/Score/Kriterien-Bewertung) ueberbrueckt
 * das Zeitfenster zwischen der 202-Antwort und dem ersten Poll, der `status="running"`
 * bestaetigt - identisches Muster wie KriterienStepPage.tsx.
 */
export function RemoteCategoryClassificationSection({
  project,
  refetchProject,
}: RemoteCategoryClassificationSectionProps) {
  const estimateQuery = useClassifyCategoriesRemoteEstimateQuery(project.id)
  const triggerMutation = useTriggerClassifyCategoriesRemoteMutation(project.id)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const run = project.last_remote_category_classification_run
  const runStatus = run?.status ?? null
  const runStartedAt = run?.started_at ?? null
  const [awaitingConfirmation, setAwaitingConfirmation] = useTriggerConfirmation(
    runStatus,
    runStartedAt,
    refetchProject
  )

  const isBusy = triggerMutation.isPending || awaitingConfirmation || runStatus === 'running'
  const consentEnabled = project.cloud_vision_detection_enabled
  const estimate = estimateQuery.data ?? null
  // Auslöse-Button bleibt disabled, solange die Schätzung nicht ladbar ist (Design-System: "kein
  // Bypass") - candidate_count===null deckt sowohl "noch ladend" als auch "Fehler beim Laden" ab.
  const candidateCount = estimate?.candidate_count ?? null
  const isTriggerDisabled =
    isBusy || !consentEnabled || candidateCount === null || candidateCount === 0

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog === null) {
      return
    }
    if (dialogOpen && !dialog.open) {
      dialog.showModal()
    } else if (!dialogOpen && dialog.open) {
      dialog.close()
    }
  }, [dialogOpen])

  function handleOpenDialog(): void {
    if (isTriggerDisabled) {
      return
    }
    setDialogOpen(true)
  }

  function handleConfirm(): void {
    setDialogOpen(false)
    setAwaitingConfirmation(true)
    triggerMutation.mutate(undefined, {
      onError: () => setAwaitingConfirmation(false),
    })
  }

  const triggerErrorDetail =
    triggerMutation.isError && triggerMutation.error instanceof ApiError
      ? triggerMutation.error.detail
      : triggerMutation.isError
        ? 'Fehler beim Auslösen der Remote-Kategorisierung.'
        : null

  const photosProcessed = run?.photos_processed ?? 0
  const photosTotal = run?.photos_total ?? 0
  const percent = photosTotal > 0 ? Math.floor((photosProcessed / photosTotal) * 100) : 0
  const announcedDecile = Math.floor(percent / 10) * 10

  const providerLabel = estimate ? formatProviderLabel(estimate.provider) : ''

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg font-semibold text-text-h">Remote-Kategorisierung</h2>
      <p className="text-sm text-text">
        Sendet die verbleibenden Fotos an ein Cloud-Vision-Modell, um zusätzliche, offene
        Kategorie-Schlagworte zu erkennen (z. B. Ereignis, Ort, Motiv) — ergänzt die lokale
        Kategorisierung, ersetzt sie nicht automatisch.
      </p>

      {!consentEnabled && (
        <p className="text-sm text-text">
          Cloud-Bilderkennung ist für dieses Projekt nicht aktiviert.{' '}
          <Link
            className="text-accent underline-offset-4 hover:underline"
            to={`/projects/${project.id}/settings`}
          >
            In den Projekteinstellungen aktivieren
          </Link>
          .
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" onClick={handleOpenDialog} disabled={isTriggerDisabled} busy={isBusy}>
          {isBusy ? 'Wird klassifiziert…' : 'Remote-Kategorisierung starten'}
        </Button>
        {consentEnabled && estimateQuery.isSuccess && estimate && (
          <p data-testid="classify-categories-remote-estimate" className="text-sm text-text">
            {candidateCount === 0
              ? 'Alle Fotos bereits klassifiziert'
              : `~${estimate.candidate_count} Fotos · ~${formatUsd(estimate.estimated_cost_usd)}`}
          </p>
        )}
      </div>

      {triggerErrorDetail && <Alert onRetry={handleOpenDialog}>{triggerErrorDetail}</Alert>}

      {run !== null && (
        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={runStatus} />
          {runStatus === 'running' && 'Wird verarbeitet…'}
          {runStatus === 'success' && 'Erfolgreich klassifiziert'}
          {runStatus === 'failed' && 'Fehlgeschlagen'}
        </p>
      )}

      {runStatus === 'success' && (
        <p className="text-sm text-text">
          Diese Ergebnisse fließen erst durch einen (ggf. erneuten)
          Kriterien-Bewertungs-Lauf in die Kategorie-Vorschläge ein.
        </p>
      )}

      {runStatus === 'running' && (
        <div className="flex w-full max-w-sm flex-col gap-1.5">
          <p className="text-sm text-text">
            {photosProcessed} von {photosTotal} Fotos verarbeitet
          </p>
          {photosTotal > 0 ? (
            <Progress value={photosProcessed} max={photosTotal}>
              {photosProcessed}/{photosTotal}
            </Progress>
          ) : (
            <Progress />
          )}
          <p aria-live="polite" className="text-sm text-text">
            {announcedDecile}% verarbeitet
          </p>
        </div>
      )}

      {runStatus === 'failed' && <Alert onRetry={handleOpenDialog}>{run?.error_message}</Alert>}

      <dialog
        ref={dialogRef}
        aria-labelledby="classify-categories-remote-dialog-title"
        className="rounded-xl border border-border bg-bg p-6 text-text shadow-warm backdrop:bg-black/40"
        onClose={() => setDialogOpen(false)}
      >
        <h3
          id="classify-categories-remote-dialog-title"
          className="text-lg font-semibold text-text-h"
        >
          Remote-Kategorisierung starten?
        </h3>
        {estimate && (
          <p className="mt-2 text-sm text-text">
            {estimate.candidate_count} Fotos werden an {providerLabel} gesendet, geschätzte
            Gesamtkosten: ~{formatUsd(estimate.estimated_cost_usd)}.
          </p>
        )}
        <p className="mt-2 text-xs text-text">Schätzung, keine exakte Abrechnung.</p>
        <div className="mt-4 flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>
            Abbrechen
          </Button>
          <Button type="button" onClick={handleConfirm}>
            Starten
          </Button>
        </div>
      </dialog>
    </section>
  )
}
