import type { ComponentProps, ReactNode } from 'react'

import { cn } from '../../lib/utils'

/*
 * specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, UI/UX-Abschnitt: natives
 * <input type="checkbox"> statt eines neuen @radix-ui/react-checkbox-Pakets - dieselbe Linie wie
 * switch.tsx und der native <dialog> ("Radix-Primitives nur dort einsetzen, wo natives HTML nicht
 * reicht", Design-System). Eine Checkbox braucht weder Portal noch freie Positionierung; die
 * native Variante bringt Tastatur-, Screenreader- und Formularsemantik vollstaendig mit.
 *
 * Bewusst KEIN Switch (der steht im Produkt bereits fuer die DAUERHAFTE Projekteinstellung, siehe
 * ProjectSettingsPage): die unterschiedliche Optik haelt die beiden Bedeutungen auseinander -
 * Einmal-Entscheidung fuer diesen Durchlauf vs. grundsaetzliche Einwilligung.
 *
 * DAS BOARD ZEIGT DIESES ELEMENT UEBERHAUPT NICHT - die Werte sind vollstaendig aus dem
 * Eingabefeld abgeleitet, damit das Kontrollkaestchen als dessen kleiner Bruder liest: 18px
 * Kasten, Radius 4px, Umriss `--border-control`, Flaeche `--surface`; gesetzt in `--accent` ueber
 * `accent-color`; deaktiviert mit `--border` und `--text-disabled`. Ein unbestimmter Zustand wird
 * nicht eingefuehrt - es gibt keinen Anwendungsfall.
 */
export interface CheckboxProps
  // `defaultChecked` ist bewusst mit ausgeschlossen (Copilot-Review-Fund, PR #307): die Komponente
  // ist ueber `checked`/`onCheckedChange` durchgaengig kontrolliert. Setzt ein Aufrufer zusaetzlich
  // `defaultChecked`, warnt React ueber die Vermischung von controlled und uncontrolled input -
  // ein Fehler, der zur Laufzeit nur als Konsolenwarnung auffaellt. Der Typ verhindert ihn.
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
        // ausrichten. Das Label traegt es stattdessen. `min-h-11` haelt die Zeile ohnehin auf
        // 44px - `tap-target` ist die Absicherung fuer den Fall, dass ein Aufrufer die Hoehe
        // ueber `className` kleiner setzt, und spannt dann nur die kurze Achse auf.
        'tap-target inline-flex min-h-11 cursor-pointer items-center gap-3 text-sm text-text-h',
        // Der deaktivierte Zustand haengt am Eingabefeld, nicht an einer JS-Kopie des Props:
        // `has-[:disabled]:` folgt dem tatsaechlichen DOM-Zustand und kann nicht auseinanderlaufen.
        'has-[:disabled]:cursor-not-allowed has-[:disabled]:text-text-disabled',
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
          'size-[18px] shrink-0 rounded-xs border border-border-control bg-surface accent-accent',
          'disabled:cursor-not-allowed disabled:border-border'
        )}
      />
      <span>{label}</span>
    </label>
  )
}
