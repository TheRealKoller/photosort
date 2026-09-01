import type { ComponentProps, ReactNode } from 'react'

import { cn } from '../../lib/utils'

// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, UI/UX-Abschnitt: natives
// <input type="checkbox"> statt eines neuen @radix-ui/react-checkbox-Pakets - dieselbe Linie wie
// switch.tsx und der native <dialog> ("Radix-Primitives nur dort einsetzen, wo natives HTML nicht
// reicht", Design-System). Eine Checkbox braucht weder Portal noch freie Positionierung; die
// native Variante bringt Tastatur-, Screenreader- und Formularsemantik vollstaendig mit.
//
// Bewusst KEIN Switch (der steht im Produkt bereits fuer die DAUERHAFTE Projekteinstellung, siehe
// ProjectSettingsPage): die unterschiedliche Optik haelt die beiden Bedeutungen auseinander -
// Einmal-Entscheidung fuer diesen Durchlauf vs. grundsaetzliche Einwilligung.
export interface CheckboxProps
  extends Omit<ComponentProps<'input'>, 'type' | 'checked' | 'onChange'> {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  /** Beschriftung; klickbar, weil das umschliessende <label> das Eingabefeld traegt. */
  label: ReactNode
}

export function Checkbox({
  checked,
  onCheckedChange,
  label,
  className,
  disabled,
  ...props
}: CheckboxProps) {
  return (
    <label
      className={cn(
        // min-h-11 (44px) traegt das Touch-Ziel-Minimum ueber die gesamte Zeile - der Klick auf
        // den Text schaltet mit, nicht nur der 16px-Kasten selbst (Design-System: "mindestens
        // 44x44px fuer jedes interaktive Element").
        'inline-flex min-h-11 cursor-pointer items-center gap-3 text-sm text-text-h',
        disabled && 'cursor-not-allowed opacity-50',
        className
      )}
    >
      <input
        // Analog switch.tsx (Copilot-Review-Fund PR #181): {...props} MUSS vor den invarianten
        // Attributen stehen, damit ein Aufrufer die kontrollierte Semantik nicht versehentlich
        // ueber die uebrigen Props ueberschreibt.
        {...props}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onCheckedChange(event.target.checked)}
        className={cn(
          'size-5 shrink-0 rounded border-border accent-accent',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
          'focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
          'disabled:cursor-not-allowed'
        )}
      />
      <span>{label}</span>
    </label>
  )
}
