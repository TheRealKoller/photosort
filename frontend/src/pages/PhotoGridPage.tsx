import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingFilter } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { CriterionDetailsPopover } from '../components/CriterionDetailsPopover'
import { MotifAssessmentMarker } from '../components/MotifAssessmentMarker'
import { PhotoCard } from '../components/PhotoCard'
import { PhotoImage } from '../components/PhotoImage'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { useDuplicateGroupIndexQuery } from '../hooks/useDuplicates'
import { useMotifsQuery } from '../hooks/useMotifs'
import { useConfirmAusschussGateMutation } from '../hooks/useProjects'
import { usePhotoSequenceQuery, useSetRatingMutation } from '../hooks/usePhotos'
import { ownFavorite, ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln" statt
// eines vollflaechigen Spinners - Anzahl ist nur eine plausible Annaeherung an einen typischen
// Batch, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

/*
 * Die Einträge bleiben unverändert, ihre Bedeutung ändert sich an zwei Stellen (ADR 0098):
 *
 * - "Unbewertet" heißt KEINE ALBUMENTSCHEIDUNG, nicht mehr "keine Bewertungszeile". Ein nur als
 *   Favorit markiertes Bild bleibt darin und behält seinen Vorschlag.
 * - "Favorit" filtert auf das eigene Kennzeichen, nicht auf einen Bewertungsstatus. Die Einträge
 *   schließen einander damit nicht mehr aus: ein Foto kann in "Favorit" UND in "Album-würdig"
 *   erscheinen.
 */
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
  // Ausschuss-Gate-Modus: kein neuer Screen, sondern diese bestehende Seite um `&gate=1` erweitert.
  const isGateMode = searchParams.get('gate') === '1'

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus)
  const setRatingMutation = useSetRatingMutation(id)
  const gateMutation = useConfirmAusschussGateMutation(id)
  // Das Motivset kommt vom Server (langlebiger Cache) - Grundlage der schreibgeschuetzten
  // Motivliste im Info-Popover. EIN Request fuer alle Kacheln.
  const motifsQuery = useMotifsQuery()
  const motifSetError = motifsQuery.isError
    ? motifsQuery.error instanceof ApiError
      ? motifsQuery.error.detail
      : 'Fehler beim Laden der Motive.'
    : undefined
  const photos = query.data?.pages.flatMap((page) => page.items) ?? []
  const totalSuggested = query.data?.pages[0]?.total ?? 0
  // Nur unter dem Vorschlags-Filter: Dort wird der Ausschuss gesichtet, und nur dort gehoert der
  // Weg durch die Serien hin. Unter jedem anderen Filter liefe die Anfrage ohne Adressaten.
  const duplicateGroupIndex = useDuplicateGroupIndexQuery(id, {
    enabled: filterParam === 'suggested',
  })

  function handleConfirmGate(): void {
    if (gateMutation.isPending) {
      return
    }
    gateMutation.mutate(undefined, {
      // Redirect-Ziel ist /projects/:id/pipeline statt /projects/:id (feste Einzelseite) (ohne
      // festen :step) - landet ueber getDefaultStepId automatisch beim naechsten sinnvollen
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
            {totalSuggested === 1 ? 'Kandidat' : 'Kandidaten'}), bevor du fortfährst. Einzelne Fotos
            kannst du hier korrigieren ("Übernehmen"-Button/Bewertung in der Detailansicht) - das
            ist aber nicht Voraussetzung, um fortzufahren.
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

      {/* EIN Weg für die ganze Liste, außerhalb des Kachelrasters — der kachelgenaue Einstieg
          bleibt daneben bestehen. Sein zugänglicher Name unterscheidet sich bewusst vom
          kachelgenauen `Duplikate vergleichen: <Dateiname>`: Der Prüfstack wählt jenen über ein
          Präfixmuster, und ein zweiter Treffer führte ihn in die falsche Ansicht.

          Bei `total === 0` und während des Ladens ausgeblendet, nicht deaktiviert (AK8): Ein Weg,
          der auf einen Leerzustand führt, ist kein Weg, und ein kurz aufblitzender Einstieg wäre
          schlimmer als keiner. */}
      {duplicateGroupIndex.isSuccess && duplicateGroupIndex.data.first_photo_id !== null && (
        <Button asChild variant="secondary" size="sm" className="self-start">
          <Link
            to={`/projects/${id}/photos/${duplicateGroupIndex.data.first_photo_id}/duplicates`}
            aria-label="Alle Duplikat-Gruppen der Reihe nach durchgehen"
          >
            Duplikat-Gruppen durchgehen
          </Link>
        </Button>
      )}

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
            // SICHERHEIT (Auflage S6): das EIGENE Kennzeichen, ueber `utils/ownRating.ts` -
            // nie `photo.ratings.some(r => r.favorite)`, das zeigte die Auszeichnung der
            // anderen Person als die eigene.
            const isFavorite = ownFavorite(photo.ratings, username)
            // Anzeigeregel (Akzeptanzkriterium der Spec): eigene Bewertung hat immer Vorrang -
            // eine Vorschlags-Badge erscheint nur, solange keine eigene Bewertung existiert.
            // Der Server garantiert bereits, dass photo.suggestion in diesem Fall null ist, aber
            // ownStatus wird hier zusaetzlich geprueft statt sich blind auf suggestion zu
            // verlassen (defensiv, gleiche Anzeigeregel wie die Detailansicht).
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
                },
              )
            }

            return (
              <PhotoCard
                key={photo.id}
                to={`/projects/${id}/photos/${photo.id}${filterParam ? `?filter=${filterParam}` : ''}`}
                relativePath={photo.relative_path}
                status={badgeStatus}
                favorite={isFavorite}
                suggested={isSuggested}
                image={
                  <PhotoImage
                    photoId={photo.id}
                    variant="thumbnail"
                    alt={photo.relative_path}
                    className="size-full object-cover"
                  />
                }
                /* Motiv-Marker in der Ecke oben links, Info-Trigger oben rechts. Beide sind
                   Geschwister der Bildflaeche und liegen nie in ihr - die Bildflaeche
                   beschneidet, und eine aufgespannte Trefferflaeche in einem beschneidenden
                   Container wuerde still abgeschnitten.
                   Der `MotifAssessmentMarker` ist der EINZIGE Motiv-Marker der Kachel; `=== null`
                   geprueft und nicht auf Falsyness, denn `undefined` (Feld nicht durchgereicht)
                   ist keine Aussage ueber den Klassifizierungsstand. */
                topLeft={photo.motif_assessment === null ? <MotifAssessmentMarker /> : undefined}
                topRight={
                  <CriterionDetailsPopover
                    criterionScores={photo.criterion_scores}
                    ranking={photo.ranking ?? null}
                    suggestion={photo.suggestion}
                    fineLabels={photo.fine_labels}
                    motifSet={motifsQuery.data}
                    motifSetLoading={motifsQuery.isLoading}
                    motifSetError={motifSetError}
                    onMotifSetRetry={() => {
                      void motifsQuery.refetch()
                    }}
                    assessment={photo.motif_assessment ?? null}
                    motifs={photo.motifs}
                    albumSuitability={photo.album_suitability ?? null}
                  />
                }
                /* Separates Tap-Ziel ausserhalb des Kachel-Links (UI/UX-Abschnitt der Spec): die
                   Kachel selbst oeffnet weiterhin die Detailansicht, "Uebernehmen" bestaetigt den
                   Vorschlag direkt, ohne zu navigieren. Das `aria-label` enthaelt den Dateinamen -
                   mehrere offene Vorschlaege im selben Raster waeren sonst per Tastatur/
                   Screenreader nicht auseinanderzuhalten. */
                /* ZWEI Wege nebeneinander, nicht einer statt des anderen: "Übernehmen"
                   bestätigt den Vorschlag hier, der Vergleich öffnet die ganze Serie. Der
                   Einstieg erscheint NUR bei `reason === 'duplicate'` - eine wegen Unschärfe
                   abgelehnte Aufnahme hat keine Gruppe, und ein Weg, der auf einen Leerzustand
                   führt, ist kein Weg. 12px Abstand zwischen den beiden aufgespannten
                   Trefferflächen (`gap-3`). */
                footer={
                  isSuggested ? (
                    <div className="flex flex-wrap gap-3">
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
                      {photo.suggestion?.reason === 'duplicate' && (
                        <Button asChild variant="ghost" size="sm">
                          <Link
                            to={`/projects/${id}/photos/${photo.id}/duplicates`}
                            aria-label={`Duplikate vergleichen: ${photo.relative_path}`}
                          >
                            Vergleichen
                          </Link>
                        </Button>
                      )}
                    </div>
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
