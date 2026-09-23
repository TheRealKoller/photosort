import { useCallback, useEffect, useMemo, useState } from 'react'
import { useOutletContext, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { AusschussEntryOut, DuplicateDecision, SuggestionReason } from '../../api/types'
import {
  DUPLICATE_IMMUTABLE_TEXT,
  DUPLICATE_ZUSTAENDE,
  DuplicatePhotoTile,
} from '../../components/DuplicatePhotoTile'
import { PhotoImage } from '../../components/PhotoImage'
import { StatusDot } from '../../components/StatusDot'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Icon } from '../../components/ui/icon'
import { Progress } from '../../components/ui/progress'
import { Skeleton } from '../../components/ui/skeleton'
import { useAusschussEntryQuery, useAusschussQuery } from '../../hooks/useAusschuss'
import { useDuplicateDecisionMutation, useDuplicateGroupQuery } from '../../hooks/useDuplicates'
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
import type { PipelineOutletContext } from './ProjectPipelineLayout'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln" -
// dieselbe Annaeherung wie in der Fotoliste, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

/** Der leere Bestand - dauerhaft sichtbar statt als fluechtiger Hinweis (AK14). Er deckt beide
 * Faelle ab, in denen nichts zu sichten ist: Der Lauf hat keinen Ausschuss gefunden, oder es gibt
 * noch gar keinen erfolgreichen Lauf mit Vorschlaegen. */
export const AUSSCHUSS_EMPTY_TEXT = 'Kein Ausschuss gefunden — es gibt derzeit nichts zu sichten.'

/** Der neutrale Erklaertext bei `open_count === 0`: Es gibt nichts zu bestaetigen, der Abschluss
 * ist keine Pflicht, die noch offen waere - er steht bereits. */
export const AUSSCHUSS_NOTHING_TO_CONFIRM_TEXT =
  'Keine offenen Vorschläge — es gibt nichts zu bestätigen.'

/** Der Erklaertext, wenn zwar nichts mehr OFFEN, der Abschluss aber noch nicht bestaetigt ist:
 * Hier gibt es sehr wohl etwas zu tun - genau dieser eine Klick gibt den naechsten Schritt frei
 * (AK13). Ohne ihn stuende die Pipeline still, sobald der Nutzer zuletzt alle Vorschlaege einzeln
 * entschieden hat (AK6). */
export const AUSSCHUSS_ALL_DECIDED_TEXT =
  'Alle Vorschläge sind entschieden — bestätige den Abschluss, um den nächsten Schritt freizugeben.'

/** Der benannte Zustand der Detailansicht, wenn die Aufnahme nicht (mehr) im Bestand liegt: Die
 * Antwort des `photo_id`-Filters ist leer, weil ein neuer Lauf die Entscheidung aufgeloest hat -
 * kein Fehler, sondern ein definierter Zustand mit Rueckweg. */
export const AUSSCHUSS_MISSING_ENTRY_TEXT =
  'Diese Aufnahme gehört nicht mehr zum Ausschuss. Möglicherweise hat ein neuer Lauf sie aufgelöst.'

/** Die Entscheidungszeile eines noch offenen Eintrags (AK14/AK4): Die Zeile trennt den GRUND der
 * Markierung von der getroffenen ENTSCHEIDUNG. */
export const AUSSCHUSS_OPEN_LABEL = 'Vorgeschlagen'

/** Die Beschriftung des Abschlusses - wortgleich mit dem frueheren Ausschuss-Gate. */
export const AUSSCHUSS_CONFIRM_TEXT = 'Ausschuss gesichtet, weiter'

/**
 * Das Grund-Kennzeichen je Kachel (AK4): Zeichen UND Wort, unterscheidbar nach Art.
 *
 * Die Farbe traegt die Aussage nie allein - das Wort steht daneben. `--danger-text` statt
 * `--danger`: Der grafische Ton haelt als Fliesstext kein AA.
 */
const GRUND_KENNZEICHEN: Record<SuggestionReason, { text: string; schrift: string }> = {
  duplicate: { text: 'Duplikat', schrift: 'text-accent' },
  low_quality: { text: 'Geringe Bildqualität', schrift: 'text-danger-text' },
}

/** Die Farbe der Entscheidungszeile. `null` (noch offen) ist zurueckhaltend: Es ist der Zustand
 * ohne Handlung, nicht einer mit. */
const ENTSCHEIDUNG_SCHRIFT: Record<DuplicateDecision | 'offen', string> = {
  keep: 'text-accent',
  discard: 'text-danger-text',
  offen: 'text-text-muted',
}

/**
 * Der Duplikat-Stapel: drei versetzte Kartenumrisse aus der Design-Nutzlast (Schluessel
 * `ausschuss`). DATEILOKALES SVG statt eines neuen Symbols im Zwanziger-Satz von `ui/icon.tsx`:
 * Der Satz des Boards fuehrt kein Stapel-Symbol, und ihn dafuer zu erweitern waere eine
 * Gestaltungsentscheidung ohne Vorlage - dieselbe Begruendung wie beim Schloss in `StepMarker`.
 */
function StapelZeichen() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" width={14} height={14} className="shrink-0">
      <rect x="1.5" y="5.5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
      <rect x="3.5" y="3.5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
      <rect x="5.5" y="1.5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
    </svg>
  )
}

/** Grund-Kennzeichen als eigenes Element - einmal fuer die Kachel, einmal fuer die Detailansicht. */
function GrundKennzeichen({ reason }: { reason: SuggestionReason }) {
  const kennzeichen = GRUND_KENNZEICHEN[reason]
  return (
    <span className={cn('flex items-center gap-1 text-xs', kennzeichen.schrift)}>
      {reason === 'duplicate' ? <StapelZeichen /> : <Icon name="image" size={14} />}
      {kennzeichen.text}
    </span>
  )
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

  const entries = useMemo(
    () => ausschussQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [ausschussQuery.data],
  )
  const total = ausschussQuery.data?.pages[0]?.total ?? 0
  const openCount = ausschussQuery.data?.pages[0]?.open_count ?? 0

  const tiles = useMemo(() => {
    const ratios = entries.map((eintrag) => eintrag.photo.aspect_ratio ?? null)
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

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Ausschuss</h2>
      <p className="text-sm text-text">
        Erkennt automatisch unscharfe, überbelichtete oder doppelte Fotos als Ausschuss-Vorschläge —
        läuft vollständig lokal auf diesem Server.
      </p>

      <Button type="button" onClick={handleTriggerScore} disabled={isScoreBusy} busy={isScoreBusy}>
        {isScoreBusy ? 'Wird aussortiert…' : 'Ausschuss aussortieren'}
      </Button>

      {scoreTriggerErrorDetail && <Alert>{scoreTriggerErrorDetail}</Alert>}

      <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
        <StatusDot status={scoringStatus} />
        {scoringRun === null && 'Noch nicht vorgeschlagen'}
        {scoringStatus === 'running' && 'Wird verarbeitet…'}
        {scoringStatus === 'success' && suggestionsFoundText}
        {scoringStatus === 'failed' && 'Fehlgeschlagen'}
      </p>

      {/* AK11: Nach der Bestaetigung bleibt der Schritt aufrufbar - weitere Anpassungen sind
          moeglich, und es kann erneut bestaetigt werden. Der Zeitstempel ist die einzige Anzeige
          des Abschlusses: Eine gesperrte Ansicht gaebe es hier nicht. */}
      {gateConfirmedAt !== null && (
        <p className="text-sm text-text">
          Ausschuss bestätigt am {formatDateTime(gateConfirmedAt)} — der Schritt bleibt aufrufbar.
        </p>
      )}

      {scoringStatus === 'running' && (
        <div className="flex w-full max-w-sm flex-col gap-2">
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
            {scoringAnnouncedDecile}% verarbeitet
          </p>
        </div>
      )}

      {scoringStatus === 'failed' && (
        <Alert onRetry={handleTriggerScore}>{scoringRun?.error_message}</Alert>
      )}

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
                {entries.length} von {total} geladen
              </p>
            )}

            {/*
              DER ABSCHLUSS IST DIE EINZIGE FREIGABE DES NAECHSTEN SCHRITTS (AK13), und `open_count`
              ist dafuer die FALSCHE BEDINGUNG: Ein Nutzer, der zuletzt alle Vorschlaege einzeln
              entschieden hat (AK6), hat `open_count === 0` und `gate_confirmed_at === null` - ein
              daran gesperrter Button liesse den Schritt nie abschliessen und die Pipeline still
              stehen. Gesperrt ist er deshalb erst, wenn beides erledigt ist: bestaetigt UND nichts
              mehr offen. Der Server setzt den Zeitstempel ohnehin auch bei leerer Menge.
            */}
            <Button
              type="button"
              onClick={() => confirmMutation.mutate()}
              disabled={confirmMutation.isPending || (gateConfirmedAt !== null && openCount === 0)}
              busy={confirmMutation.isPending}
            >
              {confirmMutation.isPending
                ? 'Wird bestätigt…'
                : openCount === 0
                  ? AUSSCHUSS_CONFIRM_TEXT
                  : `${AUSSCHUSS_CONFIRM_TEXT} (${openCount})`}
            </Button>
            {gateConfirmedAt !== null && openCount === 0 && (
              <p className="text-sm text-text">{AUSSCHUSS_NOTHING_TO_CONFIRM_TEXT}</p>
            )}
            {gateConfirmedAt === null && openCount === 0 && (
              <p className="text-sm text-text">{AUSSCHUSS_ALL_DECIDED_TEXT}</p>
            )}

            {confirmMutation.isError && (
              <Alert>
                {confirmMutation.error instanceof ApiError
                  ? confirmMutation.error.detail
                  : 'Fehler beim Bestätigen des Ausschusses.'}
              </Alert>
            )}
          </div>
        )
      )}
    </section>
  )
}

/**
 * Die Detailansicht: Grossbild, Entscheidungszeile, und beim Duplikat die ganze Gruppe daneben
 * (AK5/AK6/AK8).
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
  const eintrag: AusschussEntryOut | null = query.data?.items[0] ?? null

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

      <div className="grid w-full gap-4 lg:grid-cols-2">
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

          {decisionMutation.isError && (
            <Alert>
              {decisionMutation.error instanceof ApiError
                ? decisionMutation.error.detail
                : 'Die Entscheidung konnte nicht gespeichert werden.'}
            </Alert>
          )}
        </div>

        {eintrag.reason === 'duplicate' && eintrag.group_anchor_photo_id !== null && (
          <AusschussDetailGruppe
            projectId={projectId}
            anchorPhotoId={eintrag.group_anchor_photo_id}
          />
        )}
      </div>
    </div>
  )
}

/**
 * Die Duplikatgruppe der geoeffneten Aufnahme - aufgeloest ueber den Anker aus der Antwort, nicht
 * ueber das angeklickte Foto: Die Gruppe bleibt dieselbe, egal welches Mitglied man geoeffnet hat.
 *
 * Dieselben Bausteine wie die Vergleichsansicht, aber ohne deren Gruppen-Navigation: Der Weg
 * durch die Serien bleibt dort, hier steht die eine Serie zur geoeffneten Aufnahme.
 */
function AusschussDetailGruppe({
  projectId,
  anchorPhotoId,
}: {
  projectId: number
  anchorPhotoId: number
}) {
  const query = useDuplicateGroupQuery(projectId, anchorPhotoId)
  const decisionMutation = useDuplicateDecisionMutation(projectId, anchorPhotoId)

  /* Die laufenden Entscheidungen als MENGE von Foto-Ids: Verschiedene Aufnahmen entscheiden
     unabhaengig voneinander, und eine gruppenweite Sperre blockierte den zuegigen Durchlauf. */
  const [decidingIds, setDecidingIds] = useState<ReadonlySet<number>>(new Set())
  /** Die vergroesserte Aufnahme als FOTO-ID, nie als Index - `null` heisst "keine". Die
   * Vergroesserung bleibt INNERHALB der Gruppe: Sie zeigt ein Mitglied genauer, ohne die
   * geoeffnete Aufnahme zu wechseln. */
  const [enlargedId, setEnlargedId] = useState<number | null>(null)
  const items = query.data?.items ?? []

  function handleDecide(decidedPhotoId: number, decision: DuplicateDecision): void {
    setDecidingIds((current) => new Set(current).add(decidedPhotoId))
    decisionMutation.mutate(
      { photoId: decidedPhotoId, decision },
      {
        onSettled: () => {
          setDecidingIds((current) => {
            const next = new Set(current)
            next.delete(decidedPhotoId)
            return next
          })
        },
      },
    )
  }

  return (
    <div className="flex flex-col items-start gap-3">
      <h4 className="text-base">Duplikat-Gruppe</h4>

      {query.isLoading && (
        <ul
          role="status"
          aria-label="Duplikat-Gruppe wird geladen…"
          className="grid w-full grid-cols-2 gap-3 sm:grid-cols-3"
        >
          {Array.from({ length: 2 }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="aspect-square w-full rounded-md" />
            </li>
          ))}
        </ul>
      )}

      {query.isError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError
            ? query.error.detail
            : 'Fehler beim Laden der Duplikat-Gruppe.'}
        </Alert>
      )}

      {query.isSuccess && items.length === 0 && (
        <p className="text-sm text-text">Zu dieser Aufnahme gibt es keine Duplikat-Gruppe.</p>
      )}

      {items.length > 0 && (
        <ul className="grid w-full grid-cols-2 items-start gap-3 sm:grid-cols-3">
          {items.map((item) => (
            <DuplicatePhotoTile
              key={item.photo.id}
              photo={item.photo}
              effectiveDecision={item.effective_decision}
              keepPossible={item.keep_possible}
              enlarged={item.photo.id === enlargedId}
              deciding={decidingIds.has(item.photo.id)}
              onToggle={() =>
                setEnlargedId((current) => (current === item.photo.id ? null : item.photo.id))
              }
              onDecide={(decision) => handleDecide(item.photo.id, decision)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
