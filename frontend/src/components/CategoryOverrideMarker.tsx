import { cn } from '../lib/utils'

interface CategoryOverrideMarkerProps {
  className?: string
}

/**
 * Dezenter Kachel-Marker bei aktivem Kategorie-Override (specs/features/0055-remote-kategorie-
 * klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt "Mehrfachkandidaten-Vergleich mit
 * Override-Aktion") - gleiche halbtransparente `--bg`-Kreis-Backdrop-Technik wie der bestehende
 * CriterionDetailsPopover-Trigger, Stift-Symbol `aria-hidden`, begleitender `aria-label` auf dem
 * umschliessenden Element (analog RatingBadge). Rein dekorativ/informativ, kein Klick-Handler -
 * sitzt deshalb in der bislang unbelegten Ecke der Kachel (oben links), nicht in derselben Ecke
 * wie RatingBadge/CriterionDetailsPopover-Trigger (oben rechts). `role="img"` auf dem
 * umschliessenden Element (Copilot-Review-Fund, PR #201): ein `aria-label` auf einem reinen,
 * rollenlosen `<span>` kann von Assistive Technology ignoriert werden, `role="img"` macht das
 * Element zu einem eigenstaendigen Accessibility-Tree-Knoten mit dem `aria-label` als
 * Textalternative - passendste Rolle fuer ein rein ikonisches, nicht interaktives Element.
 */
export function CategoryOverrideMarker({ className }: CategoryOverrideMarkerProps) {
  return (
    <span
      role="img"
      aria-label="Kategorie manuell übersteuert"
      className={cn(
        'flex size-6 items-center justify-center rounded-full bg-bg/85 text-xs text-text-h backdrop-blur-sm',
        className
      )}
    >
      <span aria-hidden="true">✎</span>
    </span>
  )
}
