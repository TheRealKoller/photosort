import type { ProgressHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Duenner Wrapper um das native <progress>-Element (kein neues Balken-Widget, keine neue
 * Abhaengigkeit, determinierter Fortschritt). Kein Radix-Primitive noetig - natives <progress>
 * bringt Rolle/Semantik bereits mit; nur Tailwind-Utilities auf den browserspezifischen
 * Pseudo-Elementen fuer die Akzentfarbe statt des Browser-Standardblaus.
 *
 * Board-Masse: Fuellung `--accent`, Hoehe 8px, Radius 4px. Die SPUR liegt auf `--separator` statt
 * auf `--border`: als dekorative Flaeche unmittelbar auf dem Grund erreichte `--border` nur 1.45:1
 * und war damit praktisch unsichtbar - genau der Befund "Trennlinien und Statuspunkte verschwinden
 * auf dem Grund".
 *
 * UNBESTIMMTER ZUSTAND (`value` weggelassen, siehe ScanStepPage/AusschussStepPage/
 * ClassificationSection): Der Browser zeichnet dort von sich aus ein WANDERNDES Segment - eine
 * Positionsbewegung, die das Design-System ausdruecklich verbietet (zugelassen sind ausschliesslich
 * Farb- und Deckkraftuebergaenge). Stattdessen volle Flaeche in `--accent` mit dem bereits im
 * Produkt etablierten Puls (dieselbe Mechanik wie Skeleton, Spinner und laufender Statuspunkt) -
 * es kommt keine neue Bewegungsart hinzu, nur eine weitere Aufrufstelle einer zugelassenen.
 * `motion-reduce:animate-none` wie an den drei bestehenden Stellen; der Balken steht dann als
 * volle Akzentflaeche still, was tragbar ist, weil an allen drei Aufrufstellen eine begleitende
 * Statuszeile den Zustand "laeuft" ausschreibt.
 *
 * Die beiden Browser-Pseudo-Elemente werden im unbestimmten Zustand mitgesetzt, sonst schlaegt die
 * Voreinstellung durch. In jsdom ist davon nichts belegbar (`:indeterminate` und die
 * Pseudo-Elemente existieren dort nicht) - der Vertragstest belegt ueber den tatsaechlichen
 * Tailwind-Lauf, dass die Varianten ueberhaupt eine Regel erzeugen, die Darstellung selbst ist
 * Sichtpruefung.
 */
/**
 * `tone` waehlt die FUELLUNG, nie die Spur - die bleibt in beiden Toenen `--separator`.
 *
 * `accent` ist die Vorgabe und traegt FORTSCHRITT (die drei bestehenden Aufrufstellen bleiben
 * unveraendert). `neutral` traegt eine MESSGROESSE (`--text-h`, Spec 0427): acht Amber-Balken je
 * Foto stuenden in der Favoritenfarbe und laesen sich als Bewertung. Beide Paare
 * (Fuellung gegen Spur) stehen in der Kontrastmatrix von `designSystem.contract.test.ts`.
 *
 * Der unbestimmte Zustand bleibt dem Akzent vorbehalten: eine Messgroesse ist entweder da oder
 * nicht, sie "laeuft" nicht.
 */
const TONE_CLASSES = {
  accent: [
    '[&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent',
    'indeterminate:bg-accent indeterminate:animate-pulse motion-reduce:animate-none',
    'indeterminate:[&::-webkit-progress-bar]:bg-accent indeterminate:[&::-moz-progress-bar]:bg-transparent',
  ].join(' '),
  neutral: '[&::-webkit-progress-value]:bg-text-h [&::-moz-progress-bar]:bg-text-h',
} as const

export type ProgressTone = keyof typeof TONE_CLASSES

export function Progress({
  className,
  tone = 'accent',
  ...props
}: ProgressHTMLAttributes<HTMLProgressElement> & { tone?: ProgressTone }) {
  return (
    <progress
      className={cn(
        'h-2 w-full appearance-none overflow-hidden rounded-xs bg-separator',
        '[&::-webkit-progress-bar]:bg-separator',
        TONE_CLASSES[tone],
        className,
      )}
      {...props}
    />
  )
}
