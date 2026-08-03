import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export type BadgeTone = 'favorite' | 'album-worthy' | 'rejected' | 'accent' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  /**
   * Vorschlags-Badge-Muster (specs/architecture/0004-design-system.md): volle Fuellung = von
   * einem Menschen entschieden, gedaempfte Flaeche + Umrandung = maschineller Vorschlag, noch
   * offen. Die Symbolfarbe bleibt in beiden Faellen `--chip-fg` (siehe Kontrastpruefung in
   * index.css) - nur Flaeche/Rahmen unterscheiden sich.
   */
  suggested?: boolean
}

// Vollstaendig ausgeschriebene Klassennamen je Ton/Variante (kein Zusammenbauen per
// Template-String) - Tailwind erkennt Utility-Klassen nur als statische, vollstaendige Strings im
// Quellcode; dynamisch zusammengesetzte Klassennamen wie `bg-${color}` wuerden vom Production-
// Build-Scan uebersehen und faellen im gebauten CSS ganz weg.
const TONE_CLASSES: Record<Exclude<BadgeTone, 'neutral'>, { solid: string; suggested: string }> = {
  favorite: {
    solid: 'bg-rating-favorite border border-transparent',
    suggested: 'border-[1.5px] border-rating-favorite bg-rating-favorite/10',
  },
  'album-worthy': {
    solid: 'bg-rating-album-worthy border border-transparent',
    suggested: 'border-[1.5px] border-rating-album-worthy bg-rating-album-worthy/10',
  },
  rejected: {
    solid: 'bg-rating-rejected border border-transparent',
    suggested: 'border-[1.5px] border-rating-rejected bg-rating-rejected/10',
  },
  accent: {
    solid: 'bg-accent border border-transparent',
    suggested: 'border-[1.5px] border-accent bg-accent-bg',
  },
}

export function Badge({ tone = 'neutral', suggested = false, className, ...props }: BadgeProps) {
  if (tone === 'neutral') {
    return (
      <span
        className={cn(
          'inline-flex h-6 min-w-6 items-center justify-center rounded-md border border-border px-1.5 text-xs text-text',
          className
        )}
        {...props}
      />
    )
  }

  const toneClasses = TONE_CLASSES[tone][suggested ? 'suggested' : 'solid']

  return (
    <span
      className={cn(
        'inline-flex h-6 min-w-6 items-center justify-center rounded-md px-1.5 text-xs font-medium text-chip-fg',
        toneClasses,
        className
      )}
      {...props}
    />
  )
}
