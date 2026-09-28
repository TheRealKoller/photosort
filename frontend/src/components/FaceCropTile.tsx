import { useEffect, useState } from 'react'

import { cn } from '../lib/utils'

const UNAVAILABLE = 'Ausschnitt nicht verfügbar'

/** Ein Gesichtsausschnitt als Blob oder base64-JPEG aus einer Listenantwort. */
export type FaceCropSource = Blob | string

function toBlob(source: FaceCropSource): Blob | null {
  if (typeof source !== 'string') {
    return source
  }
  try {
    const binary = atob(source)
    const bytes = new Uint8Array(binary.length)
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index)
    }
    return new Blob([bytes], { type: 'image/jpeg' })
  } catch {
    return null
  }
}

/**
 * Macht aus einem Ausschnitt eine Blob-URL und gibt sie frei, sobald die Quelle wechselt oder die
 * Kachel aushängt. SICHERHEIT (S6): Ein Ausschnitt steht nie als `data:`-URL im DOM, und keine
 * URL überlebt ihre Kachel. `failed` heißt: nicht darstellbar.
 */
export function useFaceCropUrl(source: FaceCropSource | undefined): string | 'failed' | undefined {
  const [url, setUrl] = useState<string | 'failed' | undefined>(undefined)

  useEffect(() => {
    if (source === undefined) {
      setUrl(undefined)
      return
    }
    const blob = toBlob(source)
    if (blob === null) {
      setUrl('failed')
      return
    }
    const created = URL.createObjectURL(blob)
    setUrl(created)
    return () => URL.revokeObjectURL(created)
  }, [source])

  return url
}

interface SelectableFaceCropTileProps {
  source: FaceCropSource | undefined
  failed: boolean
  label: string
  pressed: boolean
  disabled: boolean
  onSelect: () => void
}

/** Die wählbare Ausprägung (64 px) der Gesichterwahl in der Detailansicht. */
export function SelectableFaceCropTile({
  source,
  failed,
  label,
  pressed,
  disabled,
  onSelect,
}: SelectableFaceCropTileProps) {
  const url = useFaceCropUrl(failed ? undefined : source)
  const unavailable = failed || url === 'failed'
  return (
    <button
      type="button"
      className={cn(
        'size-16 overflow-hidden rounded-md border-2',
        pressed ? 'border-accent' : 'border-border-control',
        unavailable && 'bg-separator',
      )}
      aria-label={unavailable ? `${label} – ${UNAVAILABLE}` : label}
      aria-pressed={pressed}
      aria-disabled={unavailable || undefined}
      disabled={disabled}
      onClick={unavailable ? undefined : onSelect}
    >
      {url !== undefined && url !== 'failed' && (
        <img src={url} alt="" className="size-full object-cover" />
      )}
    </button>
  )
}

/**
 * Die statische Ausprägung (96 px) für Listen, in denen der Ausschnitt Inhalt und nicht Wahl ist:
 * kein Auswahlzustand, keine Akzentkante, nicht gedämpft. Lässt er sich nicht darstellen, bleibt
 * eine Platzhalterfläche `bg-overlay` stehen.
 */
export function StaticFaceCropTile({ source, alt }: { source: FaceCropSource; alt: string }) {
  const url = useFaceCropUrl(source)
  const [broken, setBroken] = useState(false)
  if (url === 'failed' || broken) {
    return (
      <div role="img" aria-label={UNAVAILABLE} className="size-24 shrink-0 rounded-md bg-overlay" />
    )
  }
  return (
    <div className="size-24 shrink-0 overflow-hidden rounded-md bg-overlay">
      {url !== undefined && (
        <img
          src={url}
          alt={alt}
          className="size-24 rounded-md object-cover"
          onError={() => setBroken(true)}
        />
      )}
    </div>
  )
}
