import { useCallback, useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import { useLocation, useNavigate } from 'react-router'

/**
 * Liest die Id der offenen Grossansicht aus dem Verlaufszustand.
 *
 * SICHERHEIT (Auflage S1 der Spec 0531): Der Verlaufszustand ueberlebt Reload,
 * Sitzungswiederherstellung und App-Updates; seine Form ist deshalb eine nicht vertrauenswuerdige
 * Eingabe. Gelesen wird ohne `as`-Cast, und nur eine sichere Ganzzahl gilt. Die Id wird danach
 * ausschliesslich in der geladenen Liste NACHGESCHLAGEN - jede weitere Verwendung nimmt `photo.id`
 * des gefundenen Objekts, nie diesen Rohwert. Ein ungeprueft in `/photos/${…}/image` eingesetzter
 * Wert machte aus dem Bildabruf eine GET-Anfrage mit Bearer-Token an einen beliebigen API-Pfad.
 */
function readOpenPhotoId(state: unknown): number | null {
  if (typeof state !== 'object' || state === null || !('grossansicht' in state)) {
    return null
  }
  const value = state.grossansicht
  return typeof value === 'number' && Number.isSafeInteger(value) ? value : null
}

interface CurationLightboxOptions<T extends { id: number }> {
  /** Die GELADENE Liste der Seite; `undefined`, solange sie laedt (oder ohne Daten scheiterte). */
  items: readonly T[] | undefined
  /** Fokusziel, wenn der Ausloeser des geschlossenen Fotos nicht (mehr) im Dokument steht. */
  headingRef: RefObject<HTMLElement | null>
}

interface CurationLightbox<T> {
  openPhotoId: number | null
  /** Das offene Foto aus der geladenen Liste; `undefined`, wenn keines offen ist oder die Id
   * dort nicht vorkommt. */
  photo: T | undefined
  open: (photoId: number) => void
  close: () => void
  /** Callback-Ref fuer den Ausloeser eines Fotos - Ziel der Fokus-Rueckgabe. */
  triggerRef: (photoId: number) => (element: HTMLElement | null) => void
}

/**
 * Oeffnen, Schliessen und Fokus-Rueckgabe der Grossansicht in der Kuratierung.
 *
 * DER ZUSTAND IST DER VERLAUFSEINTRAG: `open` legt auf derselben URL einen Eintrag mit
 * `state: { grossansicht: <id> }` an - die Seite bleibt montiert, ihr lokaler Zustand und der
 * Query-Cache bleiben unberuehrt, und Browser-Zurueck schliesst ohne eigenen Code. Der Zustand
 * traegt NUR die Id (Auflage S2): Der Browser legt ihn in seiner Sitzungswiederherstellung auf der
 * Platte ab, ueber Abmelden hinaus; Dateinamen oder Pfade laegen dort ausserhalb jeder Bereinigung.
 *
 * `close` verhaelt sich wie Browser-Zurueck: Einen in dieser Montierung angelegten Eintrag verlaesst
 * es mit einem Schritt zurueck, einen aus Reload oder Vorwaerts-Navigation ersetzt es durch einen
 * ohne Zustand. So bleibt kein „offener" Eintrag zurueck, den ein spaeteres Zurueck wieder oeffnete.
 *
 * INVARIANTE: `close` wirkt je Verlaufseintrag hoechstens einmal. Ein zweites Esc oder ein
 * Doppelklick vor dem asynchronen `popstate` ginge sonst zwei Eintraege zurueck und verliesse die
 * Kuratierung. Der Riegel sitzt hier, weil das Grundelement `onClose` bei jedem Esc ruft.
 *
 * Steht das offene Foto nicht in der GELADENEN Liste (verschwunden oder nach Reload unbekannt),
 * schliesst der Hook von selbst; solange die Liste laedt, nicht.
 *
 * Wechselt die offene Id auf `null` - ueber jeden Schliessweg, auch Browser-Zurueck -, bekommt der
 * registrierte Ausloeser den Fokus, ohne dass die Seite scrollt; fehlt er, die Seitenueberschrift.
 * Die Rueckgabe haengt bewusst nicht am vorher fokussierten Element: Safari fokussiert einen
 * angeklickten Button nicht, und nach einem Reload gibt es keines.
 */
export function useCurationLightbox<T extends { id: number }>({
  items,
  headingRef,
}: CurationLightboxOptions<T>): CurationLightbox<T> {
  const location = useLocation()
  const navigate = useNavigate()
  const openPhotoId = readOpenPhotoId(location.state)
  const photo = openPhotoId === null ? undefined : items?.find((item) => item.id === openPhotoId)

  const openingRef = useRef(false)
  const ownEntryKeysRef = useRef(new Set<string>())
  const closedEntryKeyRef = useRef<string | null>(null)
  const triggersRef = useRef(new Map<number, HTMLElement>())
  const triggerCallbacksRef = useRef(new Map<number, (element: HTMLElement | null) => void>())
  const previousOpenPhotoIdRef = useRef<number | null>(openPhotoId)

  useEffect(() => {
    closedEntryKeyRef.current = null
    if (openingRef.current) {
      openingRef.current = false
      ownEntryKeysRef.current.add(location.key)
    }
  }, [location.key])

  const open = useCallback(
    (photoId: number) => {
      openingRef.current = true
      navigate(
        { pathname: location.pathname, search: location.search },
        { state: { grossansicht: photoId } },
      )
    },
    [navigate, location.pathname, location.search],
  )

  const close = useCallback(() => {
    if (openPhotoId === null || closedEntryKeyRef.current === location.key) {
      return
    }
    closedEntryKeyRef.current = location.key
    if (ownEntryKeysRef.current.has(location.key)) {
      void navigate(-1)
    } else {
      navigate(
        { pathname: location.pathname, search: location.search },
        { replace: true, state: null },
      )
    }
  }, [openPhotoId, navigate, location.key, location.pathname, location.search])

  useEffect(() => {
    if (openPhotoId !== null && items !== undefined && photo === undefined) {
      close()
    }
  }, [openPhotoId, items, photo, close])

  // Laeuft NACH der Aufraeumphase der Grossansicht (React fuehrt alle Aufraeumfunktionen vor den
  // neuen Effekten aus) und setzt sich damit gegen jede andere Fokusnahme beim Schliessen durch.
  useEffect(() => {
    const previous = previousOpenPhotoIdRef.current
    previousOpenPhotoIdRef.current = openPhotoId
    if (previous === null || openPhotoId !== null) {
      return
    }
    const trigger = triggersRef.current.get(previous)
    const target = trigger?.isConnected ? trigger : headingRef.current
    target?.focus({ preventScroll: true })
  }, [openPhotoId, headingRef])

  const triggerRef = useCallback((photoId: number) => {
    let callback = triggerCallbacksRef.current.get(photoId)
    if (callback === undefined) {
      callback = (element: HTMLElement | null) => {
        if (element === null) {
          triggersRef.current.delete(photoId)
        } else {
          triggersRef.current.set(photoId, element)
        }
      }
      triggerCallbacksRef.current.set(photoId, callback)
    }
    return callback
  }, [])

  return { openPhotoId, photo, open, close, triggerRef }
}
