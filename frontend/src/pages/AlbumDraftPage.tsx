import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { PhotoOut } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { AlbumDraftBar } from '../components/AlbumDraftBar'
import { AlbumDraftClosing } from '../components/AlbumDraftClosing'
import { AlbumDraftDay } from '../components/AlbumDraftDay'
import { AlbumDraftDayControls } from '../components/AlbumDraftDayControls'
import { AlbumDraftFilterNotices } from '../components/AlbumDraftFilterNotices'
import { AlbumDraftHeader } from '../components/AlbumDraftHeader'
import { AlbumDraftNotice } from '../components/AlbumDraftNotice'
import { CurationLightbox } from '../components/CurationLightbox'
import { CurationPhotoTile } from '../components/CurationPhotoTile'
import { CurationSkeletonList } from '../components/CurationSkeletonList'
import { DraftAddPanel, DraftAlternativesBand } from '../components/DraftAlternativesBand'
import { DraftEventSection } from '../components/DraftEventSection'
import { DraftExplainer } from '../components/DraftExplainer'
import { PersonFilterGroup } from '../components/PersonFilterGroup'
import { UndoToast } from '../components/UndoToast'
import { Alert } from '../components/ui/alert'
import { useCurationLightbox } from '../hooks/useCurationLightbox'
import { useDraftDecisions } from '../hooks/useDraftDecisions'
import { useDraftPosition } from '../hooks/useDraftPosition'
import type { ObserverFactory } from '../hooks/useDraftPosition'
import { useMotifsQuery } from '../hooks/useMotifs'
import { usePersonFilter } from '../hooks/usePersonFilter'
import { useDraftQuery } from '../hooks/usePhotos'
import { useModelChoiceQuery, useProjectQuery } from '../hooks/useProjects'
import {
  draftClosingTexts,
  draftCounts,
  draftMembership,
  draftMotifText,
  draftOverviewText,
  draftSizeText,
  smallerProposalText,
} from '../utils/albumDraft'
import {
  DRAFT_CLOUD_CONSENT_TEXT,
  DRAFT_EMPTY_TEXT,
  DRAFT_EYE_DISABLED_TEXT,
  SETTINGS_LINK_LABEL,
} from '../utils/albumDraftTexts'
import { groupEventsByDay } from '../utils/eventGrouping'
import type { JustifiedTile } from '../utils/justifiedRows'
import { ownRatingStatus } from '../utils/ownRating'
import { carriesPersons, filterByPersons } from '../utils/personFilter'
import { formatDayHeading } from '../utils/timeOfDay'

const SKELETON_TILE_COUNT = 6

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

type OpenPanel = { kind: 'band'; photoId: number } | { kind: 'add'; eventId: number } | null

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
 * Der EIGENE Zustand kommt ausschließlich über `ownRatingStatus` mit dem `username`-Claim.
 */
export function AlbumDraftPage({ createPositionObserver }: AlbumDraftPageProps = {}) {
  const { projectId } = useParams()
  const id = Number(projectId)
  const motifsQuery = useMotifsQuery()
  const token = getToken()
  const username = token ? decodeUsername(token) : null
  const query = useDraftQuery(id)
  const projectQuery = useProjectQuery(id)
  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const events = useMemo(() => query.data?.events ?? [], [query.data])
  const hasEvents = events.length > 0

  const categoryMethod = projectQuery.data?.model_choice.category_method ?? null
  // Die Modellwahl traegt allein den Eye-Leerzustand, und nur ohne Events: Sie wird AUSSCHLIESSLICH
  // dann geholt. Ein Cloud-Projekt fragte sonst einen Katalog ab, den diese Seite nie liest, und
  // ein Eye-Projekt mit Entwurf kippte nach dem Laden in den Leertext statt beim Entwurf zu bleiben.
  const needsModelChoice = categoryMethod === 'eye' && query.isSuccess && !hasEvents
  const modelChoiceQuery = useModelChoiceQuery(id, { enabled: needsModelChoice })
  const eyeDisabled =
    needsModelChoice &&
    modelChoiceQuery.data?.eye.unavailable_reasons.includes('eye_disabled') === true
  // Das Skeleton steht, solange EINE der drei Antworten aussteht - auch die der Modellwahl.
  const loading =
    query.isLoading || projectQuery.isLoading || (needsModelChoice && modelChoiceQuery.isLoading)

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
  const panelBaseId = useId()

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

  // Fokusziele über `data-focus-key` (numerische Ids, nie ein Name), gesucht NACH dem Render,
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

  const {
    locked,
    errorAt,
    clearError,
    undoView,
    undoBusy,
    undoError,
    undoRestart,
    endUndo,
    handleStrike,
    handleReAdd,
    handleAdd,
    handleExchange,
    handleUndo,
  } = useDraftDecisions({
    projectId: id,
    username,
    albumOf,
    struckOf,
    onRequestFocus: setFocusRequest,
    onCloseBand: (photoId) => {
      if (photoId === null) {
        setOpenPanel(null)
      } else if (openPanel?.kind === 'band' && openPanel.photoId === photoId) {
        setOpenPanel(null)
      }
    },
    onExchanged: (chosen) => {
      if (carriesPersons(chosen, personIds)) {
        setFocusRequest({ key: `decide-${chosen.id}`, scroll: true })
      } else {
        setHiddenExchange({ filterKey })
      }
    },
  })

  const cloudConsentGiven = projectQuery.data?.cloud_vision_detection_enabled === true
  // Der Freigabe-Hinweis gehoert allein zum Cloud-Verfahren: Ein Eye-Projekt braucht keine
  // Cloud-Freigabe, und ein Hinweis darauf schickte es auf den falschen Weg.
  const consentMissing = categoryMethod === 'cloud' && !cloudConsentGiven
  const target = projectQuery.data?.effective_selection_target ?? null
  const ready = query.isSuccess && projectQuery.isSuccess && !consentMissing && !loading
  // Der Freigabe-Hinweis steht nur an der Stelle eines geladenen, leeren Entwurfs; sonst
  // erschiene er neben Skeleton oder Fehler-Alert und laese sich als deren Ursache.
  const showConsent = consentMissing && query.isSuccess && projectQuery.isSuccess && !loading
  const hasEyeStage = items.some((photo) => photo.album_suitability?.source === 'eye')

  function renderTile(photo: PhotoOut, tile: JustifiedTile) {
    const struck = ownStatusOf(photo) === 'rejected'
    const bandOpen = openPanel?.kind === 'band' && openPanel.photoId === photo.id
    return (
      <CurationPhotoTile
        key={photo.id}
        photo={photo}
        width={tile.width}
        imageHeight={tile.height}
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
                  clearError()
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

  const selectionPath = `/projects/${id}/selection`
  const bandPhoto =
    openPanel?.kind === 'band'
      ? albumItems.find((photo) => photo.id === openPanel.photoId)
      : undefined
  const closing = target === null ? null : draftClosingTexts(counts, target)
  const smallerProposal =
    target === null || !query.data
      ? null
      : smallerProposalText(items, target, query.data.eligible_candidate_count)
  const dayKeys = days.map((day) => day.dayKey)

  return (
    <div ref={containerRef} className="flex flex-col gap-6">
      <AlbumDraftHeader
        headingRef={headingRef}
        overviewText={ready && hasEvents ? draftOverviewText(days.length, events.length) : null}
        showEye={hasEyeStage}
      />

      {ready && hasEvents && <DraftExplainer username={username} />}

      {ready && hasEvents && (
        <AlbumDraftBar
          barRef={barRef}
          dayNumber={dayIndex + 1}
          dayCount={days.length}
          position={position}
          eventCount={events.length}
          selectionPath={selectionPath}
          groupHeading={currentGroup?.heading ?? ''}
          sizeText={target !== null ? draftSizeText(counts, target) : null}
          smallerProposal={smallerProposal}
        />
      )}

      {loading && <CurationSkeletonList count={SKELETON_TILE_COUNT} />}

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

      {showConsent && (
        <AlbumDraftNotice
          text={DRAFT_CLOUD_CONSENT_TEXT}
          to={`/projects/${id}/settings`}
          linkLabel={SETTINGS_LINK_LABEL}
        />
      )}

      {ready && !hasEvents && eyeDisabled && (
        <AlbumDraftNotice
          text={DRAFT_EYE_DISABLED_TEXT}
          to={`/projects/${id}/settings`}
          linkLabel={SETTINGS_LINK_LABEL}
        />
      )}

      {ready && !hasEvents && !eyeDisabled && (
        <AlbumDraftNotice
          text={DRAFT_EMPTY_TEXT}
          to={`/projects/${id}/pipeline/kriterien`}
          linkLabel="Zur Klassifizierung"
        />
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

      {ready && hasEvents && (
        <AlbumDraftFilterNotices
          isFiltered={isFiltered}
          visibleCount={visibleAlbumIds.size}
          inAlbumCount={counts.inAlbum}
          hiddenExchange={hiddenExchange?.filterKey === filterKey}
          onReset={() => setPersonIds([])}
        />
      )}

      {ready && hasEvents && (
        <AlbumDraftDayControls
          onExpandAll={() => setCollapsedDayKeys(new Set())}
          onCollapseAll={() => setCollapsedDayKeys(new Set(dayKeys))}
        />
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
            <AlbumDraftDay
              key={day.dayKey}
              heading={formatDayHeading(day.dayKey)}
              collapsed={isCollapsed}
              count={dayCount}
              firstEventPosition={day.events[0]?.event.position}
              panelId={panelId}
              onToggle={() => setCollapsedDayKeys((prev) => toggleDayCollapse(prev, day.dayKey))}
            >
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
                    motifText={draftMotifText(allAlbum, username, motifsQuery.data?.items ?? [])}
                    struckPhotos={struckOf(eventId)}
                    renderAlbumTile={renderTile}
                    renderStruckTile={renderTile}
                    band={
                      bandPhoto !== undefined && bandPhoto.event?.id === eventId
                        ? {
                            photoId: bandPhoto.id,
                            node: (
                              <DraftAlternativesBand
                                key={`band-${bandPhoto.id}`}
                                id={`${panelBaseId}-band`}
                                projectId={id}
                                photo={bandPhoto}
                                username={username}
                                excludedIds={albumIds}
                                onExchange={(chosen) => handleExchange(bandPhoto, chosen, 'band')}
                                onAdd={(candidate, neighborId) =>
                                  void handleAdd(candidate, neighborId, 'band', 'band-heading')
                                }
                                busyIds={locked}
                                error={errorAt('band')}
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
                                  void handleAdd(
                                    candidate,
                                    neighborId,
                                    `panel-${eventId}`,
                                    `panel-heading-${eventId}`,
                                  )
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
                      clearError()
                      setOpenPanel(addOpen ? null : { kind: 'add', eventId })
                    }}
                    struckError={errorAt(`struck-${eventId}`)}
                  />
                )
              })}
            </AlbumDraftDay>
          )
        })}

      {ready && hasEvents && closing !== null && (
        <AlbumDraftClosing sentences={closing} selectionPath={selectionPath} />
      )}

      <UndoToast
        notice={undoView}
        busy={undoBusy}
        error={undoError}
        restartKey={undoRestart}
        onUndo={handleUndo}
        onDismiss={endUndo}
      />

      {lightbox.photo !== undefined && (
        <CurationLightbox key={lightbox.photo.id} photo={lightbox.photo} onClose={lightbox.close} />
      )}
    </div>
  )
}
