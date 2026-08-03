import type { InputHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

// Formsprache/Touch-Ziele (specs/architecture/0004-design-system.md): rounded-md (8px), 44px
// Mindesthoehe, aria-invalid-Markierung in der Fehlerfarbe statt eines zusaetzlichen Icons (siehe
// Design-System "Wiederkehrende Muster" -> Formularfehler: betroffenes Feld optisch markieren, wo
// eindeutig zuordenbar).
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-11 w-full rounded-md border border-border bg-bg px-3 text-sm text-text-h',
        'placeholder:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
        'aria-invalid:border-status-failed disabled:opacity-50 disabled:pointer-events-none',
        className
      )}
      {...props}
    />
  )
}
