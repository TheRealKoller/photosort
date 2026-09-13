import type { RatingStatus } from '../api/types'

// Farb-/Symbol-Zuordnung des Design-Systems: Bewertungsstufen sind auf einen Blick unterscheidbar -
// Farbe UND Symbol, nicht nur Text. Eigene Datei statt Export aus components/RatingBadge.tsx
// (Lint-Fund: oxlint react-refresh/only-export-components warnt, wenn eine Komponentendatei
// zusaetzlich einen benannten Konstanten-Export hat) - sowohl RatingBadge als auch PhotoDetailPage
// brauchen dieselbe ausgeschriebene Beschriftung je Bewertungsstufe.
export const RATING_STATUS_LABELS: Record<RatingStatus, string> = {
  album_worthy: 'Album-würdig',
  rejected: 'Verworfen',
}

/**
 * Die drei Einträge der Bewertungsleiste: die zweiwertige Albumentscheidung und der Favorit
 * daneben.
 *
 * Der Favorit ist seit ADR 0098 KEIN Bewertungsstatus mehr, trägt in der Oberfläche aber
 * dieselbe Form wie einer - eigenes Wort, eigenes Symbol, eigene Tonfarbe. Er ist unabhängig
 * schaltbar und kann gleichzeitig mit einer Albumentscheidung gesetzt sein.
 */
export type RatingControl = RatingStatus | 'favorite'

export const RATING_CONTROL_LABELS: Record<RatingControl, string> = {
  favorite: 'Favorit',
  ...RATING_STATUS_LABELS,
}
