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

/** S4 — die Zuschreibung. Sie steht als SICHTBARER TEXTKNOTEN vor der Begründung und damit im
 *  selben Absatz: Assistive Technik liest ihn ohnehin mit, Sehende sehen ihn. Ein `aria-labelledby`
 *  daneben trüge nichts bei - ein `<p>` hat keine namensfähige Rolle, und das benannte Element wäre
 *  sein eigenes Kind. */
const REASON_ATTRIBUTION = 'Begründung des Modells'

/** Die Beschriftung über einem Wert - dieselbe Stufe wie die Kopfzeilen des Einzelwerte-Rasters,
 *  damit „Albumtauglichkeit" und „Qualität — Einzelwerte" als gleichrangige Aufschriften lesbar
 *  sind. Das Label des Rangs ist der Grund, warum sein Wert ohne das Wort „Rang" auskommt. */
const LABEL_CLASS = 'text-xs font-semibold tracking-wide text-text-h uppercase'

/**
 * Das Urteil über ein Foto: Albumtauglichkeit mit Begründung, Rang im Ereignis, Feinlabel.
 *
 * DAS URTEIL STEHT VOR DEN EINZELWERTEN (AK5), und GROSS GESETZT IST ALLEIN DIE STUFE: `text-lg`
 * (20px) gegen `text-sm` (14px) der Rasterzeilen - Faktor 1,43 und damit über der Produktzusage
 * von 1,4. Begründung und Rang stehen klein unter ihren Labels; sie erläutern die Stufe, sie
 * wiederholen ihren Rang nicht. Die Hierarchie wird ausdrücklich NICHT allein über `--text` gegen
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
  // Auf `!== null` geprueft, nie auf Falsyness: "Rang - von 12" waere eine Rangaussage ueber ein
  // Foto ohne Rang.
  const showRankRow = ranking !== null && ranking.rank_position !== null
  const reason = albumSuitability?.reason ?? null

  return (
    <div className="flex flex-col gap-3" data-testid="photo-verdict">
      <div className="flex flex-col gap-1">
        <h3 className={LABEL_CLASS}>Albumtauglichkeit</h3>
        {/* AK5-BEZUGSGRÖSSE: `text-lg`. Der Handle macht die Zeile fuer den Browser-Pruefsatz
            auffindbar, ohne sie ueber einen Text zu suchen - der Text wechselt mit der Stufe. */}
        <p data-album-suitability-level="" className="text-lg font-semibold text-text-h">
          {albumSuitability === null
            ? ALBUM_SUITABILITY_NOT_RATED_TEXT
            : formatAlbumSuitabilityLevel(albumSuitability.level)}
        </p>
        {reason !== null && (
          // S4: Der sichtbare Vorsatz traegt die Zuschreibung fuer alle Leser - reiner
          // React-Textknoten, ungekuerzt.
          <p data-album-suitability-reason="" className="text-sm text-text">
            <span className="mr-2 text-xs tracking-wide text-text-muted uppercase">
              {REASON_ATTRIBUTION}
            </span>
            {reason}
          </p>
        )}
      </div>
      {showRankRow && ranking !== null && (
        <div className="flex flex-col gap-1">
          <h3 className={LABEL_CLASS}>Rang im Ereignis</h3>
          <p className="text-sm text-text">
            {ranking.rank_position} von {ranking.partition_size}
          </p>
        </div>
      )}
      {/* Die Chips zeichengleich mit dem Kachel-Popover; ohne Feinlabels entfaellt der Bereich
          ersatzlos. */}
      <FineLabelList fineLabels={fineLabels} />
    </div>
  )
}
