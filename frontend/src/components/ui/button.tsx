import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

// Formsprache/Touch-Ziele (specs/architecture/0004-design-system.md): Buttons sind vollstaendige
// Pillen (`rounded-full`, Regel des Organic-Design-Systems fuer kleine Bedienelemente), mind.
// 44x44px Tap-Ziel (h-11 = 44px bei der Standardgroesse), fokus-sichtbarer Ring in --accent.
// Beschriftung in der Display-Schrift (`font-heading`, Caprasimo) - die Vorlage setzt fuer `.btn`
// ausdruecklich `font-family: var(--font-heading)`.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-heading text-sm ' +
    'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ' +
    'focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        // `text-accent-fg` ist die gegen die gefuellte Akzentflaeche gerechnete dunkle Tinte
        // (4.60:1 hell, 8.03:1 dunkel) - siehe die Begruendung bei --accent-fg in index.css.
        default: 'bg-accent text-accent-fg shadow-warm hover:opacity-90',
        secondary: 'bg-border/60 text-text-h hover:bg-border',
        outline: 'border border-border bg-transparent text-text-h hover:bg-border/40',
        ghost: 'bg-transparent text-text-h hover:bg-border/40',
        // Link ist Text in Fliesstextgroesse auf dem Seitengrund - daher `--accent-strong`
        // (5.72:1) statt `--accent` (3.03:1, nur fuer Chrome kalibriert).
        link: 'bg-transparent text-accent-strong underline-offset-4 hover:underline p-0 h-auto min-h-0 min-w-0',
      },
      size: {
        default: 'h-11 min-w-11 px-4 py-2',
        sm: 'h-11 min-w-11 px-3 text-xs',
        icon: 'h-11 w-11',
      },
    },
    // Review-Fund (Branch feature/0012-visual-redesign-foundation): cva reiht die `size`-Klassen
    // NACH den `variant`-Klassen ein, tailwind-merge loest Konflikte zugunsten der zuletzt
    // vorkommenden Klasse auf - ohne diesen compoundVariant wuerden `size`s h-11/min-w-11/px-4 py-2
    // die bewusst kompakten link-Klassen (h-auto/min-w-0/p-0) immer ueberschreiben, unabhaengig von
    // der gewaehlten Groesse. Das Fehlen von `size` als Bedingung heisst laut cva "passt auf jede
    // Groesse" - reicht deshalb als ein einziger Eintrag fuer alle drei Groessen.
    compoundVariants: [
      {
        variant: 'link',
        class: 'h-auto min-h-0 min-w-0 p-0',
      },
    ],
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /**
   * Busy-Button-Muster (specs/architecture/0004-design-system.md, Funktionaler Fix 1 aus
   * specs/features/0012-visual-redesign.md): erzwingt den deaktivierten Zustand zentral in der
   * Komponente, statt sich darauf zu verlassen, dass jeder Aufrufer `disabled` UND `busy` immer
   * synchron haelt. Label-Text-Wechsel (z.B. "Anmelden…") bleibt bewusst Aufgabe des Aufrufers
   * (unveraendertes, bereits etabliertes Muster in ProjectDetailPage/LoginPage) - diese
   * Komponente ergaenzt nur den zentralen Spinner + die erzwungene Deaktivierung.
   */
  busy?: boolean
  /** Rendert die Styling-/Verhaltens-Props auf das einzelne Kind-Element (Radix Slot) statt auf
   * ein eigenes <button> - z.B. um einen react-router <Link> wie einen Button aussehen zu lassen,
   * ohne ein <button> um ein <a> zu verschachteln (invalides HTML). */
  asChild?: boolean
}

export function Button({
  className,
  variant,
  size,
  busy = false,
  asChild = false,
  type = 'button',
  disabled,
  onClick,
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : 'button'
  const isDisabled = disabled || busy
  const isDisabledSlot = asChild && isDisabled

  // Radix Slot verlangt genau EIN valides Element als Kind (klont Props direkt auf das Kind statt
  // ein eigenes DOM-Element zu rendern) - der Spinner wird deshalb nur im nativen <button>-Fall
  // zusaetzlich eingefuegt. `asChild` wird in dieser App ausschliesslich fuer navigierende Links
  // (kein eigener Pending-Zustand) verwendet, `busy` fuer native Aktions-Buttons - beide Props
  // gleichzeitig sind daher kein vorgesehener Anwendungsfall.
  //
  // Copilot-Review-Fund (PR "Tailwind-Fundament"): `aria-disabled` allein blockiert bei `asChild`
  // keine echte Interaktion, weil das native `disabled`-Attribut nicht an ein `<a href>`
  // gebunden werden kann - ein `onClick`, der nur `event.preventDefault()` aufruft, reicht bei
  // react-router `Link` NICHT aus: Radix Slot ruft laut eigener `mergeProps`-Implementierung
  // IMMER zuerst den Handler des Kindes auf (hier Links eigener Klick-Handler, der synchron
  // `navigate()` ausloest) und erst danach den hier uebergebenen - `preventDefault()` kommt also
  // zu spaet. Stattdessen wird die Interaktion an der Wurzel unterbunden: `pointer-events-none`
  // verhindert, dass ein Mausklick das Element ueberhaupt trifft (kein Klick-Event entsteht),
  // `tabIndex={-1}` entfernt es aus der Tab-Reihenfolge, sodass Enter/Leertaste es nicht ausloesen
  // koennen - dieselbe Kombination, die z.B. auch andere Bibliotheken fuer "deaktivierte Links"
  // verwenden. Aktuell kein realer Aufrufer dieser Kombination (kein `asChild disabled` im Code),
  // daher praeventive Absicherung der Basiskomponente, nicht Fix eines beobachteten Bugs.
  return (
    <Comp
      type={asChild ? undefined : type}
      className={cn(
        buttonVariants({ variant, size, className }),
        isDisabledSlot && 'pointer-events-none opacity-50'
      )}
      disabled={asChild ? undefined : isDisabled}
      aria-disabled={isDisabledSlot ? true : undefined}
      tabIndex={isDisabledSlot ? -1 : undefined}
      onClick={isDisabled ? undefined : onClick}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {busy && (
            <span
              data-testid="button-spinner"
              aria-hidden="true"
              className="size-3.5 animate-spin motion-reduce:animate-none rounded-full border-2 border-current border-t-transparent"
            />
          )}
          {children}
        </>
      )}
    </Comp>
  )
}
