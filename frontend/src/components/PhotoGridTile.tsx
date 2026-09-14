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
  /** DAUERHAFT sichtbare Aktionen am unteren Rand. Ausschliesslich der Gate-Modus setzt sie; in
   * der normalen Uebersicht gibt es sie gar nicht (AK3/AK12). */
  actions?: ReactNode
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
  actions,
}: PhotoGridTileProps) {
  const [detailsVisible, setDetailsVisible] = useState(false)
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

  // Die eigene Entscheidung hat immer Vorrang; ein Vorschlag erscheint nur, solange keine
  // vorliegt. Der Server sichert das bereits zu - hier wird es trotzdem geprueft, statt sich
  // blind darauf zu verlassen (dieselbe Anzeigeregel wie in der Detailansicht).
  const dotStatus = status ?? suggestedStatus
  const dotShape = status !== null ? 'filled' : 'ring'
  const rejected = status === 'rejected'
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
      setDetailsVisible(true)
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
      onPointerEnter={hoverCapable ? () => setDetailsVisible(true) : undefined}
      onPointerLeave={() => {
        clearTimer()
        setDetailsVisible(false)
      }}
      onFocus={() => setDetailsVisible(true)}
      onBlur={() => setDetailsVisible(false)}
    >
      <Link to={to} onClick={handleClick} className="block size-full rounded-md">
        {/* Der Ruecktritt einer verworfenen Aufnahme liegt AUSSCHLIESSLICH auf der Bildflaeche
            (AK6). Am Kachelkoerper druecke dieselbe Utility die beiden Zeichen unter die
            Kontrastschwelle; ueber einer Bildflaeche ist ein Kontrast mit Deckkraft statisch
            ohnehin nicht nachrechenbar. Die Zeichen sind deshalb GESCHWISTER dieses Elements. */}
        <div
          data-dimmed={rejected ? 'true' : undefined}
          className={cn('size-full overflow-hidden rounded-md', rejected && 'opacity-40')}
        >
          {image}
        </div>
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

      {(detailsVisible || actions !== undefined) && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col">
          {detailsVisible && (
            <p
              style={{ maxHeight: Math.round(height / DETAILS_HEIGHT_SHARE) }}
              className="overflow-hidden truncate bg-overlay px-2 py-1 font-mono text-xs text-text-h"
            >
              {fileName}
            </p>
          )}
          {actions !== undefined && (
            <div className="pointer-events-auto flex flex-wrap gap-2 bg-overlay p-1">{actions}</div>
          )}
        </div>
      )}
    </li>
  )
}
