import type { RatingStatus } from '../api/types'
import { cn } from '../lib/utils'
import { Badge } from './ui/badge'
import type { BadgeTone } from './ui/badge'
import { Icon } from './ui/icon'
import type { IconName } from './ui/icon'
import { RATING_CONTROL_LABELS, RATING_STATUS_LABELS } from '../utils/ratingLabels'

const TONE_BY_STATUS: Record<RatingStatus, BadgeTone> = {
  album_worthy: 'album-worthy',
  rejected: 'rejected',
}

/*
 * Die Bewertungssymbole des Boards (Favorit `star`, Album `book`, Aussortiert `x-circle`).
 *
 * Fuer "Album-wuerdig" gilt `book` und NICHT `check`: `check` ist im Produkt bereits das Symbol
 * der Erfolgsmeldung (ui/alert.tsx), eine Doppelbelegung braeche "Bewertungsstufen auf einen
 * Blick unterscheidbar".
 */
const SYMBOLS: Record<RatingStatus, IconName> = {
  album_worthy: 'book',
  rejected: 'x-circle',
}

const FAVORITE_SYMBOL: IconName = 'star'

// Zahnrad-Praefix vor dem Stufensymbol fuer einen automatischen Vorschlag (Design-System-Ergaenzung
// "Vorschlags-Badge"): volle Fuellung = von einem Menschen entschieden, getoente Flaeche mit
// farbigem Rand + Praefix = maschineller Vorschlag, noch offen.
const SUGGESTION_PREFIX: IconName = 'cog'

interface RatingBadgeProps {
  /** Die Albumentscheidung; `null` heisst "keine getroffen". */
  status: RatingStatus | null
  /**
   * Das Favoriten-Kennzeichen - seit ADR 0098 eine EIGENE Angabe neben der Albumentscheidung
   * und deshalb ein eigenes, gleichzeitig sichtbares Kennzeichen. Ein einzelnes Badge koennte
   * nur eines von beidem zeigen.
   */
  favorite?: boolean
  /**
   * true fuer einen unbestaetigten automatischen Vorschlag aus PhotoOut.suggestion statt einer
   * echten Bewertung aus ratings[]. Eine eigene Bewertung hat immer Vorrang, ein Vorschlag wird
   * nur gezeigt, solange keine eigene Bewertung existiert (diese Entscheidung trifft der
   * Aufrufer, nicht diese Komponente). Gilt ausschliesslich fuer die Albumentscheidung: einen
   * vorgeschlagenen Favoriten gibt es nicht.
   */
  suggested?: boolean
  className?: string
}

/**
 * MEHRFACHCODIERUNG DER DREI BEWERTUNGSZUSTAENDE - sie muessen ohne Farbwahrnehmung
 * unterscheidbar bleiben. In Graustufen-Luminanz liegen Favorit (0.48) und Album-wuerdig (0.54)
 * bei nur 1.10:1 zueinander, als reine Farbflaechen also praktisch identisch hell. Die
 * Unterscheidbarkeit traegt AUSSCHLIESSLICH ueber die Mehrfachcodierung:
 *   1. zugaenglicher Name (Favorit / Album-wuerdig / Verworfen),
 *   2. eigenes Symbol (`data-icon`: star / book / x-circle),
 *   3. beim Aussortierten zusaetzlich `data-struck` als DOM-Merkmal der Durchstreichung.
 * Alle drei sind ueber die drei Zustaende paarweise verschieden.
 *
 * Daraus folgt eine harte Regel fuer das ganze Produkt: kein Bewertungszustand darf irgendwo
 * ALLEIN durch seine Farbflaeche dargestellt werden - insbesondere nicht als farbiger Punkt,
 * Rahmen oder Balkensegment ohne begleitendes Symbol oder Text.
 */
export function RatingBadge({
  status,
  favorite = false,
  suggested = false,
  className,
}: RatingBadgeProps) {
  const label = status === null ? null : RATING_STATUS_LABELS[status]
  const accessibleLabel = suggested && label !== null ? `Vorschlag: ${label}` : label

  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      {favorite && (
        <Badge
          tone="favorite"
          data-rating-favorite="true"
          aria-label={RATING_CONTROL_LABELS.favorite}
        >
          <Icon name={FAVORITE_SYMBOL} size={14} />
          {RATING_CONTROL_LABELS.favorite}
        </Badge>
      )}

      {status === null ? (
        // Das Board zeigt fuer "Neu" gar kein Badge; im Produkt bleibt das neutrale "–"
        // erhalten, weil das Raster sonst zwischen "nicht bewertet" und "Badge noch nicht
        // geladen" nicht unterscheidbar waere. Darf beim Umkleiden nicht als Aufraeumarbeit
        // verschwinden.
        //
        // AUSNAHME: Steht das Favoriten-Kennzeichen daneben, ist das Badge nachweislich
        // geladen, und "Favorit –" laese sich wie ein widerspruechlicher Zustand.
        !favorite && (
          <Badge data-rating-status="unrated" aria-label="Unbewertet">
            –
          </Badge>
        )
      ) : (
        <Badge
          tone={TONE_BY_STATUS[status]}
          suggested={suggested}
          data-rating-status={status}
          data-suggested={suggested ? 'true' : undefined}
          data-struck={status === 'rejected' ? 'true' : undefined}
          aria-label={accessibleLabel ?? undefined}
        >
          {suggested && <Icon name={SUGGESTION_PREFIX} size={14} />}
          <Icon name={SYMBOLS[status]} size={14} />
          {/* Sichtbares Produktwort neben dem Symbol (Board-Kennzeichen) - Traeger der
                  Graustufen-Zusage oben, zusammen mit der Symbolsilhouette. Der
                  "Vorschlag:"-Praefix bleibt dem zugaenglichen Namen vorbehalten; sichtbar
                  unterscheidet ihn der Zahnrad-Praefix und die Vorschlags-Konstruktion. */}
          {label}
        </Badge>
      )}
    </span>
  )
}
