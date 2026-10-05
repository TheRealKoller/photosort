import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { RatingStatus } from '../api/types'
import { useRevealOnDemand } from '../hooks/useRevealOnDemand'
import { cn } from '../lib/utils'
import { RATING_STATUS_LABELS } from '../utils/ratingLabels'
import { Icon } from './ui/icon'

/**
 * Die Kachel der Fotouebersicht - eine eigene Komponente NEBEN `PhotoCard`, nicht deren
 * Auspraegung: Diese Kachel ist als Ganzes EIN Link auf das Foto, ohne Knopfzeile und ohne
 * Zustandswort; die Kuratierungskachel traegt Handgriffe und eine Bildflaeche, die nur die
 * Grossansicht oeffnet.
 *
 * GENAU ZWEI ZEICHEN IM RUHEZUSTAND, nie ein drittes: ein Stern und ein Punkt. Der Info-Ausloeser
 * der Bewertungsdetails und der Motiv-Marker haben in dieser Ansicht keinen Platz und entfallen
 * ersatzlos.
 *
 * DIE KACHEL IST EIN `<li>` MIT GENAU EINEM LINK AUF DAS FOTO. Daran haengt der Auffinde-Ausdruck
 * des E2E-Pruefstacks (`listitem` mit `a[href*="/photos/"]`) und damit vier Specs; ein zweiter
 * Foto-Link oder ein anderes Wurzelelement bricht sie alle gleichzeitig.
 */
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
  const { visible: detailsVisible, handlers, consumeSuppressedClick } = useRevealOnDemand()

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

  return (
    <li
      // Auflage S6: Das gerechnete Mass geht als ZAHL in eine gewoehnliche CSS-Eigenschaft - nie
      // als zusammengesetzte Zeichenkette, nie als Custom-Property, nie in einen `url()`-Kontext.
      style={{ width, height }}
      className="relative overflow-hidden rounded-md"
      {...handlers}
    >
      <Link
        to={to}
        onClick={(event) => void consumeSuppressedClick(event)}
        className="block size-full rounded-md"
      >
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
