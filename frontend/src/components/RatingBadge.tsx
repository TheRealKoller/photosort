import type { RatingStatus } from '../api/types'
import { RATING_STATUS_LABELS } from '../utils/ratingLabels'

// Kein Styling-System gewaehlt (siehe specs/architecture/0004-design-system.md), daher hier nur
// semantisches Markup + data-Attribut als zukuenftiger CSS-Hook; die tatsaechliche Farbcodierung
// folgt, sobald ein Styling-System steht.
const SYMBOLS: Record<RatingStatus, string> = {
  favorite: '★',
  album_worthy: '✓',
  rejected: '✕',
}

// Zahnrad-Praefix vor dem Stufensymbol fuer einen automatischen Vorschlag (Design-System-Ergaenzung
// "Vorschlags-Badge", specs/features/0003-automatic-best-photo-selection.md): gedaempfte/
// erkennbar-verwandte statt volle Darstellung derselben Bewertungsstufe - Faustregel "volle
// Fuellung = von einem Menschen entschieden, gedaempft/umrandet + Praefix = maschineller
// Vorschlag, noch offen".
const SUGGESTION_PREFIX = '⚙'

interface RatingBadgeProps {
  status: RatingStatus | null
  /**
   * true fuer einen unbestaetigten automatischen Vorschlag aus PhotoOut.suggestion statt einer
   * echten Bewertung aus ratings[] - siehe Anzeigeregel im UI/UX-Abschnitt der Spec: eine eigene
   * Bewertung hat immer Vorrang, ein Vorschlag wird nur gezeigt, solange keine eigene Bewertung
   * existiert (diese Entscheidung trifft der Aufrufer, nicht diese Komponente).
   */
  suggested?: boolean
  className?: string
}

export function RatingBadge({ status, suggested = false, className }: RatingBadgeProps) {
  if (status === null) {
    return (
      <span className={className} data-rating-status="unrated" aria-label="Unbewertet">
        –
      </span>
    )
  }

  const label = suggested
    ? `Vorschlag: ${RATING_STATUS_LABELS[status]}`
    : RATING_STATUS_LABELS[status]
  const symbol = suggested ? `${SUGGESTION_PREFIX}${SYMBOLS[status]}` : SYMBOLS[status]

  return (
    <span
      className={className}
      data-rating-status={status}
      data-suggested={suggested ? 'true' : undefined}
      aria-label={label}
    >
      {symbol}
    </span>
  )
}
