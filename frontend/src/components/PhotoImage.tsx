import { useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import { fetchPhotoImageBlobUrl } from '../api/photos'
import type { PhotoVariant } from '../api/types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'
import { cn } from '../lib/utils'

interface PhotoImageProps {
  photoId: number
  variant: PhotoVariant
  alt: string
  className?: string
  /** Fehler- und Platzhalterzustand bieten „Erneut versuchen" an. Ohne die Prop bleiben beide
   * Zustaende reine Anzeige. */
  retryable?: boolean
  /** Wird nach dem Druck auf „Erneut versuchen" gerufen - die Schaltflaeche verschwindet dabei,
   * und der Aufrufer entscheidet, wohin der Fokus geht. */
  onRetry?: () => void
}

/** Beitext des wiederholbaren Fehlerzustands, wenn der Fehlschlag kein `detail` des Servers
 * traegt. */
export const IMAGE_UNAVAILABLE_TEXT = 'Das große Bild ist gerade nicht abrufbar.'

type PhotoImageState =
  | { status: 'loading' }
  | { status: 'ready'; url: string }
  | { status: 'placeholder' }
  | { status: 'error'; detail: string | null }

/**
 * Laedt ein Foto-Bild authentifiziert (siehe api/client.ts::apiFetchBlob) und deckt die vier vom
 * Design-System vorgesehenen Zustaende ab: Ladend, fertig geladen,
 * Platzhalter (Backend liefert 404, weil der Worker die Variante noch nicht erzeugt hat) und
 * Fehler (jede andere Fehlerantwort). Object-URLs werden beim Unmount bzw. bei
 * photoId/variant-Wechsel wieder freigegeben, um keine Blob-URLs zu leaken.
 */
export function PhotoImage({
  photoId,
  variant,
  alt,
  className,
  retryable = false,
  onRetry,
}: PhotoImageProps) {
  const [state, setState] = useState<PhotoImageState>({ status: 'loading' })
  // Jeder Druck auf „Erneut versuchen" erhoeht den Zaehler und startet damit den Lade-Effekt neu.
  // Es gibt keine automatische oder periodische Wiederholung.
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setState({ status: 'loading' })

    fetchPhotoImageBlobUrl(photoId, variant)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url)
          return
        }
        objectUrl = url
        setState({ status: 'ready', url })
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: 'placeholder' })
        } else {
          setState({ status: 'error', detail: error instanceof ApiError ? error.detail : null })
        }
      })

    return () => {
      cancelled = true
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [photoId, variant, attempt])

  if (state.status === 'loading') {
    return (
      <div className={className} role="status" aria-label={`${alt} wird geladen…`}>
        <Skeleton className="size-full" />
      </div>
    )
  }

  function retry(): void {
    setAttempt((current) => current + 1)
    onRetry?.()
  }

  if (state.status === 'placeholder' && retryable) {
    // Kein `role="img"` um die Schaltflaeche: Kinder von `role=img` sind praesentational, der Knopf
    // waere fuer Hilfstechnik unsichtbar. Kein `alert` und keine Fehleroptik - eine noch nicht
    // erzeugte Variante ist kein Fehler.
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-md bg-separator p-4 text-center text-sm text-text',
          className,
        )}
      >
        <p>Bild wird noch verarbeitet.</p>
        <Button type="button" variant="secondary" size="sm" onClick={retry}>
          Erneut versuchen
        </Button>
      </div>
    )
  }

  if (state.status === 'placeholder') {
    return (
      <div
        // Platzhalterflaeche: dekorative Flaeche unmittelbar auf dem Grund. `bg-border/60` war
        // doppelt problematisch - unsichtbar (1.45:1 vor der Abdunklung) und ueber den
        // Deckkraft-Modifikator statisch nicht nachrechenbar.
        className={cn(
          'flex items-center justify-center rounded-md bg-separator text-xs text-text',
          className,
        )}
        role="img"
        aria-label={`${alt}: wird noch verarbeitet`}
      />
    )
  }

  if (state.status === 'error' && retryable) {
    return (
      <div className={cn('flex items-center justify-center p-4', className)}>
        {/* `detail` des Servers ausschliesslich als React-Textknoten (Alert rendert ihn so). */}
        <Alert title="Bild konnte nicht geladen werden" onRetry={retry} className="max-w-md">
          {state.detail ?? IMAGE_UNAVAILABLE_TEXT}
        </Alert>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div
        className={cn(
          // Toast-Konstruktion des Boards (Flaeche `--elevated`, farbiger 1px-Rand) statt zweier
          // Deckkraft-Toenungen: ueber einer Deckkraft-Tinte ist der Kontrast statisch nicht
          // nachrechenbar und bliebe damit dauerhaft ungeprueft.
          'flex items-center justify-center rounded-md border border-status-failed bg-elevated px-2 text-center text-xs text-text-h',
          className,
        )}
        role="alert"
      >
        Bild konnte nicht geladen werden.
      </div>
    )
  }

  return <img className={cn('rounded-md object-cover', className)} src={state.url} alt={alt} />
}
