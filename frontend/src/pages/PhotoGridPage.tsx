import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingFilter } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CategoryOverrideMarker } from '../components/CategoryOverrideMarker'
import { CriterionDetailsPopover } from '../components/CriterionDetailsPopover'
import { PhotoCard } from '../components/PhotoCard'
import { PhotoImage } from '../components/PhotoImage'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useCategoriesQuery } from '../hooks/useCategories'
import { useCategoryOverrideControls } from '../hooks/useCategoryOverrideControls'
import { useConfirmAusschussGateMutation } from '../hooks/useProjects'
import { usePhotoSequenceQuery, useSetRatingMutation } from '../hooks/usePhotos'
import { ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln"
// (specs/architecture/0004-design-system.md) statt eines vollflaechigen Spinners - Anzahl ist
// nur eine plausible Annaeherung an einen typischen Batch, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

const FILTERS: { value: RatingFilter | ''; label: string }[] = [
  { value: '', label: 'Alle' },
  { value: 'unrated', label: 'Unbewertet' },
  { value: 'suggested', label: 'Vorgeschlagen' },
  { value: 'favorite', label: 'Favorit' },
  { value: 'album_worthy', label: 'Album-würdig' },
  { value: 'rejected', label: 'Verworfen' },
]

export function PhotoGridPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const filterParam = parseRatingFilter(searchParams.get('filter'))
  const ratingStatus = filterParam === '' ? undefined : filterParam
  // Ausschuss-Gate-Modus (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md,
  // UI/UX-Abschnitt): kein neuer Screen, sondern diese bestehende Seite um `&gate=1` erweitert.
  const isGateMode = searchParams.get('gate') === '1'

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus)
  const setRatingMutation = useSetRatingMutation(id)
  const gateMutation = useConfirmAusschussGateMutation(id)
  const categoryOverrideControls = useCategoryOverrideControls(id)
  // specs/features/0289-feste-kategorien.md: das feste Set kommt vom Server (langlebiger Cache) -
  // Grundlage der Anzeigenamen und der "Alle Kategorien"-Override-Auswahl.
  const categoriesQuery = useCategoriesQuery()
  const categorySet = categoriesQuery.data ?? []
  const photos = query.data?.pages.flatMap((page) => page.items) ?? []
  const totalSuggested = query.data?.pages[0]?.total ?? 0

  function handleConfirmGate(): void {
    if (gateMutation.isPending) {
      return
    }
    gateMutation.mutate(undefined, {
      // specs/features/0042-automatisierter-flow-stepper-detailseiten.md, Akzeptanzkriterium 9:
      // Redirect-Ziel wechselt von /projects/:id (feste Einzelseite) auf /projects/:id/pipeline
      // (ohne festen :step) - landet ueber getDefaultStepId automatisch beim naechsten sinnvollen
      // Schritt, statt immer auf der (jetzt entfallenen) statischen Projekt-Detailseite.
      onSuccess: () => navigate(`/projects/${id}/pipeline`),
    })
  }

  // UI/UX-Review-Fund: setRatingMutation ist EINE Instanz fuer die ganze Seite (ein einzelner
  // useMutation-Hook) - ihr eigenes `isPending` haette bei jedem weiteren Klick, waehrend
  // irgendeine ANDERE Kachel noch unterwegs ist, den Klick stillschweigend blockiert. Das
  // widerspricht dem in der Spec genannten Zweck des Buttons ("zuegiges Batch-Bestaetigen vieler
  // aehnlicher Ausschuss-Kandidaten"). Eigener, photo-spezifischer Pending-Zustand statt dessen:
  // jede Kachel trackt unabhaengig, ob IHR EIGENER Bestaetigungs-Request noch laeuft.
  const [confirmingPhotoIds, setConfirmingPhotoIds] = useState<ReadonlySet<number>>(new Set())

  function handleFilterChange(value: RatingFilter | ''): void {
    const next = new URLSearchParams(searchParams)
    if (value === '') {
      next.delete('filter')
    } else {
      next.set('filter', value)
    }
    setSearchParams(next)
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl sm:text-2xl">Fotos</h1>

      {isGateMode && (
        <div className="flex flex-col items-start gap-3 rounded-md border border-accent bg-elevated p-3 text-sm">
          <p className="text-text-h">
            Sichte den erkannten Ausschuss ({totalSuggested}{' '}
            {totalSuggested === 1 ? 'Kandidat' : 'Kandidaten'}), bevor du fortfährst. Einzelne
            Fotos kannst du hier korrigieren ("Übernehmen"-Button/Bewertung in der
            Detailansicht) - das ist aber nicht Voraussetzung, um fortzufahren.
          </p>
          <Button
            type="button"
            onClick={handleConfirmGate}
            disabled={gateMutation.isPending}
            busy={gateMutation.isPending}
          >
            {gateMutation.isPending ? 'Wird bestätigt…' : 'Ausschuss gesichtet, weiter'}
          </Button>
          {gateMutation.isError && (
            <Alert>
              {gateMutation.error instanceof ApiError
                ? gateMutation.error.detail
                : 'Fehler beim Bestätigen des Ausschuss-Gates.'}
            </Alert>
          )}
        </div>
      )}

      <div role="group" aria-label="Filter" className="flex flex-wrap gap-2">
        {FILTERS.map((option) => (
          <Button
            key={option.value || 'all'}
            type="button"
            variant={filterParam === option.value ? 'default' : 'outline'}
            size="sm"
            aria-pressed={filterParam === option.value}
            onClick={() => handleFilterChange(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>

      {query.isLoading && (
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

      {query.isSuccess && photos.length === 0 && (
        <div className="flex flex-col items-start gap-3 text-sm text-text">
          <p>Keine Fotos mit diesem Filter.</p>
          {filterParam !== '' && (
            <Button type="button" variant="outline" onClick={() => handleFilterChange('')}>
              Filter zurücksetzen
            </Button>
          )}
        </div>
      )}

      {photos.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {photos.map((photo) => {
            const ownStatus = ownRatingStatus(photo.ratings, username)
            // Anzeigeregel (Akzeptanzkriterium der Spec): eigene Bewertung hat immer Vorrang -
            // eine Vorschlags-Badge erscheint nur, solange keine eigene Bewertung existiert.
            // Der Server garantiert bereits, dass photo.suggestion in diesem Fall null ist, aber
            // ownStatus wird hier zusaetzlich geprueft statt sich blind auf suggestion zu
            // verlassen (defensiv, gleiche Anzeigeregel wie Detail-/Vergleichsansicht).
            const isSuggested = ownStatus === null && photo.suggestion !== null
            const badgeStatus = ownStatus ?? photo.suggestion?.status ?? null
            const isConfirming = confirmingPhotoIds.has(photo.id)

            function handleConfirmSuggestion(): void {
              if (photo.suggestion === null || isConfirming) {
                return
              }
              setConfirmingPhotoIds((prev) => new Set(prev).add(photo.id))
              setRatingMutation.mutate(
                { photoId: photo.id, status: photo.suggestion.status },
                {
                  onSettled: () => {
                    setConfirmingPhotoIds((prev) => {
                      const next = new Set(prev)
                      next.delete(photo.id)
                      return next
                    })
                  },
                }
              )
            }

            return (
              <PhotoCard
                key={photo.id}
                to={`/projects/${id}/photos/${photo.id}${filterParam ? `?filter=${filterParam}` : ''}`}
                relativePath={photo.relative_path}
                status={badgeStatus}
                suggested={isSuggested}
                image={
                  <PhotoImage
                    photoId={photo.id}
                    variant="thumbnail"
                    alt={photo.relative_path}
                    className="size-full object-cover"
                  />
                }
                /* specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md:
                   Uebersteuerungs-Marker in der Ecke oben links, Info-Trigger oben rechts. Beide
                   sind seit Spec 0321 Geschwister der Bildflaeche und liegen nie in ihr - die
                   Bildflaeche beschneidet, und eine aufgespannte Trefferflaeche in einem
                   beschneidenden Container wuerde still abgeschnitten.
                   Der frueher noetige `pointer-events-none`-Kniff entfaellt ersatzlos: Das
                   Zustandskennzeichen liegt nicht mehr ueber der Kachel, sondern im Kartenkoerper,
                   und faengt deshalb keine Klicks mehr ab, die zum Kachel-Link durchsollen. */
                topLeft={photo.category_override !== null ? <CategoryOverrideMarker /> : undefined}
                topRight={
                  <CriterionDetailsPopover
                    criterionScores={photo.criterion_scores}
                    ranking={photo.ranking}
                    suggestion={photo.suggestion}
                    categoryCandidates={photo.category_candidates}
                    fineLabels={photo.fine_labels}
                    categories={categorySet}
                    categoriesLoading={categoriesQuery.isLoading}
                    categoriesError={categoriesQuery.isError}
                    onRetryCategories={() => {
                      void categoriesQuery.refetch()
                    }}
                    categoryOverride={photo.category_override}
                    onOverrideCategory={(categoryKey) =>
                      categoryOverrideControls.overrideCategory(photo.id, categoryKey)
                    }
                    onResetOverride={() => categoryOverrideControls.resetOverride(photo.id)}
                    pendingOverrideKey={categoryOverrideControls.pendingOverrideKeyFor(photo.id)}
                    resetPending={categoryOverrideControls.isResetPendingFor(photo.id)}
                  />
                }
                /* Separates Tap-Ziel ausserhalb des Kachel-Links (UI/UX-Abschnitt der Spec): die
                   Kachel selbst oeffnet weiterhin die Detailansicht, "Uebernehmen" bestaetigt den
                   Vorschlag direkt, ohne zu navigieren. Das `aria-label` enthaelt den Dateinamen -
                   mehrere offene Vorschlaege im selben Raster waeren sonst per Tastatur/
                   Screenreader nicht auseinanderzuhalten. */
                footer={
                  isSuggested ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Vorschlag übernehmen: ${photo.relative_path}`}
                      busy={isConfirming}
                      onClick={handleConfirmSuggestion}
                    >
                      {isConfirming ? 'Wird übernommen…' : 'Übernehmen'}
                    </Button>
                  ) : undefined
                }
              />
            )
          })}
        </ul>
      )}

      {query.hasNextPage && (
        <Button
          type="button"
          variant="outline"
          busy={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
          className="self-start"
        >
          {query.isFetchingNextPage ? 'Lädt…' : 'Weitere laden'}
        </Button>
      )}
    </div>
  )
}
