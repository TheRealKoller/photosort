import { useEffect } from 'react'
import type { SetURLSearchParams } from 'react-router'

import type { ClassificationReviewCaseOut } from '../api/types'

const VALID_POSITION = /^\d+$/

/**
 * Das Foto, auf das ein fehlender oder ungueltiger `?foto=` zeigt: das erste mit offenem Fall,
 * sonst das erste mit ueberhaupt einem Fall.
 */
function firstOpenPosition(cases: readonly ClassificationReviewCaseOut[]): number | null {
  const open = cases.find((reviewCase) => reviewCase.verdict === null)
  return (open ?? cases.at(0))?.photo_position ?? null
}

/**
 * Das Foto der Fallansicht aus `?foto=<Position>` samt Nachbarpositionen. Ein ungueltiger Wert wird
 * ohne Serverrunde per `replace` ersetzt.
 */
export function useReviewPhotoPosition(
  searchParams: URLSearchParams,
  setSearchParams: SetURLSearchParams,
  cases: readonly ClassificationReviewCaseOut[],
  photoCount: number,
  casesLoaded: boolean,
) {
  const fotoParam = searchParams.get('foto')
  const requestedPosition =
    fotoParam !== null && VALID_POSITION.test(fotoParam) ? Number(fotoParam) : null
  const position =
    requestedPosition !== null && requestedPosition >= 1 && requestedPosition <= photoCount
      ? requestedPosition
      : null
  const fallbackPosition = firstOpenPosition(cases)

  // Ein ungueltiger oder fehlender Wert wird erst ersetzt, wenn die Faelle da sind - vorher ist
  // das erste offene Foto unbekannt.
  useEffect(() => {
    if (position === null && casesLoaded && fallbackPosition !== null) {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.set('foto', String(fallbackPosition))
          return next
        },
        { replace: true },
      )
    }
  }, [position, casesLoaded, fallbackPosition, setSearchParams])

  const positions = [...new Set(cases.map((reviewCase) => reviewCase.photo_position))]
  const photoCases = cases.filter((reviewCase) => reviewCase.photo_position === position)
  const previousPosition = positions.findLast(
    (candidate) => position !== null && candidate < position,
  )
  const nextPosition = positions.find((candidate) => position !== null && candidate > position)
  const openPositions = [
    ...new Set(
      cases
        .filter(
          (reviewCase) => reviewCase.verdict === null && reviewCase.photo_position !== position,
        )
        .map((reviewCase) => reviewCase.photo_position),
    ),
  ]
  const nextOpenPosition =
    openPositions.find((candidate) => position !== null && candidate > position) ??
    openPositions.at(0)

  return { position, photoCases, previousPosition, nextPosition, nextOpenPosition }
}
