import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Progress } from '../components/ui/progress'
import {
  POLL_INTERVAL_MS,
  useProjectQuery,
  useTriggerScanMutation,
  useTriggerScoreMutation,
} from '../hooks/useProjects'
import { PROCESS_STATUS_DOT_CLASSES } from '../utils/processStatus'
import type { ProcessStatus } from '../utils/processStatus'

/**
 * UX-/Architect-Review-Fund (Branch feature/0012-visual-redesign-views): faerbte urspruenglich den
 * sichtbaren Statustext direkt ein (`text-status-*`) - `--status-success`/`--status-failed` sind
 * aber nur als Flaechenfarbe kalibriert, nicht als Text-/Symbolfarbe (WCAG-AA gegen `--bg`
 * verfehlt, siehe architecture/0004-design-system.md, Abschnitt Farbpalette). Gleiches Muster wie
 * ProjectListPage jetzt auch hier: nur ein dekorativer, `aria-hidden` Punkt traegt die Farbe, der
 * Text daneben bleibt neutral (`text-text`/`text-text-h`).
 */
function StatusDot({ status }: { status: ProcessStatus | null | undefined }) {
  return (
    <span
      aria-hidden="true"
      className={`size-2.5 shrink-0 rounded-full ${status ? PROCESS_STATUS_DOT_CLASSES[status] : 'bg-border'}`}
    />
  )
}

/**
 * Ueberbrueckt das Zeitfenster zwischen erfolgreichem Trigger (202) und dem ersten Poll, der den
 * neuen Scan-/Scoring-Lauf tatsaechlich bestaetigt (siehe
 * specs/features/0005-minimal-project-frontend.md und
 * specs/features/0003-automatic-best-photo-selection.md: Button bleibt deaktiviert, "bis entweder
 * Polling running bestaetigt oder der Trigger selbst fehlschlaegt"). Nur auf status==="running" zu
 * warten reicht NICHT, aus zwei Gruenden:
 *
 * 1. Bei einem bereits zuvor gelaufenen Projekt ist der beobachtete Status VOR dem Klick schon
 *    nicht-null (z.B. "failed" vom letzten Lauf) - der Worker setzt status="running" erst
 *    asynchron (backend/src/photosort/worker.py), der Invalidierungs-Refetch direkt nach der
 *    202-Antwort kann also noch den ALTEN Status liefern.
 * 2. Fast-Path (Bugfix specs/features/0017-trigger-bridge-fast-path-fix.md): laeuft der Job im
 *    Worker so schnell durch, dass zwischen dem Setzen von status="running" und dem finalen
 *    Commit kein einziger await-Punkt liegt (z.B. Scoring bei photos_total < 25 ==
 *    SCORE_COMMIT_BATCH_SIZE, ~6ms Laufzeit) - weit unter dem 2-Sekunden-Poll-Intervall. Der
 *    Zwischenzustand "running" wird dann nie beobachtet, der Status springt direkt von null auf
 *    "success"/"failed".
 *
 * Ein blosses `status !== null` wuerde AC1 zwar erfuellen, aber Grund 1 wieder aufreissen: bei
 * einem erneuten, ebenso schnellen Lauf auf einem bereits zuvor gelaufenen Projekt kann der
 * unmittelbare Invalidierungs-Refetch noch denselben (stale) Endzustand vom VORHERIGEN Lauf
 * liefern (z.B. wieder "failed") - der wuerde dann faelschlich als Bestaetigung des NEUEN Laufs
 * durchgehen. Da jeder Lauf serverseitig einen frischen `started_at`-Zeitstempel bekommt (neue
 * ScanRun/ScoringRun-Zeile, backend/src/photosort/worker.py), dient ein Vergleich des zuletzt vor
 * dem Klick beobachteten `started_at` gegen den aktuell beobachteten als zuverlaessiges
 * Unterscheidungsmerkmal zwischen "frischer, neuer Lauf" und "stehengebliebener, stale Status vom
 * vorherigen Lauf" - technische Detailentscheidung innerhalb der akzeptierten Spec 0017, die deren
 * "Entwurfsentscheidung 2" (Reset bei success/failed) mit der bereits bestehenden
 * Anti-Regressions-Testerwartung (Grund 1) vereinbar macht. Das awaiting-Flag wird deshalb
 * zurueckgesetzt, sobald "running" beobachtet wird (kann nie ein stale Wert sein, das Projekt
 * kann nicht schon vor dem Klick "running" gewesen sein) ODER sobald ein NEUER `started_at`
 * zusammen mit einem beliebigen Endzustand (success/failed) beobachtet wird. Architect-Review-Fund
 * (Spec 0017): eine Kollision zweier `started_at`-Werte (alter und neuer Lauf identisch) ist
 * praktisch ausgeschlossen, da Postgres `func.now()` Mikrosekunden-Praezision liefert und der
 * Button ohnehin waehrend des Wartens deaktiviert ist - vernachlaessigbares Restrisiko, kein Fix
 * noetig.
 *
 * Dateilokal statt exportiert (nicht in hooks/useProjects.ts): das Muster wird aktuell
 * nachweislich nur hier zweimal gebraucht (Scan-Trigger, Scoring-Trigger, per grep verifiziert) -
 * eine Auslagerung als wiederverwendbarer, exportierter Hook waere Spekulation auf einen dritten
 * Konsumenten, den es nicht gibt (siehe Spec 0017, Entwurfsentscheidung 1).
 */
function useTriggerConfirmation(
  status: ProcessStatus | null,
  startedAt: string | null,
  refetch: () => unknown
): [boolean, (value: boolean) => void] {
  const [awaiting, setAwaiting] = useState(false)

  // Ref statt Abhaengigkeit auf `refetch` selbst: `query.refetch` ist bei jedem Render eine neue
  // Funktionsreferenz, eine Abhaengigkeit darauf wuerde das Intervall bei jedem Render neu
  // aufsetzen. Bewusst als lokaler `useRef` INNERHALB des Hooks (statt als von aussen
  // hereingereichter Ref-Parameter) - so kann das react-hooks-Lint-Plugin die Stabilitaet der Ref
  // selbst erkennen, statt sie faelschlich als fehlende Abhaengigkeit zu melden.
  const refetchRef = useRef(refetch)
  refetchRef.current = refetch

  // Wird bei jedem Render aktualisiert, SOLANGE nicht gewartet wird - friert dadurch beim
  // Setzen von awaiting=true (Klick) automatisch auf den zuletzt bekannten, "alten" started_at
  // ein (gleiches Ref-statt-Effect-Update-Muster wie oben bei refetchRef).
  const baselineStartedAtRef = useRef(startedAt)
  if (!awaiting) {
    baselineStartedAtRef.current = startedAt
  }

  useEffect(() => {
    if (!awaiting) {
      return
    }
    const isNewRun = startedAt !== baselineStartedAtRef.current
    if (status === 'running' || (status !== null && isNewRun)) {
      setAwaiting(false)
      return
    }
    const interval = setInterval(() => {
      void refetchRef.current()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [awaiting, status, startedAt])

  return [awaiting, setAwaiting]
}

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const query = useProjectQuery(id)
  const scanMutation = useTriggerScanMutation(id)
  const scoreMutation = useTriggerScoreMutation(id)

  const scanStatus = query.data?.last_scan?.status ?? null
  const scanStartedAt = query.data?.last_scan?.started_at ?? null
  const [awaitingConfirmation, setAwaitingConfirmation] = useTriggerConfirmation(
    scanStatus,
    scanStartedAt,
    query.refetch
  )

  const scoringRun = query.data?.last_scoring_run ?? null
  const scoringStatus = scoringRun?.status ?? null
  const scoringStartedAt = scoringRun?.started_at ?? null
  const [awaitingScoreConfirmation, setAwaitingScoreConfirmation] = useTriggerConfirmation(
    scoringStatus,
    scoringStartedAt,
    query.refetch
  )

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Projekt nicht gefunden.</p>
        <Button asChild variant="ghost">
          <Link to="/">Zurück zur Projektliste</Link>
        </Button>
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text">
        Projekt wird geladen…
      </p>
    )
  }

  if (query.isError || !query.data) {
    return (
      <div className="flex flex-col items-start gap-3">
        <Alert>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden des Projekts.'}
        </Alert>
        <Button asChild variant="ghost">
          <Link to="/">Zurück zur Projektliste</Link>
        </Button>
      </div>
    )
  }

  const project = query.data
  const isBusy = scanMutation.isPending || awaitingConfirmation || scanStatus === 'running'

  function handleTriggerScan(): void {
    if (isBusy) {
      return
    }
    setAwaitingConfirmation(true)
    scanMutation.mutate(undefined, {
      onError: () => setAwaitingConfirmation(false),
    })
  }

  const triggerErrorDetail =
    scanMutation.isError && scanMutation.error instanceof ApiError
      ? scanMutation.error.detail
      : scanMutation.isError
        ? 'Fehler beim Auslösen des Scans.'
        : null

  const isScoreBusy =
    scoreMutation.isPending || awaitingScoreConfirmation || scoringStatus === 'running'

  function handleTriggerScore(): void {
    if (isScoreBusy) {
      return
    }
    setAwaitingScoreConfirmation(true)
    scoreMutation.mutate(undefined, {
      onError: () => setAwaitingScoreConfirmation(false),
    })
  }

  const scoreTriggerErrorDetail =
    scoreMutation.isError && scoreMutation.error instanceof ApiError
      ? scoreMutation.error.detail
      : scoreMutation.isError
        ? 'Fehler beim Auslösen der automatischen Vorauswahl.'
        : null

  const photosProcessed = scoringRun?.photos_processed ?? 0
  const photosTotal = scoringRun?.photos_total ?? 0
  const scoringPercent = photosTotal > 0 ? Math.floor((photosProcessed / photosTotal) * 100) : 0
  // Gedrosselte aria-live-Regel fuer hochfrequente Zaehler (UI/UX-Abschnitt der Spec): der
  // Screenreader bekommt nur bei vollen 10%-Schritten eine neue Ansage, nicht bei jedem
  // Poll-Tick - die exakte "X von Y"-Zeile darunter aktualisiert sich weiterhin bei jedem Poll,
  // ist aber bewusst NICHT Teil der aria-live-Region.
  const scoringAnnouncedDecile = Math.floor(scoringPercent / 10) * 10

  // Ersetzt den vormals generischen "Vorschläge aktualisiert"-Text durch die tatsächliche Anzahl
  // gefundener Vorschläge (specs/features/0021-scoring-run-vorschlagszaehler.md) - Singular nur
  // bei genau einem Treffer, sonst Plural, kein Sondertext bei 0 (UI/UX-Abschnitt der Spec).
  const suggestionsFound = scoringRun?.suggestions_found ?? 0
  const suggestionsFoundText =
    suggestionsFound === 1
      ? '1 Vorschlag gefunden'
      : `${suggestionsFound} Vorschläge gefunden`

  // Live-Fortschrittszaehler waehrend eines laufenden Scans (specs/features/0022-scan-live-
  // fortschrittszaehler.md) - bewusst OHNE Nenner/Progress-Element, da die Gesamtdateizahl beim
  // lazy OpenCloud-Ordnerdurchlauf vorab nicht bekannt ist. Singular/Plural-Regel analog
  // suggestionsFoundText oben (Spec 0021).
  const filesFound = project.last_scan?.files_found ?? 0
  const filesFoundText =
    filesFound === 1 ? '1 Datei verarbeitet' : `${filesFound} Dateien verarbeitet`

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-text-h">{project.name}</h1>
        <p className="text-sm text-text">{project.opencloud_path}</p>
      </header>

      <section className="flex flex-col items-start gap-3">
        <Button type="button" onClick={handleTriggerScan} disabled={isBusy} busy={isBusy}>
          {isBusy ? 'Scan läuft…' : 'Aktualisieren'}
        </Button>

        {triggerErrorDetail && <Alert>{triggerErrorDetail}</Alert>}

        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={project.last_scan?.status} />
          {project.last_scan === null && 'Noch nicht gescannt'}
          {project.last_scan?.status === 'running' && 'Scan läuft…'}
          {project.last_scan?.status === 'success' && 'Erfolgreich'}
          {project.last_scan?.status === 'failed' && 'Fehlgeschlagen'}
        </p>

        {project.last_scan?.status === 'running' && (
          <p className="text-sm text-text">{filesFoundText}</p>
        )}

        {project.last_scan?.status === 'success' && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-text sm:grid-cols-3">
            <dt className="text-text">Hinzugefügt</dt>
            <dd className="text-text-h">{project.last_scan.photos_added}</dd>
            <dt className="text-text">Aktualisiert</dt>
            <dd className="text-text-h">{project.last_scan.photos_updated}</dd>
            <dt className="text-text">Entfernt</dt>
            <dd className="text-text-h">{project.last_scan.photos_removed}</dd>
            <dt className="text-text">Übersprungen</dt>
            <dd className="text-text-h">{project.last_scan.files_skipped}</dd>
            <dt className="text-text">Dateien gefunden</dt>
            <dd className="text-text-h">{project.last_scan.files_found}</dd>
          </dl>
        )}

        {project.last_scan?.status === 'failed' && (
          <Alert>{project.last_scan.error_message}</Alert>
        )}
      </section>

      <section className="flex flex-col items-start gap-3">
        <Button type="button" onClick={handleTriggerScore} disabled={isScoreBusy} busy={isScoreBusy}>
          {isScoreBusy ? 'Wird vorgeschlagen…' : 'Beste Fotos automatisch vorschlagen'}
        </Button>

        {scoreTriggerErrorDetail && <Alert>{scoreTriggerErrorDetail}</Alert>}

        {/* aria-live="polite" mit bewusst STABILEM Text waehrend "running" (UI/UX-Review-Fund):
            vorher stand der sich bei jedem Poll aendernde "X von Y"-Zaehler direkt in dieser
            aria-live-Zeile - das haette die 10%-Drosselung unten wirkungslos gemacht, da diese
            Zeile trotzdem bei jedem Tick neu angesagt worden waere. Aendert sich hier nur beim
            Uebergang zwischen Zustaenden (null -> running -> success/failed), nicht bei jedem Poll -
            dadurch wird ein abgeschlossener oder fehlgeschlagener Lauf zuverlaessig angesagt, ohne
            waehrend des Laufs selbst zu spammen. Der exakte Zaehler lebt separat unten. */}
        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={scoringStatus} />
          {scoringRun === null && 'Noch nicht vorgeschlagen'}
          {scoringStatus === 'running' && 'Wird verarbeitet…'}
          {scoringStatus === 'success' && suggestionsFoundText}
          {scoringStatus === 'failed' && 'Fehlgeschlagen'}
        </p>

        {scoringStatus === 'running' && (
          <div className="flex w-full max-w-sm flex-col gap-1.5">
            <p className="text-sm text-text">
              {photosProcessed} von {photosTotal} Fotos verarbeitet
            </p>
            {/* Copilot-Review-Fund (PR #6): direkt nach dem Trigger ist der Status bereits
                "running", aber photos_total kann noch kurz 0 sein (wird im Worker erst NACH dem
                Anlegen des ScoringRun gesetzt) - <progress max={0}> ist fuer native
                progress-Elemente ungueltig/mehrdeutig. Solange photosTotal 0 ist, daher bewusst ein
                indeterminiertes <progress/> ohne value/max statt eines irrefuehrenden 0/0-Balkens. */}
            {photosTotal > 0 ? (
              <Progress value={photosProcessed} max={photosTotal}>
                {photosProcessed}/{photosTotal}
              </Progress>
            ) : (
              <Progress />
            )}
            <p aria-live="polite" className="text-sm text-text">
              {scoringAnnouncedDecile}% verarbeitet
            </p>
          </div>
        )}

        {/* Keine !isScoreBusy-Gate mehr (Spec 0017): sie unterdrueckte die Fehleranzeige bei
            ebenso schnell fehlschlagenden Laeufen, analog zur bereits ungegateten
            Scan-Fehleranzeige oben in dieser Datei. */}
        {scoringStatus === 'failed' && <Alert onRetry={handleTriggerScore}>{scoringRun?.error_message}</Alert>}
      </section>

      <nav aria-label="Fotos" className="flex flex-wrap gap-3">
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/photos`}>Fotos ansehen</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/compare`}>Bewertungen vergleichen</Link>
        </Button>
      </nav>

      <Button asChild variant="ghost" className="self-start">
        <Link to="/">Zurück zur Projektliste</Link>
      </Button>
    </div>
  )
}
