import { cn } from '../lib/utils'
import type { ScanStatusLabel } from '../utils/scanStatus'

const LABELS: Record<ScanStatusLabel, string> = {
  never: 'Noch nicht gescannt',
  running: 'Scan läuft…',
  success: 'Erfolgreich',
  failed: 'Fehlgeschlagen',
}

/*
 * Vier Zustaende in einer Form (Vorlage, Artboard 2): getoente Pille mit farbiger Beschriftung.
 * Vollstaendig ausgeschriebene Klassennamen je Zustand - Tailwind erkennt Utility-Klassen nur als
 * statische, vollstaendige Strings im Quellcode; dynamisch zusammengesetzte Namen wie
 * `bg-status-${x}-tint` wuerden vom Production-Build-Scan uebersehen und fielen im gebauten CSS weg.
 *
 * Die Tint/Strong-Paare sind in index.css fuer beide Farbschemata gerechnet (>= 6.4:1), die
 * Beschriftung darf hier also farbig sein - anders als beim frueheren Muster "farbiger Punkt neben
 * neutralem Text", das noetig war, weil die reinen Flaechenfarben als Textfarbe AA verfehlen.
 */
const TONE_CLASSES: Record<ScanStatusLabel, string> = {
  never: 'bg-status-idle-tint text-status-idle-strong',
  running: 'bg-status-running-tint text-status-running-strong',
  success: 'bg-status-success-tint text-status-success-strong',
  failed: 'bg-status-failed-tint text-status-failed-strong',
}

interface StatusTagProps {
  status: ScanStatusLabel
  className?: string
}

export function StatusTag({ status, className }: StatusTagProps) {
  return (
    <span
      data-status={status}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs',
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
