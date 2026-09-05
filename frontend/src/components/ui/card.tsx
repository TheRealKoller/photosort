import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Karte/Panel nach dem Board (specs/architecture/0005-board-dark-utility-register.md Abschnitt 6):
 * Radius 12px, Flaeche `--elevated`, 1px `--border`, FLACH.
 *
 * Der Schatten entfaellt ersatzlos: das Board arbeitet durchgehend flach, Tiefe entsteht ueber die
 * vier Flaechenstufen (`--bg` < `--surface` < `--elevated` < `--overlay`) statt ueber Weichzeichnung.
 * Das ist zugleich ein Dichtegewinn - flache Flaechen mit schwacher Rundung lassen sich enger
 * stapeln, ohne unruhig zu wirken.
 */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-lg border border-border bg-elevated', className)}
      {...props}
    />
  )
}
