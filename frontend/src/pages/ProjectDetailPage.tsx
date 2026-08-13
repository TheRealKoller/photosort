import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Progress } from '../components/ui/progress'
import {
  POLL_INTERVAL_MS,
  useProjectQuery,
  useTriggerScanMutation,
  useTriggerScoreMutation,
  useTriggerSelectTopMutation,
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
  const selectTopMutation = useTriggerSelectTopMutation(id)

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

  const topSelectionRun = query.data?.last_top_selection_run ?? null
  const topSelectionStatus = topSelectionRun?.status ?? null
  const topSelectionStartedAt = topSelectionRun?.started_at ?? null
  const [awaitingSelectTopConfirmation, setAwaitingSelectTopConfirmation] = useTriggerConfirmation(
    topSelectionStatus,
    topSelectionStartedAt,
    query.refetch
  )
  // Default 3 (UI/UX-Abschnitt der Spec) - min=1/max=10 sind nur clientseitige Hinweise
  // (native <input>-Attribute), die eigentliche Grenze wird serverseitig durchgesetzt
  // (Field(ge=1, le=10), 422 sonst). `''` ist ein bewusst erlaubter Zwischenzustand fuer ein
  // geleertes Eingabefeld (Copilot-Review-Fund, PR #51) - haette der State stattdessen sofort auf
  // den zuletzt gueltigen Wert zurueckgesetzt werden muessen, waere das kontrollierte
  // <input>-Element beim Tippen mitten im Loeschen/Neueintippen "zurueckgesprungen" (React
  // erzwingt den DOM-Wert bei jedem Render), was den naechsten Tastendruck an eine falsche
  // Cursor-Position angehaengt haette. Der leere Zwischenzustand wird erst beim tatsaechlichen
  // Start (handleTriggerSelectTop) auf den Default 3 aufgeloest, nicht schon bei jedem Tastendruck.
  const [topNPerCluster, setTopNPerCluster] = useState<number | ''>(3)
  const effectiveTopNPerCluster = topNPerCluster === '' ? 3 : topNPerCluster

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

  // Zweiphasiger Scan-Fortschritt (specs/features/0022-scan-live-fortschrittszaehler.md, erweitert
  // durch specs/features/0036-scan-performance-zweiphasig-parallel.md): `total_files` ist `null`,
  // solange die Enumerationsphase (Phase 1) noch nicht abgeschlossen ist - explizit `!== null`
  // geprueft, NIE truthy (0 ist ein gueltiger, informativer Wert fuer ein leeres Projekt, siehe
  // ADR 0020, Punkt 6). Erst danach (Phase 2, Verarbeitung) ist ein echter Nenner bekannt.
  const scanTotalFiles = project.last_scan?.total_files ?? null
  const scanFilesFound = project.last_scan?.files_found ?? 0
  const isScanEnumerating = project.last_scan?.status === 'running' && scanTotalFiles === null
  const isScanProcessing = project.last_scan?.status === 'running' && scanTotalFiles !== null
  // <progress max={0}> ist fuer native progress-Elemente ungueltig/mehrdeutig (identisches Muster
  // wie beim Scoring-/Top-Selection-Fortschritt unten) - bei total_files === 0 (leeres Projekt,
  // Phase 1 bereits abgeschlossen) bleibt der Balken deshalb indeterminiert, obwohl der Text
  // bereits "0 von 0" zeigt.
  const scanPercent =
    scanTotalFiles !== null && scanTotalFiles > 0
      ? Math.floor((scanFilesFound / scanTotalFiles) * 100)
      : 0
  // Gedrosselte aria-live-Regel (UI/UX-Abschnitt der Spec 0036, analog Scoring/Top-Selection unten)
  // - nur in der Verarbeitungsphase aktiv, mit unbekanntem Nenner in der Enumerationsphase nicht
  // sinnvoll.
  const scanAnnouncedDecile = Math.floor(scanPercent / 10) * 10

  // Verfuegbarkeitsgate (UI/UX-Abschnitt der Spec 0024): proaktiv aus bereits geladenen
  // Projektdaten abgeleitet (category_selection_enabled, last_scoring_run.status), NICHT erst
  // reaktiv nach einem fehlgeschlagenen 403/409. Bereich bleibt in beiden Faellen sichtbar, nur
  // Eingabe/Button werden deaktiviert (kein verschwindender UI-Teil).
  const isSelectTopFeatureDisabled = project.category_selection_enabled === false
  const isSelectTopPreconditionMissing = scoringStatus !== 'success'
  const isSelectTopGateDisabled = isSelectTopFeatureDisabled || isSelectTopPreconditionMissing
  const isSelectTopBusy =
    selectTopMutation.isPending ||
    awaitingSelectTopConfirmation ||
    topSelectionStatus === 'running'
  const isSelectTopDisabled = isSelectTopGateDisabled || isSelectTopBusy

  function handleTriggerSelectTop(): void {
    if (isSelectTopDisabled) {
      return
    }
    setAwaitingSelectTopConfirmation(true)
    selectTopMutation.mutate(effectiveTopNPerCluster, {
      onError: () => setAwaitingSelectTopConfirmation(false),
    })
  }

  const selectTopTriggerErrorDetail =
    selectTopMutation.isError && selectTopMutation.error instanceof ApiError
      ? selectTopMutation.error.detail
      : selectTopMutation.isError
        ? 'Fehler beim Auslösen der Top-Foto-Auswahl.'
        : null

  const candidatesProcessed = topSelectionRun?.candidates_processed ?? 0
  const candidatesTotal = topSelectionRun?.candidates_total ?? 0
  const topSelectionPercent =
    candidatesTotal > 0 ? Math.floor((candidatesProcessed / candidatesTotal) * 100) : 0
  const topSelectionAnnouncedDecile = Math.floor(topSelectionPercent / 10) * 10

  // "N unterschritten" ist ein normales Ergebnis, kein Fehler (UI/UX-Abschnitt der Spec) - kein
  // Vergleich zur angeforderten topNPerCluster-Zielanzahl im Text, analog suggestionsFoundText.
  const topSelectionSuggestionsFound = topSelectionRun?.suggestions_found ?? 0
  const topSelectionSuggestionsFoundText =
    topSelectionSuggestionsFound === 1
      ? '1 Top-Foto ausgewählt'
      : `${topSelectionSuggestionsFound} Top-Fotos ausgewählt`

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

        {isScanEnumerating && (
          <div className="flex w-full max-w-sm flex-col gap-1.5">
            <p className="text-sm text-text">Dateien werden gezählt…</p>
            <Progress />
          </div>
        )}

        {isScanProcessing && (
          <div className="flex w-full max-w-sm flex-col gap-1.5">
            <p className="text-sm text-text">
              {scanFilesFound} von {scanTotalFiles} Dateien verarbeitet
            </p>
            {scanTotalFiles !== null && scanTotalFiles > 0 ? (
              <Progress value={scanFilesFound} max={scanTotalFiles}>
                {scanFilesFound}/{scanTotalFiles}
              </Progress>
            ) : (
              <Progress />
            )}
            <p aria-live="polite" className="text-sm text-text">
              {scanAnnouncedDecile}% verarbeitet
            </p>
          </div>
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
          {isScoreBusy ? 'Wird aussortiert…' : 'Ausschuss aussortieren'}
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

        {/* specs/features/0027-vorgeschlagene-fotos-filterbar-anzeigen.md: gefilterter Link zu den
            noch unbestaetigten Vorschlaegen dieses Laufs, zusaetzlich zum generischen "Fotos
            ansehen"-Link unten - bewusst auch bei suggestions_found === 0 sichtbar (kein
            Ausblenden), da "0 gefunden" ein normales Laufergebnis ist. */}
        {scoringStatus === 'success' && (
          <Button asChild variant="secondary" size="sm">
            <Link
              to={`/projects/${project.id}/photos?filter=suggested`}
              aria-label="Vorschläge aus der Ausschuss-Aussortierung ansehen"
            >
              Vorschläge ansehen
            </Link>
          </Button>
        )}

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

      {/* Top-Fotos auswählen (specs/features/0024-top-photo-selection-category-mix.md): bewusst
          eine eigenstaendige, von der Ausschuss-Aussortierung getrennte Section - kein
          Kostenschaetzungs-Schritt, da rein lokal/kostenlos. Bereich bleibt IMMER an dieser Stelle
          sichtbar, auch wenn das Feature-Flag aus ist oder die Vorbedingung fehlt (Design-System-
          Muster "Nicht verfuegbare Aktion"). */}
      <section className="flex flex-col items-start gap-3">
        <h2 className="text-lg font-semibold text-text-h">Top-Fotos auswählen</h2>
        <p className="text-sm text-text">
          Ordnet Fotos automatisch einer Kategorie zu (Landschaft/Detail/Menschen) und wählt pro
          Foto-Moment bis zu N Top-Fotos aus — läuft vollständig lokal auf diesem Server.
        </p>

        {isSelectTopGateDisabled && (
          <p className="text-sm text-text">
            {isSelectTopFeatureDisabled
              ? 'Diese Funktion ist derzeit nicht aktiviert.'
              : 'Führe zuerst die lokale Vorauswahl oben aus.'}
          </p>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <label htmlFor="top-n-per-cluster" className="flex flex-col gap-1 text-sm text-text">
            Top-Fotos pro Foto-Moment
            <Input
              id="top-n-per-cluster"
              type="number"
              min={1}
              max={10}
              value={topNPerCluster}
              disabled={isSelectTopDisabled}
              onChange={(event) => {
                // Copilot-Review-Fund (PR #51): `Number(event.target.value)` liefert bei einem
                // geleerten Feld 0 statt NaN (anders als `valueAsNumber`), das waere unbemerkt als
                // gueltiger State-Wert durchgerutscht und haette top_n_per_cluster=0 an die API
                // gesendet (422). Ein geleertes Feld wird hier bewusst als eigener `''`-State
                // gehalten statt sofort auf den letzten gueltigen Wert zurueckzuspringen (siehe
                // Kommentar bei der State-Deklaration oben) - erst handleTriggerSelectTop loest
                // `''` auf den Default 3 auf. Getippte Werte werden auf 1..10 geklemmt (client-
                // seitige Entsprechung zu Field(ge=1, le=10), das serverseitig ohnehin gilt).
                if (event.target.value === '') {
                  setTopNPerCluster('')
                  return
                }
                const value = event.target.valueAsNumber
                if (!Number.isNaN(value)) {
                  setTopNPerCluster(Math.min(10, Math.max(1, Math.round(value))))
                }
              }}
              className="w-24"
            />
          </label>
          <Button
            type="button"
            onClick={handleTriggerSelectTop}
            disabled={isSelectTopDisabled}
            busy={isSelectTopBusy}
          >
            {isSelectTopBusy ? 'Wird ausgewählt…' : 'Auswahl starten'}
          </Button>
        </div>
        <p className="text-sm text-text">
          Pro Foto-Moment werden bis zu N Top-Fotos vorgeschlagen (weniger, falls nicht genug
          passende Motive vorhanden sind).
        </p>

        {selectTopTriggerErrorDetail && <Alert>{selectTopTriggerErrorDetail}</Alert>}

        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={topSelectionStatus} />
          {topSelectionRun === null && 'Noch nicht ausgewählt'}
          {topSelectionStatus === 'running' && 'Wird verarbeitet…'}
          {topSelectionStatus === 'success' && topSelectionSuggestionsFoundText}
          {topSelectionStatus === 'failed' && 'Fehlgeschlagen'}
        </p>

        {/* Analog zum Ausschuss-Link oben (specs/features/0027-vorgeschlagene-fotos-filterbar-
            anzeigen.md) - identischer sichtbarer Text, unterschiedliches aria-label, damit beide
            Links per Screenreader-Linkliste unterscheidbar bleiben. */}
        {topSelectionStatus === 'success' && (
          <Button asChild variant="secondary" size="sm">
            <Link
              to={`/projects/${project.id}/photos?filter=suggested`}
              aria-label="Vorschläge aus der Top-Foto-Auswahl ansehen"
            >
              Vorschläge ansehen
            </Link>
          </Button>
        )}

        {topSelectionStatus === 'running' && (
          <div className="flex w-full max-w-sm flex-col gap-1.5">
            <p className="text-sm text-text">
              {candidatesProcessed} von {candidatesTotal} Fotos verarbeitet
            </p>
            {candidatesTotal > 0 ? (
              <Progress value={candidatesProcessed} max={candidatesTotal}>
                {candidatesProcessed}/{candidatesTotal}
              </Progress>
            ) : (
              <Progress />
            )}
            <p aria-live="polite" className="text-sm text-text">
              {topSelectionAnnouncedDecile}% verarbeitet
            </p>
          </div>
        )}

        {topSelectionStatus === 'failed' && (
          <Alert onRetry={handleTriggerSelectTop}>{topSelectionRun?.error_message}</Alert>
        )}
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
