import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

/*
 * specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erstes eigenes Toggle-
 * Widget im Projekt - kein @radix-ui/react-switch in package.json, natives
 * <button role="switch" aria-checked> statt einer neuen Abhaengigkeit fuer ein einziges
 * Bedienelement (Minimalismus-Prinzip, ADR decisions/0006). "Radix-Primitives nur dort einsetzen,
 * wo natives HTML nicht reicht" (Design-System) - ein <button> mit role="switch" deckt die volle
 * ARIA-Switch-Semantik ab, kein Portal/keine freie Positionierung noetig wie beim Popover.
 *
 * Board-Geometrie (specs/architecture/0005-board-dark-utility-register.md Abschnitt 6):
 * 48 x 24px, Knauf 20px, vollrund - eine der wenigen Rundformen, die bleiben. Farben sind
 * ergaenzt, das Board zeigt sie nicht:
 *   Aus:         Spur `--overlay`, Umriss `--border-control`, Knauf in Sekundaertextfarbe
 *   Ein:         Spur `--accent`, Knauf in `--accent-fg` ("gefuellt = gesetzt", dieselbe Logik
 *                wie beim Bewertungs-Badge)
 *   Deaktiviert: Spur `--surface`, Umriss `--border`, Knauf `--text-disabled`
 * Der Zustand wird zusaetzlich ueber die KNAUFPOSITION getragen, nicht nur ueber die Farbe.
 *
 * Sichtbar 24px hoch statt der frueheren 44px; die Trefferflaeche kommt ueber `tap-target` (die
 * Breite von 48px liegt bereits ueber dem Minimum, aufgespannt wird deshalb nur die kurze Achse).
 */
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
      // Copilot-Review-Fund (PR #181): {...props} MUSS vor den invarianten Attributen
      // gespreadet werden - SwitchProps omitted aus ComponentProps<'button'> aktuell nur
      // onClick/role, nicht type/aria-checked/disabled. Kaeme der Spread zuletzt (wie zuvor),
      // koennte ein Aufrufer versehentlich ueber `type`/`aria-checked`/`disabled` in den
      // uebrigen Props die kontrollierte Switch-Semantik ueberschreiben.
      {...props}
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'group tap-target relative inline-flex h-6 w-12 shrink-0 items-center rounded-full border transition-colors',
        'disabled:cursor-not-allowed disabled:border-border disabled:bg-surface',
        checked ? 'border-accent bg-accent' : 'border-border-control bg-overlay',
        className
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none inline-block size-5 translate-x-0.5 transform rounded-full transition-transform',
          checked ? 'translate-x-6 bg-accent-fg' : 'bg-text',
          // Ueber die Gruppe an den TATSAECHLICHEN :disabled-Zustand der Schaltflaeche gebunden,
          // nicht an eine JS-Kopie des Props - beide koennen so nicht auseinanderlaufen.
          'group-disabled:bg-text-disabled'
        )}
      />
    </button>
  )
}
