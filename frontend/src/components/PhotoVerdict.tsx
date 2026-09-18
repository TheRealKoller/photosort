import { useId } from 'react'

import type { AlbumSuitabilityOut, FineLabelOut, RankingOut } from '../api/types'
import {
  ALBUM_SUITABILITY_NOT_RATED_TEXT,
  formatAlbumSuitabilityLevel,
} from '../utils/albumSuitability'
import { FineLabelList } from './FineLabelList'

interface PhotoVerdictProps {
  /** Die Albumtauglichkeit des Modells. `null` heißt „noch nicht bewertet" - dann trägt die Zeile
   * den Satz statt einer Stufe, und es erscheint KEINE Begründungszeile.
   *
   * SICHERHEIT (S1/S4/S5): `reason` ist freier, extern erzeugter Text aus einem Bild, das selbst
   * Text enthalten kann. Ausschließlich als regulärer React-Textknoten rendern - nie
   * `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in `href`/`src`/`style`, nie in einem
   * `url()`-Kontext, nie als React-`key`. Das Session-Token liegt in `localStorage`; ein
   * eingeschleustes Skript liest es unmittelbar aus und hat damit bis zu 30 Tage
   * Sitzungsübernahme ohne Widerrufsweg. Bricht in `PhotoVerdict.test.tsx > rendert eine feindlich
   * belegte Begründung als reinen Textknoten`. */
  albumSuitability: AlbumSuitabilityOut | null
  /** Die Rangzeile des Fotos im Ereignis - `null`, solange kein erfolgreicher Lauf existiert. */
  ranking: RankingOut | null
  fineLabels: FineLabelOut[]
}

/** S4 — die Zuschreibung. Sie steht sichtbar UND im zugänglichen Namen des Trägers: ein rein
 *  visueller Hinweis erreichte assistive Technik nicht, ein rein zugänglicher den Sehenden nicht. */
const REASON_ATTRIBUTION = 'Begründung des Modells'

/**
 * Das Urteil über ein Foto: Albumtauglichkeit mit Begründung, Rang im Ereignis, Feinlabel.
 *
 * DAS URTEIL STEHT VOR DEN EINZELWERTEN (AK5) und deutlich größer: Die Albumtauglichkeits-Zeile
 * trägt `text-lg` (20px) gegen `text-sm` (14px) der Rasterzeilen - Faktor 1,43 und damit über der
 * Produktzusage von 1,4. Die Hierarchie wird ausdrücklich NICHT allein über `--text` gegen
 * `--text-muted` aufgebaut; diese beiden Stufen sind nebeneinander nur schwach unterscheidbar.
 * Größe, Schnitt und Reihenfolge tragen sie.
 *
 * KEINE BEDIENHANDLUNG (AK4): Jede Angabe steht ohne Klick da - kein `<details>`, kein Auslöser.
 *
 * S4 — DIE BEGRÜNDUNG BLEIBT ALS AUSSAGE DES MODELLS KENNTLICH, nicht als Aussage von PhotoSort.
 * Bei Verletzung wird eine über Prompt-Injection erzeugte Zeile zur Systemaussage; die Wirkung ist
 * Irreführung des Nutzers, nicht Codeausführung. Sie wird ungekürzt gezeigt - Kappung findet an der
 * Quelle statt.
 */
export function PhotoVerdict({ albumSuitability, ranking, fineLabels }: PhotoVerdictProps) {
  const reasonId = useId()
  // Auf `!== null` geprueft, nie auf Falsyness: "Rang - von 12" waere eine Rangaussage ueber ein
  // Foto ohne Rang.
  const showRankRow = ranking !== null && ranking.rank_position !== null
  const reason = albumSuitability?.reason ?? null

  return (
    <div className="flex flex-col gap-3" data-testid="photo-verdict">
      {/* AK5-BEZUGSGRÖSSE: `text-lg`. Der Handle macht die Zeile fuer den Browser-Pruefsatz
          auffindbar, ohne sie ueber einen Text zu suchen - der Text wechselt mit der Stufe. */}
      <p data-album-suitability-level="" className="text-lg font-semibold text-text-h">
        {albumSuitability === null
          ? ALBUM_SUITABILITY_NOT_RATED_TEXT
          : formatAlbumSuitabilityLevel(albumSuitability.level)}
      </p>
      {reason !== null && (
        // S4: Der Traeger fuehrt die Zuschreibung im zugaenglichen Namen; der sichtbare Vorsatz
        // traegt dieselbe Aussage fuer Sehende. Reiner React-Textknoten, ungekuerzt.
        <p
          data-album-suitability-reason=""
          aria-labelledby={reasonId}
          className="text-lg text-text"
        >
          <span id={reasonId} className="mr-2 text-xs tracking-wide text-text-muted uppercase">
            {REASON_ATTRIBUTION}
          </span>
          {reason}
        </p>
      )}
      {showRankRow && ranking !== null && (
        <p className="text-lg text-text">
          Rang {ranking.rank_position} von {ranking.partition_size}
        </p>
      )}
      {/* Die Chips zeichengleich mit dem Kachel-Popover; ohne Feinlabels entfaellt der Bereich
          ersatzlos. */}
      <FineLabelList fineLabels={fineLabels} />
    </div>
  )
}
