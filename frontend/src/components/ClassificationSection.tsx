import { useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { ProjectOut } from '../api/types'
import {
  useClassificationEstimateQuery,
  useFineLabelsQuery,
  useTriggerClassificationMutation,
} from '../hooks/useProjects'
import { useTriggerConfirmation } from '../hooks/useTriggerConfirmation'
import { formatProviderLabel } from '../utils/categoryLabels'
import { StatusDot } from './StatusDot'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Progress } from './ui/progress'

interface ClassificationSectionProps {
  project: ProjectOut
  refetchProject: () => unknown
}

function formatUsd(value: number): string {
  return `$${value.toFixed(2)}`
}

/**
 * Obergrenze der angezeigten Feinlabels (specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt:
 * "maximal die haeufigsten 10-15 Eintraege"). Die Kuerzung sitzt bewusst HIER und nicht im
 * Backend: der Endpunkt ist eine vollstaendige Auswertung, die Begrenzung eine reine
 * Darstellungsentscheidung gegen Ueberinformation.
 */
const MAX_FINE_LABELS_SHOWN = 15

/**
 * Die EINE "Klassifizierung"-Section auf KriterienStepPage.tsx (specs/features/0296-
 * klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-verketteter-klassifizierungs-
 * lauf-mit-laufbezogener-cloud-freigabe.md). Ersetzt die frueher getrennten Bedienelemente
 * "Kriterien-Bewertung" (inline auf der Seite) und "Remote-Kategorisierung"
 * (RemoteCategoryClassificationSection.tsx, geloescht) vollstaendig - ein Auslöser, eine
 * Statusanzeige, ein Fortschritt.
 *
 * Drei Aenderungen gegenueber dem abgeloesten Stand, die leicht als Versehen gelesen werden
 * koennten und es nicht sind:
 *
 * 1. KEIN Bestaetigungsdialog mehr vor der kostenpflichtigen Aktion. Das Design-System-Muster ist
 *    mit dieser Spec ausdruecklich zurueckgenommen und durch die dauerhaft an der Checkbox
 *    sichtbare Kostenschaetzung ersetzt - ein Dialog zeigte die Kosten erst NACH einem Klick und
 *    verschwand wieder. Bewusst in Kauf genommenes Restrisiko: bei vorausgewaehlter Checkbox
 *    loest ein einzelner Klick Cloud-Kosten aus.
 * 2. Der Hinweis "Diese Ergebnisse fliessen erst durch einen (ggf. erneuten) Kriterien-
 *    Bewertungs-Lauf ein" (Spec 0218) ist ersatzlos entfallen - die Verkettung im Backend macht
 *    ihn gegenstandslos.
 * 3. Die Aussage "laeuft vollstaendig lokal auf diesem Server" haengt jetzt am Checkbox-Zustand
 *    statt absolut dazustehen. Sie war zuvor schlicht unwahr, sobald die Cloud-Bilderkennung
 *    freigegeben war (die Sehenswuerdigkeits-Erkennung lief innerhalb der Bewertung mit).
 *
 * `useTriggerConfirmation` (etabliert fuer Scan/Score) ueberbrueckt unveraendert das Zeitfenster
 * zwischen der 202-Antwort und dem ersten Poll, der `status="running"` bestaetigt.
 */
export function ClassificationSection({ project, refetchProject }: ClassificationSectionProps) {
  const estimateQuery = useClassificationEstimateQuery(project.id)
  const fineLabelsQuery = useFineLabelsQuery(project.id)
  const triggerMutation = useTriggerClassificationMutation(project.id)

  const consentEnabled = project.cloud_vision_detection_enabled
  // Vorbelegung = projektweite Einwilligung (Akzeptanzkriterium). Ohne Einwilligung abgewaehlt UND
  // nicht setzbar - die Checkbox erteilt selbst keine Freigabe.
  const [useCloud, setUseCloud] = useState(consentEnabled)
  const cloudChecked = consentEnabled && useCloud

  const scoringRun = project.last_scoring_run
  const run = project.last_criterion_scoring_run
  const runStatus = run?.status ?? null
  const runStartedAt = run?.started_at ?? null
  const [awaitingConfirmation, setAwaitingConfirmation] = useTriggerConfirmation(
    runStatus,
    runStartedAt,
    refetchProject
  )

  const isBusy = triggerMutation.isPending || awaitingConfirmation || runStatus === 'running'
  const estimate = estimateQuery.data ?? null
  // Auslöse-Button bleibt deaktiviert, solange die Schaetzung bei ANGEWAEHLTER Cloud-Nutzung nicht
  // ladbar ist (Design-System: "kein Bypass" - keine kostenpflichtige Aktion ohne sichtbare
  // Schaetzung). Bei abgewaehlter Checkbox entstehen keine Kosten, die Schaetzung ist dann keine
  // Vorbedingung. `candidate_count === null` deckt "noch ladend" und "Fehler beim Laden" ab.
  const candidateCount = estimate?.candidate_count ?? null
  const isTriggerDisabled =
    isBusy || scoringRun === null || (cloudChecked && candidateCount === null)

  function handleTrigger(): void {
    if (isTriggerDisabled || scoringRun === null) {
      return
    }
    setAwaitingConfirmation(true)
    triggerMutation.mutate(
      { scoringRunId: scoringRun.id, useCloud: cloudChecked },
      { onError: () => setAwaitingConfirmation(false) }
    )
  }

  const triggerErrorDetail =
    triggerMutation.isError && triggerMutation.error instanceof ApiError
      ? triggerMutation.error.detail
      : triggerMutation.isError
        ? 'Fehler beim Auslösen der Klassifizierung.'
        : null

  // Waehrend der Remote-Phase liefert der Remote-Lauf die Fortschrittszahlen, waehrend der
  // Kriterien-Phase der Lauf selbst - `phase` entscheidet, welcher der beiden gemeint ist.
  const remoteRun = project.last_remote_category_classification_run
  const isRemotePhase = run?.phase === 'remote_categories'
  const progressSource = isRemotePhase ? remoteRun : run
  const photosProcessed = progressSource?.photos_processed ?? 0
  const photosTotal = progressSource?.photos_total ?? 0
  const percent = photosTotal > 0 ? Math.floor((photosProcessed / photosTotal) * 100) : 0
  const announcedDecile = Math.floor(percent / 10) * 10

  const providerLabel = estimate ? formatProviderLabel(estimate.provider) : ''
  // Die Serverreihenfolge (photo_count absteigend, Tie-Break canonical_key) wird uebernommen und
  // nur am Ende gekuerzt - die seltensten Eintraege fallen weg, nicht die haeufigsten.
  const shownFineLabels = (fineLabelsQuery.data ?? []).slice(0, MAX_FINE_LABELS_SHOWN)

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Klassifizierung</h2>
      <p className="text-sm text-text">
        Bewertet jedes verbleibende Foto nach mehreren Kriterien (Schärfe, Belichtung, Bildinhalt),
        leitet daraus eine Kategorie ab und bildet eine Rangfolge je Foto-Moment und Kategorie.
      </p>
      {/* Zustandsabhaengige Datenschutz-Aussage: die frueher absolute Formulierung "laeuft
          vollstaendig lokal auf diesem Server" war unwahr, sobald die Cloud-Bilderkennung
          freigegeben war. Sie gilt jetzt genau dann, wenn sie zutrifft. */}
      <p className="text-sm text-text" data-testid="classification-scope-text">
        {cloudChecked
          ? `Dieser Durchlauf sendet Fotos an ${providerLabel || 'den Cloud-Anbieter'} — für Kategorie-Vorschläge und die Sehenswürdigkeits-Erkennung.`
          : 'Dieser Durchlauf läuft vollständig lokal auf diesem Server — kein Foto verlässt ihn.'}
      </p>

      <div className="flex flex-col items-start gap-1">
        <Checkbox
          checked={cloudChecked}
          onCheckedChange={setUseCloud}
          disabled={!consentEnabled || isBusy}
          label="Cloud-Bilderkennung für diesen Durchlauf nutzen"
        />

        {!consentEnabled && (
          <p className="text-sm text-text">
            Cloud-Bilderkennung ist für dieses Projekt nicht aktiviert.{' '}
            <Link
              className="text-accent-strong underline-offset-4 hover:underline"
              to={`/projects/${project.id}/settings`}
            >
              In den Projekteinstellungen aktivieren
            </Link>
            .
          </p>
        )}

        {/* Die Schaetzung steht unmittelbar an der Checkbox und ersetzt dort den frueheren
            Bestaetigungsdialog (Akzeptanzkriterium "Kosten sichtbar vor dem Start"). Sie erscheint
            nur bei angewaehlter Cloud-Nutzung - bei abgewaehlter entstehen keine Kosten, ein
            Betrag waere dort irrefuehrend. */}
        {cloudChecked && estimateQuery.isSuccess && estimate && (
          <p data-testid="classification-estimate" className="text-sm text-text">
            {estimate.candidate_count === 0
              ? 'Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten.'
              : `~${estimate.candidate_count} Fotos · ~${formatUsd(estimate.estimated_cost_usd)} — Schätzung, keine exakte Abrechnung.`}
          </p>
        )}
        {cloudChecked && estimateQuery.isError && (
          <Alert onRetry={() => void estimateQuery.refetch()}>
            Kostenschätzung konnte nicht geladen werden.
          </Alert>
        )}
      </div>

      <Button type="button" onClick={handleTrigger} disabled={isTriggerDisabled} busy={isBusy}>
        {isBusy ? 'Wird klassifiziert…' : 'Klassifizierung starten'}
      </Button>

      {triggerErrorDetail && <Alert onRetry={handleTrigger}>{triggerErrorDetail}</Alert>}

      {run !== null && (
        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={runStatus} />
          {runStatus === 'running' &&
            (isRemotePhase
              ? 'Remote-Kategorisierung läuft…'
              : 'Kriterien-Bewertung läuft…')}
          {runStatus === 'success' && 'Erfolgreich klassifiziert'}
          {runStatus === 'failed' && 'Fehlgeschlagen'}
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

      {runStatus === 'failed' && <Alert onRetry={handleTrigger}>{run?.error_message}</Alert>}

      {/* Cloud-Anteil gescheitert: der Fehler wird sichtbar gemeldet UND das Ergebnis als nicht
          (vollstaendig) angereichert gekennzeichnet - beide Akzeptanzkriterien des Abschnitts
          "Fehlerverhalten" an einer Stelle. Der Lauf selbst ist dabei erfolgreich: der lokale
          Bewertungsanteil ist vollstaendig durchgelaufen. */}
      {run?.cloud_error_message != null && (
        <Alert>
          {run.cloud_error_message} Das Ergebnis ist ohne (vollständige) Cloud-Anreicherung
          entstanden.
        </Alert>
      )}

      {/* Bewusst KEIN Fehler-Styling: ein rein lokaler Durchlauf ist ein gewuenschtes Ergebnis,
          keine Stoerung - der Hinweis macht nur nachvollziehbar, woher das Ergebnis stammt. */}
      {runStatus === 'success' && run !== null && !run.cloud_requested && (
        <p className="text-sm text-text">
          Ohne Cloud-Anreicherung durchgeführt — die Cloud-Nutzung war für diesen Durchlauf
          abgewählt.
        </p>
      )}

      {/* Feinlabel-Haeufigkeitsliste (specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt):
          das Kategorien-Set ist geschlossen, aber nicht fuer immer festgelegt - haeufige
          Feinlabels sind der Hinweis darauf, dass im Set eine Kategorie fehlt, und damit der
          Aenderungspfad. */}
      <div className="flex w-full max-w-sm flex-col gap-1.5">
        <h3 className="text-sm font-medium text-text-h">Häufigste Feinlabels</h3>
        {/* Der Kontexttext behauptet, Feinlabels seien haeufig aufgetreten - er erscheint deshalb
            nur, wenn tatsaechlich welche vorliegen. Ueber dem Leerzustand ("Keine zusaetzlichen
            Label ermittelt") waere er ein Widerspruch. */}
        {shownFineLabels.length > 0 && (
          <p className="text-xs text-text">
            Diese Feinlabels traten häufig auf — möglicherweise fehlt eine Kategorie im Set.
          </p>
        )}
        {fineLabelsQuery.isPending && (
          <p className="text-sm text-text">Feinlabels werden geladen…</p>
        )}
        {fineLabelsQuery.isError && (
          <Alert onRetry={() => void fineLabelsQuery.refetch()}>
            Feinlabels konnten nicht geladen werden.
          </Alert>
        )}
        {fineLabelsQuery.isSuccess &&
          (shownFineLabels.length === 0 ? (
            <p className="text-sm text-text">Keine zusätzlichen Label ermittelt.</p>
          ) : (
            <ul aria-label="Häufigste Feinlabels" className="flex flex-col gap-1">
              {shownFineLabels.map((label) => (
                <li
                  key={label.canonical_key}
                  className="flex items-baseline justify-between gap-3 text-sm"
                >
                  {/* Reiner React-Textknoten - freier LLM-Text, nie als HTML. */}
                  <span className="truncate text-text-h">{label.display_name}</span>
                  <span className="shrink-0 text-text">{label.photo_count} Mal</span>
                </li>
              ))}
            </ul>
          ))}
      </div>
    </section>
  )
}
