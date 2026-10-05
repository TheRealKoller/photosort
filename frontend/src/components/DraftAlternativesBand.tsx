import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { DraftAlternativesOut, EventOut, PhotoOut } from '../api/types'
import { useJustifiedRows } from '../hooks/useJustifiedRows'
import { useDraftAlternativesQuery } from '../hooks/usePhotos'
import { iconOnly } from '../utils/curationLayout'
import type { JustifiedTile } from '../utils/justifiedRows'
import { ownRatingStatus } from '../utils/ownRating'
import { referenceMarkerIndex } from '../utils/referenceMarker'
import { AlbumStateBadge } from './AlbumStateBadge'
import { CurationDetails } from './CurationDetails'
import { CurationSkeletonList } from './CurationSkeletonList'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { TileAction } from './TileAction'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

/** Band und Panel ohne Kandidaten. */
export const CANDIDATES_NONE_TEXT = 'Keine weiteren Fotos in diesem Event.'
/** Fehlschlag ohne Servertext. */
export const CANDIDATES_ERROR_TEXT = 'Fehler beim Laden der Fotos.'
/** Das Ordnungskriterium der Alternativen, in Serie UND aufgeklappter Reihe - ohne Pfeilzeichen,
 * das ein Screenreader als „Pfeil nach rechts" vorläse. */
export const ALTERNATIVES_ORDER_TEXT = 'Zeitlich geordnet, von früh nach spät'
/** Die Stelle des zu ersetzenden Bildes liegt auf einer noch nicht geladenen Seite der Reihe. */
export const REFERENCE_LATER_TEXT = 'Das zu ersetzende Bild folgt weiter hinten in der Reihe.'
/** Der Umschalter zwischen Serie und voller Reihe, zugeklappt bzw. aufgeklappt. */
export const SHOW_ALL_LABEL = 'Alle Fotos des Events'
export const SHOW_LESS_LABEL = 'Weniger anzeigen'

/** Vier Platzhalter beim Laden - reine Darstellung, die Fenstergröße schneidet der Server. */
export const BAND_SKELETON_COUNT = 4
/** Acht Kandidaten je Seite im Hinzufügen-Panel. */
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

/** Ein Handgriff an jeder Alternative. Name `"{label}: {relative_path}"`, Fokusschlüssel
 * `"{key}-{id}"` - der Pfad steht nie im Schlüssel. */
export interface CandidateAction {
  label: 'Tauschen' | 'Hinzufügen'
  key: 'exchange' | 'add'
  icon: 'repeat' | 'plus'
  /** `neighborId`: der nächste Kandidat, sonst der vorige - das Fokusziel, wenn dieser die Liste
   * verlässt. */
  onAction: (photo: PhotoOut, neighborId: number | null) => void
}

interface CandidatePanelProps {
  id: string
  heading: string
  focusKey: string
  query: CandidateQuery
  /** Fotos, die gerade im Album stehen - sie verlassen die Liste sofort, nicht erst nach dem
   * Neuladen. */
  excludedIds: ReadonlySet<number>
  username: string | null
  /** Nebeneinander, in dieser Reihenfolge. */
  actions: readonly CandidateAction[]
  busyIds: ReadonlySet<number>
  error: string | null
  onClose: () => void
  /** Steht unter dem Ordnungstext und über dem Raster (Serienhinweis, Umschalter). */
  controls?: ReactNode
  gridId?: string
  moreLabel?: string
  /** Das zu ersetzende Bild (nur im Band): Die Reihe wird eine geordnete Liste mit Ordnungstext,
   * und die Bezugsmarke steht an der Stelle, die der Server liefert. */
  reference?: PhotoOut
}

/**
 * Die Bezugsmarke: das zu ersetzende Bild an seiner zeitlichen Stelle in der Reihe - eine Zelle
 * im eigenen Seitenverhältnis mit derselben Bildbehandlung wie die Kandidaten, abgesetzt durch
 * einen ANLIEGENDEN Akzentring und das Wort „Wird ersetzt". KEIN Bedienelement: kein Button, kein
 * Fokus, keine Einstufung. Das Bild trägt `alt=""`, der Pfad steht im Namen des Listeneintrags.
 */
function ReferenceMarker({ photo, tile }: { photo: PhotoOut; tile: JustifiedTile }) {
  return (
    <li
      aria-label={`Wird ersetzt: ${photo.relative_path}`}
      style={{ width: tile.width }}
      className="flex flex-col gap-2"
    >
      <span
        style={{ height: tile.height }}
        className="block overflow-hidden rounded-md ring-2 ring-accent"
      >
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt=""
          className="size-full object-contain"
        />
      </span>
      <span className="text-xs font-semibold text-text-h">Wird ersetzt</span>
      <span className="font-mono text-xs break-all text-text">
        {photo.relative_path.split('/').pop() ?? photo.relative_path}
      </span>
    </li>
  )
}

/** Eine Zelle der Kandidatenreihe: ein Kandidat oder die Bezugsmarke. */
type CandidateCell = { kind: 'candidate'; photo: PhotoOut; position: number } | { kind: 'marker' }

/**
 * Die gemeinsame Gestalt von Alternativen-Band und Hinzufügen-Panel: eine volle Zeile des
 * Eventrasters mit Überschrift (Fokusziel beim Öffnen), Kandidaten in SERVERREIHENFOLGE als
 * justierte Reihen, Platzhaltern beim Laden, Meldung mit „Erneut versuchen" beim Fehler und einem
 * eigenen Leertext. Esc schließt.
 */
function CandidatePanel({
  id,
  heading,
  focusKey,
  query,
  excludedIds,
  username,
  actions,
  busyIds,
  error,
  onClose,
  controls,
  gridId,
  moreLabel,
  reference,
}: CandidatePanelProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true })
  }, [])

  const pages = query.data?.pages ?? []
  const loaded = pages.flatMap((page) => page.items)
  const kept = loaded
    .map((photo, rawIndex) => ({ photo, rawIndex }))
    .filter(({ photo }) => !excludedIds.has(photo.id))
  const candidates = kept.map(({ photo }) => photo)
  // Die geladenen Seiten bilden EINE Reihe ab `pages[0].offset`. Am Ende steht die Marke nur, wenn
  // keine Seite mehr folgt - sonst gehört sie an den Anfang der nächsten. Sie steht vor dem ersten
  // verbliebenen Kandidaten ab ihrer Stelle in der UNGEFILTERTEN Antwort, sonst am Ende - so
  // rutscht sie nicht mit, wenn ein Foto die Liste verlässt.
  const markerAt =
    reference === undefined || pages.length === 0
      ? null
      : referenceMarkerIndex(pages[0].reference_index, pages[0].offset, loaded.length)
  const showMarker = markerAt !== null && (markerAt < loaded.length || !query.hasNextPage)
  const markerLater =
    reference !== undefined &&
    !showMarker &&
    candidates.length > 0 &&
    pages[0]?.reference_index !== null
  const markerBeforeId =
    markerAt === null || !showMarker
      ? null
      : (kept.find(({ rawIndex }) => rawIndex >= markerAt)?.photo.id ?? null)

  const cells: CandidateCell[] = []
  candidates.forEach((photo, position) => {
    if (markerBeforeId === photo.id) {
      cells.push({ kind: 'marker' })
    }
    cells.push({ kind: 'candidate', photo, position })
  })
  if (candidates.length > 0 && showMarker && markerBeforeId === null) {
    cells.push({ kind: 'marker' })
  }
  const { ref: listRef, rows } = useJustifiedRows<HTMLElement>(
    cells.map((cell) =>
      cell.kind === 'marker'
        ? (reference?.aspect_ratio ?? null)
        : (cell.photo.aspect_ratio ?? null),
    ),
  )
  const tiles = rows.flatMap((row) => row.tiles)

  const List = reference === undefined ? 'ul' : 'ol'
  const loadError = query.isError
    ? query.error instanceof ApiError
      ? query.error.detail
      : CANDIDATES_ERROR_TEXT
    : null
  const handlesKind = actions.length > 1 ? 'candidate' : 'panel'

  return (
    <li
      id={id}
      className="flex w-full flex-col gap-3 rounded-lg border border-border bg-surface p-3"
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
      {error !== null && <Alert>{error}</Alert>}
      {reference !== undefined && candidates.length > 0 && (
        <p className="text-xs text-text">{ALTERNATIVES_ORDER_TEXT}</p>
      )}
      {controls}
      {loadError !== null && <Alert onRetry={() => void query.refetch()}>{loadError}</Alert>}
      {/* Das gesteuerte Element des Umschalters ist das jeweils sichtbare Raster; gibt es keines
          (Fehler, alle Kandidaten hinzugefügt), steht ein leerer Platzhalter mit derselben Id,
          damit `aria-controls` nie ins Leere zeigt. Das Raster bleibt direktes Kind der Fläche. */}
      {gridId !== undefined && !query.isLoading && candidates.length === 0 && <div id={gridId} />}
      {query.isLoading && <CurationSkeletonList id={gridId} count={BAND_SKELETON_COUNT} />}
      {candidates.length > 0 && (
        <List
          id={gridId}
          ref={listRef}
          aria-label={reference === undefined ? undefined : 'Alternativen, zeitlich geordnet'}
          className="flex flex-wrap gap-3"
        >
          {cells.map((cell, index) => {
            const tile = tiles[index] ?? { index, width: 0, height: 0 }
            if (cell.kind === 'marker') {
              return reference === undefined ? null : (
                <ReferenceMarker key="reference-marker" photo={reference} tile={tile} />
              )
            }
            const candidate = cell.photo
            const neighborId =
              (candidates[cell.position + 1] ?? candidates[cell.position - 1])?.id ?? null
            const struck = ownRatingStatus(candidate.ratings, username) === 'rejected'
            const busy = busyIds.has(candidate.id)
            const symbolsOnly = iconOnly(tile.width, handlesKind)
            return (
              <PhotoCard
                key={candidate.id}
                width={tile.width}
                imageHeight={tile.height}
                relativePath={candidate.relative_path}
                image={
                  <PhotoImage
                    photoId={candidate.id}
                    variant="thumbnail"
                    alt={candidate.relative_path}
                    className="size-full object-contain"
                  />
                }
                setAside={struck}
                stateMark={struck ? <AlbumStateBadge state="struck" /> : undefined}
                details={<CurationDetails photo={candidate} />}
                actions={actions.map((action, actionIndex) => (
                  <TileAction
                    key={action.key}
                    icon={action.icon}
                    label={action.label}
                    accessibleName={`${action.label}: ${candidate.relative_path}`}
                    iconOnly={symbolsOnly}
                    tileWidth={tile.width}
                    align={actionIndex === 0 ? 'start' : 'end'}
                    data-focus-key={`${action.key}-${candidate.id}`}
                    busy={busy}
                    onClick={() => action.onAction(candidate, neighborId)}
                  />
                ))}
              />
            )
          })}
        </List>
      )}
      {markerLater && <p className="text-xs text-text">{REFERENCE_LATER_TEXT}</p>}
      {!query.isLoading && loadError === null && candidates.length === 0 && (
        <p className="text-sm text-text">{CANDIDATES_NONE_TEXT}</p>
      )}

      <div className="flex flex-wrap gap-3">
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
  onAdd: (alternative: PhotoOut, neighborId: number | null) => void
  busyIds: ReadonlySet<number>
  error: string | null
  onClose: () => void
}

/**
 * Das Alternativen-Band am EINEN gewählten Foto der Seite: Abfragen nur für das gewählte Foto,
 * nie je Kachel, geladen erst beim Öffnen. Es zeigt die Aufnahmeserie des Fotos, als
 * Fenster vom Server geschnitten, mit dem Foto selbst als Marke an seiner Stelle. „Alle Fotos des
 * Events" klappt an DERSELBEN Stelle die volle zeitliche Reihe seitenweise auf - kein Dialog, keine
 * Fokusfalle, kein programmatisches Scrollen; die volle Reihe lädt erst beim ersten Aufklappen und
 * bleibt danach im Cache.
 */
export function DraftAlternativesBand({
  id,
  projectId,
  photo,
  username,
  excludedIds,
  onExchange,
  onAdd,
  busyIds,
  error,
  onClose,
}: DraftAlternativesBandProps) {
  const [expanded, setExpanded] = useState(false)
  // Einmal aufgeklappt, bleibt die Abfrage der vollen Reihe aktiv: Zurückschalten und erneutes
  // Aufklappen lesen ihren Cache, statt sie beim Wiederaktivieren neu zu laden.
  const [rowRequested, setRowRequested] = useState(false)
  const gridId = useId()
  const eventId = photo.event?.id ?? 0
  const series = useDraftAlternativesQuery(projectId, {
    eventId,
    photoId: photo.id,
    enabled: photo.event != null,
    series: true,
  })
  const row = useDraftAlternativesQuery(projectId, {
    eventId,
    photoId: photo.id,
    enabled: rowRequested && photo.event != null,
  })
  const fileName = photo.relative_path.split('/').pop() ?? photo.relative_path
  const seriesPage = series.data?.pages[0]
  const seriesRest = seriesPage?.series_rest
  const showRest =
    !expanded && typeof seriesRest === 'number' && Number.isInteger(seriesRest) && seriesRest > 0
  // Die Serie lädt leer → das Event hat keine Alternativen, kein Umschalter. Leert sie sich erst
  // durch Hinzufügen (die Fotos verlassen die geladene Seite), bleibt er stehen.
  const [hadAlternatives, setHadAlternatives] = useState(false)
  if (!hadAlternatives && seriesPage !== undefined && seriesPage.items.length > 0) {
    setHadAlternatives(true)
  }
  const showToggle =
    !series.isLoading &&
    (hadAlternatives || !(seriesPage !== undefined && seriesPage.items.length === 0))
  return (
    <CandidatePanel
      id={id}
      heading={`Alternativen zu ${fileName}`}
      focusKey="band-heading"
      query={expanded ? row : series}
      excludedIds={excludedIds}
      username={username}
      actions={[
        {
          label: 'Tauschen',
          key: 'exchange',
          icon: 'repeat',
          onAction: (alternative) => onExchange(alternative),
        },
        { label: 'Hinzufügen', key: 'add', icon: 'plus', onAction: onAdd },
      ]}
      busyIds={busyIds}
      error={error}
      onClose={onClose}
      controls={
        <>
          {showRest && (
            <p className="text-xs text-text">
              {seriesRest === 1
                ? '1 weitere Aufnahme dieser Serie unter „Alle Fotos des Events“.'
                : `${seriesRest} weitere Aufnahmen dieser Serie unter „Alle Fotos des Events“.`}
            </p>
          )}
          {showToggle && (
            <div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-expanded={expanded}
                aria-controls={gridId}
                onClick={() => {
                  setExpanded((current) => !current)
                  setRowRequested(true)
                }}
              >
                {expanded ? SHOW_LESS_LABEL : SHOW_ALL_LABEL}
              </Button>
            </div>
          )}
        </>
      }
      gridId={gridId}
      moreLabel={expanded ? 'Weitere Fotos' : undefined}
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
      actions={[{ label: 'Hinzufügen', key: 'add', icon: 'plus', onAction: onAdd }]}
      busyIds={busyIds}
      error={error}
      onClose={onClose}
      moreLabel="Weitere Fotos"
    />
  )
}
