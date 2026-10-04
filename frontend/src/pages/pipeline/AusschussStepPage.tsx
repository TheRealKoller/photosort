import { useCallback, useEffect, useMemo } from 'react'
import { Link, useNavigate, useOutletContext, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { AusschussPhotoEntry, DuplicateDecision } from '../../api/types'
import { GrundKennzeichen } from '../../components/AusschussGrund'
import { DUPLICATE_IMMUTABLE_TEXT, DUPLICATE_ZUSTAENDE } from '../../components/DuplicatePhotoTile'
import { DuplicateStackTile } from '../../components/DuplicateStackTile'
import { PhotoImage } from '../../components/PhotoImage'
import { RerunBlock } from '../../components/RerunBlock'
import { StatusDot } from '../../components/StatusDot'
import { StepActionBar } from '../../components/StepActionBar'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Progress } from '../../components/ui/progress'
import { Skeleton } from '../../components/ui/skeleton'
import { useAusschussEntryQuery, useAusschussQuery } from '../../hooks/useAusschuss'
import { useDuplicateDecisionMutation } from '../../hooks/useDuplicates'
import { useConfirmAusschussGateMutation, useTriggerScoreMutation } from '../../hooks/useProjects'
import { useTriggerConfirmation } from '../../hooks/useTriggerConfirmation'
import { useElementWidth } from '../../hooks/useElementWidth'
import { cn } from '../../lib/utils'
import { formatDateTime } from '../../utils/formatStats'
import {
  GRID_GAP_PX,
  MIN_ROW_HEIGHT_PX,
  TARGET_ROW_HEIGHT_PX,
  justifiedRows,
  naturalTiles,
} from '../../utils/justifiedRows'
import type { JustifiedTile } from '../../utils/justifiedRows'
import { duplicateComparePath } from '../../utils/projectRoutes'
import { deriveStepAction } from '../../utils/stepActions'
import { AUSSCHUSS_NOTHING_SORTED_TEXT } from '../../utils/stepActionTexts'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln" -
// dieselbe Annaeherung wie in der Fotoliste, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

/** Der leere Bestand - dauerhaft sichtbar statt als fluechtiger Hinweis (AK14). Er deckt beide
 * Faelle ab, in denen nichts zu sichten ist: Der Lauf hat keinen Ausschuss gefunden, oder es gibt
 * noch gar keinen erfolgreichen Lauf mit Vorschlaegen. */
export const AUSSCHUSS_EMPTY_TEXT = 'Kein Ausschuss gefunden — es gibt derzeit nichts zu sichten.'

/** Der benannte Zustand der Detailansicht, wenn die Aufnahme nicht (mehr) im Bestand liegt: Die
 * Antwort des `photo_id`-Filters ist leer, weil ein neuer Lauf die Entscheidung aufgeloest hat -
 * kein Fehler, sondern ein definierter Zustand mit Rueckweg. */
export const AUSSCHUSS_MISSING_ENTRY_TEXT =
  'Diese Aufnahme gehört nicht mehr zum Ausschuss. Möglicherweise hat ein neuer Lauf sie aufgelöst.'

/** Die Entscheidungszeile eines noch offenen Eintrags (AK14/AK4): Die Zeile trennt den GRUND der
 * Markierung von der getroffenen ENTSCHEIDUNG. */
export const AUSSCHUSS_OPEN_LABEL = 'Vorgeschlagen'

/** Die Farbe der Entscheidungszeile. `null` (noch offen) ist zurueckhaltend: Es ist der Zustand
 * ohne Handlung, nicht einer mit. */
const ENTSCHEIDUNG_SCHRIFT: Record<DuplicateDecision | 'offen', string> = {
  keep: 'text-accent',
  discard: 'text-danger-text',
  offen: 'text-text-muted',
}

/** Der gespeicherte Zeilenwert als Wort. `null` heisst "noch nicht entschieden" - es gibt keine
 * Ruecknahme, und die Ansicht bietet deshalb auch keine an (ADR 0111). */
function entscheidungswort(decision: DuplicateDecision | null): string {
  return decision === null ? AUSSCHUSS_OPEN_LABEL : DUPLICATE_ZUSTAENDE[decision].text
}

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
 * Der Ausschuss-Schritt: Erkennung, Uebersicht und Abschluss an EINER Stelle (Spec 0525).
 *
 * ZWEI EINSTIEGE WAREN GESTERN, EINER IST HEUTE: Der Schritt stoesst das Aussortieren an und
 * fuehrt danach unmittelbar in die Uebersicht seiner eigenen Bilder (AK2) - die Uebersicht ist
 * eine eigene Ansicht und kein Filter der Fotoliste (AK3). Der frueher eigene Ausschuss-Gate-
 * Schritt ist mit der Zusammenlegung entfallen: Erkennung und Sichtung sind eine Einheit, und die
 * Bestaetigung gibt den naechsten Schritt frei (AK13).
 *
 * DIE DETAILANSICHT IST DIESELBE SEITE, kein Dialog und keine zweite Route (AK5/AK8): Sie haengt
 * am `?photo=<id>`-Parameter der Schritt-Route, damit ein Deep-Link auf eine Aufnahme teilbar und
 * der Browser-Zurueck-Knopf der Weg zurueck in die Uebersicht ist.
 *
 * DER TRIGGER BLEIBT BEWUSST UNGEGATET: Er war nie an `last_scan.status` gekoppelt, und die
 * Zusammenlegung fuehrt hier kein neues Gate ein.
 */
export function AusschussStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()
  const [searchParams, setSearchParams] = useSearchParams()
  const scoreMutation = useTriggerScoreMutation(project.id)
  const confirmMutation = useConfirmAusschussGateMutation(project.id)
  const navigate = useNavigate()

  const scoringRun = project.last_scoring_run ?? null
  const scoringStatus = scoringRun?.status ?? null
  const scoringStartedAt = scoringRun?.started_at ?? null
  const [awaitingScoreConfirmation, setAwaitingScoreConfirmation] = useTriggerConfirmation(
    scoringStatus,
    scoringStartedAt,
    refetchProject,
  )

  const detailPhotoId = parsePhotoParam(searchParams.get('photo'))
  // Nur nach einem erfolgreichen Lauf: Ohne ihn gibt es keine Vorschlaege und damit keinen
  // Bestand - jeder Aufruf dieses Schritts setzte sonst eine Anfrage ab, die nichts beantworten
  // kann. Die Abfrage bleibt auch in der Detailansicht geladen, damit die Rueckkehr in die
  // Uebersicht die bereits geholten Seiten behaelt.
  const ausschussQuery = useAusschussQuery(project.id, { enabled: scoringStatus === 'success' })

  const { ref: gridRef, width: containerWidth } = useElementWidth<HTMLUListElement>()

  // Einzel-Eintraege und Stapel stehen im selben Raster; gezaehlt wird nach Eintraegen.
  const entries = useMemo(
    () => ausschussQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [ausschussQuery.data],
  )
  const total = ausschussQuery.data?.pages[0]?.total ?? 0
  // `null`, solange der Bestand nicht geladen ist - die Abschluss-Aktion steht dann ohne Anzahl.
  const openCount = ausschussQuery.data?.pages[0]?.open_count ?? null

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
  const isScoreBusy = isTriggerPending || scoringStatus === 'running'
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
      statusText = 'Noch nicht vorgeschlagen'
      break
    case 'running':
      statusText =
        scoringStatus === 'running'
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

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Ausschuss</h2>
      <p className="text-sm text-text">
        Erkennt automatisch unscharfe, überbelichtete oder doppelte Fotos als Ausschuss-Vorschläge —
        läuft vollständig lokal auf diesem Server.
      </p>
      <p className="text-sm text-text">{AUSSCHUSS_NOTHING_SORTED_TEXT}</p>
      {rerun !== null && (
        <RerunBlock rerun={rerun} onRerun={handleTriggerScore} disabled={isScoreBusy} />
      )}

      {scoreTriggerErrorDetail && <Alert>{scoreTriggerErrorDetail}</Alert>}

      {scoringStatus === 'success' && <p className="text-sm text-text">{suggestionsFoundText}</p>}

      {/* Nach der Bestaetigung bleibt der Schritt aufrufbar - weitere Anpassungen sind moeglich,
          und es kann erneut bestaetigt werden. */}
      {gateConfirmedAt !== null && (
        <p className="text-sm text-text">
          Ausschuss bestätigt am {formatDateTime(gateConfirmedAt)} — der Schritt bleibt aufrufbar.
        </p>
      )}

      {/* Ohne Wiederholung: Die einzige Wiederholung ist die Hauptaktion der Leiste. */}
      {scoringStatus === 'failed' && <Alert>{scoringRun?.error_message}</Alert>}

      {istDetailansicht ? (
        <AusschussDetail projectId={project.id} photoId={detailPhotoId} onClose={closeDetail} />
      ) : (
        scoringStatus === 'success' && (
          <div className="flex w-full flex-col items-start gap-3">
            {ausschussQuery.isLoading && (
              <ul
                role="status"
                aria-label="Ausschnitt wird geladen…"
                className="flex flex-wrap gap-3"
              >
                {naturalTiles(
                  Array.from({ length: SKELETON_TILE_COUNT }, () => null),
                  TARGET_ROW_HEIGHT_PX,
                ).map((tile) => (
                  <li key={tile.index} aria-hidden="true" style={{ width: tile.width }}>
                    <Skeleton className="size-full rounded-md" style={{ height: tile.height }} />
                  </li>
                ))}
              </ul>
            )}

            {ausschussQuery.isError && (
              <Alert onRetry={() => void ausschussQuery.refetch()}>
                {ausschussQuery.error instanceof ApiError
                  ? ausschussQuery.error.detail
                  : 'Fehler beim Laden des Ausschusses.'}
              </Alert>
            )}

            {ausschussQuery.isSuccess && entries.length === 0 && (
              <p className="text-sm text-text">{AUSSCHUSS_EMPTY_TEXT}</p>
            )}

            {entries.length > 0 && (
              <ul data-ausschuss-grid ref={gridRef} className="flex flex-wrap gap-3">
                {entries.map((eintrag, index) => {
                  const tile = tiles.get(index)
                  if (eintrag.kind === 'group') {
                    return (
                      <DuplicateStackTile
                        key={`gruppe-${eintrag.group_anchor_photo_id}`}
                        projectId={project.id}
                        entry={eintrag}
                        width={tile?.width ?? 0}
                        height={tile?.height ?? 0}
                      />
                    )
                  }
                  return (
                    <li
                      key={eintrag.photo.id}
                      style={{ width: tile?.width ?? 0, height: tile?.height ?? 0 }}
                      className="relative overflow-hidden rounded-md bg-elevated"
                    >
                      {/* Die Bildflaeche ist ein natives `<button>` - Enter und Leertaste wirken
                          ohne eigenen Tastatur-Handler, und der zugaengliche Name nennt die
                          Aktion samt Dateiname. */}
                      <button
                        type="button"
                        onClick={() => openDetail(eintrag.photo.id)}
                        aria-label={`${eintrag.photo.relative_path} öffnen`}
                        data-testid="ausschuss-image"
                        className="block size-full"
                      >
                        <PhotoImage
                          photoId={eintrag.photo.id}
                          variant="thumbnail"
                          alt={eintrag.photo.relative_path}
                          className="size-full object-cover"
                        />
                      </button>

                      {/* Beide Kennzeichen liegen auf der UNDURCHSICHTIGEN Flaeche `--overlay` und
                          sind fuer Zeigegeraete durchlaessig: Die Bildflaeche bleibt die eine
                          Trefferflaeche dieser Kachel. */}
                      <span className="pointer-events-none absolute left-1 top-1 rounded-sm bg-overlay p-1">
                        <GrundKennzeichen reason={eintrag.reason} />
                      </span>
                      <span
                        className={cn(
                          'pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-overlay px-2 py-1 text-xs',
                          ENTSCHEIDUNG_SCHRIFT[eintrag.decision ?? 'offen'],
                        )}
                      >
                        <span data-testid="ausschuss-decision">
                          {entscheidungswort(eintrag.decision)}
                        </span>
                        <span className="min-w-6 truncate font-mono text-text-muted">
                          {eintrag.photo.relative_path.split('/').pop()}
                        </span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}

            {/* Der Sichtbarkeitsnachweis: Die geladene Seite ist nicht der ganze Bestand. */}
            {(ausschussQuery.hasNextPage || ausschussQuery.isFetchingNextPage) && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={ausschussQuery.isFetchingNextPage}
                busy={ausschussQuery.isFetchingNextPage}
                onClick={() => void ausschussQuery.fetchNextPage()}
              >
                Mehr laden
              </Button>
            )}
            {(ausschussQuery.hasNextPage || ausschussQuery.isFetchingNextPage) && (
              <p aria-live="polite" className="text-sm text-text">
                {entries.length} von {total} Einträgen geladen
              </p>
            )}
          </div>
        )
      )}

      {confirmMutation.isError && (
        <Alert>
          {confirmMutation.error instanceof ApiError
            ? confirmMutation.error.detail
            : 'Fehler beim Bestätigen des Ausschusses.'}
        </Alert>
      )}

      <StepActionBar
        action={action}
        status={
          <>
            <StatusDot status={scoringStatus} />
            {statusText}
          </>
        }
        detail={
          scoringStatus === 'running' && (
            <div className="flex w-full max-w-sm flex-col gap-2">
              <p className="text-sm text-text">
                {photosProcessed} von {photosTotal} Fotos verarbeitet
              </p>
              {photosTotal > 0 ? (
                <Progress aria-hidden="true" value={photosProcessed} max={photosTotal} />
              ) : (
                <Progress aria-hidden="true" />
              )}
            </div>
          )
        }
        onAction={action.kind === 'confirm' ? handleConfirm : handleTriggerScore}
        busy={action.kind === 'confirm' && confirmMutation.isPending}
      />
    </section>
  )
}

/**
 * Die Detailansicht: Grossbild und Entscheidungszeile, beim Gruppenmitglied dazu der Weg in die
 * Vergleichsansicht (A10). Die Gruppe selbst wird hier nicht geladen - sie wird dort entschieden.
 *
 * `Esc` schliesst nur, solange diese Ansicht ueberhaupt offen ist - das erledigt die Komponente
 * selbst statt der Seite, weil sie genau dann montiert ist.
 */
function AusschussDetail({
  projectId,
  photoId,
  onClose,
}: {
  projectId: number
  photoId: number
  onClose: () => void
}) {
  const query = useAusschussEntryQuery(projectId, photoId)
  const eintrag: AusschussPhotoEntry | null = query.data ?? null

  /* Der Schreibweg ist der EINZELNE: Er trifft genau diese Aufnahme. Der Anker der Gruppe ist
     dabei nur der Ort, an dem die Antwort im Zwischenspeicher landet - die Menge der betroffenen
     Fotos bestimmt der Server, die Oberflaeche schickt keine Id-Liste mit. */
  const decisionMutation = useDuplicateDecisionMutation(
    projectId,
    eintrag?.group_anchor_photo_id ?? photoId,
  )

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text">
        Aufnahme wird geladen…
      </p>
    )
  }

  if (query.isError) {
    return (
      <Alert onRetry={() => void query.refetch()}>
        {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Aufnahme.'}
      </Alert>
    )
  }

  if (eintrag === null) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-text">{AUSSCHUSS_MISSING_ENTRY_TEXT}</p>
        <Button type="button" variant="outline" onClick={onClose}>
          Zurück zur Übersicht
        </Button>
      </div>
    )
  }

  /* „Aufheben" gibt es nur, wo es etwas bewirkt: Bei einer Ablehnung wegen geringer Bildqualitaet
     gibt es keine Gruppe, und kein Wert der Entscheidungszeile aendert den Zustand dieser
     Aufnahme. Die Anzeige bietet den Wert deshalb nicht an - der Server weist ihn trotzdem NICHT
     ab (Auflage S4 der Spec 0486 bleibt unveraendert in Kraft). Die Bedingung ist der SERVERWERT
     `keep_possible` (`duplicates.py::keep_possible_for`, Auflage S7) - NICHT eine Ableitung aus
     `reason`: Traegt der Eintrag eine Entscheidungszeile, die einen Lauf ueberlebt hat, in dem
     `suggested_status` und `duplicate_of` zurueckgesetzt wurden, ist der Grund `low_quality` und
     "behalten" wirkt trotzdem. */
  const keepPossible = eintrag.keep_possible

  return (
    <div className="flex w-full flex-col items-start gap-3">
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg">Aufnahme im Ausschuss</h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label="Detailansicht schließen"
          onClick={onClose}
        >
          Schließen
        </Button>
      </div>

      <div className="flex w-full flex-col gap-4">
        <div className="flex flex-col items-start gap-3">
          {/* Grossbild in der Variante `display`: Hier wird beurteilt, und ein hochskaliertes
              Vorschaubild entschiede die Frage nach der Schaerfe falsch. `object-contain`, damit
              nichts beschnitten wird. */}
          <div className="w-full overflow-hidden rounded-md bg-surface">
            <PhotoImage
              photoId={eintrag.photo.id}
              variant="display"
              alt={eintrag.photo.relative_path}
              className="max-h-96 w-full object-contain"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <GrundKennzeichen reason={eintrag.reason} />
            <span
              data-testid="detail-decision"
              className={ENTSCHEIDUNG_SCHRIFT[eintrag.decision ?? 'offen']}
            >
              {entscheidungswort(eintrag.decision)}
            </span>
            <span className="font-mono text-xs text-text-muted">{eintrag.photo.relative_path}</span>
          </div>

          <div
            role="group"
            aria-label="Entscheidung über diese Aufnahme"
            className="flex flex-wrap gap-3"
          >
            {keepPossible && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label={`${DUPLICATE_ZUSTAENDE.keep.text} (Detailansicht): ${eintrag.photo.relative_path}`}
                aria-pressed={eintrag.decision === 'keep'}
                disabled={decisionMutation.isPending}
                busy={decisionMutation.isPending && eintrag.decision !== 'keep'}
                onClick={() =>
                  decisionMutation.mutate({ photoId: eintrag.photo.id, decision: 'keep' })
                }
              >
                {DUPLICATE_ZUSTAENDE.keep.text}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label={`${DUPLICATE_ZUSTAENDE.discard.text} (Detailansicht): ${eintrag.photo.relative_path}`}
              aria-pressed={eintrag.decision === 'discard'}
              disabled={decisionMutation.isPending}
              busy={decisionMutation.isPending && eintrag.decision !== 'discard'}
              onClick={() =>
                decisionMutation.mutate({ photoId: eintrag.photo.id, decision: 'discard' })
              }
            >
              {DUPLICATE_ZUSTAENDE.discard.text}
            </Button>
          </div>

          {!keepPossible && <p className="text-xs text-text-muted">{DUPLICATE_IMMUTABLE_TEXT}</p>}

          {/* Am Anker, nicht am Grund: Auch der Gewinner mit Schaerfe-Ablehnung (`low_quality`)
              liegt in einer Gruppe. Ohne Anker gibt es keinen Weg ins Leere. */}
          {eintrag.group_anchor_photo_id !== null && (
            <Button asChild variant="outline" size="sm">
              <Link
                to={duplicateComparePath(projectId, eintrag.group_anchor_photo_id, {
                  fromAusschuss: true,
                })}
              >
                Duplikat-Gruppe vergleichen
              </Link>
            </Button>
          )}

          {decisionMutation.isError && (
            <Alert>
              {decisionMutation.error instanceof ApiError
                ? decisionMutation.error.detail
                : 'Die Entscheidung konnte nicht gespeichert werden.'}
            </Alert>
          )}
        </div>
      </div>
    </div>
  )
}
