import { useId } from 'react'

import type { CriterionScoreOut } from '../api/types'
import { partitionByPresenceThreshold } from '../utils/criterionScores'
import { formatCriterionPercent } from '../utils/formatStats'

interface CriterionScoreGridProps {
  criterionScores: CriterionScoreOut[]
}

/** Eine Nachschlagzeile: Name links, Wert rechts. `text-sm` ist die Bezugsgröße von AK5 - die
 *  Albumtauglichkeits-Zeile des Urteils steht mindestens beim 1,4-fachen davon. */
function ScoreRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <dt className="text-text">{label}</dt>
      <dd className="font-medium text-text-h" data-criterion-value="">
        {value}
      </dd>
    </div>
  )
}

/**
 * Die fünfzehn Einzelwerte eines Fotos (acht Qualität, sieben Bildinhalt) als Nachschlagraster.
 *
 * NACHSCHLAGEN, NICHT LESEN: Das Raster steht hinter dem Urteil und beantwortet die Frage "welcher
 * Einzelwert steht wo" - deshalb mehrspaltig ab `sm:`, auf Telefonbreite einspaltig, und in der
 * kleinsten Textstufe der Seite.
 *
 * KEIN AUFKLAPPEN, KEIN AUSLÖSER (AK4): Jede Angabe steht ohne Bedienhandlung da. Ein Block ohne
 * Inhalt entfällt vollständig - keine Kopfzeile, kein leeres `<dl>`; bei komplett leerer Eingabe
 * rendert die Komponente `null` statt eines leeren Rahmens.
 *
 * DIES IST NICHT DIE VARIANTE VON `CriterionDetailsList`. Das kompakte Kachel-Popover und dieses
 * große Seitenraster sind zwei Darstellungen mit verschiedener Elementstruktur und Schriftgröße;
 * eine gemeinsame Komponente hätte zwei sich ausschließende Zweige. Geteilt wird ausschließlich,
 * was zeichengleich ist - die Aufteilung in `utils/criterionScores.ts`.
 *
 * KEIN RANG. Er ist keiner der fünfzehn Einzelwerte, sondern Teil des URTEILS und steht
 * ausschließlich in `PhotoVerdict` (Spec 0497, AK5). Nähme dieser Baustein ihn ebenfalls
 * entgegen, stünde dieselbe Angabe an zwei Stellen der Seite - die beiden liefen früher oder
 * später auseinander, und der Nutzer läse denselben Rang zweimal untereinander.
 */
export function CriterionScoreGrid({ criterionScores }: CriterionScoreGridProps) {
  const { quality: qualityScores, content: contentScores } =
    partitionByPresenceThreshold(criterionScores)
  const showQualityBlock = qualityScores.length > 0
  const showContentBlock = contentScores.length > 0

  // Ein einzelnes useId() mit Suffixen: Die Ids muessen auch dann eindeutig bleiben, wenn eine
  // zweite Instanz gleichzeitig im DOM steht.
  const blockId = useId()
  const qualityHeadingId = `${blockId}-quality`
  const contentHeadingId = `${blockId}-content`

  if (!showQualityBlock && !showContentBlock) {
    return null
  }

  return (
    <div className="grid gap-6 sm:grid-cols-2" data-testid="criterion-score-grid">
      {showQualityBlock && (
        // role="group" + aria-labelledby am Wrapper, NICHT am <dl>: Ein <dl> hat in dieser
        // Toolchain keine namensfaehige Rolle, die Beschriftung kaeme dort weder im
        // Accessibility-Tree noch in einer Rollenabfrage an.
        <div role="group" aria-labelledby={qualityHeadingId} className="flex flex-col gap-2">
          <h3
            id={qualityHeadingId}
            className="text-xs font-semibold tracking-wide text-text-h uppercase"
          >
            Bildqualität
          </h3>
          <dl className="flex flex-col gap-2">
            {qualityScores.map((score) => (
              // S3: geschluesselt ueber den Registry-Schluessel, nie ueber den Anzeigenamen.
              <ScoreRow
                key={score.criterion_key}
                label={score.display_name}
                value={formatCriterionPercent(score.value)}
              />
            ))}
          </dl>
        </div>
      )}
      {showContentBlock && (
        <div role="group" aria-labelledby={contentHeadingId} className="flex flex-col gap-2">
          <h3
            id={contentHeadingId}
            className="text-xs font-semibold tracking-wide text-text-h uppercase"
          >
            Bildinhalt
          </h3>
          <dl className="flex flex-col gap-2">
            {contentScores.map((score) => (
              <ScoreRow
                key={score.criterion_key}
                label={score.display_name}
                value={formatCriterionPercent(score.value)}
              />
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}
