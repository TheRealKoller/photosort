import * as PopoverPrimitive from '@radix-ui/react-popover'
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

// Duenner Radix-Wrapper. Bewusst Popover statt Tooltip: das ARIA-Tooltip-Pattern ist
// hover/focus-only konzipiert und oeffnet sich nicht per Tap, Radix Popover hat einen echten
// Button-Trigger, der nativ per Tap funktioniert. Enthaelt selbst KEINE geraetespezifische
// Hover-Logik - die lebt feature-spezifisch beim Aufrufer (Vorlage: components/Stepper.tsx).
export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger
export const PopoverClose = PopoverPrimitive.Close

// Bewusst KEINE outline-unterdrueckende Utility auf dem Panel: Radix setzt beim Oeffnen den Fokus auf den
// Content-Knoten (`tabindex="-1"`). Ohne Kontur bekaeme ein Tastaturnutzer dort gar keine
// Rueckmeldung, wohin der Fokus gesprungen ist - und eine outline-unterdrueckende Utility liegt
// in einer spaeteren Cascade Layer als die globale Fokusregel, wuerde sie also gewinnen.
//
// Board-Werte: Radius 8px, Flaeche `--elevated`, flach. Das Popover rueckt damit von `--surface`
// auf `--elevated` - es liest so als aufgesetzte Ebene und nicht als weitere Karte. Der frueher
// hier gesetzte Schatten entfaellt ersatzlos: Tiefe tragen die vier Flaechenstufen.
//
// `ref` als normale Prop (React 19, kein `forwardRef` noetig) - bindet einen Ref an den
// tatsaechlichen DOM-Knoten jenseits der Portal-Grenze. Kein eigener Unit-Test hier (Testkonzept
// Punkt 7, "duenne generische Primitive"); Oeffnen, Schliessen und Hover-Verhalten pruefen die
// Aufrufer (`Stepper.test.tsx`).
export function PopoverContent({
  className,
  sideOffset = 8,
  ref,
  ...props
}: ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          // HOEHENSCHRANKE ZWEISTUFIG: `max-h-[60vh]` allein ist eine Schranke gegen den VIEWPORT,
          // keine gegen den tatsaechlich verfuegbaren Platz. Sobald der Trigger so steht, dass
          // weder ueber noch unter ihm 60vh frei sind - seit die Foto-Karte einen Kartenkoerper
          // hat, ist das bei 360px der Regelfall -, schiebt Radix das Panel zwar auf die groessere
          // Seite, kuerzt es aber nicht: es ragte unten aus dem Sichtbereich.
          // `--radix-popover-content-available-height` ist genau der Wert, den Radix bei der
          // Kollisionsvermeidung ohnehin misst; das Minimum aus beiden haelt die Board-Schranke UND
          // den Sichtbereich ein.
          'z-50 max-h-[min(60vh,var(--radix-popover-content-available-height))] w-72 overflow-y-auto rounded-md border border-border bg-elevated p-4 text-sm text-text',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}
