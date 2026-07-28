import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { PhotoImage } from '../components/PhotoImage'
import { RatingButtons } from '../components/RatingButtons'
import {
  useDeleteRatingMutation,
  usePhotoSequenceQuery,
  useSetRatingMutation,
} from '../hooks/usePhotos'
import { findOwnRating, ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'
import { RATING_STATUS_LABELS } from '../utils/ratingLabels'

// Bounded so a broken/degenerate filter can never spin forever fetching pages while searching
// for the next unrated photo - 80 * PHOTOS_PAGE_SIZE(60) covers well beyond any realistic
// project size for this two-person MVP (specs/features/0002-manual-categorization.md).
const MAX_AUTO_ADVANCE_PAGE_FETCHES = 80

const SWIPE_THRESHOLD_PX = 50

function isTextInputFocused(): boolean {
  const active = document.activeElement
  if (active === null) {
    return false
  }
  if (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA') {
    return true
  }
  return (active as HTMLElement).isContentEditable
}

export function PhotoDetailPage() {
  const { projectId, photoId } = useParams()
  const id = Number(projectId)
  const currentPhotoId = Number(photoId)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const filterParam = parseRatingFilter(searchParams.get('filter'))
  const ratingStatus = filterParam === '' ? undefined : filterParam
  const filterQuery = filterParam ? `?filter=${filterParam}` : ''

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus)
  const setMutation = useSetRatingMutation(id)
  const deleteMutation = useDeleteRatingMutation(id)

  const [completed, setCompleted] = useState(false)

  const photos = query.data?.pages.flatMap((page) => page.items) ?? []
  const total = query.data?.pages[0]?.total ?? 0
  const index = photos.findIndex((photo) => photo.id === currentPhotoId)
  const currentPhoto = index >= 0 ? photos[index] : undefined

  function goTo(targetPhotoId: number): void {
    navigate(`/projects/${id}/photos/${targetPhotoId}${filterQuery}`)
  }

  function handlePrev(): void {
    if (index > 0) {
      goTo(photos[index - 1].id)
    }
  }

  async function handleNext(): Promise<void> {
    if (index < 0) {
      return
    }
    let currentPhotos = photos
    let fetches = 0
    while (index + 1 >= currentPhotos.length && query.hasNextPage && fetches < MAX_AUTO_ADVANCE_PAGE_FETCHES) {
      const result = await query.fetchNextPage()
      currentPhotos = result.data?.pages.flatMap((page) => page.items) ?? currentPhotos
      fetches += 1
    }
    if (index + 1 < currentPhotos.length) {
      goTo(currentPhotos[index + 1].id)
    }
  }

  /**
   * Sucht ab fromIndex vorwaerts in der zum Klick-Zeitpunkt geladenen Foto-Sequenz nach dem
   * naechsten unbewerteten Foto (specs/features/0002-manual-categorization.md: Auto-Advance).
   * Arbeitet bewusst auf dieser VOR der durch die Mutation ausgeloesten Invalidierung erfassten
   * Momentaufnahme statt auf einem Refetch zu warten: da sich nur das gerade bewertete Foto
   * aendert, bleibt der Bewertungsstatus aller anderen Fotos in der Momentaufnahme weiterhin
   * korrekt - unabhaengig davon, ob/wann die Invalidierung neu laedt.
   */
  async function advanceToNextUnrated(fromIndex: number): Promise<void> {
    let currentPhotos = photos
    let i = fromIndex
    let fetches = 0
    for (;;) {
      while (i < currentPhotos.length) {
        const candidate = currentPhotos[i]
        if (findOwnRating(candidate.ratings, username) === undefined) {
          goTo(candidate.id)
          return
        }
        i += 1
      }
      if (!query.hasNextPage || fetches >= MAX_AUTO_ADVANCE_PAGE_FETCHES) {
        break
      }
      const result = await query.fetchNextPage()
      currentPhotos = result.data?.pages.flatMap((page) => page.items) ?? currentPhotos
      fetches += 1
    }
    setCompleted(true)
  }

  const currentOwnStatus = ownRatingStatus(currentPhoto?.ratings ?? [], username)
  // Anzeigeregel (Akzeptanzkriterium der Spec): eigene Bewertung hat immer Vorrang - der Server
  // liefert suggestion in diesem Fall ohnehin bereits als null, currentOwnStatus wird hier
  // trotzdem zusaetzlich geprueft (defensiv, gleiche Regel wie Grid-/Vergleichsansicht).
  const suggestion = currentOwnStatus === null ? (currentPhoto?.suggestion ?? null) : null

  function handleToggleRating(status: RatingStatus): void {
    if (!currentPhoto || setMutation.isPending || deleteMutation.isPending) {
      return
    }
    // Auto-Advance gilt laut Spec nur "nach dem Setzen einer Bewertung" - ein Toggle zurueck auf
    // unbewertet ist eine Korrektur (Nutzer macht einen Fehlklick rueckgaengig), kein "fertig mit
    // diesem Foto"; automatisches Weiterspringen waere hier ueberraschend statt hilfreich.
    if (currentOwnStatus === status) {
      deleteMutation.mutate(currentPhoto.id)
    } else {
      const fromIndex = index + 1
      setMutation.mutate(
        { photoId: currentPhoto.id, status },
        { onSuccess: () => void advanceToNextUnrated(fromIndex) }
      )
    }
  }

  // Ref-Indirektion (wie ProjectDetailPage.tsx::refetchRef): der Listener wird nur EINMAL
  // registriert, liest aber bei jedem Tastendruck die jeweils aktuellen Handler.
  const handlersRef = useRef({ handlePrev, handleNext, handleToggleRating })
  handlersRef.current = { handlePrev, handleNext, handleToggleRating }

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent): void {
      if (isTextInputFocused()) {
        return
      }
      switch (event.key) {
        case 'ArrowLeft':
          handlersRef.current.handlePrev()
          break
        case 'ArrowRight':
          void handlersRef.current.handleNext()
          break
        case '1':
          handlersRef.current.handleToggleRating('favorite')
          break
        case '2':
          handlersRef.current.handleToggleRating('album_worthy')
          break
        case '3':
          handlersRef.current.handleToggleRating('rejected')
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])

  // Swipe navigiert, Bewertung erfolgt separat per Tap auf die Bewertungs-Buttons (nicht per
  // Swipe, um versehentliche Bewertungen zu vermeiden) - specs/features/0002-manual-
  // categorization.md.
  const touchStartXRef = useRef<number | null>(null)

  function handleTouchStart(event: React.TouchEvent<HTMLDivElement>): void {
    touchStartXRef.current = event.touches[0]?.clientX ?? null
  }

  function handleTouchEnd(event: React.TouchEvent<HTMLDivElement>): void {
    const startX = touchStartXRef.current
    touchStartXRef.current = null
    if (startX === null) {
      return
    }
    const endX = event.changedTouches[0]?.clientX ?? startX
    const deltaX = endX - startX
    if (deltaX > SWIPE_THRESHOLD_PX) {
      handlePrev()
    } else if (deltaX < -SWIPE_THRESHOLD_PX) {
      void handleNext()
    }
  }

  if (query.isLoading) {
    return <p role="status">Fotos werden geladen…</p>
  }

  if (query.isError) {
    return (
      <div role="alert">
        <p>{query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}</p>
        <button type="button" onClick={() => void query.refetch()}>
          Erneut versuchen
        </button>
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
      </div>
    )
  }

  if (completed) {
    return (
      <div>
        <p role="status">Fertig! Keine weiteren unbewerteten Fotos.</p>
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
        <Link to={`/projects/${id}/compare`}>Zur Vergleichsansicht</Link>
      </div>
    )
  }

  if (!currentPhoto) {
    return (
      <div>
        <p>Foto nicht in der aktuellen Auswahl gefunden.</p>
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
      </div>
    )
  }

  const isMutating = setMutation.isPending || deleteMutation.isPending

  return (
    <div>
      <p>Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren</p>
      <p>
        {index + 1}/{total}
      </p>

      <div onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
        <PhotoImage photoId={currentPhoto.id} variant="display" alt={currentPhoto.relative_path} />
      </div>

      <button type="button" aria-label="Vorheriges Foto" onClick={handlePrev} disabled={index <= 0}>
        Zurück
      </button>
      <button
        type="button"
        aria-label="Nächstes Foto"
        onClick={() => void handleNext()}
        disabled={index + 1 >= photos.length && !query.hasNextPage}
      >
        Weiter
      </button>

      {suggestion && (
        <div>
          <p>Automatischer Vorschlag: {RATING_STATUS_LABELS[suggestion.status]}</p>
          <p>
            {/* Server liefert die Begruendung bereits regelbasiert ueber `reason`
                (backend/src/photosort/api/photos.py::_to_suggestion_out) - hier bewusst nicht
                erneut aus duplicate_of abgeleitet (Test-Review-Fund: doppelte, potenziell
                auseinanderlaufende Business-Logik). */}
            {suggestion.reason === 'duplicate'
              ? `Duplikat von Foto #${suggestion.duplicate_of}`
              : 'Geringe Bildqualität'}
          </p>
          {/* Ruft denselben Mutation-Pfad wie ein manueller Klick auf die passende
              RatingButtons-Option auf (UI/UX-Abschnitt der Spec) - der bestehende Auto-Advance
              greift danach unveraendert. Kein eigener "Vorschlag verwerfen"-Zustand: normale
              Weiternavigation ist das implizite Ignorieren. */}
          <button
            type="button"
            onClick={() => handleToggleRating(suggestion.status)}
            disabled={isMutating}
          >
            Vorschlag übernehmen
          </button>
        </div>
      )}

      <RatingButtons
        currentStatus={currentOwnStatus}
        onToggle={handleToggleRating}
        disabled={isMutating}
        busy={isMutating}
      />

      <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
    </div>
  )
}
