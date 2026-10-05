import { useState } from 'react'

import { cn } from '../lib/utils'
import { Button } from './ui/button'
import type { ButtonProps } from './ui/button'
import { Icon } from './ui/icon'
import type { IconName } from './ui/icon'

export interface TileActionProps extends Omit<
  ButtonProps,
  'children' | 'size' | 'variant' | 'aria-label' | 'asChild'
> {
  icon: IconName
  /** Das Kurzwort - ein festes Literal, nie ein Wert aus der API. */
  label: string
  /** `{Handlung}: {Dateipfad}` - in beiden Formen derselbe zugaengliche Name. */
  accessibleName: string
  /** Nur das Symbol; die Kachel entscheidet das fuer ALLE ihre Knoepfe zugleich. */
  iconOnly: boolean
  /** Die gerechnete Kachelbreite - der Kurzhinweis wird nie breiter und verlaesst die Kachel nie. */
  tileWidth: number
  /** Erster Knopf der Zeile `start` (Hinweis linksbuendig), zweiter `end` (rechtsbuendig). */
  align: 'start' | 'end'
}

/**
 * Ein Handgriff auf einer Kuratierungskachel: Symbol plus Kurzwort, auf einer schmalen Kachel nur
 * das Symbol. Am Telefon sichtbar 44px (heisser Pfad), ab `sm` 32px.
 *
 * Im Symbolmodus erscheint das Kurzwort beim Ueberfahren und bei Tastaturfokus UEBER dem Knopf
 * (`aria-hidden`, der Name traegt es bereits). Am Telefon gibt es keinen Ueberfahren-Zustand und
 * nach einem Tipp kein `:focus-visible`, also keinen Hinweis. Der Tastaturfokus wird beim
 * Fokussieren gelesen statt per Variante gestylt: Fokus-Varianten sind der globalen
 * Fokusdarstellung vorbehalten.
 *
 * Bei `busy` ERSETZT der Spinner das Symbol: daneben gestellt wuechse ein beschrifteter Knopf ueber
 * die Breite, auf die die Knopfzeile gerechnet ist.
 */
export function TileAction({
  icon,
  label,
  accessibleName,
  iconOnly,
  tileWidth,
  align,
  busy = false,
  className,
  onFocus,
  onBlur,
  ...props
}: TileActionProps) {
  const [keyboardFocus, setKeyboardFocus] = useState(false)

  return (
    <Button
      variant="outline"
      size={iconOnly ? 'icon' : 'compact'}
      busy={busy}
      aria-label={accessibleName}
      // `relative`: Positionskontext des Kurzhinweises. `tap-target` setzt ihn ueber CSS bereits,
      // er steht hier trotzdem ausdruecklich, damit der Hinweis nicht an einer fremden Regel haengt.
      className={cn(
        'group relative shrink-0',
        iconOnly ? 'size-11 sm:size-8' : 'h-11 sm:h-8',
        className,
      )}
      onFocus={(event) => {
        setKeyboardFocus(event.currentTarget.matches(':focus-visible'))
        onFocus?.(event)
      }}
      onBlur={(event) => {
        setKeyboardFocus(false)
        onBlur?.(event)
      }}
      {...props}
    >
      {!busy && <Icon name={icon} size={14} />}
      {!iconOnly && label}
      {iconOnly && (
        <span
          data-tile-action-hint=""
          data-align={align}
          data-shown={keyboardFocus ? 'true' : undefined}
          aria-hidden="true"
          style={{ maxWidth: tileWidth }}
          className={cn(
            'pointer-events-none absolute bottom-full z-10 mb-1 hidden w-max rounded-sm border border-border-control bg-overlay px-2 py-1 text-xs whitespace-normal text-text-h group-hover:block',
            align === 'start' ? 'left-0' : 'right-0',
            keyboardFocus && 'block',
          )}
        >
          {label}
        </span>
      )}
    </Button>
  )
}
