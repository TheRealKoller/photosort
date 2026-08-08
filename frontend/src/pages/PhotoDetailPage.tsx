import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { PhotoImage } from '../components/PhotoImage'
import { QualityMeter } from '../components/QualityMeter'
import { RatingButtons } from '../components/RatingButtons'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import {
  useDeleteRatingMutation,
  usePhotoSequenceQuery,
  useSetRatingMutation,
} from '../hooks/usePhotos'
import { CATEGORY_LABELS } from '../utils/categoryLabels'
import { findOwnRating, ownRatingStatus } from '../utils/ownRating'
import { qualityLevel } from '../utils/qualityLevel'
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
    return (
      <p role="status" className="text-sm text-text">
        Fotos werden geladen…
      </p>
    )
  }

  if (query.isError) {
    return (
      <div className="flex flex-col items-start gap-3">
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
        <Button asChild variant="ghost">
          <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
        </Button>
      </div>
    )
  }

  if (completed) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="status" className="text-text-h">
          Fertig! Keine weiteren unbewerteten Fotos.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="secondary">
            <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link to={`/projects/${id}/compare`}>Zur Vergleichsansicht</Link>
          </Button>
        </div>
      </div>
    )
  }

  if (!currentPhoto) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Foto nicht in der aktuellen Auswahl gefunden.</p>
        <Button asChild variant="ghost">
          <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
        </Button>
      </div>
    )
  }

  const isMutating = setMutation.isPending || deleteMutation.isPending

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-text">Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren</p>
      <p className="text-sm text-text">
        {index + 1}/{total}
      </p>

      <div
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        className="mx-auto w-full max-w-2xl"
      >
        <PhotoImage
          photoId={currentPhoto.id}
          variant="display"
          alt={currentPhoto.relative_path}
          className="aspect-[4/3] w-full rounded-xl object-contain"
        />
      </div>

      <div className="flex justify-between gap-3">
        <Button type="button" variant="outline" aria-label="Vorheriges Foto" onClick={handlePrev} disabled={index <= 0}>
          Zurück
        </Button>
        <Button
          type="button"
          variant="outline"
          aria-label="Nächstes Foto"
          onClick={() => void handleNext()}
          disabled={index + 1 >= photos.length && !query.hasNextPage}
        >
          Weiter
        </Button>
      </div>

      {suggestion && (
        <div className="flex flex-col items-start gap-1.5 rounded-xl border border-accent-border bg-accent-bg p-3 text-sm">
          <p className="text-text-h">Automatischer Vorschlag: {RATING_STATUS_LABELS[suggestion.status]}</p>
          <p className="text-text">
            {/* Server liefert die Begruendung bereits regelbasiert ueber `reason`
                (backend/src/photosort/api/photos.py::_to_suggestion_out) - hier bewusst nicht
                erneut aus duplicate_of abgeleitet (Test-Review-Fund: doppelte, potenziell
                auseinanderlaufende Business-Logik). "top_pick" (Spec 0024) zeigt zusaetzlich
                Kategorie + eine grobe Qualitaets-Einordnung statt eines Rohwerts (UI/UX-Abschnitt
                der Spec) - beide nur fuer top_pick gesetzt (category/local_quality_score sind bei
                duplicate/low_quality entweder null oder fachlich nicht gemeint). */}
            {suggestion.reason === 'duplicate' && `Duplikat von Foto #${suggestion.duplicate_of}`}
            {suggestion.reason === 'low_quality' && 'Geringe Bildqualität'}
            {suggestion.reason === 'top_pick' && suggestion.category && (
              <>
                Kategorie: {CATEGORY_LABELS[suggestion.category]}
                {(() => {
                  const level = qualityLevel(suggestion.local_quality_score)
                  return level ? (
                    <>
                      {' · '}
                      <QualityMeter level={level} />
                    </>
                  ) : null
                })()}
              </>
            )}
          </p>
          {/* Ruft denselben Mutation-Pfad wie ein manueller Klick auf die passende
              RatingButtons-Option auf (UI/UX-Abschnitt der Spec) - der bestehende Auto-Advance
              greift danach unveraendert. Kein eigener "Vorschlag verwerfen"-Zustand: normale
              Weiternavigation ist das implizite Ignorieren. */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            busy={isMutating}
            onClick={() => handleToggleRating(suggestion.status)}
          >
            Vorschlag übernehmen
          </Button>
        </div>
      )}

      <RatingButtons
        currentStatus={currentOwnStatus}
        onToggle={handleToggleRating}
        disabled={isMutating}
        busy={isMutating}
      />

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
      </Button>
    </div>
  )
}
