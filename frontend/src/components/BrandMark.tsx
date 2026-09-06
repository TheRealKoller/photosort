import { cn } from '../lib/utils'
import { Icon } from './ui/icon'

interface BrandMarkProps {
  className?: string
}

/**
 * Bildmarke: schwach gerundete Akzentflaeche (Radius 8px) mit dem `camera`-Symbol des Boards in
 * `--accent-fg`.
 *
 * Die frueheren drei ueberlappenden Kreise waren die Formsprache des Vorgaengersystems ("soft
 * circular accents") und haben auf dem neuen, dunklen Grund zusaetzlich nicht mehr funktioniert:
 * der kleinste Kreis war ein `bg-bg`-Ausstanz, der auf einer Creme-Flaeche als heller Ausschnitt
 * las und auf `#0B0C10` als schwarzes Loch.
 *
 * Rein dekorativ und daher `aria-hidden` - die Wortmarke "PhotoSort" steht als Ueberschrift
 * direkt daneben und traegt die zugaengliche Benennung, eine zweite Nennung waere fuer
 * Screenreader nur Doppelung.
 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'flex size-16 items-center justify-center rounded-md bg-accent text-accent-fg',
        className
      )}
    >
      <Icon name="camera" size={24} />
    </span>
  )
}
