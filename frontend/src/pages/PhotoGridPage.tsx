import { Link, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import type { RatingFilter } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'
import { PhotoImage } from '../components/PhotoImage'
import { RatingBadge } from '../components/RatingBadge'
import { usePhotoSequenceQuery } from '../hooks/usePhotos'
import { ownRatingStatus } from '../utils/ownRating'
import { parseRatingFilter } from '../utils/ratingFilter'

// Design-System-Muster "Skeleton-/Platzhalter-Kacheln ... wo Inhalte schrittweise eintrudeln"
// (specs/architecture/0004-design-system.md) statt eines vollflaechigen Spinners - Anzahl ist
// nur eine plausible Annaeherung an einen typischen Batch, keine harte Vorgabe.
const SKELETON_TILE_COUNT = 6

const FILTERS: { value: RatingFilter | ''; label: string }[] = [
  { value: '', label: 'Alle' },
  { value: 'unrated', label: 'Unbewertet' },
  { value: 'favorite', label: 'Favorit' },
  { value: 'album_worthy', label: 'Album-würdig' },
  { value: 'rejected', label: 'Verworfen' },
]

export function PhotoGridPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [searchParams, setSearchParams] = useSearchParams()
  const filterParam = parseRatingFilter(searchParams.get('filter'))
  const ratingStatus = filterParam === '' ? undefined : filterParam

  const token = getToken()
  const username = token ? decodeUsername(token) : null

  const query = usePhotoSequenceQuery(id, ratingStatus)
  const photos = query.data?.pages.flatMap((page) => page.items) ?? []

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
    <div>
      <h1>Fotos</h1>

      <div role="group" aria-label="Filter">
        {FILTERS.map((option) => (
          <button
            key={option.value || 'all'}
            type="button"
            aria-pressed={filterParam === option.value}
            onClick={() => handleFilterChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {query.isLoading && (
        <ul role="status" aria-label="Fotos werden geladen…">
          {Array.from({ length: SKELETON_TILE_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true" />
          ))}
        </ul>
      )}

      {query.isError && (
        <div role="alert">
          <p>
            {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Fotos.'}
          </p>
          <button type="button" onClick={() => void query.refetch()}>
            Erneut versuchen
          </button>
        </div>
      )}

      {query.isSuccess && photos.length === 0 && (
        <div>
          <p>Keine Fotos mit diesem Filter.</p>
          {filterParam !== '' && (
            <button type="button" onClick={() => handleFilterChange('')}>
              Filter zurücksetzen
            </button>
          )}
        </div>
      )}

      {photos.length > 0 && (
        <ul>
          {photos.map((photo) => (
            <li key={photo.id}>
              <Link
                to={`/projects/${id}/photos/${photo.id}${filterParam ? `?filter=${filterParam}` : ''}`}
              >
                <PhotoImage photoId={photo.id} variant="thumbnail" alt={photo.relative_path} />
                <RatingBadge status={ownRatingStatus(photo.ratings, username)} />
              </Link>
            </li>
          ))}
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
