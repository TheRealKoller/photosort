import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

// specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erstes eigenes Toggle-
// Widget im Projekt - kein @radix-ui/react-switch in package.json, natives
// <button role="switch" aria-checked> statt einer neuen Abhaengigkeit fuer ein einziges
// Bedienelement (Minimalismus-Prinzip, ADR decisions/0006). "Radix-Primitives nur dort einsetzen,
// wo natives HTML nicht reicht" (Design-System) - ein <button> mit role="switch" deckt die volle
// ARIA-Switch-Semantik ab, kein Portal/keine freie Positionierung noetig wie beim Popover.
export interface SwitchProps extends Omit<ComponentProps<'button'>, 'onClick' | 'role'> {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}

export function Switch({
  checked,
  onCheckedChange,
  className,
  disabled,
  ...props
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        // h-11 (44px) traegt allein bereits das Touch-Ziel-Minimum (Design-System: "mindestens
        // 44x44px fuer jedes interaktive Element") - w-16 liegt deutlich darueber.
        'relative inline-flex h-11 w-16 shrink-0 items-center rounded-full border border-border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'bg-accent' : 'bg-border',
        className
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          'inline-block size-8 translate-x-1 transform rounded-full bg-bg shadow-warm transition-transform',
          checked && 'translate-x-6'
        )}
      />
    </button>
  )
}
