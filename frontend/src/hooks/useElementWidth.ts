import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Die gemessene INNENBREITE eines Elements, ueber `ResizeObserver`.
 *
 * DIE BREITE KOMMT AUS `entry.contentRect.width`, NIE AUS DEM ELEMENT. Das ist eine Bauvorgabe,
 * keine Vorliebe: In jsdom sind `clientWidth` und `getBoundingClientRect().width` konstant 0. Ein
 * Raster, das seine Breite aus dem Element liest, ist im Komponententest nicht pruefbar - und die
 * Zusagen des justierten Rasters haengen alle an dieser einen Zahl.
 *
 * Vor der ersten Messung und in einer Umgebung ohne `ResizeObserver` ist die Breite `0`. Der
 * Aufrufer behandelt das als "noch nicht gemessen" und zeichnet kein Raster - `justifiedRows`
 * liefert dafuer eine leere Liste statt `NaN`.
 *
 * Rueckgabe ist ein REF-RUECKRUF, kein `RefObject`: Ein Objekt-Ref traegt seinen Knoten erst nach
 * dem Rendern, und ein Effekt, der ihn ausliest, verpasst einen Knotenwechsel ohne
 * Abhaengigkeitswechsel stillschweigend.
 */
export function useElementWidth<T extends Element>(): {
  ref: (node: T | null) => void
  width: number
} {
  const [width, setWidth] = useState(0)
  const observerRef = useRef<ResizeObserver | null>(null)

  const ref = useCallback((node: T | null) => {
    observerRef.current?.disconnect()
    observerRef.current = null
    if (node === null || typeof ResizeObserver === 'undefined') {
      return
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry === undefined) {
        return
      }
      setWidth(entry.contentRect.width)
    })
    observer.observe(node)
    observerRef.current = observer
  }, [])

  useEffect(
    () => () => {
      observerRef.current?.disconnect()
      observerRef.current = null
    },
    [],
  )

  return { ref, width }
}
