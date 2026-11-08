import type { PhotoOut } from '../api/types'
import { NOT_PROPOSED_BADGE_TEXT } from '../utils/albumDraft'
import {
  ALBUM_SUITABILITY_EYE_ORIGIN_TEXT,
  ALBUM_SUITABILITY_ORIGIN_LABEL,
  REASON_ATTRIBUTION,
} from '../utils/albumSuitability'
import { qualityLevel } from '../utils/qualityLevel'
import { QualityMeter } from './QualityMeter'

/**
 * Die Angaben der Leiste einer Kuratierungskachel vor dem Dateinamen: die Begründung des Modells
 * VOLLSTÄNDIG (kein `line-clamp`, keine Kürzung) ODER - wenn die zählende Stufe aus Eyes
 * Auswertung stammt - die Herkunftszeile aus den beiden Konstanten in `albumSuitability.ts`, dann
 * die Albumtauglichkeit als Stufe mit Wort, gegebenenfalls „· nicht vorgeschlagen". Die Herkunft
 * geht der Begründung vor: Eye liefert keinen Modelltext, und eine unerwartet gesetzte Begründung
 * wäre die Aussage eines anderen Verfahrens. Ohne beides (`null` oder leer) fehlt die Zeile
 * restlos.
 *
 * SICHERHEIT: Die Begründung ist freier Modelltext zu einem Bild, das selbst Text enthalten kann
 * (Prompt-Injection). Sie steht AUSSCHLIESSLICH als React-Textknoten - nie über
 * `dangerouslySetInnerHTML`, nie in einem Attribut (`aria-label`, `title`, `href`, `style`, `key`),
 * nie im Namen von Bild oder Knöpfen. Das Session-Token liegt in `localStorage`; eine XSS-Senke
 * wäre ein Tokendiebstahl. Vor ihr steht im selben Träger die Zuschreibung an das Modell, ohne
 * Badge, Bewertungsfarbe, Symbol oder Meldungsrolle: ungekürzt gezeigt, sähe ein eingeschleuster
 * Satz sonst wie eine Meldung der Anwendung aus. Die Herkunftszeile trägt dagegen nur zwei
 * Konstanten als Textknoten. Erzwungen in `CurationPhotoTile.test.tsx`.
 */
export function CurationDetails({
  photo,
  notProposed = false,
}: {
  photo: PhotoOut
  notProposed?: boolean
}) {
  // `?? null` fuer den FEHLENDEN Wert, nie fuer die Zahl selbst: `0` ist ein gueltiger
  // Qualitaetswert, und ein `||` verloere ihn lautlos.
  const level = qualityLevel(photo.ranking?.rank_score ?? null)
  const reason = photo.album_suitability?.reason ?? null
  const fromEye = photo.album_suitability?.source === 'eye'

  return (
    <>
      {fromEye ? (
        <p data-album-suitability-origin="">
          <span className="mr-1 text-text-muted">{ALBUM_SUITABILITY_ORIGIN_LABEL}</span>{' '}
          <span>{ALBUM_SUITABILITY_EYE_ORIGIN_TEXT}</span>
        </p>
      ) : (
        reason !== null &&
        reason !== '' && (
          <p data-album-suitability-reason="">
            <span className="mr-1 text-text-muted">{REASON_ATTRIBUTION}</span>
            {reason}
          </p>
        )
      )}
      <p className="text-text">
        <QualityMeter level={level} />
        {notProposed && ` · ${NOT_PROPOSED_BADGE_TEXT}`}
      </p>
    </>
  )
}
