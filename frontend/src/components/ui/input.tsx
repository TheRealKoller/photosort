import type { InputHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

/**
 * Eingabefeld in den drei Board-Zustaenden (specs/architecture/0005-board-dark-utility-register.md
 * Abschnitt 6): normal / fokussiert / fehlerhaft, Radius 6px, Flaeche `--surface`, Text 14px.
 *
 * - Normal: 1px `--border-control`. Bewusst NICHT der dekorative `--border` (1.34:1 auf dieser
 *   Flaeche) - der Umriss ist hier das Identifikationsmerkmal des Bedienelements und muss 3:1
 *   halten, sonst ist das Feld auf dem dunklen Grund nicht als Feld erkennbar.
 * - Fokussiert: 1,5px `--accent` am Feld, Textmarke in `--accent`, Text auf Primaerstufe. Die
 *   FOKUSDARSTELLUNG selbst ist davon unabhaengig die eine globale, abgesetzte Kontur aus
 *   index.css - deshalb `focus:` (Zustand des Feldes) und keine eigene Ring-Utility hier.
 * - Fehlerhaft: 1px `--danger` am Feld. Beschriftung und Meldung tragen `--danger-text` (nicht
 *   `--danger` - als Fliesstext haelt der Board-Ton auf erhoehten Flaechen kein AA); das ist
 *   Sache des Formulars, nicht dieser Komponente.
 * - Ergaenzt (das Board zeigt beides nicht): Platzhalter in `--text-muted` - nie in
 *   `--text-disabled`, ein Platzhalter ist Inhalt; deaktiviert mit `--border` und
 *   `--text-disabled`.
 *
 * FOKUSSIERT + FEHLERHAFT gleichzeitig loeschen sich nicht gegenseitig aus: der Fehlerumriss
 * bleibt am Feld (`aria-invalid:` gewinnt ueber `focus:`, weil es spaeter in der Klassenliste
 * steht), die Fokusdarstellung liegt als abgesetzte Kontur aussen herum. Beide sind gleichzeitig
 * sichtbar.
 *
 * HOEHE: 44px statt der kompakten Board-Masse. Ein `<input>` ist ein ersetztes Element und traegt
 * KEINE Pseudo-Elemente - die Trefferflaechen-Aufspannung (`tap-target`) wuerde hier still gar
 * nichts tun. Wo 44px nicht ueber die Aufspannung erreichbar sind, wird das Element sichtbar gross
 * genug gemacht, statt die Aufspannung heimlich wegzulassen.
 */
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-11 w-full rounded-sm border border-border-control bg-surface px-3 text-sm text-text-h',
        'caret-accent placeholder:text-text-muted',
        'focus:border-[1.5px] focus:border-accent focus:outline-none',
        'aria-invalid:border aria-invalid:border-danger',
        'disabled:pointer-events-none disabled:border-border disabled:text-text-disabled',
        className
      )}
      {...props}
    />
  )
}
