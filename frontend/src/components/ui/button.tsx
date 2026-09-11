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
 * TREFFERFLÄCHE: keine 44px-GRÖSSENregel, sondern eine TREFFERFLÄCHENregel - `tap-target` spannt
 * ein transparentes Pseudo-Element auf mindestens 44px auf, ohne die sichtbare Dichte zu kosten.
 * Nur auf der kurzen Achse: eine beschriftete Schaltfläche ist breit genug, die Symbol-Variante
 * bekommt `tap-target-square`. Der `link`-Variante wird NICHT aufgespannt - sie ist Inline-Text im
 * Textfluss, eine 44px-Fläche darum würde Nachbarklicks schlucken.
 *
 * ZUSTAND "GEDRÜCKT" IST PFLICHT: Tailwind bindet `hover:` an `@media (hover: hover)` - am Telefon
 * fällt der Überfahren-Zustand ersatzlos weg, ein Fingertipp erzeugte ohne `active:` gar keine
 * sichtbare Rückmeldung. Jede Ausprägung trägt deshalb den Board-Zustand "Gedrückt" als `active:`.
 *
 * FOKUS: keine eigene Fokusdarstellung. Die eine globale, abgesetzte Kontur in index.css ist die
 * alleinige Fokusdarstellung; eine hier hartkodierte Ring-Versatzfarbe wäre auf den Seitengrund
 * verdrahtet und erzeugte auf Karten und in Dialogen einen falsch getönten Kranz.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-xs font-semibold ' +
    'transition-colors disabled:pointer-events-none disabled:border disabled:border-border ' +
    'disabled:bg-surface disabled:text-text-disabled disabled:opacity-40',
  {
    variants: {
      variant: {
        // Primär: gefüllte Akzentfläche mit dunkler Tinte (10.67:1) - sofort als die eine
        // Hauptaktion lesbar. Überfahren/gedrückt nur über Deckkraft, die Fläche bleibt.
        default: 'bg-accent text-accent-fg hover:opacity-85 active:opacity-70',
        // Sekundär: der UMRISS ist hier das Identifikationsmerkmal, nicht die Fläche - in einem
        // Dialog ist die Fläche identisch zum Grund. Deshalb --border-control (>= 3:1) und nicht
        // der dekorative --border (1.04-1.45:1), der den Button dort unsichtbar machen würde.
        secondary:
          'border border-border-control bg-overlay text-text-h hover:opacity-80 active:bg-border active:text-text',
        // `outline` ist auf Sekundär vereinheitlicht: das Board kennt keine vierte gefüllte
        // Ausprägung. Bewusst als eigener Variantenname erhalten, damit die bestehenden
        // Aufrufstellen unverändert bleiben.
        outline:
          'border border-border-control bg-overlay text-text-h hover:opacity-80 active:bg-border active:text-text',
        // Unaufdringlich: nur Beschriftung; erst beim Überfahren/Drücken entsteht eine Fläche.
        // Die gedrückte Fläche ist `--border`; die Beschriftung bleibt darauf `--text` (5.49:1).
        // `--text-muted` wäre hier 4.36:1 und damit knapp unter AA - und "gedrückt" ist am Telefon
        // der EINZIGE Zustand, den es gibt, also kein Randfall.
        ghost:
          'bg-transparent text-text hover:bg-overlay hover:text-text-h active:bg-border active:text-text',
        // Zerstörerisch: zeichengleich zur primären, nur andere Fläche. Gefüllt statt umrandet,
        // und zwar nicht aus Geschmack - eine umrandete Danger-Variante ist mit dieser Palette
        // nicht sauber baubar: --danger-text misst auf --overlay (Dialogfläche) 4.51 und auf der
        // gedrückten Zustandsfläche --border 4.33, der am Telefon EINZIGE Zustand "gedrückt"
        // verfehlte also AA. Dazu stünden "Abbrechen" (sekundär, umrandet) und "Löschen" als zwei
        // gleich aussehende Umrisse nebeneinander.
        //
        // EINE Ausprägung, nicht zwei: Auslöser und bestätigende Aktion im Dialog tragen
        // dieselbe. KOLLISIONSREGEL (verbindlich): gefülltes --danger mit dunkler Tinte bei
        // Radius 6px ist formgleich mit dem Kennzeichen "Aussortiert" und dem aktiven
        // "Verwerfen"-Eintrag der Bewertungsleiste - `destructive` darf deshalb auf keiner
        // Ansicht stehen, die Bewertungs-Kennzeichen oder die Bewertungsleiste zeigt (Raster,
        // Kuratierung, Einzelbild, Vergleich).
        destructive: 'bg-danger text-danger-fg hover:opacity-85 active:opacity-70',
        // Link ist Text im Fließtext, keine Schaltfläche - eigene Größe und kein Board-Maß.
        link: 'bg-transparent text-sm font-normal text-accent-strong underline-offset-4 hover:underline active:underline p-0 h-auto min-h-0 min-w-0',
      },
      size: {
        default: 'h-8 min-w-8 px-4 py-2',
        sm: 'h-8 min-w-8 px-3',
        icon: 'size-8',
      },
    },
    // cva reiht die `size`-Klassen NACH den `variant`-Klassen ein, tailwind-merge löst Konflikte
    // zugunsten der zuletzt vorkommenden Klasse auf - ohne diesen compoundVariant würden `size`s
    // Höhen-/Polsterungsklassen die bewusst kompakten link-Klassen (h-auto/min-w-0/p-0) immer
    // überschreiben, unabhängig von der gewählten Größe. Das Fehlen von `size` als Bedingung heißt
    // laut cva "passt auf jede Größe" - ein einziger Eintrag deckt deshalb alle drei Größen ab.
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
   * Label-Text-Wechsel (z.B. "Anmelden…") bleibt bewusst Aufgabe des Aufrufers - diese Komponente
   * ergänzt nur den zentralen Spinner und die erzwungene Deaktivierung.
   */
  busy?: boolean
  /** Rendert die Styling-/Verhaltens-Props auf das einzelne Kind-Element (Radix Slot) statt auf
   * ein eigenes <button> - z.B. um einen react-router <Link> wie einen Button aussehen zu lassen,
   * ohne ein <button> um ein <a> zu verschachteln (invalides HTML). */
  asChild?: boolean
  /** React 19 reicht `ref` als reguläre Prop durch; `ButtonHTMLAttributes` deklariert sie nicht.
   * Gebraucht z.B. von ui/dialog.tsx, das den Erstfokus gezielt auf die Abbrechen-Schaltfläche
   * legt. */
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

  // Die Trefferflächen-Aufspannung steht bewusst hier und nicht in der `size`-Variante: sie hängt
  // an BEIDEN Achsen der gewählten Größe UND daran, dass es sich nicht um die link-Variante
  // handelt. tailwind-merge kennt `tap-target` nicht und könnte es aus einer Variante heraus nicht
  // wieder entfernen.
  const tapTargetClass =
    variant === 'link' ? undefined : size === 'icon' ? 'tap-target-square' : 'tap-target'

  // Radix Slot verlangt genau EIN valides Element als Kind (klont Props direkt auf das Kind statt
  // ein eigenes DOM-Element zu rendern) - der Spinner wird deshalb nur im nativen <button>-Fall
  // zusätzlich eingefügt. `asChild` wird in dieser App ausschließlich für navigierende Links (kein
  // eigener Pending-Zustand) verwendet, `busy` für native Aktions-Buttons - beide Props
  // gleichzeitig sind kein vorgesehener Anwendungsfall.
  //
  // DEAKTIVIERTE LINKS: `aria-disabled` allein blockiert bei `asChild` keine echte Interaktion,
  // weil das native `disabled`-Attribut nicht an ein `<a href>` gebunden werden kann - und ein
  // `onClick`, der nur `event.preventDefault()` aufruft, reicht bei react-router `Link` NICHT aus:
  // Radix Slot ruft laut eigener `mergeProps`-Implementierung IMMER zuerst den Handler des Kindes
  // auf (Links eigener Klick-Handler löst synchron `navigate()` aus) und erst danach den hier
  // übergebenen - `preventDefault()` kommt zu spät. Stattdessen wird die Interaktion an der Wurzel
  // unterbunden: `pointer-events-none` verhindert, dass ein Mausklick das Element überhaupt trifft
  // (kein Klick-Event entsteht), `tabIndex={-1}` entfernt es aus der Tab-Reihenfolge, sodass
  // Enter/Leertaste es nicht auslösen können. Präventive Absicherung der Basiskomponente: es gibt
  // derzeit keinen Aufrufer mit `asChild disabled`.
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
