import type { ReactNode } from 'react'

import { Button } from './button'
import { Icon } from './icon'
import type { IconName } from './icon'
import { cn } from '../../lib/utils'

export type AlertVariant = 'success' | 'warning' | 'error'

interface AlertProps {
  children: ReactNode
  variant?: AlertVariant
  /** Kuratierter Titel. Fehlt er, greift der Standardtitel der Auspraegung - ein Titel ist
   * Pflicht, die Meldung darf ihre Bedeutung nie allein ueber die Umrissfarbe tragen. */
  title?: string
  /** Loest bei Klick auf "Erneut versuchen" aus - fehlt diese Prop, wird kein Retry-Button
   * gerendert (z.B. fuer reine Formularfehler ohne sinnvolle Wiederholaktion). */
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

/*
 * Einheitliche Meldungskomponente (specs/architecture/0004-design-system.md, "Fehlerzustand mit
 * Retry"), jetzt in der Toast-Konstruktion des Boards und in drei Auspraegungen
 * (specs/architecture/0005-board-dark-utility-register.md Abschnitt 6): Flaeche `--elevated`,
 * farbiger 1px-Rand, Symbol 18px, Titel in Primaertext, Beitext in Sekundaertext.
 *
 * BEWUSSTE ABGRENZUNG: Uebernommen wird die OPTIK des Board-Toasts, nicht sein VERHALTEN.
 * Meldungen bleiben inline und kontextnah (Banner ueber der betroffenen Ansicht, mit "Erneut
 * versuchen", wo eine Wiederholung sinnvoll ist). Ein schwebendes, selbst verschwindendes
 * Toast-System waere neues Verhalten und damit eine funktionale Aenderung, die Spec 0320
 * ausschliesst.
 *
 * Die frueher hier verwendete Konstruktion (`bg-status-failed/10` + `border-status-failed/40`) lag
 * ausserhalb jeder Kontrastmatrix: ueber einer Deckkraft-Tinte ist Kontrast statisch nicht
 * rechenbar. Das `⚠`-Textzeichen entfaellt - es steht in keiner der beiden Symbollisten.
 */
const VARIANTS: Record<AlertVariant, { icon: IconName; title: string; frame: string; body: string }> = {
  success: {
    icon: 'check',
    title: 'Erfolg',
    frame: 'border-accent-2 text-accent-2',
    body: 'text-text',
  },
  warning: {
    // `info` statt des Board-`star`: `star` ist im Produkt das Favorit-Symbol, dieselbe Form fuer
    // "Warnung" zu verwenden braeche "Bewertungsstufen auf einen Blick unterscheidbar"
    // (ADR 0055 Punkt 7e).
    icon: 'info',
    title: 'Hinweis',
    frame: 'border-accent text-accent',
    body: 'text-text',
  },
  error: {
    icon: 'x-circle',
    title: 'Fehler',
    // Rand in `--danger` (grafisch, >= 3:1 auf allen vier Flaechen), Meldungstext in
    // `--danger-text` - der Board-Ton haelt als Fliesstext auf erhoehten Flaechen kein AA.
    frame: 'border-danger text-danger-text',
    body: 'text-danger-text',
  },
}

export function Alert({
  children,
  variant = 'error',
  title,
  onRetry,
  retryLabel = 'Erneut versuchen',
  className,
}: AlertProps) {
  const config = VARIANTS[variant]

  return (
    <div
      role="alert"
      data-alert-variant={variant}
      className={cn(
        'flex flex-wrap items-start gap-3 rounded-md border bg-elevated p-3 text-sm',
        config.frame,
        className
      )}
    >
      <Icon name={config.icon} size={18} className="shrink-0" />
      <div className="flex min-w-40 flex-1 flex-col gap-1">
        <p className="font-semibold text-text-h">{title ?? config.title}</p>
        {/* Fremdtext (`detail` des Servers) ausschliesslich als regulaerer React-Textknoten - nie
            dangerouslySetInnerHTML, kein Markdown-/Rich-Text-Rendering, keine Verlinkung. */}
        <p className={config.body}>{children}</p>
      </div>
      {onRetry && (
        <Button type="button" variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  )
}
