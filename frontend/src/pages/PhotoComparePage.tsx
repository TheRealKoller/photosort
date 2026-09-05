import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { PhotoImage } from '../components/PhotoImage'
import { RatingBadge } from '../components/RatingBadge'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { usePhotoSequenceQuery } from '../hooks/usePhotos'
import { findOwnRating } from '../utils/ownRating'

/**
 * Vergleichsansicht (specs/features/0002-manual-categorization.md): zeigt pro Foto beide
 * Bewertungen nebeneinander, inkl. "unbewertet" als eigener sichtbarer Zustand. Nur lesend hier -
 * die Bearbeitung findet in der (per Deep-Link geoeffneten) Einzelbild-Ansicht statt, die
 * ohnehin ausschliesslich die eigene Bewertung des angemeldeten Nutzers editiert (user_id kommt
 * serverseitig immer aus dem JWT, nie aus der Navigation).
 */
export function PhotoComparePage() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id)
  const photos = query.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl sm:text-2xl">Vergleich</h1>

      {query.isLoading && (
        <p role="status" className="text-sm text-text">
          Fotos werden geladen…
        </p>
      )}

      {query.isError && (
        <Alert onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
        </Alert>
      )}

      {query.isSuccess && photos.length === 0 && (
        <p className="text-sm text-text">Keine Fotos in diesem Projekt.</p>
      )}

      {photos.length > 0 && (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {photos.map((photo) => {
            const mine = findOwnRating(photo.ratings, username)
            const others = photo.ratings.filter((rating) => rating.username !== username)
            // ADR 0006 / UI/UX-Abschnitt der Spec 0003: der Vorschlag ersetzt innerhalb der
            // bestehenden "Ich"-Position nur die bisherige "–"-Darstellung, solange keine eigene
            // Bewertung vorliegt - kein dritter Spalten-/Personen-Slot neben "Ich"/"Andere".
            const myStatus = mine?.status ?? photo.suggestion?.status ?? null
            const myStatusIsSuggested = mine === undefined && photo.suggestion !== null
            return (
              <li key={photo.id} className="flex flex-col gap-2 rounded-xl border border-border p-2">
                <Link
                  to={`/projects/${id}/photos/${photo.id}`}
                  className="block aspect-square overflow-hidden rounded-md"
                >
                  {/* Spec 0002 (Bild-Auflösungen): "Einzelbild-/Vergleichsansicht
                      Display-Auflösung" - bewusst dieselbe Auflösung wie PhotoDetailPage,
                      nicht die Grid-Thumbnail-Auflösung. */}
                  <PhotoImage
                    photoId={photo.id}
                    variant="display"
                    alt={photo.relative_path}
                    className="size-full object-cover"
                  />
                </Link>
                <span className="flex items-center gap-1.5 text-sm text-text">
                  Ich: <RatingBadge status={myStatus} suggested={myStatusIsSuggested} />
                </span>
                {others.length > 0 ? (
                  others.map((rating) => (
                    <span key={rating.user_id} className="flex items-center gap-1.5 text-sm text-text">
                      {rating.username}: <RatingBadge status={rating.status} />
                    </span>
                  ))
                ) : (
                  <span className="flex items-center gap-1.5 text-sm text-text">
                    Andere: <RatingBadge status={null} />
                  </span>
                )}
              </li>
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
