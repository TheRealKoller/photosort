import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export type BadgeTone = 'favorite' | 'album-worthy' | 'rejected' | 'accent' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  /**
   * Vorschlags-Badge-Muster (specs/architecture/0004-design-system.md): volle Fuellung = von
   * einem Menschen entschieden, gedaempfte Flaeche + Umrandung = maschineller Vorschlag, noch
   * offen. Die Symbolfarbe unterscheidet sich bewusst zwischen beiden Faellen (Copilot-Review-Fund,
   * PR "Tailwind-Fundament" - siehe Kommentar bei `TONE_CLASSES`): vollflaechig nutzt die
   * tonspezifische `--rating-<ton>-fg`, gedaempft/umrandet nutzt `--text-h`.
   */
  suggested?: boolean
}

// Vollstaendig ausgeschriebene Klassennamen je Ton/Variante (kein Zusammenbauen per
// Template-String) - Tailwind erkennt Utility-Klassen nur als statische, vollstaendige Strings im
// Quellcode; dynamisch zusammengesetzte Klassennamen wie `bg-${color}` wuerden vom Production-
// Build-Scan uebersehen und faellen im gebauten CSS ganz weg.
//
// Symbolfarbe, vollflaechig (`solid`): jeder Bewertungston bringt seine EIGENE, gegen genau
// diese Fuellung gerechnete Vordergrundfarbe mit (`--rating-<ton>-fg`). Der frueher hier
// verwendete gemeinsame `--chip-fg` ist mit dem Organic-Design-Import entfallen: dessen drei
// Toene tragen keine gemeinsame Vordergrundfarbe mit WCAG-AA (schwarz haelt auf Ocker 7.88:1 und
// Salbei 4.99:1, faellt auf Ziegel auf 3.53:1; Creme haelt auf Ziegel 5.00:1, faellt auf Ocker
// auf 2.24:1). `tone="accent"` nutzt weiterhin `--accent-fg`, die gegen den Akzent kalibrierte
// Farbe (siehe `Button`s `default`-Variante fuer denselben Grund).
//
// Symbolfarbe, gedaempft (`suggested`): Copilot-Review-Fund (PR "Tailwind-Fundament") - der
// Hintergrund ist hier nur eine 10%-Deckkraft-Tinte AUF `--bg`, nicht die volle Bewertungsfarbe.
// Eine gegen die volle Fuellung kalibrierte Vordergrundfarbe waere hier also falsch. `--text-h`
// ist stattdessen genau fuer diesen Zweck (Text auf `--bg`, in beiden Modi separat kalibriert)
// vorgesehen und wird hier verwendet.
const TONE_CLASSES: Record<Exclude<BadgeTone, 'neutral'>, { solid: string; suggested: string }> = {
  favorite: {
    solid: 'bg-rating-favorite text-rating-favorite-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-favorite bg-rating-favorite/10 text-text-h',
  },
  'album-worthy': {
    solid: 'bg-rating-album-worthy text-rating-album-worthy-fg border border-transparent',
    suggested: 'border-[1.5px] border-rating-album-worthy bg-rating-album-worthy/10 text-text-h',
  },
  rejected: {
    solid: 'bg-rating-rejected text-rating-rejected-fg border border-transparent',
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
          'inline-flex h-6 min-w-6 items-center justify-center rounded-full border border-border px-2 text-xs text-text',
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
        'inline-flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-xs font-medium',
        TONE_CLASSES[tone][variant],
        className
      )}
      {...props}
    />
  )
}
