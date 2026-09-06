import { PROCESS_STATUS_DOT_CLASSES } from '../utils/processStatus'
import type { ProcessStatus } from '../utils/processStatus'

/**
 * UX-/Architect-Review-Fund (Branch feature/0012-visual-redesign-views): faerbte urspruenglich den
 * sichtbaren Statustext direkt ein (`text-status-*`) - `--status-success`/`--status-failed` sind
 * aber nur als Flaechenfarbe kalibriert, nicht als Text-/Symbolfarbe (WCAG-AA gegen `--bg`
 * verfehlt, siehe architecture/0004-design-system.md, Abschnitt Farbpalette). Nur ein dekorativer,
 * `aria-hidden` Punkt traegt die Farbe, der Text daneben bleibt neutral (`text-text`/`text-text-h`).
 *
 * Verschoben nach components/StatusDot.tsx (specs/features/0042-automatisierter-flow-stepper-
 * detailseiten.md): bisher dateilokal in ProjectDetailPage.tsx, dort von den vier Sections
 * Scan/Ausschuss-Erkennung/Ausschuss-Gate/Kriterien-Bewertung gemeinsam genutzt. Mit der
 * Aufteilung in fuenf eigenstaendige Detailseiten-Dateien entstehen daraus vier getrennte
 * Konsumenten-Dateien (ScanStepPage/AusschussStepPage/GateStepPage/KriterienStepPage) - die
 * bisherige Dateilokal-Voraussetzung entfaellt, analog zu hooks/useTriggerConfirmation.ts.
 */
export function StatusDot({ status }: { status: ProcessStatus | null | undefined }) {
  return (
    <span
      aria-hidden="true"
      // Rueckfallfarbe "kein Status" auf --separator statt --border (Spec 0321): der Punkt steht
      // unmittelbar auf --bg/--surface und erreichte dort mit --border nur 1.45:1 - er war
      // faktisch nicht vorhanden. Jetzt 2.38:1.
      className={`size-2.5 shrink-0 rounded-full ${status ? PROCESS_STATUS_DOT_CLASSES[status] : 'bg-separator'}`}
    />
  )
}
