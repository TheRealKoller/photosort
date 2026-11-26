import type { MotifKey, MotifSetOut, PhotoOut } from '../api/types'
import type { MotifCorrectionError } from '../hooks/useMotifCorrection'
import { formatDateTime } from '../utils/formatStats'
import { EyeAttribution } from './EyeAttribution'
import { MotifStrengthSection } from './MotifStrengthSection'
import { PhotoVerdict } from './PhotoVerdict'

interface PhotoVerdictSectionProps {
  photo: PhotoOut
  eyeFineLabels: PhotoOut['fine_labels'] | null
  motifSet: MotifSetOut | undefined
  motifSetLoading: boolean
  motifSetError: string | undefined
  onMotifSetRetry: () => void
  onCorrect: (motifKey: MotifKey, applies: boolean) => void
  onWithdraw: (motifKey: MotifKey) => void
  pendingMotifKey: MotifKey | null
  error: MotifCorrectionError | null
}

export function PhotoVerdictSection({
  photo,
  eyeFineLabels,
  motifSet,
  motifSetLoading,
  motifSetError,
  onMotifSetRetry,
  onCorrect,
  onWithdraw,
  pendingMotifKey,
  error,
}: PhotoVerdictSectionProps) {
  return (
    <section
      className="flex flex-col gap-4 rounded-md border border-border bg-surface p-4"
      aria-labelledby="verdict-heading"
      data-testid="verdict-section"
    >
      <h2 id="verdict-heading" className="sr-only">
        Urteil
      </h2>
      {/* Die zaehlende Stufe kommt aus `album_suitability` - sie reist mit ihrer Herkunft, statt
          hier aus der Eye-Kopfzeile geraten zu werden. `?? null` heisst "noch nicht eingestuft"
          und nicht "Feld nicht durchgereicht": diese Ansicht zeigt die Zeile immer, mit Stufe
          oder mit dem Satz. Die Feinlabels bleiben Eyes rohe Tags, solange eine Eye-Kopfzeile
          existiert. */}
      <PhotoVerdict
        albumSuitability={photo.album_suitability ?? null}
        ranking={photo.ranking ?? null}
        fineLabels={eyeFineLabels ?? photo.fine_labels}
      />

      {/* DAS EYE-BAND: zwischen Urteil und Motivbereich, weil es die HERKUNFT der Angaben im
          Urteil benennt - Modellrevision, Fassung der Uebersetzung und Zeitpunkt stammen aus
          `photo_eye_results`, nicht aus einer geratenen Anbieterzeile. Es nennt die
          Albumtauglichkeit nur dann, wenn sie tatsaechlich aus Eye zaehlt (`source === 'eye'`);
          sonst erklaert es allein die Feinlabels. Die Fassung ist ein Rohwert und nur ein
          Textknoten, nie HTML, `href`, `src`, `style`, `key`, `aria-label` oder `title`. Die
          Namensnennung steht darunter, an derselben Stelle wie die Angabe selbst. */}
      {photo.eye_result != null && (
        <div
          className="flex flex-col gap-1 rounded-sm border border-separator bg-elevated px-3 py-2"
          data-testid="eye-band"
        >
          <p className="text-xs text-text">
            {photo.album_suitability?.source === 'eye'
              ? 'Albumtauglichkeit und Feinlabels'
              : 'Feinlabels'}{' '}
            stammen aus der Eye-Auswertung — Modellrevision {photo.eye_result.model_revision},
            Übersetzung {photo.eye_result.mapping_version},{' '}
            {formatDateTime(photo.eye_result.computed_at)}.
          </p>
          <EyeAttribution />
        </div>
      )}

      <section
        className="flex flex-col gap-2 text-base"
        aria-labelledby="motifs-heading"
        data-testid="motifs-section"
      >
        <h2
          id="motifs-heading"
          className="text-xs font-semibold tracking-wide text-text-h uppercase"
        >
          Motive
        </h2>
        <MotifStrengthSection
          motifSet={motifSet}
          motifSetLoading={motifSetLoading}
          motifSetError={motifSetError}
          onMotifSetRetry={onMotifSetRetry}
          assessment={photo.motif_assessment ?? null}
          motifs={photo.motifs ?? []}
          editable
          onCorrect={onCorrect}
          onWithdraw={onWithdraw}
          pendingMotifKey={pendingMotifKey}
          error={error}
        />
      </section>
    </section>
  )
}
