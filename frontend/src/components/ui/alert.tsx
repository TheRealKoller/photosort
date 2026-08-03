import type { ReactNode } from 'react'

import { Button } from './button'
import { cn } from '../../lib/utils'

interface AlertProps {
  children: ReactNode
  /** Loest bei Klick auf "Erneut versuchen" aus - fehlt diese Prop, wird kein Retry-Button
   * gerendert (z.B. fuer reine Formularfehler ohne sinnvolle Wiederholaktion). */
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

// Einheitliche Fehlerbanner-Komponente (specs/architecture/0004-design-system.md, "Fehlerzustand
// mit Retry") - ersetzt die bisher pro View einzeln nachgebauten <div role="alert"> +
// <button onClick={refetch}>-Paare (u.a. jetzt auch in PhotoDetailPage/PhotoComparePage
// vereinheitlicht, siehe specs/features/0012-visual-redesign.md, Funktionaler Fix 2).
export function Alert({ children, onRetry, retryLabel = 'Erneut versuchen', className }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-wrap items-center gap-3 rounded-xl border border-status-failed/40 bg-status-failed/10',
        'px-4 py-3 text-sm text-text-h',
        className
      )}
    >
      <span aria-hidden="true" className="text-status-failed">
        ⚠
      </span>
      <p className="flex-1">{children}</p>
      {onRetry && (
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  )
}
