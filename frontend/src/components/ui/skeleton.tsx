import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Skeleton-Ladezustand (specs/architecture/0004-design-system.md): Platzhalterbloecke mit dezentem
 * Puls - kein Shimmer-Lauflicht (unnoetige Bewegungsunruhe beim zuegigen Durchsehen vieler Fotos).
 * `prefers-reduced-motion` respektiert Tailwinds `motion-reduce:animate-none`.
 *
 * FLAECHE IST `--text-disabled`, nicht `--elevated`. Das vergibt dem Token bewusst eine zweite
 * Rolle (im Design-System-Dokument als solche gefuehrt) und ist eine Sichtbarkeits-, keine
 * Geschmacksentscheidung: `--elevated` misst gegen den Seitengrund 1.23:1 und gegen `--surface`
 * 1.14:1 - der Platzhalter waere praktisch unsichtbar, und eine ladende Seite waere fuer sehende
 * Nutzer nicht von "haengt" oder "keine Eintraege" zu unterscheiden. Betroffen sind genau die
 * Stellen mit der laengsten Wartezeit (Projektliste, Fotoraster, Kuratierung, Einzelbild).
 * Gerechnete Kandidaten gegen `--bg`: `--overlay` 1.39, `--border` 1.45, `--text-disabled` 1.96,
 * `--border-control` 4.48. `--text-disabled` ist der Kompromiss - sichtbar genug, ohne dass ein
 * Raster voller Platzhalter lauter wirkt als der spaetere Inhalt. Eine Kontrastschwelle gilt hier
 * nicht (der Block ist `aria-hidden`, die Ansage traegt `role="status"` am Aufrufer); das
 * Kriterium ist Sichtbarkeit.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse motion-reduce:animate-none rounded-md bg-text-disabled', className)}
      {...props}
    />
  )
}
