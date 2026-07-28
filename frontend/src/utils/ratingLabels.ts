import type { RatingStatus } from '../api/types'

// Farb-/Symbol-Zuordnung gemaess specs/architecture/0004-design-system.md ("Bewertungsstufen auf
// einen Blick unterscheidbar" - Farbe UND Symbol, nicht nur Text). Eigene Datei statt Export aus
// components/RatingBadge.tsx (Lint-Fund: oxlint react-refresh/only-export-components warnt, wenn
// eine Komponentendatei zusaetzlich einen benannten Konstanten-Export hat) - sowohl RatingBadge
// als auch PhotoDetailPage brauchen dieselbe ausgeschriebene Beschriftung je Bewertungsstufe.
export const RATING_STATUS_LABELS: Record<RatingStatus, string> = {
  favorite: 'Favorit',
  album_worthy: 'Album-würdig',
  rejected: 'Verworfen',
}
