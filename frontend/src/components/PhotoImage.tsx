import { useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import { fetchPhotoImageBlobUrl } from '../api/photos'
import type { PhotoVariant } from '../api/types'
import { Skeleton } from './ui/skeleton'
import { cn } from '../lib/utils'

interface PhotoImageProps {
  photoId: number
  variant: PhotoVariant
  alt: string
  className?: string
}

type PhotoImageState =
  | { status: 'loading' }
  | { status: 'ready'; url: string }
  | { status: 'placeholder' }
  | { status: 'error' }

/**
 * Laedt ein Foto-Bild authentifiziert (siehe api/client.ts::apiFetchBlob) und deckt die vier in
 * specs/architecture/0004-design-system.md vorgesehenen Zustaende ab: Ladend, fertig geladen,
 * Platzhalter (Backend liefert 404, weil der Worker die Variante noch nicht erzeugt hat) und
 * Fehler (jede andere Fehlerantwort). Object-URLs werden beim Unmount bzw. bei
 * photoId/variant-Wechsel wieder freigegeben, um keine Blob-URLs zu leaken.
 */
export function PhotoImage({ photoId, variant, alt, className }: PhotoImageProps) {
  const [state, setState] = useState<PhotoImageState>({ status: 'loading' })

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
          setState({ status: 'error' })
        }
      })

    return () => {
      cancelled = true
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [photoId, variant])

  if (state.status === 'loading') {
    return (
      <div className={className} role="status" aria-label={`${alt} wird geladen…`}>
        <Skeleton className="size-full" />
      </div>
    )
  }

  if (state.status === 'placeholder') {
    return (
      <div
        // Platzhalterflaeche: dekorative Flaeche unmittelbar auf dem Grund. `bg-border/60` war
        // doppelt problematisch - unsichtbar (1.45:1 vor der Abdunklung) und ueber den
        // Deckkraft-Modifikator statisch nicht nachrechenbar (Spec 0321).
        className={cn('flex items-center justify-center rounded-md bg-separator text-xs text-text', className)}
        role="img"
        aria-label={`${alt}: wird noch verarbeitet`}
      />
    )
  }

  if (state.status === 'error') {
    return (
      <div
        className={cn(
          'flex items-center justify-center rounded-md border border-status-failed/40 bg-status-failed/10 px-2 text-center text-xs text-text-h',
          className
        )}
        role="alert"
      >
        Bild konnte nicht geladen werden.
      </div>
    )
  }

  return <img className={cn('rounded-md object-cover', className)} src={state.url} alt={alt} />
}
