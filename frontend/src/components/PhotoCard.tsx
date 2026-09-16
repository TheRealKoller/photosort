import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { RatingStatus } from '../api/types'
import { cn } from '../lib/utils'
import { RatingBadge } from './RatingBadge'

export interface PhotoCardProps {
  /** Ziel des Kachel-Links. Fehlt es, ist die Bildflaeche KEIN Link. */
  to?: string
  /** Vollstaendiger Pfad des Fotos. Sichtbar wird ausschliesslich der Basisname. */
  relativePath: string
  /**
   * Bewertungszustand der Karte. `undefined` heisst "die Karte traegt keinen Zustand" (Vergleich
   * und Kuratierung zeigen ihn woanders bzw. gar nicht), `null` ist der Board-Zustand "neu".
   */
  status?: RatingStatus | null
  /**
   * Das EIGENE Favoriten-Kennzeichen - seit ADR 0098 unabhaengig von `status` und deshalb eine
   * eigene Prop statt eines dritten Werts darin.
   */
  favorite?: boolean
  /** true fuer einen unbestaetigten automatischen Vorschlag statt einer echten Bewertung. */
  suggested?: boolean
  /**
   * Der Gegenstand dieser Karte ist BEISEITEGELEGT - die Bildflaeche tritt zurueck und der
   * Dateiname wird durchgestrichen, OHNE dass die Karte damit einen Bewertungszustand behauptet.
   *
   * Getrennt von `status='rejected'`, weil die beiden verschiedene Dinge sagen: jenes ist die
   * Streichung EINES Nutzers und traegt deshalb das Kennzeichen "Verworfen", dieses die
   * gemeinsame Herausnahme des PROJEKTS aus der Endauswahl. Auf einer Ansicht, die je Teilnehmer
   * ein benanntes Bewertungs-Kennzeichen zeigt, waere ein unbenanntes "Verworfen" am
   * Kartenkoerper als Haltung einer Person lesbar - genau die Verwechslung, die die Trennung von
   * `ratings[].status` und `final_selection_decision` ausschliesst.
   */
  setAside?: boolean
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
 * Die Foto-Karte des Boards. Sie lebt GENAU EINMAL - `PhotoGridPage`, `CurationPhotoTile` und
 * `SelectionPhotoTile` bauen keine eigene Kachel.
 *
 * AUFBAU (zugleich DOM- und Fokusreihenfolge): Bildbereich mit den beiden Ecken-Overlays,
 * darunter die Statuszeile (Kennzeichen links, Dateiname rechts), darunter die Fusszeile.
 * Kennzeichen und Dateiname sind nicht fokussierbar und schieben sich damit zwischen Bild und
 * Fusszeile, ohne die Reihenfolge der Bedienelemente zu veraendern.
 *
 * DAS KENNZEICHEN SITZT IM KARTENKOERPER, NICHT IN DER BILDECKE: Ein Textbadge "Album-wuerdig"
 * ueber dem Foto braucht bei 360px und zwei Spalten mehr Platz, als die Ecke hat, und die Ecke
 * oben rechts ist fuer den Info-Trigger reserviert.
 *
 * DIE ECKEN-OVERLAYS SIND GESCHWISTER DER BILDFLAECHE, NIE IHRE KINDER. Die Bildflaeche traegt
 * `overflow-hidden`; eine aufgespannte Trefferflaeche innerhalb eines beschneidenden Containers
 * wuerde still abgeschnitten.
 *
 * DER FUENFTE BOARD-ZUSTAND "AUSGEWAEHLT" WIRD NICHT GEBAUT: PhotoSort kennt heute keine
 * Foto-Auswahl. Es gibt weder eine `selected`-Prop noch ein `data-selected`, und es entsteht
 * keine Vorbereitung darauf.
 */
export function PhotoCard({
  to,
  relativePath,
  status,
  favorite = false,
  suggested = false,
  setAside = false,
  image,
  topLeft,
  topRight,
  footer,
}: PhotoCardProps) {
  // BEIDE Faelle werden gleich dargestellt, und nur einer traegt zusaetzlich ein Kennzeichen: die
  // eigene Streichung (Bewertung eines Nutzers) und die gemeinsame Herausnahme aus der Endauswahl
  // (Entscheidung des Projekts). Traeger ist die Durchstreichung des Dateinamens - bei `setAside`
  // ohne Bewertungszustand ist sie der einzige.
  const stepsBack = status === 'rejected' || setAside

  /*
   * DIE BILDFLAECHE STEHT IMMER IN VOLLER HELLIGKEIT (ADR 0112), auch bei einer Streichung oder
   * einer Herausnahme: Eine gedaempfte Bildflaeche verfaelscht die Beurteilung des Motivs, und
   * beurteilt wird ueberall dort, wo diese Karte steht. Den Zustand tragen Kennzeichen (Symbol und
   * Wort) und der durchgestrichene Dateiname, beide ausserhalb der Bildflaeche.
   */
  const imageAreaClassName = 'block aspect-square overflow-hidden rounded-md'

  // Nur der Basisname: Der Ordnerteil ist auf ~60px ohnehin unlesbar und steht bereits im `alt`
  // des Bildes sowie im `aria-label` der Fusszeilen-Aktion.
  const fileName = relativePath.split('/').pop() ?? relativePath

  return (
    <li
      data-rating-status={status === undefined ? undefined : (status ?? 'unrated')}
      data-rating-favorite={favorite ? 'true' : undefined}
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
        {status === null && !favorite && (
          // Der Zustand "neu" traegt das WORT, nicht das neutrale "–"-Badge. Reiner Text, kein
          // `aria-label`, kein `RatingBadge` - das "–" bleibt seinen uebrigen Aufrufstellen
          // (Haltungszeilen der Endauswahl) vorbehalten, wo es "hat nicht bewertet" heisst.
          //
          // Traegt die Karte das Favoriten-Kennzeichen, steht dort dessen Badge statt "Neu":
          // "Favorit" ohne Albumkennzeichen daneben IST die Aussage "noch nicht entschieden",
          // und beides nebeneinander laese sich wie ein Widerspruch.
          <span className="shrink-0 text-xs text-text-muted">Neu</span>
        )}
        {status !== undefined && (status !== null || favorite) && (
          <RatingBadge
            status={status}
            favorite={favorite}
            suggested={suggested}
            className="shrink-0"
          />
        )}
        {/* SICHERHEIT: Der Dateiname stammt aus dem WebDAV-Walk der OpenCloud und ist damit extern
            entstandener Text. Er wird ausschliesslich als regulaerer React-Textknoten gerendert -
            nie ueber `dangerouslySetInnerHTML`, und er fliesst in kein `href`, `src`, `style` oder
            `url()`. Das Session-Token liegt in `localStorage`; ein eingeschleustes
            Skript laese es unmittelbar aus. Abgesichert in PhotoCard.test.tsx.

            `min-w-6` neben `truncate`, damit ein langes Kennzeichen den Namen nie auf null
            drueckt - sonst verschwaende auch die Durchstreichung. Eine Zeile, kein Umbruch: in
            einer Rasterzeile gleichen sich die Kartenhoehen aus, ein zweizeiliger Name auf EINER
            Karte machte alle Karten der Zeile hoeher. */}
        <span
          data-struck={stepsBack ? 'true' : undefined}
          className={cn(
            'min-w-6 truncate font-mono text-xs',
            stepsBack ? 'text-text-muted line-through' : 'text-text',
          )}
        >
          {fileName}
        </span>
      </div>

      {footer}
    </li>
  )
}
