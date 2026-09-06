import { cn } from '../lib/utils'
import type { ScanStatusLabel } from '../utils/scanStatus'

const LABELS: Record<ScanStatusLabel, string> = {
  never: 'Noch nicht gescannt',
  running: 'Scan läuft…',
  success: 'Erfolgreich',
  failed: 'Fehlgeschlagen',
}

/*
 * Vier Zustaende in einer Form, umgestellt auf die TOAST-KONSTRUKTION des Boards
 * (decisions/0055-dark-utility-register-fundament.md Punkt 5): Flaeche `--elevated`, farbiger
 * 1px-Rand, farbige Beschriftung - statt eigener Tint-/Strong-Paare, die das Board nicht kennt.
 * Die acht `--status-*-tint`/`-strong`-Tokens sind in index.css darauf UMDEFINIERT worden statt
 * gestrichen; die Aufrufstellen hier bleiben dadurch unveraendert.
 *
 * Alle vier Beschriftungen halten damit AA auf `#1E2230` (8.64 / 9.48 / 5.08 / 6.44), nachgerechnet
 * in src/designSystem.contract.test.ts.
 *
 * Vollstaendig ausgeschriebene Klassennamen je Zustand - Tailwind erkennt Utility-Klassen nur als
 * statische, vollstaendige Strings im Quellcode.
 */
const TONE_CLASSES: Record<ScanStatusLabel, string> = {
  never: 'bg-status-idle-tint border-status-idle-strong text-status-idle-strong',
  running: 'bg-status-running-tint border-status-running-strong text-status-running-strong',
  success: 'bg-status-success-tint border-status-success-strong text-status-success-strong',
  failed: 'bg-status-failed-tint border-status-failed-strong text-status-failed-strong',
}

interface StatusTagProps {
  status: ScanStatusLabel
  className?: string
}

export function StatusTag({ status, className }: StatusTagProps) {
  return (
    <span
      data-status={status}
      // Radius 6px statt der frueheren vollen Pille - die einzige verbleibende Pillenform ist der
      // Kategorie-Chip.
      className={cn(
        'inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs font-semibold',
        TONE_CLASSES[status],
        className
      )}
    >
      {status === 'running' && (
        <span
          data-testid="status-tag-spinner"
          aria-hidden="true"
          className={cn(
            'inline-block size-2.5 shrink-0 rounded-full border-2 border-current border-t-transparent',
            'animate-spin motion-reduce:animate-none'
          )}
        />
      )}
      {LABELS[status]}
    </span>
  )
}
