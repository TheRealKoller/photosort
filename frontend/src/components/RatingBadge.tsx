import type { RatingStatus } from '../api/types'
import { Badge } from './ui/badge'
import type { BadgeTone } from './ui/badge'
import { Icon } from './ui/icon'
import type { IconName } from './ui/icon'
import { RATING_STATUS_LABELS } from '../utils/ratingLabels'

const TONE_BY_STATUS: Record<RatingStatus, BadgeTone> = {
  favorite: 'favorite',
  album_worthy: 'album-worthy',
  rejected: 'rejected',
}

/*
 * Die drei Bewertungssymbole des Boards (specs/architecture/0005-board-dark-utility-register.md
 * Abschnitt 6: Favorit `star`, Album `book`, Aussortiert `x-circle`). Sie ersetzen die frueheren
 * Sonderzeichen ★/✓/✕.
 *
 * `book` fuer "Album-wuerdig" folgt dem Board und der ADR (0055 Punkt 6c nennt den achromatischen
 * Nachweis ausdruecklich als `star`/`book`/`x-circle`); die Umsetzungsliste der Spec fuehrt an
 * dieser einen Stelle `check` auf, was die bisherigen Zeichen 1:1 uebersetzt haette. Aufgeloest
 * zugunsten des Boards: `check` ist im Produkt bereits das Symbol der Erfolgsmeldung
 * (ui/alert.tsx), eine Doppelbelegung braeche "Bewertungsstufen auf einen Blick unterscheidbar".
 */
const SYMBOLS: Record<RatingStatus, IconName> = {
  favorite: 'star',
  album_worthy: 'book',
  rejected: 'x-circle',
}

// Zahnrad-Praefix vor dem Stufensymbol fuer einen automatischen Vorschlag (Design-System-Ergaenzung
// "Vorschlags-Badge", specs/features/0003-automatic-best-photo-selection.md): volle Fuellung = von
// einem Menschen entschieden, getoente Flaeche mit farbigem Rand + Praefix = maschineller
// Vorschlag, noch offen.
const SUGGESTION_PREFIX: IconName = 'cog'

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

/**
 * MEHRFACHCODIERUNG DER DREI BEWERTUNGSZUSTAENDE (Akzeptanzkriterium "ohne Farbwahrnehmung
 * unterscheidbar"). Nachgerechnet in Graustufen-Luminanz liegen Favorit (0.48) und Album-wuerdig
 * (0.54) bei nur 1.10:1 zueinander - als reine Farbflaechen praktisch identisch hell. Das
 * Kriterium traegt deshalb AUSSCHLIESSLICH ueber die Mehrfachcodierung:
 *   1. zugaenglicher Name (Favorit / Album-wuerdig / Verworfen),
 *   2. eigenes Symbol (`data-icon`: star / book / x-circle),
 *   3. beim Aussortierten zusaetzlich `data-struck` als DOM-Merkmal der Durchstreichung.
 * Alle drei sind ueber die drei Zustaende paarweise verschieden.
 *
 * Daraus folgt eine harte Regel fuer das ganze Produkt: kein Bewertungszustand darf irgendwo
 * ALLEIN durch seine Farbflaeche dargestellt werden - insbesondere nicht als farbiger Punkt,
 * Rahmen oder Balkensegment ohne begleitendes Symbol oder Text.
 */
export function RatingBadge({ status, suggested = false, className }: RatingBadgeProps) {
  if (status === null) {
    // Das Board zeigt fuer "Neu" gar kein Badge; im Produkt bleibt das neutrale "–" erhalten,
    // weil das Raster sonst zwischen "nicht bewertet" und "Badge noch nicht geladen" nicht
    // unterscheidbar waere. Darf beim Umkleiden nicht als Aufraeumarbeit verschwinden.
    return (
      <Badge className={className} data-rating-status="unrated" aria-label="Unbewertet">
        –
      </Badge>
    )
  }

  const label = suggested
    ? `Vorschlag: ${RATING_STATUS_LABELS[status]}`
    : RATING_STATUS_LABELS[status]

  return (
    <Badge
      className={className}
      tone={TONE_BY_STATUS[status]}
      suggested={suggested}
      data-rating-status={status}
      data-suggested={suggested ? 'true' : undefined}
      data-struck={status === 'rejected' ? 'true' : undefined}
      aria-label={label}
    >
      {suggested && <Icon name={SUGGESTION_PREFIX} size={14} />}
      <Icon name={SYMBOLS[status]} size={14} />
      {/* Sichtbares Produktwort neben dem Symbol (Spec 0321, Board-Kennzeichen). Es ist die
          Haelfte der Graustufen-Zusage: Favorit und Album-wuerdig liegen achromatisch bei 1.08:1
          zueinander, ihre Unterscheidung traegt ausschliesslich ueber Wort und Symbolsilhouette.
          Der "Vorschlag:"-Praefix bleibt dem zugaenglichen Namen vorbehalten - sichtbar
          unterscheidet ihn der Zahnrad-Praefix und die Vorschlags-Konstruktion. */}
      {RATING_STATUS_LABELS[status]}
    </Badge>
  )
}
