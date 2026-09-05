import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export type BadgeTone = 'favorite' | 'album-worthy' | 'rejected' | 'accent' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  /**
   * Vorschlags-Badge-Muster (specs/architecture/0004-design-system.md): volle Fuellung = von
   * einem Menschen entschieden, getoente Flaeche mit farbigem Rand und farbiger Beschriftung =
   * maschineller Vorschlag, noch offen.
   */
  suggested?: boolean
}

/*
 * Vollstaendig ausgeschriebene Klassennamen je Ton/Variante (kein Zusammenbauen per
 * Template-String) - Tailwind erkennt Utility-Klassen nur als statische, vollstaendige Strings im
 * Quellcode; dynamisch zusammengesetzte Klassennamen wie `bg-${color}` wuerden vom Production-
 * Build-Scan uebersehen und fielen im gebauten CSS ganz weg. Statisch erzwungen in
 * src/designSystem.contract.test.ts.
 *
 * SOLID: Board-Bewertungs-Badge - voll gefuellte Flaeche mit DUNKLER TINTE. Jeder Bewertungston
 * bringt seine eigene Vordergrundfarbe mit (`--rating-<ton>-fg`); sie tragen seit
 * decisions/0055-dark-utility-register-fundament.md Punkt 4e zwar alle denselben Wert, bleiben
 * aber drei getrennte Tokens: dass eine gemeinsame Tinte auf allen drei Toenen haelt, ist eine
 * Eigenschaft dieser konkreten Palette und keine Regel - beim Vorgaengersystem war sie
 * nachweislich nicht gegeben, und ein Ton-Wechsel wuerde die Kopplung sonst still brechen.
 *
 * SUGGESTED: umgestellt auf die TOAST-KONSTRUKTION des Boards (Flaeche `--elevated`, farbiger
 * 1px-Rand, farbige Beschriftung). Die frueher hier verwendete Konstruktion `bg-rating-<ton>` mit 10 % Deckkraft plus
 * `text-text-h` war eine PhotoSort-eigene Erfindung, die das Board nicht kennt: ueber einer
 * Deckkraft-Tinte ist Kontrast statisch nicht rechenbar, sie waere damit dauerhaft ungeprueft
 * geblieben. Auf `--elevated` faellt jetzt jedes Paar in die Kontrastmatrix.
 *
 * `rejected` traegt als Beschriftung `--danger-text` statt `--rating-rejected`: der Board-Ton
 * erreicht auf der erhoehten Flaeche nur 4.46:1 und haelt als Fliesstext kein AA (ADR 0055
 * Punkt 4d).
 */
const TONE_CLASSES: Record<Exclude<BadgeTone, 'neutral'>, { solid: string; suggested: string }> = {
  favorite: {
    solid: 'bg-rating-favorite text-rating-favorite-fg border border-transparent',
    suggested: 'border border-rating-favorite bg-elevated text-rating-favorite',
  },
  'album-worthy': {
    solid: 'bg-rating-album-worthy text-rating-album-worthy-fg border border-transparent',
    suggested: 'border border-rating-album-worthy bg-elevated text-rating-album-worthy',
  },
  rejected: {
    solid: 'bg-rating-rejected text-rating-rejected-fg border border-transparent',
    suggested: 'border border-rating-rejected bg-elevated text-danger-text',
  },
  accent: {
    solid: 'bg-accent text-accent-fg border border-transparent',
    suggested: 'border border-accent bg-elevated text-accent',
  },
}

export function Badge({ tone = 'neutral', suggested = false, className, ...props }: BadgeProps) {
  const variant = suggested ? 'suggested' : 'solid'

  if (tone === 'neutral') {
    return (
      <span
        data-badge-tone={tone}
        className={cn(
          'inline-flex h-6 min-w-6 items-center justify-center rounded-sm border border-border px-2 text-xs text-text',
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
      // Radius 6px statt der frueheren vollen Pille (Board-Formsprache: die einzige verbleibende
      // Pillenform ist der Kategorie-Chip mit 16px). Der Formunterschied 6px <-> 16px ist eine
      // der drei Gegenmassnahmen zur Farbnaehe zwischen Bewertungs- und Kategoriefarben.
      className={cn(
        'inline-flex h-6 min-w-6 items-center justify-center gap-1 rounded-sm px-2 text-xs font-semibold',
        TONE_CLASSES[tone][variant],
        className
      )}
      {...props}
    />
  )
}
