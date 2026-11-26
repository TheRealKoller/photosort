import type { ComponentProps, ReactNode } from 'react'

import { cn } from '../../lib/utils'

/*
 * Natives <input type="checkbox">: Es bringt Tastatur-, Screenreader- und Formularsemantik
 * vollstaendig mit; eine Checkbox braucht weder Portal noch freie Positionierung.
 *
 * Bewusst KEIN Switch (der steht fuer die DAUERHAFTE Projekteinstellung): die unterschiedliche
 * Optik haelt die beiden Bedeutungen auseinander - Einmal-Entscheidung fuer diesen Durchlauf vs.
 * grundsaetzliche Einwilligung.
 *
 * Das Board zeigt dieses Element nicht; die Werte sind vollstaendig aus dem Eingabefeld
 * abgeleitet, damit das Kontrollkaestchen als dessen kleiner Bruder liest: 18px Kasten, Radius
 * 4px, Umriss `--border-control`, Flaeche `--surface`; gesetzt in `--accent` ueber
 * `accent-color`; deaktiviert mit `--border` und `--text-disabled`. Ein unbestimmter Zustand wird
 * nicht eingefuehrt - es gibt keinen Anwendungsfall.
 */
export interface CheckboxProps
  // `defaultChecked` ist bewusst mit ausgeschlossen: die Komponente ist ueber
  // `checked`/`onCheckedChange` durchgaengig kontrolliert. Ein Aufrufer, der zusaetzlich
  // `defaultChecked` setzt, mischt controlled und uncontrolled - React warnt dann zur Laufzeit;
  // der Typ verhindert es.
  extends Omit<ComponentProps<'input'>, 'type' | 'checked' | 'defaultChecked' | 'onChange'> {
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
        // Die TREFFERFLAECHE ist die ganze ZEILE, nicht der 18px-Kasten: ein <input> ist ein
        // ersetztes Element und traegt keine Pseudo-Elemente, `tap-target` koennte dort nichts
        // ausrichten. `min-h-11` haelt die Zeile auf 44px; setzt ein Aufrufer die Hoehe ueber
        // `className` kleiner, spannt `tap-target` nur die kurze Achse auf.
        'tap-target inline-flex min-h-11 cursor-pointer items-center gap-3 text-sm text-text-h',
        // Der deaktivierte Zustand haengt am Eingabefeld, nicht an einer JS-Kopie des Props:
        // `has-[:disabled]:` folgt dem tatsaechlichen DOM-Zustand und kann nicht auseinanderlaufen.
        'has-[:disabled]:cursor-not-allowed has-[:disabled]:text-text-disabled',
        className,
      )}
    >
      <input
        // {...props} MUSS vor den invarianten Attributen stehen, damit ein Aufrufer die
        // kontrollierte Semantik nicht ueber die uebrigen Props ueberschreibt.
        {...props}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onCheckedChange(event.target.checked)}
        className={cn(
          'size-[18px] shrink-0 rounded-xs border border-border-control bg-surface accent-accent',
          'disabled:cursor-not-allowed disabled:border-border',
        )}
      />
      <span>{label}</span>
    </label>
  )
}
