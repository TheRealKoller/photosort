import type { ReactNode } from 'react'

import { formatDraftPhotoCount } from '../utils/albumDraft'
import { Button } from './ui/button'

export interface AlbumDraftDayProps {
  heading: string
  collapsed: boolean
  count: number
  /** Positionshaken des zugeklappten Tages - nur dann, sonst tragen ihn die Events selbst. */
  firstEventPosition: number | undefined
  panelId: string
  onToggle: () => void
  children: ReactNode
}

/** Ein Tag des Album-Entwurfs mit aufklappbarer Überschrift. */
export function AlbumDraftDay({
  heading,
  collapsed,
  count,
  firstEventPosition,
  panelId,
  onToggle,
  children,
}: AlbumDraftDayProps) {
  return (
    <section
      data-draft-position={collapsed ? firstEventPosition : undefined}
      className="flex flex-col gap-4"
    >
      <h2 className="text-lg">
        <Button
          variant="ghost"
          aria-expanded={!collapsed}
          aria-controls={panelId}
          onClick={onToggle}
          className="h-auto min-h-11 w-full justify-start whitespace-normal px-2 py-1 text-left text-lg font-normal"
        >
          <span aria-hidden="true">{collapsed ? '▶' : '▼'}</span>
          <span>{heading}</span>
          {collapsed && (
            <>
              {' '}
              <span className="font-normal text-text">{`(${formatDraftPhotoCount(count)})`}</span>
            </>
          )}
        </Button>
      </h2>
      {!collapsed && (
        <div id={panelId} className="flex flex-col gap-6">
          {children}
        </div>
      )}
    </section>
  )
}
