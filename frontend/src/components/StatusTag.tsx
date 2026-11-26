import { cn } from '../lib/utils'
import type { ScanStatusLabel } from '../utils/scanStatus'

/*
 * Die Statuszustaende in einer Form, nach der TOAST-KONSTRUKTION des Boards: Flaeche `--elevated`,
 * farbiger 1px-Rand, farbige Beschriftung.
 *
 * Jeder Tonwert haelt AA auf dem Seitengrund; nachgerechnet in
 * src/designSystem.*.contract.test.ts.
 *
 * Vollstaendig ausgeschriebene Klassennamen je Zustand - Tailwind erkennt Utility-Klassen nur als
 * statische, vollstaendige Strings im Quellcode.
 */
const TONE_CLASSES: Record<ScanStatusLabel, string> = {
  never: 'bg-status-idle-tint border-status-idle-strong text-status-idle-strong',
  running: 'bg-status-running-tint border-status-running-strong text-status-running-strong',
  success: 'bg-status-success-tint border-status-success-strong text-status-success-strong',
  failed: 'bg-status-failed-tint border-status-failed-strong text-status-failed-strong',
  // „wartet" und „abgebrochen" sind weder Erfolg noch Fehler - derselbe neutrale Ton wie „noch
  // nie geschehen", den das Wort daneben praezisiert.
  queued: 'bg-status-idle-tint border-status-idle-strong text-status-idle-strong',
  cancelled: 'bg-status-idle-tint border-status-idle-strong text-status-idle-strong',
}

interface StatusTagProps {
  /** Bestimmt Tonwert und Laufindikator, nicht die Beschriftung. */
  status: ScanStatusLabel
  /** PFLICHT: Jede Aufrufstelle traegt ihren Wortlaut selbst. Eine hier hinterlegte
   * Vorgabetabelle waere eine zweite Textquelle, die kein Aufrufer mehr ausloest. */
  label: string
  className?: string
}

export function StatusTag({ status, label, className }: StatusTagProps) {
  return (
    <span
      data-status={status}
      // Radius 6px; die einzige Pillenform im Produkt ist der Kategorie-Chip.
      className={cn(
        'inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs font-semibold',
        TONE_CLASSES[status],
        className,
      )}
    >
      {status === 'running' && (
        <span
          data-testid="status-tag-spinner"
          aria-hidden="true"
          className={cn(
            'inline-block size-2.5 shrink-0 rounded-full border-2 border-current border-t-transparent',
            'animate-spin motion-reduce:animate-none',
          )}
        />
      )}
      {label}
    </span>
  )
}
