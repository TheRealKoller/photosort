import { useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode, Ref } from 'react'

import { useRevealOnDemand } from '../hooks/useRevealOnDemand'
import { cn } from '../lib/utils'
import { Alert } from './ui/alert'

export interface PhotoCardProps {
  /** Die gerechnete Kachelbreite in Pixeln (`useJustifiedRows`). */
  width: number
  /** Die gerechnete Hoehe der Bildflaeche in Pixeln - die Hoehe der Reihe. */
  imageHeight: number
  /** Macht die Bildflaeche zu einer Schaltflaeche mit genau diesem einen Aktivierungsweg. Fehlt
   * die Prop, ist die Bildflaeche weder Link noch Schaltflaeche. */
  onImageActivate?: () => void
  /** Zugaenglicher Name der Bildflaeche als Schaltflaeche, z. B. „Großansicht: {Pfad}". */
  imageTriggerLabel?: string
  imageTriggerRef?: Ref<HTMLButtonElement>
  /** Vollstaendiger Pfad des Fotos. Sichtbar wird ausschliesslich der Basisname, in der Leiste. */
  relativePath: string
  /** Gestrichen bzw. herausgenommen: Der Dateiname in der Leiste ist durchgestrichen. */
  setAside?: boolean
  /** Bezugskachel eines offenen Alternativen-Bands: anliegender Akzentring um die Bildflaeche. */
  anchored?: boolean
  /** Inhalt der Bildflaeche - `PhotoImage` oder ein Platzhalter, eingepasst (`object-contain`). */
  image: ReactNode
  /** Das Zustandszeichen oben links in der Bildecke (`AlbumStateBadge`). */
  stateMark?: ReactNode
  /** Angaben der Leiste VOR dem Dateinamen (Grund, Albumtauglichkeit). */
  details?: ReactNode
  /** Die Knopfzeile: erster Knopf links, zweiter rechts, nie umbrochen. */
  actions: ReactNode
  /** Grund eines gescheiterten Handgriffs an dieser Kachel. */
  error?: string | null
  /** Unter der Knopfzeile (Haltungszeilen der Endauswahl). */
  footer?: ReactNode
}

/**
 * DIE Kachel der Kuratierung - Album-Entwurf, Gestrichen-Zeile, Alternativen, Hinzufuegen-Panel
 * und Endauswahl. Aufbau, zugleich DOM- und Fokusreihenfolge: Bildflaeche (Ausloeser der
 * Grossansicht), Zustandszeichen, Leiste bei Bedarf, Knopfzeile, Fehlermeldung, Fusszeile.
 *
 * DIE BILDFLAECHE HAT DAS SEITENVERHAELTNIS DES FOTOS und keine Polsterung, Kartenflaeche oder
 * Rahmen. Breite und Hoehe kommen gerechnet von aussen; das Bild wird eingepasst, nie
 * beschnitten. Sie steht IMMER in voller Helligkeit, auch gestrichen oder herausgenommen: eine
 * gedaempfte Flaeche verfaelscht die Beurteilung des Motivs.
 *
 * ZUSTANDSZEICHEN UND LEISTE SIND GESCHWISTER DER BILDFLAECHE, NIE IHRE KINDER: Die Bildflaeche
 * beschneidet (`overflow-hidden`). Die Knopfzeile liegt ausserhalb jedes beschneidenden
 * Containers, sonst wuerde ihre aufgespannte Trefferflaeche still abgeschnitten.
 *
 * DIE LEISTE STEHT IMMER IM DOM, im Ruhezustand `sr-only`: Grund und Dateiname bleiben fuer
 * Bildschirmleser im Lesefluss zwischen Zustandszeichen und Knoepfen. Sichtbar wird sie beim
 * Ueberfahren (feiner Zeiger), bei Fokus auf irgendeinem Bedienelement der Kachel und nach einem
 * langen Druck. Der lange Druck aktiviert nichts - weder die Grossansicht noch einen Knopf.
 *
 * SICHERHEIT: Der Dateiname stammt aus dem WebDAV-Walk der OpenCloud und ist extern entstandener
 * Text. Er steht ausschliesslich als React-Textknoten - nie ueber `dangerouslySetInnerHTML`, nie in
 * `href`, `src`, `style` oder `url()`. Das Session-Token liegt in `localStorage`; ein
 * eingeschleustes Skript laese es unmittelbar aus. Die Inline-Stile tragen nur gerechnete Zahlen.
 */
export function PhotoCard({
  width,
  imageHeight,
  onImageActivate,
  imageTriggerLabel,
  imageTriggerRef,
  relativePath,
  setAside = false,
  anchored = false,
  image,
  stateMark,
  details,
  actions,
  error = null,
  footer,
}: PhotoCardProps) {
  const { visible, handlers, consumeSuppressedClick } = useRevealOnDemand()
  const fileName = relativePath.split('/').pop() ?? relativePath
  const stripRef = useRef<HTMLDivElement>(null)
  const [overflowing, setOverflowing] = useState(false)
  useLayoutEffect(() => {
    const strip = stripRef.current
    setOverflowing(visible && strip !== null && strip.scrollHeight > strip.clientHeight)
  }, [visible, imageHeight, width])
  const imageAreaClassName = cn(
    'block size-full overflow-hidden rounded-md',
    anchored && 'ring-2 ring-accent',
  )

  return (
    <li
      style={{ width }}
      data-anchored={anchored ? 'true' : undefined}
      className="flex flex-col"
      {...handlers}
      onClickCapture={(event) => {
        if (consumeSuppressedClick(event)) {
          event.stopPropagation()
        }
      }}
    >
      <div className="relative" style={{ height: imageHeight }}>
        {onImageActivate === undefined ? (
          <div className={imageAreaClassName}>{image}</div>
        ) : (
          <button
            ref={imageTriggerRef}
            type="button"
            aria-label={imageTriggerLabel}
            onClick={onImageActivate}
            className={cn(imageAreaClassName, 'cursor-zoom-in')}
          >
            {image}
          </button>
        )}
        {stateMark !== undefined && <div className="absolute top-1 left-1">{stateMark}</div>}
        {/* Hoechstens so hoch wie das Bild; was darueber hinausginge, scrollt SENKRECHT in der
            Leiste, statt abgeschnitten zu werden - der Grund bleibt vollstaendig erreichbar. Nur
            eine tatsaechlich ueberlaufende, sichtbare Leiste wird Tab-Stopp: So erreicht die
            Tastatur den Rest, und die gewohnte Folge Bild → Knoepfe bleibt sonst unveraendert. */}
        <div
          ref={stripRef}
          data-tile-details=""
          data-visible={visible ? 'true' : undefined}
          tabIndex={overflowing ? 0 : undefined}
          style={{ maxHeight: imageHeight }}
          className={
            visible
              ? 'absolute inset-x-0 bottom-0 flex flex-col gap-1 overflow-y-auto rounded-b-md bg-overlay px-2 py-1 text-xs text-text-h'
              : 'sr-only'
          }
        >
          {details}
          <p
            data-struck={setAside ? 'true' : undefined}
            className={cn(
              'font-mono break-all',
              setAside ? 'text-text-muted line-through' : 'text-text',
            )}
          >
            {fileName}
          </p>
        </div>
      </div>
      <div className="mt-2 flex justify-between gap-3">{actions}</div>
      {error !== null && (
        <div className="mt-2">
          <Alert>{error}</Alert>
        </div>
      )}
      {footer}
    </li>
  )
}
