import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import type { VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes, Ref } from 'react'

import { cn } from '../../lib/utils'

/*
 * Schaltfläche nach dem Board "Dark Utility Register".
 *
 * FORM: Radius 6px (`rounded-sm`), Polsterung 16/8px, Inter Semi-Bold 12px, sichtbare Höhe 32px.
 *
 * TREFFERFLÄCHE: `tap-target` spannt ein transparentes Pseudo-Element auf mindestens 44px auf,
 * ohne die sichtbare Dichte zu kosten, und nur auf der kurzen Achse; die Symbol-Variante bekommt
 * `tap-target-square`. Der `link`-Variante wird NICHT aufgespannt - sie ist Inline-Text im
 * Textfluss, eine 44px-Fläche darum würde Nachbarklicks schlucken.
 *
 * Jede Ausprägung trägt `active:`: Tailwind bindet `hover:` an `@media (hover: hover)`, am Telefon
 * fiele der Überfahren-Zustand ersatzlos weg und ein Fingertipp erzeugte ohne `active:` keine
 * sichtbare Rückmeldung.
 *
 * FOKUS: keine eigene Fokusdarstellung. Die eine globale, abgesetzte Kontur in index.css ist die
 * alleinige; eine hier hartkodierte Ring-Versatzfarbe wäre auf den Seitengrund verdrahtet und
 * erzeugte auf Karten und in Dialogen einen falsch getönten Kranz.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-xs font-semibold ' +
    'transition-colors disabled:pointer-events-none disabled:border disabled:border-border ' +
    'disabled:bg-surface disabled:text-text-disabled disabled:opacity-40',
  {
    variants: {
      variant: {
        // Primär: gefüllte Akzentfläche mit dunkler Tinte - sofort als die eine Hauptaktion
        // lesbar. Überfahren/gedrückt nur über Deckkraft, die Fläche bleibt.
        default: 'bg-accent text-accent-fg hover:opacity-85 active:opacity-70',
        // Sekundär: der UMRISS ist hier das Identifikationsmerkmal, nicht die Fläche - in einem
        // Dialog ist die Fläche identisch zum Grund. Deshalb `--border-control` (>= 3:1) und nicht
        // der dekorative `--border`, der den Button dort unsichtbar machen würde.
        secondary:
          'border border-border-control bg-overlay text-text-h hover:opacity-80 active:bg-border active:text-text',
        // `outline` ist auf Sekundär vereinheitlicht; der Variantenname bleibt bewusst erhalten.
        outline:
          'border border-border-control bg-overlay text-text-h hover:opacity-80 active:bg-border active:text-text',
        // Unaufdringlich: nur Beschriftung; erst beim Überfahren/Drücken entsteht eine Fläche.
        // Die gedrückte Fläche ist `--border`; die Beschriftung bleibt darauf `--text`.
        // `--text-muted` läge hier unter AA - und "gedrückt" ist am Telefon der EINZIGE Zustand,
        // den es gibt, also kein Randfall.
        ghost:
          'bg-transparent text-text hover:bg-overlay hover:text-text-h active:bg-border active:text-text',
        // Zerstörerisch: zeichengleich zur primären, nur andere Fläche. Gefüllt statt umrandet -
        // eine umrandete Danger-Variante wäre mit dieser Palette nicht AA-fest: `--danger-text`
        // verfehlt auf der gedrückten Fläche `--border` die Schwelle, und "gedrückt" ist am
        // Telefon der EINZIGE Zustand.
        //
        // EINE Ausprägung, nicht zwei: Auslöser und bestätigende Aktion im Dialog tragen
        // dieselbe. KOLLISIONSREGEL (verbindlich): gefülltes --danger mit dunkler Tinte bei
        // Radius 6px ist formgleich mit dem Kennzeichen "Aussortiert" und dem aktiven
        // "Verwerfen"-Eintrag der Bewertungsleiste - `destructive` darf deshalb auf keiner
        // Ansicht stehen, die Bewertungs-Kennzeichen oder die Bewertungsleiste zeigt (Raster,
        // Kuratierung, Einzelbild, Endauswahl).
        destructive: 'bg-danger text-danger-fg hover:opacity-85 active:opacity-70',
        // Link ist Text im Fließtext, keine Schaltfläche - eigene Größe und kein Board-Maß.
        link: 'bg-transparent text-sm font-normal text-accent-strong underline-offset-4 hover:underline active:underline p-0 h-auto min-h-0 min-w-0',
      },
      size: {
        default: 'h-8 min-w-8 px-4 py-2',
        sm: 'h-8 min-w-8 px-3',
        // Symbol (14px) plus Kurzwort auf einer Kachel: schmaler, damit zwei nebeneinander passen.
        compact: 'h-8 min-w-8 gap-1 px-2',
        icon: 'size-8',
      },
    },
    // cva reiht die `size`-Klassen NACH den `variant`-Klassen ein, tailwind-merge löst Konflikte
    // zugunsten der zuletzt vorkommenden Klasse auf - ohne diesen compoundVariant überschrieben
    // `size`s Höhen-/Polsterungsklassen die bewusst kompakten link-Klassen (h-auto/min-w-0/p-0).
    // `size` fehlt als Bedingung, weil der Eintrag für jede Größe gilt.
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
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  /**
   * Busy-Button-Muster: erzwingt den deaktivierten Zustand zentral in der Komponente, statt sich
   * darauf zu verlassen, dass jeder Aufrufer `disabled` UND `busy` synchron hält. Der
   * Label-Text-Wechsel (z.B. "Anmelden…") bleibt Aufgabe des Aufrufers.
   */
  busy?: boolean
  /** Rendert die Styling-/Verhaltens-Props auf das einzelne Kind-Element (Radix Slot) statt auf
   * ein eigenes <button> - z.B. um einen react-router <Link> wie einen Button aussehen zu lassen,
   * ohne ein <button> um ein <a> zu verschachteln (invalides HTML). */
  asChild?: boolean
  /** React 19 reicht `ref` als reguläre Prop durch; `ButtonHTMLAttributes` deklariert sie
   * nicht. */
  ref?: Ref<HTMLButtonElement>
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

  // Die Trefferflächen-Aufspannung steht hier und nicht in der `size`-Variante: sie hängt an
  // BEIDEN Achsen der gewählten Größe UND daran, dass es sich nicht um die link-Variante handelt.
  // tailwind-merge kennt `tap-target` nicht und könnte es aus einer Variante heraus nicht wieder
  // entfernen.
  const tapTargetClass =
    variant === 'link' ? undefined : size === 'icon' ? 'tap-target-square' : 'tap-target'

  // Radix Slot verlangt genau EIN valides Element als Kind (klont Props direkt auf das Kind) -
  // der Spinner wird deshalb nur im nativen <button>-Fall zusätzlich eingefügt. `asChild` wird
  // ausschließlich für navigierende Links verwendet, `busy` für native Aktions-Buttons.
  //
  // DEAKTIVIERTE LINKS: `aria-disabled` allein blockiert bei `asChild` keine echte Interaktion -
  // das native `disabled`-Attribut lässt sich nicht an ein `<a href>` binden, und ein `onClick`
  // mit `event.preventDefault()` kommt zu spät: Radix Slot ruft IMMER zuerst den Handler des
  // Kindes auf, und react-router `Link` löst dort synchron `navigate()` aus. Stattdessen wird die
  // Interaktion an der Wurzel unterbunden: `pointer-events-none` verhindert, dass ein Mausklick
  // das Element überhaupt trifft, `tabIndex={-1}` entfernt es aus der Tab-Reihenfolge, sodass
  // Enter/Leertaste es nicht auslösen können.
  return (
    <Comp
      type={asChild ? undefined : type}
      className={cn(
        buttonVariants({ variant, size, className }),
        tapTargetClass,
        isDisabledSlot && 'pointer-events-none opacity-40',
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
