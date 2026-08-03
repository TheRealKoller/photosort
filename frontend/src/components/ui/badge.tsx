import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export type BadgeTone = 'favorite' | 'album-worthy' | 'rejected' | 'accent' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  /**
   * Vorschlags-Badge-Muster (specs/architecture/0004-design-system.md): volle Fuellung = von
   * einem Menschen entschieden, gedaempfte Flaeche + Umrandung = maschineller Vorschlag, noch
   * offen. Die Symbolfarbe unterscheidet sich bewusst zwischen beiden Faellen (Copilot-Review-Fund,
   * PR "Tailwind-Fundament" - siehe Kommentar bei `TONE_CLASSES`): vollflaechig nutzt `--chip-fg`,
   * gedaempft/umrandet nutzt `--text-h`.
   */
  suggested?: boolean
}

// Vollstaendig ausgeschriebene Klassennamen je Ton/Variante (kein Zusammenbauen per
// Template-String) - Tailwind erkennt Utility-Klassen nur als statische, vollstaendige Strings im
// Quellcode; dynamisch zusammengesetzte Klassennamen wie `bg-${color}` wuerden vom Production-
// Build-Scan uebersehen und faellen im gebauten CSS ganz weg.
//
// Symbolfarbe, vollflaechig (`solid`): `--chip-fg` (nahezu schwarz, in beiden Farbschemata
// identisch) ist NUR fuer vollflaechig gefuellte Chips kalibriert, wo der Hintergrund die
// kraeftige, modusunabhaengige Bewertungsfarbe selbst ist. `tone="accent"` nutzt im vollflaechigen
// Zustand `--accent-fg` statt `--chip-fg`, da `--chip-fg` gegen `--accent` (hell) nur 3.84:1
// erreicht, verfehlt WCAG-AA (siehe `Button`s `default`-Variante fuer denselben Grund).
//
// Symbolfarbe, gedaempft (`suggested`): Copilot-Review-Fund (PR "Tailwind-Fundament") - der
// Hintergrund ist hier nur eine 10%-Deckkraft-Tinte AUF `--bg`, nicht die volle Bewertungsfarbe.
// `--bg` unterscheidet sich stark zwischen hell (nahezu weiss) und dunkel (nahezu schwarz);
// `--chip-fg` ist aber in beiden Modi gleich (#000000) - im Dunkelmodus waere das praktisch
// schwarzer Text auf praktisch schwarzem Hintergrund. `--text-h` ist stattdessen genau fuer
// diesen Zweck (Text auf `--bg`, in beiden Modi separat kalibriert) vorgesehen und wird hier
// verwendet statt `--chip-fg`.
const TONE_CLASSES: Record<Exclude<BadgeTone, 'neutral'>, { solid: string; suggested: string }> = {
  favorite: {
    solid: 'bg-rating-favorite text-chip-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-favorite bg-rating-favorite/10 text-text-h',
  },
  'album-worthy': {
    solid: 'bg-rating-album-worthy text-chip-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-album-worthy bg-rating-album-worthy/10 text-text-h',
  },
  rejected: {
    solid: 'bg-rating-rejected text-chip-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-rejected bg-rating-rejected/10 text-text-h',
  },
  accent: {
    solid: 'bg-accent text-accent-fg border border-transparent',
    suggested: 'border-[1.5px] border-accent bg-accent-bg text-text-h',
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
