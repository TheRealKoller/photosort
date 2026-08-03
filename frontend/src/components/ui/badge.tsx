import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export type BadgeTone = 'favorite' | 'album-worthy' | 'rejected' | 'accent' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  /**
   * Vorschlags-Badge-Muster (specs/architecture/0004-design-system.md): volle Fuellung = von
   * einem Menschen entschieden, gedaempfte Flaeche + Umrandung = maschineller Vorschlag, noch
   * offen. Die Symbolfarbe ist fuer Rating-Toene in beiden Faellen `--chip-fg` (Hintergrund
   * hinter dem Symbol bleibt auch im gedaempften Zustand nahe `--bg`, siehe Kontrastpruefung in
   * index.css); nur `tone="accent"` nutzt im vollflaechigen Zustand `--accent-fg` statt
   * `--chip-fg`, da dort die kraeftige Akzentfarbe selbst der Hintergrund ist.
   */
  suggested?: boolean
}

// Vollstaendig ausgeschriebene Klassennamen je Ton/Variante (kein Zusammenbauen per
// Template-String) - Tailwind erkennt Utility-Klassen nur als statische, vollstaendige Strings im
// Quellcode; dynamisch zusammengesetzte Klassennamen wie `bg-${color}` wuerden vom Production-
// Build-Scan uebersehen und faellen im gebauten CSS ganz weg.
//
// Symbolfarbe (Review-Fund auf Branch feature/0012-visual-redesign-foundation): `--chip-fg`
// (nahezu schwarz) ist NUR fuer die vier Bewertungsfarben und fuer den gedaempften/umrandeten
// Vorschlags-Zustand kalibriert, wo der Hintergrund hinter dem Symbol ohnehin fast `--bg`
// entspricht (nur 10% Deckkraft-Tint). Bei vollflaechig gefuelltem `accent`-Ton ist der Hintergrund
// dagegen die kraeftige Akzentfarbe selbst - dafuer existiert bereits die passend abgestimmte
// `--accent-fg` (siehe `Button`s `default`-Variante), NICHT `--chip-fg` (auf `--accent` hell nur
// 3.84:1, verfehlt WCAG-AA).
const TONE_CLASSES: Record<Exclude<BadgeTone, 'neutral'>, { solid: string; suggested: string }> = {
  favorite: {
    solid: 'bg-rating-favorite text-chip-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-favorite bg-rating-favorite/10 text-chip-fg',
  },
  'album-worthy': {
    solid: 'bg-rating-album-worthy text-chip-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-album-worthy bg-rating-album-worthy/10 text-chip-fg',
  },
  rejected: {
    solid: 'bg-rating-rejected text-chip-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-rejected bg-rating-rejected/10 text-chip-fg',
  },
  accent: {
    solid: 'bg-accent text-accent-fg border border-transparent',
    suggested: 'border-[1.5px] border-accent bg-accent-bg text-chip-fg',
  },
}

export function Badge({ tone = 'neutral', suggested = false, className, ...props }: BadgeProps) {
  const variant = suggested ? 'suggested' : 'solid'

  if (tone === 'neutral') {
    return (
      <span
        data-badge-tone={tone}
        className={cn(
          'inline-flex h-6 min-w-6 items-center justify-center rounded-md border border-border px-1.5 text-xs text-text',
          className
        )}
        {...props}
      />
    )
  }

  return (
    <span
      data-badge-tone={tone}
      data-badge-variant={variant}
      className={cn(
        'inline-flex h-6 min-w-6 items-center justify-center rounded-md px-1.5 text-xs font-medium',
        TONE_CLASSES[tone][variant],
        className
      )}
      {...props}
    />
  )
}
