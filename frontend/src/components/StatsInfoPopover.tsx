import type { ReactNode } from 'react'

import { Button } from './ui/button'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from './ui/popover'

/**
 * Erlaeuterung unmittelbar bei der Kennzahl - das im Projekt etablierte
 * Info-Popover-Muster (Radix, Klick-Ausloeser, 44x44px Trefferflaeche). Bewusst KEIN
 * `title`-Attribut: auf Touchgeraeten unzuverlaessig ausloesbar.
 */
export function StatsInfoPopover({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Erkläre ${label}`}
          className="shrink-0 border border-border-control"
        >
          i
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-center justify-between gap-3 pb-3">
          <p className="text-sm font-semibold text-text-h">{label}</p>
          <PopoverClose asChild>
            <Button variant="ghost" size="icon" aria-label="Schließen" className="shrink-0">
              <span aria-hidden="true">×</span>
            </Button>
          </PopoverClose>
        </div>
        <p className="text-sm text-text">{children}</p>
      </PopoverContent>
    </Popover>
  )
}
