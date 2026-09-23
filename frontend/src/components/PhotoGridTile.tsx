import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { Link } from 'react-router'

import type { RatingStatus } from '../api/types'
import { cn } from '../lib/utils'
import { RATING_STATUS_LABELS } from '../utils/ratingLabels'
import { Icon } from './ui/icon'

/**
 * Die Kachel der Fotouebersicht - eine eigene Komponente NEBEN `PhotoCard`, nicht deren
 * Auspraegung (ADR 0110 Punkt 5). Die beiden teilen nichts, was eine Prop trennen koennte: Die
 * Fotokarte ist ein Kartenkoerper mit fester quadratischer Bildflaeche, sichtbarer Statuszeile und
 * Fusszeile; diese Kachel ist eine Bildflaeche im EIGENEN Seitenverhaeltnis, ohne Koerper, ohne
 * Fusszeile, mit zwei Zeichen in der Bildecke und einer erst auf Anforderung eingeblendeten Zeile.
 *
 * GENAU ZWEI ZEICHEN IM RUHEZUSTAND, nie ein drittes: ein Stern und ein Punkt. Der Info-Ausloeser
 * der Bewertungsdetails und der Motiv-Marker haben in dieser Ansicht keinen Platz und entfallen
 * ersatzlos.
 *
 * DIE KACHEL IST EIN `<li>` MIT GENAU EINEM LINK AUF DAS FOTO. Daran haengt der Auffinde-Ausdruck
 * des E2E-Pruefstacks (`listitem` mit `a[href*="/photos/"]`) und damit vier Specs; ein zweiter
 * Foto-Link oder ein anderes Wurzelelement bricht sie alle gleichzeitig.
 */

/** Ab dieser Druckdauer erscheint die Angabenzeile, statt zu navigieren (AK8). */
export const LONG_PRESS_MS = 500

/** Ein Geraet mit feinem Zeiger und Hover-Faehigkeit loest die Zeile durch Ueberfahren aus. */
const HOVER_QUERY = '(hover: hover) and (pointer: fine)'

/**
 * Die Angabenzeile ueberdeckt hoechstens ein Viertel der Bildhoehe (AK7). Als gerechnete ZAHL in
 * einer gewoehnlichen CSS-Eigenschaft (Auflage S6), nicht als willkuerliche Klasse: Der
 * Vertragstest weist `max-h-[25%]` zurueck, und eine Custom-Property naehme anders als eine
 * gewoehnliche Eigenschaft nahezu beliebige Token-Folgen auf.
 */
const DETAILS_HEIGHT_SHARE = 4

export interface PhotoGridTileProps {
  /** Ziel des einen Kachel-Links. */
  to: string
  /** Vollstaendiger Pfad des Fotos. Sichtbar wird ausschliesslich der Basisname, und nur auf
   * Anforderung. */
  relativePath: string
  /** Die EIGENE Albumentscheidung; `null` heisst "keine getroffen". */
  status: RatingStatus | null
  /** Der noch nicht bestaetigte Vorschlag; `null` heisst "keiner offen". Die eigene Entscheidung
   * hat immer Vorrang - liegt eine vor, bleibt der Vorschlag ungezeigt. */
  suggestedStatus: RatingStatus | null
  /** Das EIGENE Favoriten-Kennzeichen, nie das einer anderen Person. */
  favorite: boolean
  /** Die gerechnete Breite und Hoehe dieser Kachel in ganzen Pixeln (`utils/justifiedRows.ts`). */
  width: number
  height: number
  /** Inhalt der Bildflaeche - `PhotoImage` oder ein Platzhalter. */
  image: ReactNode
}

/** Die Farbe des Punktes - in BEIDEN Formen dieselbe, sodass auch bei einem Vorschlag erkennbar
 * bleibt, WOFUER vorgeschlagen wird. */
const DOT_COLOR: Record<RatingStatus, string> = {
  album_worthy: 'border-accent-2',
  rejected: 'border-danger',
}
const DOT_FILL: Record<RatingStatus, string> = {
  album_worthy: 'bg-accent-2',
  rejected: 'bg-danger',
}

export function PhotoGridTile({
  to,
  relativePath,
  status,
  suggestedStatus,
  favorite,
  width,
  height,
  image,
}: PhotoGridTileProps) {
  /*
   * WOHER die Zeile kam, nicht nur DASS sie da ist. Die drei Auslöser haben verschiedene
   * Gegenstücke, und ein gemeinsames `boolean` könnte sie nicht auseinanderhalten:
   *
   * Ein TOUCH-Pointer wird nach `pointerup` vom Browser ZERSTÖRT und feuert dabei `pointerleave`,
   * ohne Zutun des Nutzers. Blendete das Verlassen bedingungslos aus, verschwände die eben per
   * langem Druck eingeblendete Zeile im selben Moment, in dem der Finger sie freigibt - der
   * Dateiname wäre am Telefon faktisch nie zu sehen.
   */
  const [detailsSource, setDetailsSource] = useState<'hover' | 'focus' | 'press' | null>(null)
  const detailsVisible = detailsSource !== null
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const suppressClickRef = useRef(false)

  // Einmal beim ersten Rendern gelesen: Die Geraeteklasse wechselt waehrend einer Sitzung nicht,
  // und ein Abonnement je Kachel waere bei zweihundert Kacheln zweihundert Abonnements.
  const hoverCapable = useMemo(
    () =>
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia(HOVER_QUERY).matches,
    [],
  )

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => clearTimer, [clearTimer])

  /*
   * Das Gegenstück zum langen Druck: Eine so eingeblendete Zeile schließt beim nächsten Druck
   * IRGENDWO (andere Kachel, Seitengrund, dieselbe Kachel erneut) oder beim Rollen. Am
   * Zeigegerät übernimmt das Verlassen der Kachel diese Rolle, am Telefon gibt es das nicht.
   *
   * `capture: true` - ein `pointerdown` auf einem Bedienelement, das `stopPropagation` ruft,
   * erreichte die Blasenphase am Dokument sonst nie, und die Zeile bliebe stehen.
   * Die Rücknahme hängt am Zustand selbst: Ohne eingeblendete Zeile lauscht nichts.
   */
  useEffect(() => {
    if (detailsSource !== 'press') {
      return undefined
    }
    const schliessen = (): void => setDetailsSource(null)
    document.addEventListener('pointerdown', schliessen, { capture: true })
    window.addEventListener('scroll', schliessen, { passive: true })
    return () => {
      document.removeEventListener('pointerdown', schliessen, { capture: true })
      window.removeEventListener('scroll', schliessen)
    }
  }, [detailsSource])

  // Die eigene Entscheidung hat immer Vorrang; ein Vorschlag erscheint nur, solange keine
  // vorliegt. Der Server sichert das bereits zu - hier wird es trotzdem geprueft, statt sich
  // blind darauf zu verlassen (dieselbe Anzeigeregel wie in der Detailansicht).
  const dotStatus = status ?? suggestedStatus
  const dotShape = status !== null ? 'filled' : 'ring'
  const fileName = relativePath.split('/').pop() ?? relativePath

  const stateWords = [
    favorite ? 'Favorit' : null,
    status !== null ? RATING_STATUS_LABELS[status] : null,
    status === null && suggestedStatus !== null
      ? `${RATING_STATUS_LABELS[suggestedStatus]} vorgeschlagen`
      : null,
  ].filter((word): word is string => word !== null)

  function handlePointerDown(): void {
    if (hoverCapable) {
      return
    }
    clearTimer()
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      // Der lange Druck blendet die Zeile ein und navigiert AUSDRUECKLICH NICHT. Ohne diesen
      // Merker folgte der Browser unmittelbar danach dem Link, und die eben eingeblendete Zeile
      // waere nie zu sehen.
      suppressClickRef.current = true
      setDetailsSource('press')
    }, LONG_PRESS_MS)
  }

  function handleClick(event: MouseEvent<HTMLAnchorElement>): void {
    if (suppressClickRef.current) {
      suppressClickRef.current = false
      event.preventDefault()
    }
  }

  return (
    <li
      // Auflage S6: Das gerechnete Mass geht als ZAHL in eine gewoehnliche CSS-Eigenschaft - nie
      // als zusammengesetzte Zeichenkette, nie als Custom-Property, nie in einen `url()`-Kontext.
      style={{ width, height }}
      className="relative overflow-hidden rounded-md"
      onPointerDown={handlePointerDown}
      onPointerUp={clearTimer}
      onPointerCancel={clearTimer}
      onPointerEnter={hoverCapable ? () => setDetailsSource('hover') : undefined}
      onPointerLeave={() => {
        // Der laufende Druck wird IMMER abgebrochen - wer den Finger von der Kachel zieht, wollte
        // die Zeile nicht. Ausgeblendet wird dagegen nur, was durch Ueberfahren kam: Nach dem
        // Loslassen eines Touch-Pointers feuert der Browser dieses Ereignis von selbst.
        clearTimer()
        setDetailsSource((quelle) => (quelle === 'hover' ? null : quelle))
      }}
      onFocus={() => setDetailsSource('focus')}
      onBlur={() => setDetailsSource((quelle) => (quelle === 'focus' ? null : quelle))}
    >
      <Link to={to} onClick={handleClick} className="block size-full rounded-md">
        {/* JEDE AUFNAHME STEHT IN VOLLER HELLIGKEIT, auch die verworfene (ADR 0112) - eine
            gedaempfte Bildflaeche verfaelscht die Beurteilung des Motivs. Den Zustand tragen
            allein die beiden Zeichen und die Zustandswoerter, beide ausserhalb dieses Elements.

            DAS ELEMENT SELBST BLEIBT: Es traegt Beschnitt und Rundung der Bildflaeche - ohne es
            liefe das Bild ueber die Kachelrundung hinaus, ohne dass eine Pruefung anschluege. */}
        <div className="size-full overflow-hidden rounded-md">{image}</div>
        {/* Die Bedeutung der beiden Zeichen zusaetzlich als UNSICHTBARER Text. Der Stern und der
            Punkt ersetzen das bisherige beschriftete Kennzeichen; ohne diesen Text verloere die
            Ansicht ihre Aussage fuer Bildschirmleser. Der Dateiname steht hier bewusst NICHT - er
            ist im Ruhezustand nicht im Dokument (AK7) und erreicht den Bildschirmleser ueber das
            `alt` des Bildes. */}
        {stateWords.length > 0 && <span className="sr-only">{stateWords.join(', ')}</span>}
      </Link>

      {(favorite || dotStatus !== null) && (
        // Die Zeichen stehen auf der UNDURCHSICHTIGEN Flaeche `--overlay`, nie auf einer
        // teildeckenden: Ueber einer Bildflaeche ist ein Kontrast mit Deckkraft statisch nicht
        // nachrechenbar, und der Vertragstest weist Deckkraft-Modifikatoren auf Farb-Utilities
        // zurueck.
        <span className="pointer-events-none absolute left-1 top-1 flex items-center gap-1 rounded-sm bg-overlay p-1">
          {favorite && (
            <span data-mark="favorite" className="flex">
              <Icon name="star" size={14} className="text-accent" />
            </span>
          )}
          {dotStatus !== null && (
            <span
              data-mark="album"
              data-mark-shape={dotShape}
              data-mark-status={dotStatus}
              className={cn(
                'block size-3 rounded-full border-2',
                DOT_COLOR[dotStatus],
                dotShape === 'filled' && DOT_FILL[dotStatus],
              )}
            />
          )}
        </span>
      )}

      {detailsVisible && (
        <p
          style={{ maxHeight: Math.round(height / DETAILS_HEIGHT_SHARE) }}
          className="pointer-events-none absolute inset-x-0 bottom-0 overflow-hidden truncate bg-overlay px-2 py-1 font-mono text-xs text-text-h"
        >
          {fileName}
        </p>
      )}
    </li>
  )
}
