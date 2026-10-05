import type { PhotoOut } from '../api/types'
import { NOT_PROPOSED_BADGE_TEXT } from '../utils/albumDraft'
import { REASON_ATTRIBUTION } from '../utils/albumSuitability'
import { qualityLevel } from '../utils/qualityLevel'
import { QualityMeter } from './QualityMeter'

/**
 * Die Angaben der Leiste einer Kuratierungskachel vor dem Dateinamen: die Begründung des Modells
 * VOLLSTÄNDIG (kein `line-clamp`, keine Kürzung), dann die Albumtauglichkeit als Stufe mit Wort,
 * gegebenenfalls „· nicht vorgeschlagen". Ohne Begründung (`null` oder leer) fehlt ihre Zeile
 * restlos.
 *
 * SICHERHEIT: Die Begründung ist freier Modelltext zu einem Bild, das selbst Text enthalten kann
 * (Prompt-Injection). Sie steht AUSSCHLIESSLICH als React-Textknoten - nie über
 * `dangerouslySetInnerHTML`, nie in einem Attribut (`aria-label`, `title`, `href`, `style`, `key`),
 * nie im Namen von Bild oder Knöpfen. Das Session-Token liegt in `localStorage`; eine XSS-Senke
 * wäre ein Tokendiebstahl. Vor ihr steht im selben Träger die Zuschreibung an das Modell, ohne
 * Badge, Bewertungsfarbe, Symbol oder Meldungsrolle: ungekürzt gezeigt, sähe ein eingeschleuster
 * Satz sonst wie eine Meldung der Anwendung aus. Erzwungen in `CurationPhotoTile.test.tsx`.
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

  return (
    <>
      {reason !== null && reason !== '' && (
        <p data-album-suitability-reason="">
          <span className="mr-1 text-text-muted">{REASON_ATTRIBUTION}</span>
          {reason}
        </p>
      )}
      <p className="text-text">
        <QualityMeter level={level} />
        {notProposed && ` · ${NOT_PROPOSED_BADGE_TEXT}`}
      </p>
    </>
  )
}
