import { clsx } from 'clsx'
import type { ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Standard-shadcn/ui-Hilfsfunktion: kombiniert bedingte Klassenlisten (clsx) und loest
 * widersprechende Tailwind-Utility-Klassen zugunsten der zuletzt angegebenen auf (tailwind-merge) -
 * z.B. `cn('px-2', condition && 'px-4')` ergibt zuverlaessig nur `px-4`, nicht beide Klassen.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
