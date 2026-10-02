import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut, RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CurationLightbox } from '../components/CurationLightbox'
import { CurationPhotoTile } from '../components/CurationPhotoTile'
import { DraftAddPanel, DraftAlternativesBand } from '../components/DraftAlternativesBand'
import { DraftAlternativesDialog } from '../components/DraftAlternativesDialog'
import { DraftEventSection } from '../components/DraftEventSection'
import { DraftExplainer } from '../components/DraftExplainer'
import { PersonFilterGroup } from '../components/PersonFilterGroup'
import { UndoToast } from '../components/UndoToast'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useCurationLightbox } from '../hooks/useCurationLightbox'
import { useDraftPosition } from '../hooks/useDraftPosition'
import type { ObserverFactory } from '../hooks/useDraftPosition'
import { useMotifsQuery } from '../hooks/useMotifs'
import { usePersonFilter } from '../hooks/usePersonFilter'
import {
  useDraftDecisionMutation,
  useDraftExchangeMutation,
  useDraftExchangeUndoMutation,
  useDraftQuery,
} from '../hooks/usePhotos'
import { useProjectQuery } from '../hooks/useProjects'
import {
  draftClosingTexts,
  draftCounts,
  draftMembership,
  draftMotifText,
  draftOverviewText,
  draftSizeText,
  formatDraftPhotoCount,
  reAddDecision,
} from '../utils/albumDraft'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import { groupEventsByDay } from '../utils/eventGrouping'
import { ownRatingStatus } from '../utils/ownRating'
import { carriesPersons, filterByPersons } from '../utils/personFilter'
import { formatDayHeading } from '../utils/timeOfDay'

/**
 * Der Leerzustand des Entwurfs - nur ein Lauf ohne Events zeigt ihn. Er benennt den fehlenden
 * Schritt und verlinkt ihn.
 */
export const DRAFT_EMPTY_TEXT = 'Noch kein Auswahlvorschlag — führe die Kriterien-Bewertung aus.'

/**
 * Der Leerzustand OHNE Cloud-Freigabe - mit Vorrang vor `DRAFT_EMPTY_TEXT`. Er WIEDERHOLT DEN
 * ZUSTIMMUNGSTEXT NICHT: was an die Cloud geht, steht an genau einer Stelle.
 */
export const DRAFT_CLOUD_CONSENT_TEXT =
  'Ohne Cloud-Freigabe entsteht kein Album-Entwurf. Die Freigabe erteilst du in den ' +
  'Projekteinstellungen.'

/** Titel des Hinweises nach einem Tausch („Gestrichen" kommt aus der Begriffsquelle). */
export const EXCHANGED_TITLE = 'Getauscht'

const SKELETON_TILE_COUNT = 6
const ACTION_FAILED_TEXT = 'Die Aktion ist fehlgeschlagen.'

/** Toggelt den Klapp-Zustand eines Tages - liefert ein neues `Set`. */
export function toggleDayCollapse(collapsedDayKeys: Set<string>, dayKey: string): Set<string> {
  const next = new Set(collapsedDayKeys)
  if (next.has(dayKey)) {
    next.delete(dayKey)
  } else {
    next.add(dayKey)
  }
  return next
}

type UndoTarget =
  | { kind: 'strike'; photo: PhotoOut; previous: RatingStatus | null }
  | {
      kind: 'exchange'
      replaced: PhotoOut
      chosen: PhotoOut
      chosenPrevious: 'rejected' | null
      replacedPrevious: 'album_worthy' | null
    }

type OpenPanel = { kind: 'band'; photoId: number } | { kind: 'add'; eventId: number } | null

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.detail : ACTION_FAILED_TEXT
}

export interface AlbumDraftPageProps {
  /** Test-Naht: der Beobachter der Positionsanzeige (jsdom kennt keinen). */
  createPositionObserver?: ObserverFactory
}

/**
 * Der Album-Entwurf: der Vorschlag als Entwurf, „nur abweichen, wo nötig". Streichen, Tauschen
 * (Band am Foto), Hinzufügen (Panel je Event) und Wieder aufnehmen (Gestrichen-Zeile) schreiben den
 * Serverzustand in den einmal geladenen Entwurf - nie ein Neuladen, damit Scrollposition und Fokus
 * stehen bleiben. Es gibt keinen gespeicherten Zustand „fertig".
 *
 * Der EIGENE Zustand kommt ausschließlich über `ownRatingStatus` mit dem `username`-Claim (S6/S10).
 */
export function AlbumDraftPage({ createPositionObserver }: AlbumDraftPageProps = {}) {
  const { projectId } = useParams()
  const id = Number(projectId)
  const motifsQuery = useMotifsQuery()
  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = useDraftQuery(id)
  const projectQuery = useProjectQuery(id)
  const decisionMutation = useDraftDecisionMutation(id, username)
  const exchangeMutation = useDraftExchangeMutation(id, username)
  const undoMutation = useDraftExchangeUndoMutation(id, username)
  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const events = useMemo(() => query.data?.events ?? [], [query.data])

  const [searchParams, setSearchParams] = useSearchParams()
  const { personsQuery, personIds, setPersonIds } = usePersonFilter(searchParams, setSearchParams)
  const isFiltered = personIds.length > 0
  const filterKey = personIds.join(',')
  const [hiddenExchange, setHiddenExchange] = useState<{ filterKey: string } | null>(null)

  const headingRef = useRef<HTMLHeadingElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const barRef = useRef<HTMLDivElement>(null)
  const lightbox = useCurationLightbox({ items: query.data?.items, headingRef })

  const [openPanel, setOpenPanel] = useState<OpenPanel>(null)
  const [allAlternativesPhotoId, setAllAlternativesPhotoId] = useState<number | null>(null)
  const panelBaseId = useId()

  // Die Sperre je Foto: der Ref ist die SYNCHRONE Wahrheit, der State löst das Neurendern aus.
  const lockedRef = useRef<Set<number>>(new Set())
  const [locked, setLocked] = useState<Set<number>>(new Set())
  function lock(ids: number[]): boolean {
    if (ids.some((photoId) => lockedRef.current.has(photoId))) {
      return false
    }
    lockedRef.current = new Set([...lockedRef.current, ...ids])
    setLocked(lockedRef.current)
    return true
  }
  function unlock(ids: number[]): void {
    lockedRef.current = new Set([...lockedRef.current].filter((photoId) => !ids.includes(photoId)))
    setLocked(lockedRef.current)
  }

  const [actionError, setActionError] = useState<{ where: string; message: string } | null>(null)
  const errorAt = (where: string) => (actionError?.where === where ? actionError.message : null)

  const [undo, setUndo] = useState<{ key: number; target: UndoTarget } | null>(null)
  const [undoError, setUndoError] = useState<string | null>(null)
  const [undoRestart, setUndoRestart] = useState(0)
  const undoKeyRef = useRef(0)
  function showUndo(target: UndoTarget): void {
    undoKeyRef.current += 1
    setUndo({ key: undoKeyRef.current, target })
    setUndoError(null)
  }
  function endUndo(): void {
    setUndo(null)
    setUndoError(null)
  }

  // Fokusziele über `data-focus-key` (numerische Ids, nie ein Name - S11), gesucht NACH dem Render,
  // in dem der Handgriff angekommen ist. Nie `body`, kein Scrollsprung.
  const [focusRequest, setFocusRequest] = useState<{ key: string; scroll: boolean } | null>(null)
  useEffect(() => {
    if (focusRequest === null) {
      return
    }
    const target = containerRef.current?.querySelector<HTMLElement>(
      `[data-focus-key="${focusRequest.key}"]`,
    )
    if (target) {
      target.focus({ preventScroll: true })
      if (focusRequest.scroll) {
        target.scrollIntoView?.({ block: 'nearest' })
      }
    }
    setFocusRequest(null)
  }, [focusRequest, query.data, openPanel])

  useEffect(() => {
    if (hiddenExchange !== null) {
      headingRef.current?.focus()
    }
  }, [hiddenExchange])

  const ownStatusOf = (photo: PhotoOut) => ownRatingStatus(photo.ratings, username)
  const counts = draftCounts(items, username)
  const albumItems = items.filter((photo) => draftMembership(photo, ownStatusOf(photo)) === 'album')
  const albumIds = new Set(albumItems.map((photo) => photo.id))
  const visibleAlbumIds = new Set(filterByPersons(albumItems, personIds).map((photo) => photo.id))
  const days = groupEventsByDay(events, items)

  const [collapsedDayKeys, setCollapsedDayKeys] = useState<Set<string>>(new Set())
  const layoutKey = `${days.map((day) => day.dayKey).join()}|${[...collapsedDayKeys].join()}`
  const position = useDraftPosition(containerRef, barRef, layoutKey, createPositionObserver)
  const dayIndex = Math.max(
    0,
    days.findIndex((day) => day.events.some((group) => group.event.position === position)),
  )
  const currentGroup = days
    .flatMap((day) => day.events)
    .find((group) => group.event.position === position)

  function albumOf(eventId: number): PhotoOut[] {
    return albumItems.filter(
      (photo) => photo.event?.id === eventId && visibleAlbumIds.has(photo.id),
    )
  }
  function struckOf(eventId: number): PhotoOut[] {
    return items.filter(
      (photo) =>
        photo.event?.id === eventId && draftMembership(photo, ownStatusOf(photo)) === 'struck',
    )
  }

  function handleStrike(photo: PhotoOut): void {
    if (!lock([photo.id])) {
      return
    }
    endUndo()
    setActionError(null)
    const previous = ownStatusOf(photo)
    const siblings = albumOf(photo.event?.id ?? 0)
    const index = siblings.findIndex((candidate) => candidate.id === photo.id)
    const neighbor = siblings[index + 1] ?? siblings[index - 1]
    decisionMutation.mutate(
      { photoId: photo.id, status: 'rejected' },
      {
        onSuccess: () => {
          if (openPanel?.kind === 'band' && openPanel.photoId === photo.id) {
            setOpenPanel(null)
          }
          showUndo({ kind: 'strike', photo, previous })
          setFocusRequest({
            key: neighbor ? `decide-${neighbor.id}` : `struck-toggle-${photo.event?.id ?? 0}`,
            scroll: false,
          })
        },
        onError: (error) =>
          setActionError({ where: `tile-${photo.id}`, message: errorText(error) }),
        onSettled: () => unlock([photo.id]),
      },
    )
  }

  function handleReAdd(photo: PhotoOut): void {
    if (!lock([photo.id])) {
      return
    }
    endUndo()
    setActionError(null)
    const struck = struckOf(photo.event?.id ?? 0)
    const index = struck.findIndex((candidate) => candidate.id === photo.id)
    const neighbor = struck[index + 1] ?? struck[index - 1]
    decisionMutation.mutate(
      { photoId: photo.id, status: reAddDecision(photo) },
      {
        onSuccess: () =>
          setFocusRequest({
            key: neighbor ? `readd-${neighbor.id}` : `decide-${photo.id}`,
            scroll: false,
          }),
        onError: (error) =>
          setActionError({ where: `struck-${photo.event?.id ?? 0}`, message: errorText(error) }),
        onSettled: () => unlock([photo.id]),
      },
    )
  }

  function handleAdd(candidate: PhotoOut, neighborId: number | null, eventId: number): void {
    if (!lock([candidate.id])) {
      return
    }
    endUndo()
    setActionError(null)
    decisionMutation.mutate(
      { photoId: candidate.id, status: 'album_worthy', insert: candidate },
      {
        onSuccess: () =>
          setFocusRequest({
            key: neighborId === null ? `panel-heading-${eventId}` : `add-${neighborId}`,
            scroll: false,
          }),
        onError: (error) =>
          setActionError({ where: `panel-${eventId}`, message: errorText(error) }),
        onSettled: () => unlock([candidate.id]),
      },
    )
  }

  function handleExchange(replaced: PhotoOut, chosen: PhotoOut, where: string): void {
    if (!lock([replaced.id, chosen.id])) {
      return
    }
    endUndo()
    setActionError(null)
    const chosenPrevious = ownStatusOf(chosen) === 'rejected' ? 'rejected' : null
    const replacedPrevious = ownStatusOf(replaced) === 'album_worthy' ? 'album_worthy' : null
    exchangeMutation.mutate(
      { replaced, chosen },
      {
        onSuccess: () => {
          setOpenPanel(null)
          setAllAlternativesPhotoId(null)
          showUndo({ kind: 'exchange', replaced, chosen, chosenPrevious, replacedPrevious })
          if (carriesPersons(chosen, personIds)) {
            setFocusRequest({ key: `decide-${chosen.id}`, scroll: true })
          } else {
            setHiddenExchange({ filterKey })
          }
        },
        onError: (error) => setActionError({ where, message: errorText(error) }),
        onSettled: () => unlock([replaced.id, chosen.id]),
      },
    )
  }

  function handleUndo(): void {
    if (undo === null) {
      return
    }
    const { target } = undo
    const onError = (error: unknown) => {
      setUndoError(errorText(error))
      setUndoRestart((previous) => previous + 1)
    }
    if (target.kind === 'strike') {
      if (!lock([target.photo.id])) {
        return
      }
      decisionMutation.mutate(
        // Ohne Rangzeile hat das Streichen das Foto aus der Antwortmenge genommen; das Einfügen ist
        // idempotent und stellt es an seinen Platz zurück.
        { photoId: target.photo.id, status: target.previous, insert: target.photo },
        {
          onSuccess: () => {
            endUndo()
            setFocusRequest({ key: `decide-${target.photo.id}`, scroll: false })
          },
          onError,
          onSettled: () => unlock([target.photo.id]),
        },
      )
      return
    }
    const ids = [target.replaced.id, target.chosen.id]
    if (!lock(ids)) {
      return
    }
    undoMutation.mutate(
      {
        photo_id: target.chosen.id,
        replaced_photo_id: target.replaced.id,
        photo_previous_status: target.chosenPrevious,
        replaced_previous_status: target.replacedPrevious,
      },
      {
        onSuccess: () => {
          endUndo()
          setFocusRequest({ key: `decide-${target.replaced.id}`, scroll: false })
        },
        onError,
        onSettled: () => unlock(ids),
      },
    )
  }

  const cloudConsentGiven = projectQuery.data?.cloud_vision_detection_enabled === true
  const target = projectQuery.data?.effective_selection_target ?? null
  const motifSetError = motifsQuery.isError
    ? motifsQuery.error instanceof ApiError
      ? motifsQuery.error.detail
      : 'Fehler beim Laden der Motive.'
    : undefined
  const ready = query.isSuccess && projectQuery.isSuccess && cloudConsentGiven
  const hasEvents = events.length > 0
  const selectionPath = `/projects/${id}/selection`

  function renderTile(photo: PhotoOut) {
    const struck = ownStatusOf(photo) === 'rejected'
    const bandOpen = openPanel?.kind === 'band' && openPanel.photoId === photo.id
    return (
      <CurationPhotoTile
        key={photo.id}
        photo={photo}
        motifSet={motifsQuery.data}
        motifSetLoading={motifsQuery.isLoading}
        motifSetError={motifSetError}
        onMotifSetRetry={() => void motifsQuery.refetch()}
        ownStatus={ownStatusOf(photo)}
        deciding={locked.has(photo.id)}
        onDecide={() => (struck ? handleReAdd(photo) : handleStrike(photo))}
        alternatives={
          struck
            ? undefined
            : {
                expanded: bandOpen,
                controls: `${panelBaseId}-band`,
                onToggle: () => {
                  setActionError(null)
                  setOpenPanel(bandOpen ? null : { kind: 'band', photoId: photo.id })
                },
              }
        }
        error={errorAt(`tile-${photo.id}`)}
        onOpenLarge={lightbox.open}
        largeTriggerRef={lightbox.triggerRef(photo.id)}
      />
    )
  }

  const bandPhoto =
    openPanel?.kind === 'band'
      ? albumItems.find((photo) => photo.id === openPanel.photoId)
      : undefined
  const allAlternativesPhoto = items.find((photo) => photo.id === allAlternativesPhotoId)
  const closing = target === null ? null : draftClosingTexts(counts, target)
  const undoView =
    undo === null
      ? null
      : undo.target.kind === 'strike'
        ? {
            key: undo.key,
            title: ALBUM_STATE_LABELS.struck,
            photoId: undo.target.photo.id,
            relativePath: undo.target.photo.relative_path,
          }
        : {
            key: undo.key,
            title: EXCHANGED_TITLE,
            photoId: undo.target.replaced.id,
            relativePath: undo.target.replaced.relative_path,
          }
  const dayKeys = days.map((day) => day.dayKey)

  return (
    <div ref={containerRef} className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 ref={headingRef} tabIndex={-1} className="text-xl sm:text-2xl">
          Album-Entwurf
        </h1>
        {ready && hasEvents && (
          <p className="text-sm text-text">{draftOverviewText(days.length, events.length)}</p>
        )}
      </header>

      {ready && hasEvents && <DraftExplainer username={username} />}

      {ready && hasEvents && (
        <div
          ref={barRef}
          data-draft-bar=""
          className="sticky top-header z-10 flex flex-col gap-1 border-b border-separator bg-bg py-2"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm text-text-h">
              {`Tag ${dayIndex + 1} von ${days.length} · Event ${position} von ${events.length}`}
            </p>
            <Button asChild variant="secondary" size="sm" className="shrink-0">
              <Link to={selectionPath}>Zur Endauswahl</Link>
            </Button>
          </div>
          <p className="truncate text-sm text-text">{currentGroup?.heading ?? ''}</p>
          {target !== null && <p className="text-sm text-text">{draftSizeText(counts, target)}</p>}
        </div>
      )}

      {(query.isLoading || projectQuery.isLoading) && (
        <ul
          role="status"
          aria-label="Fotos werden geladen…"
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4"
        >
          {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
              <Skeleton className="aspect-square w-full rounded-md" />
            </li>
          ))}
        </ul>
      )}

      {query.isError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
      )}

      {projectQuery.isError && (
        <Alert onRetry={() => void projectQuery.refetch()}>
          {projectQuery.error instanceof ApiError
            ? projectQuery.error.detail
            : 'Fehler beim Laden des Projekts.'}
        </Alert>
      )}

      {query.isSuccess && projectQuery.isSuccess && !cloudConsentGiven && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{DRAFT_CLOUD_CONSENT_TEXT}</p>
          <Button asChild variant="secondary" size="sm">
            <Link to={`/projects/${id}/settings`}>Zu den Projekteinstellungen</Link>
          </Button>
        </div>
      )}

      {ready && !hasEvents && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">{DRAFT_EMPTY_TEXT}</p>
          <Button asChild variant="secondary" size="sm">
            <Link to={`/projects/${id}/pipeline/kriterien`}>Zur Kriterien-Bewertung</Link>
          </Button>
        </div>
      )}

      {ready && hasEvents && (
        <PersonFilterGroup
          persons={personsQuery.data}
          isError={personsQuery.isError}
          onRetry={() => void personsQuery.refetch()}
          selected={personIds}
          onChange={setPersonIds}
        />
      )}

      {ready && hasEvents && isFiltered && (
        <p role="status" className="text-sm text-text">
          {hiddenExchange?.filterKey === filterKey
            ? 'Das eingetauschte Foto ist durch den Filter ausgeblendet.'
            : `${visibleAlbumIds.size} von ${counts.inAlbum} Fotos des Entwurfs sichtbar.`}
        </p>
      )}

      {ready && hasEvents && isFiltered && visibleAlbumIds.size === 0 && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">Keine Fotos des Entwurfs mit diesem Filter.</p>
          <Button type="button" variant="outline" size="sm" onClick={() => setPersonIds([])}>
            Filter zurücksetzen
          </Button>
        </div>
      )}

      {ready && hasEvents && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCollapsedDayKeys(new Set())}
          >
            Alle Tage aufklappen
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCollapsedDayKeys(new Set(dayKeys))}
          >
            Alle Tage zuklappen
          </Button>
        </div>
      )}

      {ready &&
        days.map((day) => {
          const panelId = `day-panel-${day.dayKey}`
          const isCollapsed = collapsedDayKeys.has(day.dayKey)
          const dayCount = day.events.reduce(
            (sum, group) =>
              sum + albumItems.filter((photo) => photo.event?.id === group.event.id).length,
            0,
          )
          return (
            <section
              key={day.dayKey}
              data-draft-position={isCollapsed ? day.events[0]?.event.position : undefined}
              className="flex flex-col gap-4"
            >
              <h2 className="text-lg">
                <Button
                  variant="ghost"
                  aria-expanded={!isCollapsed}
                  aria-controls={panelId}
                  onClick={() => setCollapsedDayKeys((prev) => toggleDayCollapse(prev, day.dayKey))}
                  className="h-auto min-h-11 w-full justify-start whitespace-normal px-2 py-1 text-left text-lg font-normal"
                >
                  <span aria-hidden="true">{isCollapsed ? '▶' : '▼'}</span>
                  <span>{formatDayHeading(day.dayKey)}</span>
                  {isCollapsed && (
                    <>
                      {' '}
                      <span className="font-normal text-text">{`(${formatDraftPhotoCount(dayCount)})`}</span>
                    </>
                  )}
                </Button>
              </h2>
              {!isCollapsed && (
                <div id={panelId} className="flex flex-col gap-6">
                  {day.events.map((group) => {
                    const eventId = group.event.id
                    const allAlbum = albumItems.filter((photo) => photo.event?.id === eventId)
                    const visible = albumOf(eventId)
                    const addOpen = openPanel?.kind === 'add' && openPanel.eventId === eventId
                    const addId = `${panelBaseId}-add-${eventId}`
                    return (
                      <DraftEventSection
                        key={eventId}
                        event={group.event}
                        heading={group.heading}
                        albumPhotos={visible}
                        albumCount={allAlbum.length}
                        motifText={draftMotifText(
                          allAlbum,
                          username,
                          motifsQuery.data?.items ?? [],
                        )}
                        struckPhotos={struckOf(eventId)}
                        renderAlbumTile={renderTile}
                        renderStruckTile={renderTile}
                        band={
                          bandPhoto !== undefined && bandPhoto.event?.id === eventId
                            ? {
                                photoId: bandPhoto.id,
                                node: (
                                  <DraftAlternativesBand
                                    key="band"
                                    id={`${panelBaseId}-band`}
                                    projectId={id}
                                    photo={bandPhoto}
                                    username={username}
                                    excludedIds={albumIds}
                                    onExchange={(chosen) =>
                                      handleExchange(bandPhoto, chosen, 'band')
                                    }
                                    busyIds={locked}
                                    error={errorAt('band')}
                                    onOpenAll={() => {
                                      setActionError(null)
                                      setAllAlternativesPhotoId(bandPhoto.id)
                                    }}
                                    onClose={() => {
                                      setOpenPanel(null)
                                      setFocusRequest({
                                        key: `alternatives-${bandPhoto.id}`,
                                        scroll: false,
                                      })
                                    }}
                                  />
                                ),
                              }
                            : null
                        }
                        addPanel={
                          addOpen
                            ? {
                                id: addId,
                                node: (
                                  <DraftAddPanel
                                    key="panel"
                                    id={addId}
                                    projectId={id}
                                    event={group.event}
                                    eventName={group.heading}
                                    username={username}
                                    excludedIds={albumIds}
                                    onAdd={(candidate, neighborId) =>
                                      handleAdd(candidate, neighborId, eventId)
                                    }
                                    busyIds={locked}
                                    error={errorAt(`panel-${eventId}`)}
                                    onClose={() => {
                                      setOpenPanel(null)
                                      setFocusRequest({
                                        key: `add-trigger-${eventId}`,
                                        scroll: false,
                                      })
                                    }}
                                  />
                                ),
                              }
                            : null
                        }
                        onToggleAdd={() => {
                          setActionError(null)
                          setOpenPanel(addOpen ? null : { kind: 'add', eventId })
                        }}
                        struckError={errorAt(`struck-${eventId}`)}
                      />
                    )
                  })}
                </div>
              )}
            </section>
          )
        })}

      {ready && hasEvents && closing !== null && (
        <section className="flex flex-col items-start gap-2 border-t border-separator pt-6">
          <h2 className="text-lg">Stand des Entwurfs</h2>
          {closing.map((sentence) => (
            <p key={sentence} className="text-sm text-text">
              {sentence}
            </p>
          ))}
          <Button asChild>
            <Link to={selectionPath}>Zur Endauswahl</Link>
          </Button>
        </section>
      )}

      <UndoToast
        notice={undoView}
        busy={undo !== null && (decisionMutation.isPending || undoMutation.isPending)}
        error={undoError}
        restartKey={undoRestart}
        onUndo={handleUndo}
        onDismiss={endUndo}
      />

      {allAlternativesPhoto !== undefined && (
        <DraftAlternativesDialog
          projectId={id}
          photo={allAlternativesPhoto}
          username={username}
          open
          onClose={() => {
            setAllAlternativesPhotoId(null)
            setActionError(null)
          }}
          onChoose={(chosen) => handleExchange(allAlternativesPhoto, chosen, 'dialog')}
          exchanging={exchangeMutation.isPending}
          error={errorAt('dialog')}
        />
      )}

      {lightbox.photo !== undefined && (
        <CurationLightbox key={lightbox.photo.id} photo={lightbox.photo} onClose={lightbox.close} />
      )}
    </div>
  )
}
