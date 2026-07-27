import { apiFetch } from './client'
import type { RatingOut, RatingStatus } from './types'

export function setRating(photoId: number, status: RatingStatus): Promise<RatingOut> {
  return apiFetch<RatingOut>(`/photos/${photoId}/rating`, { method: 'PUT', body: { status } })
}

export function deleteRating(photoId: number): Promise<void> {
  return apiFetch<void>(`/photos/${photoId}/rating`, { method: 'DELETE' })
}
