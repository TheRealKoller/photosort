import { Fragment, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { DraftAlternativesOut, EventOut, PhotoOut } from '../api/types'
import { useDraftAlternativesQuery } from '../hooks/usePhotos'
import { cn } from '../lib/utils'
import { ownRatingStatus } from '../utils/ownRating'
import { qualityLevel } from '../utils/qualityLevel'
import { referenceMarkerIndex } from '../utils/referenceMarker'
import { AlbumStateBadge } from './AlbumStateBadge'
import { PHOTO_CARD_GRID_CLASS } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { QualityMeter } from './QualityMeter'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

/** Band und Panel ohne Kandidaten. */
export const CANDIDATES_NONE_TEXT = 'Keine weiteren Fotos in diesem Event.'
/** Fehlschlag ohne Servertext. */
export const CANDIDATES_ERROR_TEXT = 'Fehler beim Laden der Fotos.'
/** Das Ordnungskriterium der Alternativen, in Band UND Dialog (Spec 0569) - ohne Pfeilzeichen,
 * das ein Screenreader als „Pfeil nach rechts" vorläse. */
export const ALTERNATIVES_ORDER_TEXT = 'Zeitlich geordnet, von früh nach spät'

/** Die vier zeitlich nächsten Alternativen im Band, acht Kandidaten je Seite im Hinzufügen-Panel. */
export const BAND_SIZE = 4
export const ADD_PAGE_SIZE = 8
/** Was das Panel von `useDraftAlternativesQuery` liest. */
interface CandidateQuery {
  data?: { pages: DraftAlternativesOut[] }
  isLoading: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
  hasNextPage: boolean
  isFetchingNextPage: boolean
  fetchNextPage: () => unknown
}

interface CandidatePanelProps {
  id: string
  heading: string
  focusKey: string
  query: CandidateQuery
  /** Fotos, die gerade im Album stehen - sie verlassen die Liste sofort, nicht erst nach dem
   * Neuladen. */
  excludedIds: ReadonlySet<number>
  limit?: number
  username: string | null
  actionLabel: 'Tauschen' | 'Hinzufügen'
  actionKey: 'exchange' | 'add'
  /** `neighborId`: der nächste Kandidat, sonst der vorige - das Fokusziel, wenn dieser die Liste
   * verlässt. */
  onAction: (photo: PhotoOut, neighborId: number | null) => void
  busyIds: ReadonlySet<number>
  error: string | null
  onClose: () => void
  extra?: ReactNode
  moreLabel?: string
  /** Das zu ersetzende Bild (nur im Band): Die Reihe wird eine geordnete Liste mit Ordnungstext,
   * und die Bezugsmarke steht an der Stelle, die der Server liefert. */
  reference?: PhotoOut
}

/**
 * Die Bezugsmarke (Spec 0569): das zu ersetzende Bild an seiner zeitlichen Stelle in der Reihe -
 * dieselbe Bildfläche wie die Kandidaten, abgesetzt durch einen ANLIEGENDEN Akzentring und das
 * Wort „Wird ersetzt". KEIN Bedienelement: kein Button, kein Fokus, keine Einstufung. Das Bild
 * trägt `alt=""`, der Pfad steht im Namen des Listeneintrags.
 */
export function ReferenceMarker({
  photo,
  showFileName = false,
  className,
}: {
  photo: PhotoOut
  showFileName?: boolean
  className?: string
}) {
  return (
    <li
      aria-label={`Wird ersetzt: ${photo.relative_path}`}
      className={cn('flex min-w-0 flex-col gap-2', className)}
    >
      <span className="block aspect-square w-full overflow-hidden rounded-md ring-2 ring-accent">
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt=""
          className="size-full object-contain"
        />
      </span>
      <span className="text-xs font-semibold text-text-h">Wird ersetzt</span>
      {showFileName && (
        <span className="truncate font-mono text-xs text-text">
          {photo.relative_path.split('/').pop() ?? photo.relative_path}
        </span>
      )}
    </li>
  )
}

/**
 * Die gemeinsame Gestalt von Alternativen-Band und Hinzufügen-Panel: eine volle Rasterzeile mit
 * Überschrift (Fokusziel beim Öffnen), Kandidaten in SERVERREIHENFOLGE, Platzhaltern beim Laden,
 * Meldung mit „Erneut versuchen" beim Fehler und einem eigenen Leertext. Esc schließt.
 */
function CandidatePanel({
  id,
  heading,
  focusKey,
  query,
  excludedIds,
  limit,
  username,
  actionLabel,
  actionKey,
  onAction,
  busyIds,
  error,
  onClose,
  extra,
  moreLabel,
  reference,
}: CandidatePanelProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true })
  }, [])

  const pages = query.data?.pages ?? []
  const kept = pages
    .flatMap((page) => page.items)
    .map((photo, rawIndex) => ({ photo, rawIndex }))
    .filter(({ photo }) => !excludedIds.has(photo.id))
    .slice(0, limit)
  const candidates = kept.map(({ photo }) => photo)
  // Die Marke steht vor dem ersten verbliebenen Kandidaten ab ihrer Stelle in der UNGEFILTERTEN
  // Antwort, sonst am Ende - so rutscht sie bei einem optimistischen Tausch nicht mit.
  const markerAt =
    reference === undefined || pages.length === 0
      ? null
      : referenceMarkerIndex(pages[0].reference_index, pages[0].offset, pages[0].items.length)
  const markerBeforeId =
    markerAt === null ? null : (kept.find(({ rawIndex }) => rawIndex >= markerAt)?.photo.id ?? null)
  const marker =
    reference === undefined ? null : (
      <ReferenceMarker key="reference-marker" photo={reference} showFileName />
    )
  const List = reference === undefined ? 'ul' : 'ol'
  const loadError = query.isError
    ? query.error instanceof ApiError
      ? query.error.detail
      : CANDIDATES_ERROR_TEXT
    : null

  return (
    <li
      id={id}
      className="col-span-full flex flex-col gap-3 rounded-lg border border-border bg-surface p-3"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation()
          onClose()
        }
      }}
    >
      <h4 ref={headingRef} tabIndex={-1} data-focus-key={focusKey} className="text-sm text-text-h">
        {heading}
      </h4>
      {reference !== undefined && candidates.length > 0 && (
        <p className="text-xs text-text">{ALTERNATIVES_ORDER_TEXT}</p>
      )}
      {query.isLoading && (
        <ul role="status" aria-label="Fotos werden geladen…" className={PHOTO_CARD_GRID_CLASS}>
          {Array.from({ length: BAND_SIZE }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="aspect-square w-full rounded-md" />
            </li>
          ))}
        </ul>
      )}
      {loadError !== null && <Alert onRetry={() => void query.refetch()}>{loadError}</Alert>}
      {error !== null && <Alert>{error}</Alert>}
      {candidates.length > 0 && (
        <List
          aria-label={reference === undefined ? undefined : 'Alternativen, zeitlich geordnet'}
          className={PHOTO_CARD_GRID_CLASS}
        >
          {candidates.map((candidate, index) => {
            const neighborId = (candidates[index + 1] ?? candidates[index - 1])?.id ?? null
            const struck = ownRatingStatus(candidate.ratings, username) === 'rejected'
            const fileName = candidate.relative_path.split('/').pop() ?? candidate.relative_path
            return (
              <Fragment key={candidate.id}>
                {markerBeforeId === candidate.id && marker}
                <li className="flex min-w-0 flex-col gap-2">
                  <span className="block aspect-square w-full overflow-hidden rounded-md">
                    <PhotoImage
                      photoId={candidate.id}
                      variant="thumbnail"
                      alt={candidate.relative_path}
                      className="size-full object-contain"
                    />
                  </span>
                  <span className="truncate font-mono text-xs text-text">{fileName}</span>
                  <QualityMeter
                    level={qualityLevel(candidate.ranking?.rank_score ?? null)}
                    className="text-xs"
                  />
                  {struck && (
                    <span>
                      <AlbumStateBadge state="struck" />
                    </span>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-11 sm:h-8"
                    data-focus-key={`${actionKey}-${candidate.id}`}
                    busy={busyIds.has(candidate.id)}
                    aria-label={`${actionLabel}: ${candidate.relative_path}`}
                    onClick={() => onAction(candidate, neighborId)}
                  >
                    {actionLabel}
                  </Button>
                </li>
              </Fragment>
            )
          })}
          {markerAt !== null && markerBeforeId === null && marker}
        </List>
      )}
      {!query.isLoading && loadError === null && candidates.length === 0 && (
        <p className="text-sm text-text">{CANDIDATES_NONE_TEXT}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {moreLabel !== undefined && query.hasNextPage && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            busy={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {moreLabel}
          </Button>
        )}
        {candidates.length > 0 && extra}
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Schließen
        </Button>
      </div>
    </li>
  )
}

export interface DraftAlternativesBandProps {
  id: string
  projectId: number
  photo: PhotoOut
  username: string | null
  excludedIds: ReadonlySet<number>
  onExchange: (alternative: PhotoOut) => void
  busyIds: ReadonlySet<number>
  error: string | null
  onOpenAll: () => void
  onClose: () => void
}

/**
 * Das Alternativen-Band am EINEN gewählten Foto der Seite: eine Abfrage je gewähltem Foto, nie
 * eine je Kachel, geladen erst beim Öffnen. Die vier zeitlich nächsten Alternativen desselben
 * Events, als Fenster vom Server geschnitten, mit dem Foto selbst als Marke an seiner Stelle; der
 * Dialog „Alle Alternativen" zeigt den vollständigen Bestand seitenweise.
 */
export function DraftAlternativesBand({
  id,
  projectId,
  photo,
  username,
  excludedIds,
  onExchange,
  busyIds,
  error,
  onOpenAll,
  onClose,
}: DraftAlternativesBandProps) {
  const query = useDraftAlternativesQuery(projectId, {
    eventId: photo.event?.id ?? 0,
    photoId: photo.id,
    enabled: photo.event != null,
    nearest: BAND_SIZE,
  })
  const fileName = photo.relative_path.split('/').pop() ?? photo.relative_path
  return (
    <CandidatePanel
      id={id}
      heading={`Alternativen zu ${fileName}`}
      focusKey="band-heading"
      query={query}
      excludedIds={excludedIds}
      limit={BAND_SIZE}
      username={username}
      actionLabel="Tauschen"
      actionKey="exchange"
      onAction={onExchange}
      busyIds={busyIds}
      error={error}
      onClose={onClose}
      extra={
        <Button type="button" variant="ghost" size="sm" onClick={onOpenAll}>
          Alle Alternativen
        </Button>
      }
      reference={photo}
    />
  )
}

export interface DraftAddPanelProps {
  id: string
  projectId: number
  event: EventOut
  eventName: string
  username: string | null
  excludedIds: ReadonlySet<number>
  onAdd: (candidate: PhotoOut, neighborId: number | null) => void
  busyIds: ReadonlySet<number>
  error: string | null
  onClose: () => void
}

/**
 * Das Hinzufügen-Panel eines Events: alle Fotos des Events mit Rangzeile, die nicht im Album sind,
 * nach Qualität (ohne Bezugsbild), acht je Seite. Der Personenfilter filtert es nicht.
 */
export function DraftAddPanel({
  id,
  projectId,
  event,
  eventName,
  username,
  excludedIds,
  onAdd,
  busyIds,
  error,
  onClose,
}: DraftAddPanelProps) {
  const query = useDraftAlternativesQuery(projectId, {
    eventId: event.id,
    photoId: null,
    enabled: true,
    pageSize: ADD_PAGE_SIZE,
  })
  return (
    <CandidatePanel
      id={id}
      heading={`Foto zu ${eventName} hinzufügen`}
      focusKey={`panel-heading-${event.id}`}
      query={query}
      excludedIds={excludedIds}
      username={username}
      actionLabel="Hinzufügen"
      actionKey="add"
      onAction={onAdd}
      busyIds={busyIds}
      error={error}
      onClose={onClose}
      moreLabel="Weitere Fotos"
    />
  )
}
