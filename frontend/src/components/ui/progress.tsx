import type { ProgressHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Duenner Wrapper um das native <progress>-Element (specs/architecture/0004-design-system.md:
 * "kein neues Balken-Widget/keine neue Abhaengigkeit", Spec 0003 "Determinierter Fortschritt").
 * Kein Radix-Primitive noetig - natives <progress> bringt Rolle/Semantik bereits mit; nur
 * Tailwind-Utilities auf den browserspezifischen Pseudo-Elementen fuer die Akzentfarbe statt des
 * Browser-Standardblaus.
 *
 * Board-Masse (specs/architecture/0005-board-dark-utility-register.md Abschnitt 6): Spur
 * `--border`, Fuellung `--accent`, Hoehe 8px, Radius 4px (statt der frueheren vollen Rundung).
 *
 * `value`/`max` weggelassen (wie bisher) ergibt bewusst einen indeterminierten Balken (siehe
 * ProjectDetailPage: `photos_total` kurz 0 direkt nach Trigger).
 */
export function Progress({
  className,
  ...props
}: ProgressHTMLAttributes<HTMLProgressElement>) {
  return (
    <progress
      className={cn(
        'h-2 w-full appearance-none overflow-hidden rounded-xs bg-border',
        '[&::-webkit-progress-bar]:bg-border [&::-webkit-progress-value]:bg-accent',
        '[&::-moz-progress-bar]:bg-accent',
        className
      )}
      {...props}
    />
  )
}
