import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { PhotoOut } from '../api/types'
import { ownRatingStatus } from '../utils/ownRating'

// Bounded so a broken/degenerate filter can never spin forever fetching pages while searching for
// the next unrated photo.
const MAX_AUTO_ADVANCE_PAGE_FETCHES = 80

interface PhotoSequenceNavigationOptions {
  projectId: number
  photos: PhotoOut[]
  index: number
  hasNextPage: boolean
  fetchNextPage: () => Promise<{ data?: { pages: { items: PhotoOut[] }[] } }>
  filterQuery: string
  username: string | null
}

export function usePhotoSequenceNavigation({
  projectId,
  photos,
  index,
  hasNextPage,
  fetchNextPage,
  filterQuery,
  username,
}: PhotoSequenceNavigationOptions) {
  const navigate = useNavigate()
  const [completed, setCompleted] = useState(false)

  function goTo(targetPhotoId: number): void {
    navigate(`/projects/${projectId}/photos/${targetPhotoId}${filterQuery}`)
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
      hasNextPage &&
      fetches < MAX_AUTO_ADVANCE_PAGE_FETCHES
    ) {
      const result = await fetchNextPage()
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
        // "Noch offen" ist die fehlende ALBUMENTSCHEIDUNG, nicht die fehlende Zeile: ein nur als
        // Favorit markiertes Foto ist unentschieden und darf nicht uebersprungen werden.
        if (ownRatingStatus(candidate.ratings, username) === null) {
          goTo(candidate.id)
          return
        }
        i += 1
      }
      if (!hasNextPage || fetches >= MAX_AUTO_ADVANCE_PAGE_FETCHES) {
        break
      }
      const result = await fetchNextPage()
      currentPhotos = result.data?.pages.flatMap((page) => page.items) ?? currentPhotos
      fetches += 1
    }
    setCompleted(true)
  }

  return { goTo, handlePrev, handleNext, advanceToNextUnrated, completed }
}
