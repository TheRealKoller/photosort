import { useEffect, useRef, useState } from 'react'

import { PhotoImage } from './PhotoImage'
import { Button } from './ui/button'

/** Verweildauer des Hinweises. */
export const UNDO_TOAST_MS = 8000

const FINE_HOVER_QUERY = '(hover: hover) and (pointer: fine)'

export interface UndoNoticeView {
  /** Wechselt mit jedem neuen Handgriff - ein neuer Hinweis beginnt mit voller Zeit. */
  key: number
  title: string
  photoId: number
  relativePath: string
}

export interface UndoToastProps {
  notice: UndoNoticeView | null
  /** true, solange das Rückgängig läuft: Knopf `busy`, die Zeit steht. */
  busy: boolean
  /** Grund eines gescheiterten Rückgängig aus der Serverantwort - steht an Stelle des Knopfs. */
  error: string | null
  /** Wechselt nach einem Fehlschlag: die 8 s beginnen neu. */
  restartKey: number
  onUndo: () => void
  onDismiss: () => void
}

/**
 * Der Rückgängig-Hinweis nach Streichen und Tausch - die einzige benannte Ausnahme vom
 * „kein Toast-Verhalten" des Design-Systems.
 *
 * Er steht 8 s. Fokus darin hält die Zeit an, ein Zeiger darüber ebenfalls (nur bei feinem Zeiger
 * mit Hover); danach läuft die RESTZEIT weiter. Er endet nach Ablauf, mit Esc bei Fokus darin und -
 * über den Aufrufer - nach erfolgreichem Rückgängig und mit jedem neuen Handgriff.
 *
 * Titel und Dateiname liegen in einem DAUERHAFT eingehängten `role="status"`; der Knopf liegt
 * außerhalb davon, und der Fokus wird nie in den Hinweis gezogen. Dateiname und Server-`detail`
 * sind Textknoten (S11), das Vorschaubild kommt über den authentifizierten Abruf nach Foto-Id.
 */
export function UndoToast({ notice, busy, error, restartKey, onUndo, onDismiss }: UndoToastProps) {
  const [focusWithin, setFocusWithin] = useState(false)
  const [hovered, setHovered] = useState(false)
  const remainingRef = useRef(UNDO_TOAST_MS)
  const timerKeyRef = useRef<string | null>(null)
  const onDismissRef = useRef(onDismiss)
  onDismissRef.current = onDismiss

  const paused = busy || focusWithin || hovered
  const timerKey = notice === null ? null : `${notice.key}:${restartKey}`

  useEffect(() => {
    if (timerKey === null) {
      timerKeyRef.current = null
      return
    }
    if (timerKeyRef.current !== timerKey) {
      timerKeyRef.current = timerKey
      remainingRef.current = UNDO_TOAST_MS
    }
    if (paused) {
      return
    }
    const startedAt = Date.now()
    const timer = window.setTimeout(() => onDismissRef.current(), remainingRef.current)
    return () => {
      window.clearTimeout(timer)
      remainingRef.current = Math.max(0, remainingRef.current - (Date.now() - startedAt))
    }
  }, [timerKey, paused])

  return (
    <div className="pointer-events-none fixed inset-x-4 top-header z-20 flex justify-center pt-2">
      <div
        data-undo-toast=""
        // Ohne Hinweis bleibt das `role="status"` eingehängt; die Fläche hat dann keine Höhe.
        className={
          notice === null
            ? 'pointer-events-auto flex w-full sm:max-w-md'
            : 'pointer-events-auto flex w-full items-center gap-3 rounded-md border border-border-control bg-elevated p-3 transition-opacity duration-150 motion-reduce:transition-none sm:max-w-md'
        }
        onFocus={() => setFocusWithin(true)}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setFocusWithin(false)
          }
        }}
        onPointerEnter={() => {
          if (
            typeof window.matchMedia === 'function' &&
            window.matchMedia(FINE_HOVER_QUERY).matches
          ) {
            setHovered(true)
          }
        }}
        onPointerLeave={() => setHovered(false)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            onDismiss()
          }
        }}
      >
        {notice !== null && (
          <div className="size-10 shrink-0 overflow-hidden rounded-md">
            <PhotoImage
              photoId={notice.photoId}
              variant="thumbnail"
              alt=""
              className="size-full object-cover"
            />
          </div>
        )}
        <div role="status" className="flex min-w-0 flex-1 flex-col">
          {notice !== null && (
            <>
              <span className="text-sm text-text-h">{notice.title}</span>
              <span className="truncate font-mono text-xs text-text">
                {notice.relativePath.split('/').pop() ?? notice.relativePath}
              </span>
            </>
          )}
        </div>
        {notice !== null &&
          (error === null ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="shrink-0"
              busy={busy}
              onClick={onUndo}
            >
              Rückgängig
            </Button>
          ) : (
            <p className="shrink-0 basis-1/2 text-sm text-danger-text">{error}</p>
          ))}
      </div>
    </div>
  )
}
