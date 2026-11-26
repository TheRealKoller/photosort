import { PROCESS_STATUS_DOT_CLASSES } from '../utils/processStatus'
import type { ProcessStatus } from '../utils/processStatus'

/**
 * Statusfarben sind als FLAECHENfarbe kalibriert, nicht als Text-/Symbolfarbe (WCAG-AA gegen
 * `--bg` verfehlt). Nur ein dekorativer, `aria-hidden` Punkt traegt die Farbe; der Text daneben
 * bleibt neutral (`text-text`/`text-text-h`).
 */
export function StatusDot({ status }: { status: ProcessStatus | null | undefined }) {
  return (
    <span
      aria-hidden="true"
      // Rueckfallfarbe "kein Status" auf --separator statt --border: der Punkt steht unmittelbar
      // auf --bg/--surface, wo --border faktisch unsichtbar ist.
      className={`size-2.5 shrink-0 rounded-full ${status ? PROCESS_STATUS_DOT_CLASSES[status] : 'bg-separator'}`}
    />
  )
}
