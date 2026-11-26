import { useCallback, useMemo } from 'react'
import { useNavigate, useOutletContext, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import { AusschussActionBar } from '../../components/AusschussActionBar'
import { AusschussDetail } from '../../components/AusschussDetail'
import { Alert } from '../../components/ui/alert'
import { AusschussOverview } from '../../components/AusschussOverview'
import { AusschussRecognition } from '../../components/AusschussRecognition'
import { useAusschussQuery } from '../../hooks/useAusschuss'
import { useCancelOperation } from '../../hooks/useOperations'
import { useConfirmAusschussGateMutation, useTriggerScoreMutation } from '../../hooks/useProjects'
import { useTriggerConfirmation } from '../../hooks/useTriggerConfirmation'
import { useElementWidth } from '../../hooks/useElementWidth'
import {
  GRID_GAP_PX,
  MIN_ROW_HEIGHT_PX,
  TARGET_ROW_HEIGHT_PX,
  justifiedRows,
  naturalTiles,
} from '../../utils/justifiedRows'
import type { JustifiedTile } from '../../utils/justifiedRows'
import {
  CANCEL_TEXTS,
  cancelRequestedText,
  cancelledText,
  waitingText,
} from '../../utils/operationTexts'
import { deriveStepAction } from '../../utils/stepActions'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/** Der `photo`-Parameter der Schritt-Route. Alles ausserhalb einer positiven ganzen Zahl ist
 * KEIN Fehler, sondern die Uebersicht: Ein Deep-Link ohne gueltige Aufnahme ist ein regulaerer
 * Zustand mit definierter Antwort, kein leerer Screen. */
function parsePhotoParam(raw: string | null): number | null {
  if (raw === null || raw === '') {
    return null
  }
  const wert = Number(raw)
  return Number.isInteger(wert) && wert >= 1 ? wert : null
}

/**
 * Der Ausschuss-Schritt: Erkennung, Uebersicht und Abschluss an EINER Stelle.
 *
 * EIN EINSTIEG: Der Schritt stoesst das Aussortieren an und fuehrt danach unmittelbar in die
 * Uebersicht seiner eigenen Bilder - die Uebersicht ist eine eigene Ansicht und kein Filter der
 * Fotoliste. Die Bestaetigung gibt den naechsten Schritt frei.
 *
 * DIE DETAILANSICHT IST DIESELBE SEITE, kein Dialog und keine zweite Route: Sie haengt
 * am `?photo=<id>`-Parameter der Schritt-Route, damit ein Deep-Link auf eine Aufnahme teilbar und
 * der Browser-Zurueck-Knopf der Weg zurueck in die Uebersicht ist.
 *
 * DER TRIGGER IST NICHT AN `last_scan.status` GEKOPPELT.
 */
export function AusschussStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()
  const [searchParams, setSearchParams] = useSearchParams()
  const scoreMutation = useTriggerScoreMutation(project.id)
  const confirmMutation = useConfirmAusschussGateMutation(project.id)
  const cancelMutation = useCancelOperation(project.id)
  const navigate = useNavigate()

  const scoringRun = project.last_scoring_run ?? null
  const scoringStatus = scoringRun?.status ?? null
  // Der Abbruch adressiert GENAU diesen Lauf.
  const scoringRunId = scoringRun?.id ?? null
  const isCancelRequested = scoringRun?.cancel_requested_at != null
  const scoringStartedAt = scoringRun?.started_at ?? null
  const [awaitingScoreConfirmation, setAwaitingScoreConfirmation] = useTriggerConfirmation(
    scoringStatus,
    scoringStartedAt,
    refetchProject,
  )

  const detailPhotoId = parsePhotoParam(searchParams.get('photo'))
  const autoFilter = searchParams.get('auto') === '1'
  // Nur nach einem erfolgreichen Lauf: Ohne ihn gibt es keine Vorschlaege und damit keinen
  // Bestand - jeder Aufruf dieses Schritts setzte sonst eine Anfrage ab, die nichts beantworten
  // kann. Die Abfrage bleibt auch in der Detailansicht geladen, damit die Rueckkehr in die
  // Uebersicht die bereits geholten Seiten behaelt.
  const ausschussQuery = useAusschussQuery(project.id, {
    enabled: scoringStatus === 'success',
    autoDecided: autoFilter,
  })

  const { ref: gridRef, width: containerWidth } = useElementWidth<HTMLUListElement>()

  // Einzel-Eintraege und Stapel stehen im selben Raster; gezaehlt wird nach Eintraegen.
  const entries = useMemo(
    () => ausschussQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [ausschussQuery.data],
  )
  const total = ausschussQuery.data?.pages[0]?.total ?? 0
  // `null`, solange der Bestand nicht geladen ist - die Abschluss-Aktion steht dann ohne Anzahl.
  const openCount = ausschussQuery.data?.pages[0]?.open_count ?? null
  // Projektweit und damit auch in der gefilterten Ansicht dieselbe Zahl.
  const autoDecidedGroupCount = ausschussQuery.data?.pages[0]?.auto_decided_group_count ?? null

  const tiles = useMemo(() => {
    const ratios = entries.map(
      (eintrag) => (eintrag.kind === 'photo' ? eintrag.photo : eintrag.cover).aspect_ratio ?? null,
    )
    if (containerWidth <= 0) {
      return new Map(naturalTiles(ratios, TARGET_ROW_HEIGHT_PX).map((tile) => [tile.index, tile]))
    }
    const rows = justifiedRows({
      ratios,
      containerWidth,
      gap: GRID_GAP_PX,
      targetRowHeight: TARGET_ROW_HEIGHT_PX,
      minRowHeight: MIN_ROW_HEIGHT_PX,
    })
    return new Map<number, JustifiedTile>(
      rows.flatMap((row) => row.tiles.map((tile) => [tile.index, tile] as const)),
    )
  }, [entries, containerWidth])

  const isTriggerPending = scoreMutation.isPending || awaitingScoreConfirmation
  const isScoreBusy = isTriggerPending || scoringStatus === 'running' || scoringStatus === 'queued'
  const { action, rerun } = deriveStepAction('ausschuss', project, { openCount, isTriggerPending })

  function handleTriggerScore(): void {
    if (isScoreBusy) {
      return
    }
    setAwaitingScoreConfirmation(true)
    scoreMutation.mutate(undefined, {
      onError: () => setAwaitingScoreConfirmation(false),
    })
  }

  function handleCancelScoring(): void {
    if (scoringRunId !== null) {
      cancelMutation.mutate({ kind: 'ausschuss', runId: scoringRunId })
    }
  }

  /* Gewechselt wird erst nach dem Neuladen des Projekts: Mit dem alten Stand
     (`gate_confirmed_at === null`) leitete der Guard des Layouts sofort zum Ausschuss zurück. Der
     Callback gilt nur diesem Aufruf und entfällt, wenn die Seite vor der Antwort verlassen wurde.
     Das Ziel kommt aus der Ableitung, nie aus Adresse oder Verlauf (offene Weiterleitung). */
  function handleConfirm(): void {
    confirmMutation.mutate(undefined, {
      onSuccess: async () => {
        const { data } = await refetchProject()
        if (data === undefined) {
          return
        }
        const next = deriveStepAction('ausschuss', data, {
          openCount: 0,
          isTriggerPending: false,
        }).action
        if (next.kind === 'next') {
          void navigate(next.to, { state: { focusHeading: true } })
        }
      },
    })
  }

  /* Push, kein `replace`: Der Zurueck-Knopf des Browsers ist damit die Rueckkehr in die
     Detailansicht, und `?photo` bleibt als teilbare Adresse in der Leiste stehen. */
  const openDetail = useCallback(
    (photoId: number) => {
      const next = new URLSearchParams(searchParams)
      next.set('photo', String(photoId))
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  const closeDetail = useCallback(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('photo')
    setSearchParams(next)
  }, [searchParams, setSearchParams])

  const scoreTriggerErrorDetail =
    scoreMutation.isError && scoreMutation.error instanceof ApiError
      ? scoreMutation.error.detail
      : scoreMutation.isError
        ? 'Fehler beim Auslösen der automatischen Vorauswahl.'
        : null

  const photosProcessed = scoringRun?.photos_processed ?? 0
  const photosTotal = scoringRun?.photos_total ?? 0
  const scoringPercent = photosTotal > 0 ? Math.floor((photosProcessed / photosTotal) * 100) : 0
  const scoringAnnouncedDecile = Math.floor(scoringPercent / 10) * 10

  const suggestionsFound = scoringRun?.suggestions_found ?? 0
  const suggestionsFoundText =
    suggestionsFound === 1 ? '1 Vorschlag gefunden' : `${suggestionsFound} Vorschläge gefunden`

  const gateConfirmedAt = scoringRun?.gate_confirmed_at ?? null
  const istDetailansicht = scoringStatus === 'success' && detailPhotoId !== null

  let statusText: string
  switch (action.kind) {
    case 'start':
      statusText =
        scoringStatus === 'cancelled' ? cancelledText('ausschuss') : 'Noch nicht vorgeschlagen'
      break
    case 'queued':
      statusText = isCancelRequested ? cancelRequestedText('ausschuss') : waitingText('ausschuss')
      break
    case 'running':
      statusText = isCancelRequested
        ? cancelRequestedText('ausschuss')
        : scoringStatus === 'running'
          ? `Ausschuss läuft… ${scoringAnnouncedDecile}% verarbeitet`
          : 'Ausschuss läuft…'
      break
    case 'retry':
      statusText = 'Ausschuss fehlgeschlagen'
      break
    case 'confirm':
      statusText =
        openCount === null
          ? 'Abschluss offen'
          : openCount === 0
            ? 'Alle Vorschläge entschieden'
            : openCount === 1
              ? '1 Vorschlag offen'
              : `${openCount} Vorschläge offen`
      break
    default:
      statusText = 'Ausschuss bestätigt'
  }

  // „wartet" traegt keinen Statuspunkt - es laeuft noch nichts. Nach dem Ausloesen zeigt der
  // Punkt sofort den laufenden Zustand, nicht den alten.
  const statusDot =
    action.kind === 'running' ? 'running' : action.kind === 'queued' ? null : scoringStatus

  return (
    <section className="flex flex-col items-start gap-3">
      <AusschussRecognition
        projectId={project.id}
        rerun={rerun}
        onRerun={handleTriggerScore}
        disabled={isScoreBusy}
        busy={isTriggerPending}
        triggerError={scoreTriggerErrorDetail}
        scoringStatus={scoringStatus}
        suggestionsFoundText={suggestionsFoundText}
        autoDecidedGroupCount={
          !autoFilter && ausschussQuery.isSuccess ? autoDecidedGroupCount : null
        }
        gateConfirmedAt={gateConfirmedAt}
        errorMessage={scoringRun?.error_message}
      />

      {istDetailansicht ? (
        <AusschussDetail projectId={project.id} photoId={detailPhotoId} onClose={closeDetail} />
      ) : (
        scoringStatus === 'success' && (
          <AusschussOverview
            autoFilter={autoFilter}
            loading={ausschussQuery.isLoading}
            error={ausschussQuery.isError ? ausschussQuery.error : null}
            empty={ausschussQuery.isSuccess && entries.length === 0}
            entries={entries}
            total={total}
            hasNextPage={ausschussQuery.hasNextPage}
            isFetchingNextPage={ausschussQuery.isFetchingNextPage}
            gridRef={gridRef}
            tiles={tiles}
            projectId={project.id}
            onOpen={openDetail}
            onLoadMore={() => void ausschussQuery.fetchNextPage()}
            onRetry={() => void ausschussQuery.refetch()}
          />
        )
      )}

      {confirmMutation.isError && (
        <Alert>
          {confirmMutation.error instanceof ApiError
            ? confirmMutation.error.detail
            : 'Fehler beim Bestätigen des Ausschusses.'}
        </Alert>
      )}

      {cancelMutation.isError && (
        <Alert onRetry={handleCancelScoring} retryLabel={CANCEL_TEXTS.retry}>
          {CANCEL_TEXTS.failed}
        </Alert>
      )}

      <AusschussActionBar
        action={action}
        statusDot={statusDot}
        statusText={statusText}
        photosProcessed={photosProcessed}
        photosTotal={photosTotal}
        scoringStatus={scoringStatus}
        onAction={action.kind === 'confirm' ? handleConfirm : handleTriggerScore}
        busy={action.kind === 'confirm' && confirmMutation.isPending}
        onCancel={handleCancelScoring}
        cancelRequested={isCancelRequested}
        cancelPending={cancelMutation.isPending}
        cancelFocusToken={cancelMutation.data ?? null}
      />
    </section>
  )
}
