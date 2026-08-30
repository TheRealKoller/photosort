import { cn } from '../lib/utils'

interface BrandMarkProps {
  className?: string
}

/**
 * Bildmarke aus drei ueberlappenden weichen Kreisen (Terrakotta, Salbei, Grundton) - so im
 * importierten Mockup auf dem Anmeldebildschirm angelegt. Bewusst aus den Formen des
 * Design-Systems gebaut statt als eigenes Logo: "soft circular accents" sind dort die
 * Grundformensprache, damit braucht die Marke keine eigene Schriftzug-Gestaltung.
 *
 * Rein dekorativ und daher `aria-hidden` - die Wortmarke "PhotoSort" steht als Ueberschrift
 * direkt daneben und traegt die zugaengliche Benennung, eine zweite Nennung waere fuer
 * Screenreader nur Doppelung.
 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <span aria-hidden="true" className={cn('relative block size-[74px]', className)}>
      <span className="absolute left-0 top-[6px] size-14 rounded-full bg-accent" />
      <span className="absolute left-[30px] top-0 size-10 rounded-full bg-accent-2/90" />
      <span className="absolute left-[22px] top-[34px] size-[26px] rounded-full bg-bg" />
    </span>
  )
}
