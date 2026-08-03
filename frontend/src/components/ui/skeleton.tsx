import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Skeleton-Ladezustand (specs/architecture/0004-design-system.md): warm-neutrale Platzhalterblöcke
 * mit dezentem Puls (kein Shimmer-Lauflicht - unnoetige Bewegungsunruhe beim zuegigen Durchsehen
 * vieler Fotos). `prefers-reduced-motion` respektiert Tailwinds `motion-reduce:animate-none`.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse motion-reduce:animate-none rounded-md bg-border/70', className)}
      {...props}
    />
  )
}
