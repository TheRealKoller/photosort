import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingOut } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { PhotoImage } from '../components/PhotoImage'
import { RatingBadge } from '../components/RatingBadge'
import { usePhotoSequenceQuery } from '../hooks/usePhotos'

function ownRating(ratings: RatingOut[], username: string | null): RatingOut | undefined {
  if (username === null) {
    return undefined
  }
  return ratings.find((rating) => rating.username === username)
}

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
    <div>
      <h1>Vergleich</h1>

      {query.isLoading && <p role="status">Fotos werden geladen…</p>}

      {query.isError && (
        <div role="alert">
          <p>
            {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
          </p>
        </div>
      )}

      {query.isSuccess && photos.length === 0 && <p>Keine Fotos in diesem Projekt.</p>}

      {photos.length > 0 && (
        <ul>
          {photos.map((photo) => {
            const mine = ownRating(photo.ratings, username)
            const others = photo.ratings.filter((rating) => rating.username !== username)
            return (
              <li key={photo.id}>
                <Link to={`/projects/${id}/photos/${photo.id}`}>
                  <PhotoImage photoId={photo.id} variant="thumbnail" alt={photo.relative_path} />
                </Link>
                <span>
                  Ich: <RatingBadge status={mine?.status ?? null} />
                </span>
                {others.length > 0 ? (
                  others.map((rating) => (
                    <span key={rating.user_id}>
                      {rating.username}: <RatingBadge status={rating.status} />
                    </span>
                  ))
                ) : (
                  <span>
                    Andere: <RatingBadge status={null} />
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {query.hasNextPage && (
        <button
          type="button"
          onClick={() => void query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
        >
          {query.isFetchingNextPage ? 'Lädt…' : 'Weitere laden'}
        </button>
      )}

      <Link to={`/projects/${id}`}>Zurück zum Projekt</Link>
    </div>
  )
}
