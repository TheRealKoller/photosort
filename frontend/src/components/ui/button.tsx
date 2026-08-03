import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

// Formsprache/Touch-Ziele (specs/architecture/0004-design-system.md): rounded-md (8px), mind.
// 44x44px Tap-Ziel (h-11 = 44px bei der Standardgroesse), fokus-sichtbarer Ring in --accent.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ' +
    'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ' +
    'focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-accent text-accent-fg shadow-warm hover:opacity-90',
        secondary: 'bg-border/60 text-text-h hover:bg-border',
        outline: 'border border-border bg-transparent text-text-h hover:bg-border/40',
        ghost: 'bg-transparent text-text-h hover:bg-border/40',
        link: 'bg-transparent text-accent underline-offset-4 hover:underline p-0 h-auto min-h-0 min-w-0',
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

  // Radix Slot verlangt genau EIN valides Element als Kind (klont Props direkt auf das Kind statt
  // ein eigenes DOM-Element zu rendern) - der Spinner wird deshalb nur im nativen <button>-Fall
  // zusaetzlich eingefuegt. `asChild` wird in dieser App ausschliesslich fuer navigierende Links
  // (kein eigener Pending-Zustand) verwendet, `busy` fuer native Aktions-Buttons - beide Props
  // gleichzeitig sind daher kein vorgesehener Anwendungsfall.
  return (
    <Comp
      type={asChild ? undefined : type}
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={asChild ? undefined : isDisabled}
      aria-disabled={asChild && isDisabled ? true : undefined}
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
