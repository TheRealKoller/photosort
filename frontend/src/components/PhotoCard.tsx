import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { RatingStatus } from '../api/types'
import { cn } from '../lib/utils'
import { RatingBadge } from './RatingBadge'

export interface PhotoCardProps {
  /**
   * Ziel des Kachel-Links. Fehlt es, ist die Bildflaeche KEIN Link - die Kuratierung kennt heute
   * keinen Sprung in die Detailansicht, und "es wird nichts hinzugefuegt" ist Akzeptanzkriterium.
   */
  to?: string
  /** Vollstaendiger Pfad des Fotos. Sichtbar wird ausschliesslich der Basisname. */
  relativePath: string
  /**
   * Bewertungszustand der Karte. `undefined` heisst "die Karte traegt keinen Zustand" (Vergleich
   * und Kuratierung zeigen ihn woanders bzw. gar nicht), `null` ist der Board-Zustand "neu".
   */
  status?: RatingStatus | null
  /** true fuer einen unbestaetigten automatischen Vorschlag statt einer echten Bewertung. */
  suggested?: boolean
  /** Inhalt der Bildflaeche - `PhotoImage` oder ein Platzhalter. */
  image: ReactNode
  /** Ecken-Overlay oben links (heute: `CategoryOverrideMarker`). */
  topLeft?: ReactNode
  /** Ecken-Overlay oben rechts (heute: `CriterionDetailsPopover`). */
  topRight?: ReactNode
  /** Fusszeile der Karte - Aktion oder ergaenzende Zeilen. */
  footer?: ReactNode
}

/**
 * Die Foto-Karte des Boards (specs/features/0321-dark-utility-register-ansichten.md,
 * Entscheidungen 1-5). Sie lebt GENAU EINMAL: zuvor war die Kachel in `PhotoGridPage`,
 * `CurateCategoriesPage` und `PhotoComparePage` dreimal von Hand gebaut und dreimal verschieden -
 * vier Zustaende in drei Kopien waeren dreimal derselbe Fehler gewesen.
 *
 * AUFBAU (zugleich DOM- und Fokusreihenfolge): Bildbereich mit den beiden Ecken-Overlays,
 * darunter die Statuszeile (Kennzeichen links, Dateiname rechts), darunter die Fusszeile.
 * Kennzeichen und Dateiname sind nicht fokussierbar und schieben sich damit zwischen Bild und
 * Fusszeile, ohne die Reihenfolge der Bedienelemente zu veraendern.
 *
 * DAS KENNZEICHEN SITZT IM KARTENKOERPER, NICHT IN DER BILDECKE (Entscheidung 2). Board-treu und
 * zugleich die Loesung eines echten Problems: Ein Textbadge "Album-wuerdig" ueber dem Foto braucht
 * bei 360px und zwei Spalten mehr Platz, als die Ecke hat, und die Ecke oben rechts ist fuer den
 * Info-Trigger reserviert. Damit entfaellt zugleich der `pointer-events-none`-Kniff, mit dem die
 * Badge Klicks an den darunterliegenden Link durchreichte.
 *
 * DIE ECKEN-OVERLAYS SIND GESCHWISTER DER BILDFLAECHE, NIE IHRE KINDER. Die Bildflaeche traegt
 * `overflow-hidden`; eine aufgespannte Trefferflaeche innerhalb eines beschneidenden Containers
 * wuerde still abgeschnitten.
 *
 * DER FUENFTE BOARD-ZUSTAND "AUSGEWAEHLT" WIRD NICHT GEBAUT (Entscheidung 5, von Daniel
 * zurueckgestellt): PhotoSort kennt heute keine Foto-Auswahl. Es gibt weder eine `selected`-Prop
 * noch ein `data-selected`, und es entsteht keine Vorbereitung darauf.
 */
export function PhotoCard({
  to,
  relativePath,
  status,
  suggested = false,
  image,
  topLeft,
  topRight,
  footer,
}: PhotoCardProps) {
  const isRejected = status === 'rejected'

  /*
   * AUSSORTIERT: Nur die BILDFLAECHE tritt zurueck, die Bedeutungstraeger nicht (Entscheidung 4).
   * Das Board daempft die ganze Karte auf 40 %; ADR 0055 Abweichung 7 hat das bereits abgelehnt
   * und ist bindend - Deckkraft auf einem Container mischt gegen den Seitengrund und ist statisch
   * nicht nachrechenbar (weisse Schrift bei 40 % ueber `--bg` erreicht 3.79:1, die dunkle Tinte
   * auf dem roten Badge wird praktisch unlesbar). Kennzeichen, Dateiname, die beiden Ecken-Trigger
   * und die Fusszeilen-Aktion bleiben deshalb voll deckend; der Dateiname traegt zusaetzlich die
   * Durchstreichung. Optisch tritt die Karte trotzdem zurueck, und die Zusage "ohne
   * Farbwahrnehmung erkennbar" traegt ueber Deckkraft UND Durchstreichung UND Symbol UND Text.
   *
   * Diese eine Zeile ist die einzige `opacity-`-Fundstelle der Datei und als solche im
   * Vertragstest freigegeben - ein spaeteres `opacity-40` am Kartenkoerper wuerde dort rot.
   */
  const imageAreaClassName = cn('block aspect-square overflow-hidden rounded-md', isRejected && 'opacity-40')

  // Nur der Basisname: Der Ordnerteil ist auf ~60px ohnehin unlesbar und steht bereits im `alt`
  // des Bildes sowie im `aria-label` der Fusszeilen-Aktion.
  const fileName = relativePath.split('/').pop() ?? relativePath

  return (
    <li
      data-rating-status={status === undefined ? undefined : (status ?? 'unrated')}
      // Board-Karte: Radius 12px, Flaeche `--elevated`, Rand `--border`. Die Polsterung ist am
      // Telefon bewusst 8px statt der 12px des Boards - bei 360px und zwei Spalten misst die
      // Kachel 158px, 12px Polsterung schruempfen die Bildflaeche um 16 %, und die Bildflaeche ist
      // dort die knappste Ressource der Anwendung. Ab `sm:` gilt das Board-Mass.
      className="flex flex-col gap-2 rounded-lg border border-border bg-elevated p-2 sm:p-3"
    >
      <div className="relative">
        {to === undefined ? (
          <div className={imageAreaClassName}>{image}</div>
        ) : (
          <Link to={to} className={imageAreaClassName}>
            {image}
          </Link>
        )}
        {topLeft !== undefined && <div className="absolute left-2 top-2">{topLeft}</div>}
        {topRight !== undefined && <div className="absolute right-2 top-2">{topRight}</div>}
      </div>

      <div className="flex items-center justify-between gap-2">
        {status === null && (
          // Entscheidung 3: Der Zustand "neu" traegt das WORT, nicht das neutrale "–"-Badge. Reiner
          // Text, kein `aria-label`, kein `RatingBadge` - das "–" bleibt seinen uebrigen
          // Aufrufstellen (Vergleichsansicht) vorbehalten, wo es "hat nicht bewertet" heisst.
          <span className="shrink-0 text-xs text-text-muted">Neu</span>
        )}
        {status !== undefined && status !== null && (
          <RatingBadge status={status} suggested={suggested} className="shrink-0" />
        )}
        {/* SICHERHEIT: Der Dateiname stammt aus dem WebDAV-Walk der OpenCloud und ist damit extern
            entstandener Text. Er wird ausschliesslich als regulaerer React-Textknoten gerendert -
            nie ueber `dangerouslySetInnerHTML`, und er fliesst in kein `href`, `src`, `style` oder
            `url()`. Seit ADR 0005 liegt das Session-Token in `localStorage`; ein eingeschleustes
            Skript laese es unmittelbar aus. Abgesichert in PhotoCard.test.tsx.

            `min-w-6` neben `truncate`, damit ein langes Kennzeichen den Namen nie auf null
            drueckt - sonst verschwaende auch die Durchstreichung. Eine Zeile, kein Umbruch: in
            einer Rasterzeile gleichen sich die Kartenhoehen aus, ein zweizeiliger Name auf EINER
            Karte machte alle Karten der Zeile hoeher. */}
        <span
          data-struck={isRejected ? 'true' : undefined}
          className={cn(
            'min-w-6 truncate font-mono text-xs',
            isRejected ? 'text-text-muted line-through' : 'text-text'
          )}
        >
          {fileName}
        </span>
      </div>

      {footer}
    </li>
  )
}
