import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

// Formsprache (specs/architecture/0004-design-system.md): 12px Radius fuer Karten/Panels, dezenter
// Schatten im Hellmodus ("wie ein aufgelegtes Foto"), im Dunkelmodus stattdessen ein Rahmen statt
// Schatten (heller Schatten auf dunklem Grund waere unsichtbar) - beides ueber --shadow-warm/
// --border geloest, die pro Farbschema bereits in index.css unterschiedlich definiert sind.
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-xl border border-border bg-bg shadow-warm', className)}
      {...props}
    />
  )
}
