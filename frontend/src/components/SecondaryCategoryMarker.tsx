import { cn } from '../lib/utils'

interface SecondaryCategoryMarkerProps {
  className?: string
}

/**
 * Dezenter Kachel-Marker fuer eine Kachel, die unter einer ihrer NEBENkategorien steht
 * (specs/features/0300-nebenkategorien.md, UI/UX-Abschnitt) - gleicher Aufbau und dieselbe
 * halbtransparente `--bg`-Kreis-Backdrop-Technik wie der `CategoryOverrideMarker` daneben.
 *
 * Das Zeichen ist bewusst ein VERZWEIGUNGSPFEIL `↳` und kein `↓`: es bezeichnet eine
 * Nebenzugehoerigkeit, keine Abwertung. Es ist `aria-hidden`; die Aussage traegt der `aria-label`
 * auf dem umschliessenden Element (`role="img"`, damit der Name im Accessibility-Tree ankommt -
 * ein `aria-label` auf einem rollenlosen `<span>` kann ignoriert werden). FARBE TRAEGT DIE AUSSAGE
 * NICHT: die Rolle steht zusaetzlich als Text in den Bewertungsdetails.
 *
 * Rein dekorativ/informativ, kein Klick-Handler. Sitzt im `topLeft`-Slot der `PhotoCard`, bei
 * einem zugleich uebersteuerten Foto rechts neben dem Uebersteuerungs-Marker.
 */
export function SecondaryCategoryMarker({ className }: SecondaryCategoryMarkerProps) {
  return (
    <span
      role="img"
      aria-label="Nebenkategorie"
      className={cn(
        'flex size-6 items-center justify-center rounded-full bg-bg/85 text-xs text-text-h backdrop-blur-sm',
        className,
      )}
    >
      <span aria-hidden="true">↳</span>
    </span>
  )
}
