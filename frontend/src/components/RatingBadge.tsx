import type { RatingStatus } from '../api/types'

// Farb-/Symbol-Zuordnung gemaess specs/architecture/0004-design-system.md ("Bewertungsstufen auf
// einen Blick unterscheidbar" - Farbe UND Symbol, nicht nur Text). Kein Styling-System gewaehlt
// (siehe Design-System-Dokument), daher hier nur semantisches Markup + data-Attribut als
// zukuenftiger CSS-Hook; die tatsaechliche Farbcodierung folgt, sobald ein Styling-System steht.
const LABELS: Record<RatingStatus, string> = {
  favorite: 'Favorit',
  album_worthy: 'Album-würdig',
  rejected: 'Verworfen',
}

const SYMBOLS: Record<RatingStatus, string> = {
  favorite: '★',
  album_worthy: '✓',
  rejected: '✕',
}

interface RatingBadgeProps {
  status: RatingStatus | null
  className?: string
}

export function RatingBadge({ status, className }: RatingBadgeProps) {
  if (status === null) {
    return (
      <span className={className} data-rating-status="unrated" aria-label="Unbewertet">
        –
      </span>
    )
  }

  return (
    <span className={className} data-rating-status={status} aria-label={LABELS[status]}>
      {SYMBOLS[status]}
    </span>
  )
}
