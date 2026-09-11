import type { RatingStatus } from '../api/types'

// Farb-/Symbol-Zuordnung des Design-Systems: Bewertungsstufen sind auf einen Blick unterscheidbar -
// Farbe UND Symbol, nicht nur Text. Eigene Datei statt Export aus components/RatingBadge.tsx
// (Lint-Fund: oxlint react-refresh/only-export-components warnt, wenn eine Komponentendatei
// zusaetzlich einen benannten Konstanten-Export hat) - sowohl RatingBadge als auch PhotoDetailPage
// brauchen dieselbe ausgeschriebene Beschriftung je Bewertungsstufe.
export const RATING_STATUS_LABELS: Record<RatingStatus, string> = {
  favorite: 'Favorit',
  album_worthy: 'Album-würdig',
  rejected: 'Verworfen',
}
