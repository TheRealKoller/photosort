import type { ProgressHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Duenner Wrapper um das native <progress>-Element (specs/architecture/0004-design-system.md:
 * "kein neues Balken-Widget/keine neue Abhaengigkeit", Spec 0003 "Determinierter Fortschritt").
 * Kein Radix-Primitive noetig - natives <progress> bringt Rolle/Semantik bereits mit; nur
 * Tailwind-Utilities auf den browserspezifischen Pseudo-Elementen fuer die Akzentfarbe statt des
 * Browser-Standardblaus.
 *
 * Board-Masse (specs/architecture/0005-board-dark-utility-register.md Abschnitt 6): Fuellung
 * `--accent`, Hoehe 8px, Radius 4px. Die SPUR liegt seit Spec 0321 auf `--separator` statt auf
 * `--border`: als dekorative Flaeche unmittelbar auf dem Grund erreichte `--border` nur 1.45:1 und
 * war damit praktisch unsichtbar - genau der Befund "Trennlinien und Statuspunkte verschwinden auf
 * dem Grund".
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
export function Progress({
  className,
  ...props
}: ProgressHTMLAttributes<HTMLProgressElement>) {
  return (
    <progress
      className={cn(
        'h-2 w-full appearance-none overflow-hidden rounded-xs bg-separator',
        '[&::-webkit-progress-bar]:bg-separator [&::-webkit-progress-value]:bg-accent',
        '[&::-moz-progress-bar]:bg-accent',
        'indeterminate:bg-accent indeterminate:animate-pulse motion-reduce:animate-none',
        'indeterminate:[&::-webkit-progress-bar]:bg-accent indeterminate:[&::-moz-progress-bar]:bg-transparent',
        className
      )}
      {...props}
    />
  )
}
