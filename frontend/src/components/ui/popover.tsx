import * as PopoverPrimitive from '@radix-ui/react-popover'
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

// Duenner Radix-Wrapper (specs/features/0040-bewertungsdetails-info-popover.md, Architektur-
// Abschnitt) - erste Verwendung von @radix-ui/react-popover im Projekt (bisher nur
// @radix-ui/react-slot fuer `asChild`-Komposition, siehe ui/button.tsx). Bewusst Popover statt
// Tooltip: das ARIA-Tooltip-Pattern ist hover/focus-only konzipiert und oeffnet sich nicht per
// Tap, Radix Popover hat einen echten Button-Trigger, der nativ per Tap funktioniert. Enthaelt
// selbst KEINE geraetespezifische Hover-Logik - die lebt feature-spezifisch in
// components/CriterionDetailsPopover.tsx, das diese generische Primitive nutzt (analog zum
// bestehenden Muster ui/badge.tsx -> CategoryBadge.tsx).
export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger
export const PopoverClose = PopoverPrimitive.Close

// Bewusst KEINE outline-unterdrueckende Utility auf dem Panel: Radix setzt beim Oeffnen den Fokus auf den
// Content-Knoten (`tabindex="-1"`). Ohne Kontur bekaeme ein Tastaturnutzer dort gar keine
// Rueckmeldung, wohin der Fokus gesprungen ist - und eine outline-unterdrueckende Utility liegt
// in einer spaeteren Cascade Layer als die globale Fokusregel, wuerde sie also gewinnen.
//
// Board-Werte (specs/architecture/0005-board-dark-utility-register.md Abschnitt 5/6): Radius 8px,
// Flaeche `--elevated`, flach. Das Popover rueckt damit von `--surface` auf `--elevated` - es
// liest so als aufgesetzte Ebene und nicht als weitere Karte. Der frueher hier gesetzte Schatten
// entfaellt ersatzlos: Tiefe tragen die vier Flaechenstufen.
//
// `ref` als normale Prop (React 19, kein `forwardRef` noetig, specs/features/0041-
// bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md, Architektur-Abschnitt) - laesst
// CriterionDetailsPopover.tsx einen contentRef an den tatsaechlichen DOM-Knoten binden, fuer den
// Ref-basierten Grace-Bereich-Check des Hover-Auto-Close ueber die Portal-Grenze hinweg. Kein
// eigener Unit-Test hier (Testkonzept Punkt 7, "duenne generische Primitive") - ein kaputtes
// Forwarding zeigt sich indirekt, aber vollstaendig in jedem Grace-Bereich-Test von
// CriterionDetailsPopover.test.tsx.
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
          // HOEHENSCHRANKE ZWEISTUFIG (Befund aus dem e2e-Lauf zu Spec 0321): `max-h-[60vh]`
          // allein ist eine Schranke gegen den VIEWPORT, keine gegen den tatsaechlich
          // verfuegbaren Platz. Sobald der Trigger so steht, dass weder ueber noch unter ihm 60vh
          // frei sind - seit die Foto-Karte einen Kartenkoerper hat, ist das bei 360px der
          // Regelfall -, schiebt Radix das Panel zwar auf die groessere Seite, kuerzt es aber
          // nicht: es ragte unten aus dem Sichtbereich. `--radix-popover-content-available-height`
          // ist genau der Wert, den Radix bei der Kollisionsvermeidung ohnehin misst; das
          // Minimum aus beiden haelt die Board-Schranke UND den Sichtbereich ein.
          'z-50 max-h-[min(60vh,var(--radix-popover-content-available-height))] w-72 overflow-y-auto rounded-md border border-border bg-elevated p-4 text-sm text-text',
          className
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}
