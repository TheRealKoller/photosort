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

// Styling konsistent mit ui/card.tsx (Formsprache: rounded-md/shadow-warm - hier bewusst 8px
// [rounded-md] statt der 12px-Karten-Variante, siehe UI/UX-Abschnitt der Spec) und ui/alert.tsx
// (Bannermuster). `shadow-warm` loest sich ueber index.css automatisch je Farbschema auf
// (`--shadow: none` im Dunkelmodus) - dieselbe "Schatten durch Rahmen ersetzt"-Regel wie bei Card,
// ohne eine eigene `dark:`-Klasse noetig zu haben.
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
          'z-50 max-h-[60vh] w-72 overflow-y-auto rounded-md border border-border bg-bg p-3 text-sm text-text shadow-warm outline-none',
          className
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}
