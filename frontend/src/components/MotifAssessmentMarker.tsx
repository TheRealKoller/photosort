import { cn } from '../lib/utils'

interface MotifAssessmentMarkerProps {
  className?: string
}

/**
 * Dezenter Kachel-Marker für ein Foto, das noch keinen Klassifizierungslauf gesehen hat - gleiche
 * halbtransparente `--bg`-Kreis-Backdrop-Technik wie der `CriterionDetailsPopover`-Trigger,
 * Zeichen `aria-hidden`, begleitender `aria-label` auf dem umschließenden Element.
 *
 * `role="img"` auf dem umschließenden Element: ein `aria-label` auf einem rollenlosen `<span>`
 * kann von Assistive Technology ignoriert werden.
 *
 * DER EINZIGE Motiv-Marker der Kachel. Lokale Grundlage und Dokument-Ausschluss stehen im
 * Info-Popover und in der Einzelbildansicht - weitere Ecken-Glyphen würden die Kachel zu einer
 * Legende machen, und die Motivstärken selbst haben bei 158px Kachelbreite ohnehin keinen Platz.
 *
 * Rein informativ, kein Klick-Handler und ausdrücklich KEINE aufgespannte Trefferfläche: sie läge
 * über der Bildfläche und schluckte den Klick, der zur Einzelbildansicht führt.
 */
export function MotifAssessmentMarker({ className }: MotifAssessmentMarkerProps) {
  return (
    <span
      role="img"
      aria-label="Motive noch nicht bestimmt"
      className={cn(
        'flex size-6 items-center justify-center rounded-full bg-bg/85 text-xs text-text-h backdrop-blur-sm',
        className,
      )}
    >
      <span aria-hidden="true">○</span>
    </span>
  )
}
