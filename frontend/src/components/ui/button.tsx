import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/*
 * Schaltflaeche nach dem Board "Dark Utility Register" (specs/architecture/0005-board-dark-utility-
 * register.md Abschnitt 6, specs/features/0320-dark-utility-register.md).
 *
 * FORM: Radius 6px (`rounded-sm`) statt der vollen Pille des Vorgaengersystems, Polsterung 16/8px,
 * Inter Semi-Bold 12px, sichtbare Hoehe 32px statt 44px.
 *
 * TREFFERFLAECHE: Die frueher hier verankerte 44px-GROESSENregel ist zu einer
 * TREFFERFLAECHENregel geworden (ADR 0055 Punkt 8) - `tap-target` spannt ein transparentes
 * Pseudo-Element auf mindestens 44px auf, ohne die sichtbare Dichte zu kosten. Nur auf der kurzen
 * Achse: eine beschriftete Schaltflaeche ist breit genug, die Symbol-Variante bekommt
 * `tap-target-square`. Der `link`-Variante wird NICHT aufgespannt - sie ist Inline-Text im
 * Textfluss, eine 44px-Flaeche darum wuerde Nachbarklicks schlucken.
 *
 * ZUSTAND "GEDRUECKT" IST PFLICHT: Tailwind bindet `hover:` an `@media (hover: hover)` - am
 * Telefon faellt der Ueberfahren-Zustand ersatzlos weg. Vor dieser Umstellung gab es im gesamten
 * Code 27 `hover:`- und null `active:`-Stellen, ein Fingertipp erzeugte also gar keine sichtbare
 * Rueckmeldung. Jede Ausprägung traegt deshalb den Board-Zustand "Gedrueckt" als `active:`.
 *
 * FOKUS: keine eigene Fokusdarstellung mehr. Die eine globale, abgesetzte Kontur in index.css ist
 * die alleinige Fokusdarstellung; die frueher hier hartkodierte Ring-Versatzfarbe war auf den
 * Seitengrund verdrahtet und erzeugte auf Karten und in Dialogen einen falsch getoenten Kranz.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-xs font-semibold ' +
    'transition-colors disabled:pointer-events-none disabled:border disabled:border-border ' +
    'disabled:bg-surface disabled:text-text-disabled disabled:opacity-40',
  {
    variants: {
      variant: {
        // Primaer: gefuellte Akzentflaeche mit dunkler Tinte (10.67:1) - sofort als die eine
        // Hauptaktion lesbar. Ueberfahren/gedrueckt nur ueber Deckkraft, die Flaeche bleibt.
        default: 'bg-accent text-accent-fg hover:opacity-85 active:opacity-70',
        // Sekundaer: der UMRISS ist hier das Identifikationsmerkmal, nicht die Flaeche - in einem
        // Dialog ist die Flaeche identisch zum Grund. Deshalb --border-control (>= 3:1) und nicht
        // der dekorative --border (1.04-1.45:1), der den Button dort unsichtbar machen wuerde.
        secondary:
          'border border-border-control bg-overlay text-text-h hover:opacity-80 active:bg-border active:text-text',
        // `outline` ist auf Sekundaer vereinheitlicht: das Board kennt keine vierte gefuellte
        // Auspraegung. Bewusst als eigener Variantenname erhalten, damit die bestehenden
        // Aufrufstellen unveraendert bleiben.
        outline:
          'border border-border-control bg-overlay text-text-h hover:opacity-80 active:bg-border active:text-text',
        // Unaufdringlich: nur Beschriftung; erst beim Ueberfahren/Druecken entsteht eine Flaeche.
        ghost:
          'bg-transparent text-text hover:bg-overlay hover:text-text-h active:bg-border active:text-text-muted',
        // Link ist Text im Fliesstext, keine Schaltflaeche - eigene Groesse und kein Board-Mass.
        link: 'bg-transparent text-sm font-normal text-accent-strong underline-offset-4 hover:underline active:underline p-0 h-auto min-h-0 min-w-0',
      },
      size: {
        default: 'h-8 min-w-8 px-4 py-2',
        sm: 'h-8 min-w-8 px-3',
        icon: 'size-8',
      },
    },
    // Review-Fund (Branch feature/0012-visual-redesign-foundation): cva reiht die `size`-Klassen
    // NACH den `variant`-Klassen ein, tailwind-merge loest Konflikte zugunsten der zuletzt
    // vorkommenden Klasse auf - ohne diesen compoundVariant wuerden `size`s Hoehen-/Polsterungs-
    // Klassen die bewusst kompakten link-Klassen (h-auto/min-w-0/p-0) immer ueberschreiben,
    // unabhaengig von der gewaehlten Groesse. Das Fehlen von `size` als Bedingung heisst laut cva
    // "passt auf jede Groesse" - reicht deshalb als ein einziger Eintrag fuer alle drei Groessen.
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

  // Die Trefferflaechen-Aufspannung steht bewusst hier und nicht in der `size`-Variante: sie haengt
  // an BEIDEN Achsen der gewaehlten Groesse UND daran, dass es sich nicht um die link-Variante
  // handelt. tailwind-merge kennt `tap-target` nicht und koennte es aus einer Variante heraus
  // nicht wieder entfernen.
  const tapTargetClass =
    variant === 'link' ? undefined : size === 'icon' ? 'tap-target-square' : 'tap-target'

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
        tapTargetClass,
        isDisabledSlot && 'pointer-events-none opacity-40'
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
