import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { CategoryKey, RatingStatus } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CloudVisionStatusList } from '../components/CloudVisionStatusList'
import { CriterionDetailsList, hasCategoryControls } from '../components/CriterionDetailsList'
import { PhotoImage } from '../components/PhotoImage'
import { RatingButtons } from '../components/RatingButtons'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { useCategoriesQuery } from '../hooks/useCategories'
import { useCategoryOverrideControls } from '../hooks/useCategoryOverrideControls'
import {
  useDeleteRatingMutation,
  usePhotoSequenceQuery,
  useSetRatingMutation,
} from '../hooks/usePhotos'
import { formatDateTime } from '../utils/formatStats'
import { findOwnRating, ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'
import { primaryRanking } from '../utils/rankings'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { formatTimeOffset } from '../utils/timeOffset'

// Bounded so a broken/degenerate filter can never spin forever fetching pages while searching for
// the next unrated photo - 80 * PHOTOS_PAGE_SIZE(60) covers well beyond any realistic project size
// for this two-person MVP.
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
  const categoryOverrideControls = useCategoryOverrideControls(id)
  // Das feste Set kommt vom Server (langlebiger Cache) - Grundlage der Anzeigenamen und der "Alle
  // Kategorien"-Override-Auswahl.
  const categoriesQuery = useCategoriesQuery()
  const categorySet = categoriesQuery.data ?? []

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
    while (
      index + 1 >= currentPhotos.length &&
      query.hasNextPage &&
      fetches < MAX_AUTO_ADVANCE_PAGE_FETCHES
    ) {
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
   * naechsten unbewerteten Foto (Auto-Advance). Arbeitet bewusst auf dieser VOR der durch die
   * Mutation ausgeloesten Invalidierung erfassten Momentaufnahme statt auf einem Refetch zu warten:
   * da sich nur das gerade bewertete Foto aendert, bleibt der Bewertungsstatus aller anderen Fotos
   * in der Momentaufnahme weiterhin korrekt - unabhaengig davon, ob/wann die Invalidierung neu
   * laedt.
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
        { onSuccess: () => void advanceToNextUnrated(fromIndex) },
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

  // Swipe navigiert, Bewertung erfolgt separat per Tap auf die Bewertungs-Buttons (nicht per Swipe,
  // um versehentliche Bewertungen zu vermeiden).
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

  /* Beide Einbindungen der Aufschluesselung teilen EIN Props-Objekt: Bedienteil oben und
     Informationsteil unten
     sind zwei Ausschnitte derselben Darstellung und duerfen nicht auseinanderlaufen - zwei
     getrennt gepflegte Prop-Listen taeten genau das beim naechsten neuen Prop.
     showSuggestion={false} - die Ausschuss-Gruppe bleibt exklusiv im "Automatischer
     Vorschlag"-Kasten, suggestion wird hier bewusst nicht durchgereicht (kein Feld-/Logik-Merge
     zwischen beiden Bereichen). */
  /* Die Detailansicht zeigt EIN Foto - gemeint ist immer seine Hauptzugehoerigkeit.
     `rankings[0]` waere hier die falsche Abkuerzung,
     die Rolle kommt aus `is_primary`. Einmal gebildet, weil sie an zwei Stellen gebraucht wird:
     im Sichtbarkeitsgate des Bedienteils und in den Props beider Einbindungen. */
  const ranking = primaryRanking(currentPhoto)

  const detailsProps = {
    criterionScores: currentPhoto.criterion_scores,
    ranking,
    rankings: currentPhoto.rankings,
    suggestion: null,
    showSuggestion: false,
    categoryCandidates: currentPhoto.category_candidates,
    fineLabels: currentPhoto.fine_labels,
    categories: categorySet,
    categoriesLoading: categoriesQuery.isLoading,
    categoriesError: categoriesQuery.isError,
    onRetryCategories: () => {
      void categoriesQuery.refetch()
    },
    categoryOverride: currentPhoto.category_override,
    onOverrideCategory: (categoryKey: CategoryKey) =>
      categoryOverrideControls.overrideCategory(currentPhoto.id, categoryKey),
    onResetOverride: () => categoryOverrideControls.resetOverride(currentPhoto.id),
    pendingOverrideKey: categoryOverrideControls.pendingOverrideKeyFor(currentPhoto.id),
    resetPending: categoryOverrideControls.isResetPendingFor(currentPhoto.id),
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Bleibt unveraendert stehen (es wird nichts entfernt): durch die neuen
          Tasten-Kaestchen teilweise redundant, aber der Pfeiltasten-Teil hat kein sichtbares
          Gegenstueck. Nur als Metadatenzeile gesetzt statt als Fliesstext. */}
      <p className="text-xs text-text-muted">
        Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren
      </p>
      <p className="text-xs text-text-muted">
        {index + 1}/{total}
      </p>

      <div
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        className="relative mx-auto w-full max-w-2xl"
      >
        <PhotoImage
          photoId={currentPhoto.id}
          variant="display"
          alt={currentPhoto.relative_path}
          className="aspect-[4/3] w-full rounded-md object-contain"
        />
      </div>

      {/* Unmittelbar unter dem Foto: die primaere, haeufigste Handlung. role="group" mit
          aria-label="Bewertung" bleibt unveraendert - die Leiste wandert nur nach oben. */}
      <RatingButtons
        currentStatus={currentOwnStatus}
        onToggle={handleToggleRating}
        disabled={isMutating}
        busy={isMutating}
      />

      {/* Bedienteil der Bewertungsdetails (Akzeptanzkriterium 1b): Kandidatenliste bzw. die
          einzeilige "Kategorie"-Anzeige, der Konfidenz-Erklaerhinweis und die "Alle
          Kategorien"-Auswahl. Die reinen Informationsanzeigen derselben Komponente stehen weiter
          unten (`part="info"`). Der Wrapper haengt an derselben exportierten Vorbedingung, die
          auch die Komponente prueft - sonst verbrauchte ein leerer Bereich im `gap-4` dieser
          Seite einen sichtbaren Abstand. Bewusst kein Card-Rahmen/Schatten wie das Popover
          (Designprinzip "Die Fotos sind der Star"). */}
      {hasCategoryControls(currentPhoto.criterion_scores, ranking) && (
        <div className="text-sm text-text" data-testid="category-controls-section">
          <CriterionDetailsList {...detailsProps} part="controls" />
        </div>
      )}

      <div className="flex justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          aria-label="Vorheriges Foto"
          onClick={handlePrev}
          disabled={index <= 0}
        >
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
        <div className="flex flex-col items-start gap-2 rounded-md border border-accent bg-elevated p-3 text-sm">
          <p className="text-text-h">
            Automatischer Vorschlag: {formatSuggestionStatusLabel(suggestion)}
          </p>
          {/* Formatierung aus utils/suggestionLabels.ts - dasselbe Muster wird auch von
              CriterionDetailsPopover.tsx verwendet, keine zweite Kopie derselben Logik. Der
              fruehere dritte Fall "top_pick" (Kategorie + Qualitaets-Einordnung) ist entfallen -
              dieser Kuratierungs-Kontext lebt in der
              eigenstaendigen /curate-Ansicht statt in diesem Ausschuss-Vorschlagskasten (siehe
              api/types.ts::SuggestionOut-Docstring). */}
          <p className="text-text">{formatSuggestionReason(suggestion)}</p>
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

      {/* Trennlinie zwischen Bedien- und Informationsteil: ohne sie
          stiessen Vorschlagskasten und Informationsblöcke unvermittelt aneinander, und der
          Wechsel von "was ich mit diesem Foto tue" zu "was das System über dieses Foto weiß"
          waere nicht ablesbar. `--separator` ist die freistehende Linie auf dem Grund. */}
      <div className="border-t border-separator" />

      {/* AUFNAHMEZEIT - eine NEUE Anzeigestelle, keine Kennzeichnung an einer bestehenden: eine
          Aufnahmezeit je Foto wurde vor Spec 0426 nirgends gezeigt. Sie steht im
          Informationsteil, weil sie sagt, was das System über dieses Foto weiß. */}
      <section className="flex flex-col gap-1 text-sm" data-testid="taken-at-section">
        <h2 className="text-xs font-semibold tracking-wide text-text-h uppercase">Aufnahmezeit</h2>
        <p className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-text">{formatDateTime(currentPhoto.taken_at)}</span>
          {/* Die Marke NUR im Korrekturfall, im Ton von `CategoryOverrideMarker`: eine Korrektur
              ist der GEWOLLTE Zustand, kein Alarm. */}
          {currentPhoto.time_offset_minutes !== 0 && (
            <span className="text-xs text-text-muted" data-corrected="true">
              korrigiert
            </span>
          )}
        </p>
        {/* Die zweite Zeile nur im Korrekturfall - bei Versatz `0` wäre sie eine Wiederholung
            derselben Zeit und damit eine Aussage ohne Inhalt. */}
        {currentPhoto.time_offset_minutes !== 0 && (
          <p className="text-xs text-text-muted">
            aufgezeichnet{' '}
            <span className="font-mono">{formatDateTime(currentPhoto.taken_at_original)}</span> ·{' '}
            {formatTimeOffset(currentPhoto.time_offset_minutes)}
          </p>
        )}
        {/* Ist keine Kamera bestimmbar, steht das als RUHIGER SATZ da und nicht als Fehlen. */}
        <p className="text-xs text-text-muted">
          {currentPhoto.camera === null
            ? 'Die Kamera dieses Fotos ist nicht bestimmbar.'
            : currentPhoto.camera.label}
        </p>
      </section>

      {/* Layout & Platzierung: unmittelbar vor der CriterionDetailsList UND nach den
          Bewertungs-Buttons - beides zusammen ist erst seit der Umordnung der Seite erfuellbar
          (die Bewertungsleiste stand zuvor weiter unten). IMMER sichtbar (bewusste
          Stakeholder-Entscheidung, kein Ausblenden bei not_candidate/not_run, siehe
          Spec-Abschnitt "Entscheidungen") - anders als die CriterionDetailsList darunter kein
          `.length > 0`-Sichtbarkeitsgate. */}
      <div className="text-sm text-text" data-testid="cloud-vision-status-section">
        <CloudVisionStatusList cloudVisionStatus={currentPhoto.cloud_vision_status} />
      </div>

      {/* Informationsteil der permanenten Sektion - permanent statt Info-Popover; die fruehere
          Platzierungsvorgabe "vor den Navigationsbuttons" ist abgeloest, die permanente
          Sichtbarkeit selbst gilt weiter. Gleiche Sichtbarkeitsregel wie die bisherige
          Icon-Sichtbarkeit: kein leerer Bereich bei leerer Liste. */}
      {currentPhoto.criterion_scores.length > 0 && (
        <div className="text-sm text-text" data-testid="criterion-details-section">
          <CriterionDetailsList {...detailsProps} part="info" />
        </div>
      )}

      <Button asChild variant="ghost" className="self-start">
        <Link to={`/projects/${id}/photos${filterQuery}`}>Zurück zum Grid</Link>
      </Button>
    </div>
  )
}
